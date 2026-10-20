from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect,get_object_or_404
from django.http import Http404,HttpResponse
from .forms import (
    GenerationForm,
    LessonDetailsForm,
    LessonSectionForm,
    LessonQuestionForm,
)


from .section_development import (
    SectionDevelopmentError,
    develop_section_content,
)

import random
from django.views.decorators.http import require_POST
from .models import Lesson
from .services import generate_lesson, LessonGenerationError
from django.db.models import Q
from django.contrib import messages
from core.models import Course, CourseOutlineItem, Lesson
from core.course_outline_service import generate_and_save_course_outline
from core.course_chunk_generator import (
    CourseChunkGenerationError,
    generate_course_session_batch,
)
from .tasks import generate_lesson_task
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
import logging
from io import BytesIO
from docx import Document
from docx.shared import Inches, Pt
from pptx import Presentation
from pptx.util import Inches as PptxInches, Pt as PptxPt

from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor





logger = logging.getLogger(__name__)


from django.http import JsonResponse

@login_required
def lesson_generation_status(request, lesson_id):
    lesson = get_object_or_404(
        Lesson,
        id=lesson_id,
        creator=request.user,
    )

    if lesson.creator_id and (
        not request.user.is_authenticated
        or lesson.creator_id != request.user.id
    ):
        raise Http404

    return JsonResponse({
        "id": str(lesson.id),
        "status": lesson.generation_status,
        "progress": lesson.generation_progress,
        "stage": lesson.generation_stage,
        "error": lesson.generation_error,
        "completed": (
            lesson.generation_status
            in (
                Lesson.GenerationStatus.COMPLETED,
                Lesson.GenerationStatus.FAILED,
            )
        ),
    })

@login_required
def generate_course_session(request, course_id, outline_item_id):
    if request.method != "POST":
        raise Http404

    if not request.user.is_authenticated:
        raise Http404

    course = get_object_or_404(
        Course,
        id=course_id,
        creator=request.user,
    )

    outline_item = get_object_or_404(
        CourseOutlineItem,
        id=outline_item_id,
        course=course,
    )

    # Do not generate the same session twice.
    existing_lesson = Lesson.objects.filter(
        outline_item=outline_item
    ).first()

    if existing_lesson:
        return redirect(
            "core:lesson_detail",
            lesson_id=existing_lesson.id,
        )

    if outline_item.status not in (
        CourseOutlineItem.Status.PLANNED,
        CourseOutlineItem.Status.FAILED,
    ):
        messages.warning(
            request,
            "This session is not available for generation.",
        )
        return redirect(
            "core:course_outline",
            course_id=course.id,
        )

    # Generate one session only, using its reviewed outline.
    outline_item.status = CourseOutlineItem.Status.GENERATING
    outline_item.generation_error = ""
    outline_item.save(
        update_fields=["status", "generation_error", "updated_at"]
    )

    data = {
        "mode": "full_course",
        "topic": course.title,
        "source_text": course.description,
        "learner_level": course.learner_level,
        "detail_level": "standard",
        "course_weeks": course.duration_weeks,
        "classes_per_week": course.classes_per_week,
        "duration_minutes": course.class_duration_minutes,
        "session_outline": {
            "title": outline_item.title,
            "topic": outline_item.topic,
            "learning_objectives": outline_item.learning_objectives,
        },
    }

    try:
        sessions, provider_response = generate_course_session_batch(
            data,
            start_session=outline_item.session_number,
            session_count=1,
        )

        session = sessions[0]

        # Preserve the reviewed outline's title and topic.
        session_content = clean_generated_text(session.content)
        session_objectives = clean_generated_text(
            session.learning_objectives
        )

        lesson = Lesson.objects.create(
            generation_progress=100,
            generation_stage="Completed",
            generation_started_at=timezone.now(),
            generation_completed_at=timezone.now(),
            creator=request.user,
            course=course,
            outline_item=outline_item,
            title=outline_item.title,
            topic=outline_item.topic,
            source_text=course.description,
            generation_mode=Lesson.GenerationMode.FULL_COURSE,
            learner_level=course.learner_level,
            duration_minutes=course.class_duration_minutes,
            detail_level="standard",
            notes_format="both",
            learning_notes=(
                f"Session {outline_item.session_number}: "
                f"{outline_item.topic}"
            ),
            teaching_notes=clean_generated_text(session.teaching_notes),
            presentation_content=clean_generated_text({
                "learning_objectives": session_objectives,
                "sections": (
                    [
                        {
                            "heading": section.heading,
                            "content": section.content,
                        }
                        for section in session.sections
                    ]
                    if session.sections
                    else [
                        {
                            "heading": outline_item.title,
                            "content": session_content,
                        }
                    ]
                ),
                "key_points": [],
                "examples": [],
                "fun_facts": [],
                "questions": [
                    {
                        "question": question.question,
                        "question_type": question.question_type,
                        "options": question.options,
                        "answer": question.answer,
                        "explanation": question.explanation,
                        "hint": question.hint,
                        "section_heading": question.section_heading,
                    }
                    for question in session.quiz_questions
                ],
                "activities": [
                    {
                        "title": "Practice activity",
                        "instructions": clean_generated_text(
                            session.activity
                        ),
                        "activity_type": "class_activity",
                    }
                ] if session.activity else [],
                "assignment": clean_generated_text(session.assignment),
                "conclusion": "",
                "presentation_slides": [],
                "course_weeks": [],
                "sources": [],
            }),
            ai_provider=provider_response.provider,
            generation_status=Lesson.GenerationStatus.COMPLETED,
        )

        outline_item.status = CourseOutlineItem.Status.READY_FOR_REVIEW
        outline_item.generation_error = ""
        outline_item.save(
            update_fields=["status", "generation_error", "updated_at"]
        )

        return redirect(
            "core:lesson_detail",
            lesson_id=lesson.id,
        )

    except Exception:
        logger.exception(
            "Course session generation failed. Course ID: %s, "
            "outline item ID: %s",
            course.id,
            outline_item.id,
        )

        outline_item.status = CourseOutlineItem.Status.FAILED
        outline_item.generation_error = (
            "Session generation failed. Check the server logs for details, "
            "then retry this session."
        )
        outline_item.save(
            update_fields=[
                "status",
                "generation_error",
                "updated_at",
            ]
        )

        messages.error(
            request,
            "Session generation failed. Please try again.",
        )
        return redirect(
            "core:course_outline",
            course_id=course.id,
        )


def clean_generated_text(value):
    """Remove em dashes from generated text recursively."""
    if isinstance(value, str):
        return value.replace("â€”", ", ").replace("  ", " ").strip()

    if isinstance(value, list):
        return [clean_generated_text(item) for item in value]

    if isinstance(value, dict):
        return {
            key: clean_generated_text(item)
            for key, item in value.items()
        }

    return value

@login_required
def generate(request):
    submitted = request.method == "POST"
    generated_output = None
    generation_error = None

    form = (
        GenerationForm(request.POST)
        if submitted
        else GenerationForm()
    )

    if submitted and form.is_valid():
        data = form.cleaned_data

        if data["mode"] == "full_course":
            if not request.user.is_authenticated:
                generation_error = (
                    "Please sign in before creating a full course."
                )
            else:
                course_title = (
                    data.get("topic")
                    or "Course from supplied material"
                ).strip()[:200]

                course = Course.objects.create(
                    creator=request.user,
                    title=course_title,
                    description=data.get("source_text", ""),
                    learner_level=data.get(
                        "learner_level", "intermediate"
                    ),
                    duration_weeks=data["course_weeks"],
                    classes_per_week=data["classes_per_week"],
                    class_duration_minutes=data[
                        "class_duration_minutes"
                    ],
                    outline_status=Course.OutlineStatus.DRAFT,
                )

                try:
                    generate_and_save_course_outline(course, data)

                    return redirect(
                        "core:course_outline",
                        course_id=course.id,
                    )

                except Exception:
                    logger.exception(
                        "Course outline generation failed for %s",
                        course.id,
                    )

                    generation_error = (
                        "Course outline generation failed. "
                        "Your saved progress has been preserved."
                    )

        else:
            lesson_title = (
                data.get("topic")
                or "Lesson generation in progress"
            ).strip()[:200]

            lesson = Lesson.objects.create(
                creator=request.user,
                title=lesson_title,
                topic=data.get("topic", ""),
                source_text=data.get("source_text", ""),
                generation_mode=data["mode"],
                learner_level=data.get(
                    "learner_level", "intermediate"
                ),
                duration_minutes=data.get("duration_minutes") or 60,
                detail_level=data.get("detail_level", "standard"),
                notes_format=data.get("notes_format", "both"),
                generation_status=Lesson.GenerationStatus.GENERATING,
                generation_progress=0,
                generation_stage="Waiting to start",
                generation_error="",
            )

            # Queue generation only after the database transaction commits.
            def queue_lesson_generation(
                lesson_id=str(lesson.pk),
                payload=data.copy(),
            ):
                try:
                    generate_lesson_task.delay(
                        lesson_id,
                        payload,
                    )
                except Exception:
                    logger.exception(
                        "Could not queue lesson generation for %s",
                        lesson_id,
                    )

                    Lesson.objects.filter(pk=lesson_id).update(
                        generation_status=Lesson.GenerationStatus.FAILED,
                        generation_stage="Could not start generation",
                        generation_error=(
                            "We couldn't start lesson generation. "
                            "Please try again."
                        ),
                        generation_completed_at=timezone.now(),
                    )

            transaction.on_commit(queue_lesson_generation)

            return render(
                request,
                "generate.html",
                {
                    "form": form,
                    "submitted": True,
                    "generation_data": data,
                    "generation_lesson": lesson,
                    "generated_output": None,
                    "generation_error": None,
                },
            )

    context = {
        "form": form,
        "submitted": submitted,
        "generation_data": (
            form.cleaned_data
            if submitted and form.is_valid()
            else None
        ),
        "generated_output": generated_output,
        "generation_error": generation_error,
    }

    return render(request, "generate.html", context)


@login_required
def library(request):
    lessons = Lesson.objects.filter(
        creator=request.user,
        course__isnull=True,
    )

    courses = Course.objects.filter(
        creator=request.user,
    )

    search_query = request.GET.get("q", "").strip()
    selected_status = request.GET.get("status", "").strip()
    selected_mode = request.GET.get("mode", "").strip()
    selected_publication = request.GET.get("publication", "").strip()

    if search_query:
        lessons = lessons.filter(
            Q(title__icontains=search_query)
            | Q(topic__icontains=search_query)
        )
        courses = courses.filter(
            Q(title__icontains=search_query)
            | Q(description__icontains=search_query)
        )

    valid_statuses = [
        value for value, label in Lesson.GenerationStatus.choices
    ]
    valid_modes = [
        value for value, label in Lesson.GenerationMode.choices
    ]
    valid_publication_statuses = {
        value for value, label in Lesson.PublicationStatus.choices
    }

    if selected_status in valid_statuses:
        lessons = lessons.filter(generation_status=selected_status)

    if selected_mode in valid_modes:
        lessons = lessons.filter(generation_mode=selected_mode)

    if selected_publication in valid_publication_statuses:
        lessons = lessons.filter(
            publication_status=selected_publication
        )
        courses = courses.filter(status=selected_publication)

    for course in courses:
        items = course.outline_items.all()

        total_sessions = items.count()
        completed_sessions = items.filter(
            status__in=[
                CourseOutlineItem.Status.READY_FOR_REVIEW,
                CourseOutlineItem.Status.APPROVED,
            ]
        ).count()

        course.total_sessions = total_sessions
        course.completed_sessions = completed_sessions
        course.progress_percent = (
            round(completed_sessions * 100 / total_sessions)
            if total_sessions
            else 0
        )

    context = {
        "lessons": lessons,
        "courses": courses,
        "search_query": search_query,
        "selected_status": selected_status,
        "selected_mode": selected_mode,
        "selected_publication": selected_publication,
        "status_choices": Lesson.GenerationStatus.choices,
        "mode_choices": Lesson.GenerationMode.choices,
    }

    return render(request, "library.html", context)




LESSON_MODE_TEMPLATES = {
    Lesson.GenerationMode.QUICK_LESSON: "core/lessons/quick_lesson.html",
    Lesson.GenerationMode.SUMMARY: "core/lessons/summary.html",
    Lesson.GenerationMode.PRESENTATION: "core/lessons/presentation.html",
    Lesson.GenerationMode.CUSTOM_CONTENT: "core/lessons/custom_content.html",
    Lesson.GenerationMode.FULL_COURSE: "core/lessons/full_course.html",
}




import re


def split_course_content(content, fallback_title="Lesson content"):
    """
    Split a generated course session into individual player steps.

    Supports timed headings such as:
    - Introduction (10 minutes):
    - Section 1: Understanding for Loops (15 minutes):
    - Discussion and Reflection (5 minutes):
    - Quiz (10 minutes):
    - After-class Assignment:
    """
    if not isinstance(content, str) or not content.strip():
        return []

    # Normalize escaped line endings sometimes returned by AI providers.
    content = content.replace("\\r\\n", "\n")
    content = content.replace("\\n", "\n")
    content = re.sub(r"\\[ \t]*\n", "\n", content)
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    heading_pattern = re.compile(
        r"^[ \t]*(?:#{1,6}[ \t]*)?"
        r"("
        r"Introduction(?:[ \t]*\([^)\n]*\))?[ \t]*:?"
        r"|Section[ \t]+\d+[ \t]*:[ \t]*.+"
        r"|Discussion and Reflection(?:[ \t]*\([^)\n]*\))?[ \t]*:?"
        r"|Quiz(?:[ \t]*\([^)\n]*\))?[ \t]*:?"
        r"|After-class Assignment[ \t]*:?"
        r")[ \t]*$",
        re.IGNORECASE | re.MULTILINE,
    )

    matches = list(heading_pattern.finditer(content))

    if not matches:
        return [{
            "title": fallback_title,
            "content": content.strip(),
        }]

    sections = []

    # Preserve any useful text appearing before the first recognized heading.
    prefix = content[:matches[0].start()].strip()
    if prefix:
        sections.append({
            "title": fallback_title,
            "content": prefix,
        })

    for index, match in enumerate(matches):
        start = match.end()
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(content)
        )

        body = content[start:end].strip()
        heading = match.group(1).strip()

        title = re.sub(
            r"^Section\s+\d+\s*:\s*",
            "",
            heading,
            flags=re.IGNORECASE,
        )

        title = re.sub(
            r"\s*\(\s*\d+\s*(?:minutes?|mins?)\s*\)",
            "",
            title,
            flags=re.IGNORECASE,
        )

        title = title.rstrip(": ").strip()
        if body:
            sections.append({
                "title": title or fallback_title,
                "content": body,
            })

    return sections


def build_lesson_steps(lesson, content):
    steps = []

    def add_step(step_type, title, body=None, items=None):
        steps.append({
            "type": step_type,
            "title": title,
            "body": body,
            "items": items or [],
        })

    if lesson.learning_notes:
        add_step("text", "Introduction", lesson.learning_notes)

    if content.get("learning_objectives"):
        add_step(
            "objectives",
            "Learning objectives",
            items=content["learning_objectives"],
        )

    for index, section in enumerate(content.get("sections", []), start=1):
        heading = section.get("heading", f"Section {index}")
        section_content = section.get("content", "")

        # A stored section may contain an entire generated session.
        # Split it into smaller steps when recognizable headings exist.
        split_sections = split_course_content(
            section_content,
            fallback_title=heading,
        )


        for split_section in split_sections:
            # The interactive quiz is rendered separately from
            # content["questions"], so skip the text-based quiz heading.
            if split_section["title"].strip().lower() == "quiz":
                continue

            add_step(
                "text",
                split_section["title"],
                split_section["content"],
            )


    if content.get("examples"):
        add_step(
            "examples",
            "Examples in practice",
            items=content["examples"],
        )

    if content.get("key_points"):
        add_step(
            "points",
            "Key takeaways",
            items=content["key_points"],
        )

    if content.get("questions"):
        add_step(
            "questions",
            "Quiz",
            items=content["questions"],
        )

    if content.get("activities"):
        add_step(
            "activities",
            "Practice activities",
            items=content["activities"],
        )

    if content.get("assignment"):
        add_step("text", "Your assignment", content["assignment"])

    if content.get("conclusion"):
        add_step("text", "Lesson recap", content["conclusion"])

    return steps

@login_required
def lesson_detail(request, lesson_id):
    lesson = get_object_or_404(
        Lesson,
        id=lesson_id,
        creator=request.user,
    )

    course_sessions = []
    current_session_number = None

    if lesson.course_id:
        course_sessions = list(
            lesson.course.outline_items
            .select_related("lesson")
            .order_by("week_number", "position", "session_number")
        )

        if lesson.outline_item_id:
            current_session_number = lesson.outline_item.session_number

    content = lesson.presentation_content
    if not isinstance(content, dict):
        content = {}

    mode_template = LESSON_MODE_TEMPLATES.get(
        lesson.generation_mode,
        LESSON_MODE_TEMPLATES[Lesson.GenerationMode.QUICK_LESSON],
    )

    public_lesson_url = ""

    if (
        lesson.publication_status == Lesson.PublicationStatus.PUBLISHED
        and lesson.generation_status == Lesson.GenerationStatus.COMPLETED
    ):
        if lesson.course_id:
            public_path = reverse(
                "core:public_course_session",
                kwargs={
                    "course_slug": lesson.course.slug,
                    "lesson_slug": lesson.slug,
                },
            )
        else:
            public_path = reverse(
                "core:public_lesson_detail",
                kwargs={"slug": lesson.slug},
            )

        public_lesson_url = request.build_absolute_uri(public_path)

    return render(
        request,
        "lesson_detail.html",
        {
            "lesson": lesson,
            "content": content,
            "mode_template": mode_template,
            "course_sessions": course_sessions,
            "current_session_number": current_session_number,
            "lesson_steps": build_lesson_steps(lesson, content),
            "public_lesson_url": public_lesson_url,
        },
    )


@login_required
@require_POST
def toggle_lesson_publication(request, lesson_id):
    lesson = get_object_or_404(
        Lesson,
        id=lesson_id,
        creator=request.user,
    )

    if lesson.generation_status != Lesson.GenerationStatus.COMPLETED:
        messages.warning(
            request,
            "Only completed lessons can be published.",
        )
        return redirect("core:lesson_detail", lesson_id=lesson.id)

    if (
        lesson.publication_status
        == Lesson.PublicationStatus.PUBLISHED
    ):
        lesson.publication_status = Lesson.PublicationStatus.DRAFT
        lesson.published_at = None
        message = "Lesson unpublished successfully."
    else:
        lesson.publication_status = Lesson.PublicationStatus.PUBLISHED
        lesson.published_at = timezone.now()
        message = "Lesson published successfully."

    lesson.save(
        update_fields=[
            "publication_status",
            "published_at",
            "updated_at",
        ]
    )
    # Run this after the lesson has been successfully published.
    # Keep your existing lesson validation and save logic.

    if lesson.course_id:
        course = lesson.course

        if course.status != Course.Status.PUBLISHED:
            course.status = Course.Status.PUBLISHED
            course.save(update_fields=["status"])

        messages.success(request, message)
    return redirect("core:lesson_detail", lesson_id=lesson.id)



def public_lesson_detail(request, slug):
    lesson = get_object_or_404(
        Lesson,
        slug=slug,
        course__isnull=True,
        publication_status=Lesson.PublicationStatus.PUBLISHED,
        generation_status=Lesson.GenerationStatus.COMPLETED,
    )

    content = lesson.presentation_content
    if not isinstance(content, dict):
        content = {}

    mode_template = LESSON_MODE_TEMPLATES.get(
        lesson.generation_mode,
        LESSON_MODE_TEMPLATES[Lesson.GenerationMode.QUICK_LESSON],
    )

    return render(
        request,
        "core/public_lesson_detail.html",
        {
            "lesson": lesson,
            "content": content,
            "mode_template": mode_template,
            "lesson_steps": build_lesson_steps(lesson, content),
            "is_public": True,
        },
    )


def public_course_detail(request, course_slug, lesson_slug=None):
    course = get_object_or_404(
        Course,
        slug=course_slug,
        status=Course.Status.PUBLISHED,
    )

    published_sessions = list(
        CourseOutlineItem.objects.filter(
            course=course,
            lesson__isnull=False,
            lesson__publication_status=Lesson.PublicationStatus.PUBLISHED,
            lesson__generation_status=Lesson.GenerationStatus.COMPLETED,
        )
        .select_related("lesson")
        .order_by("week_number", "position", "session_number")
    )

    lesson = None
    content = {}
    mode_template = None
    lesson_steps = []

    if lesson_slug:
        lesson = get_object_or_404(
            Lesson,
            slug=lesson_slug,
            course=course,
            outline_item__course=course,
            publication_status=Lesson.PublicationStatus.PUBLISHED,
            generation_status=Lesson.GenerationStatus.COMPLETED,
        )

        content = lesson.presentation_content
        if not isinstance(content, dict):
            content = {}

        mode_template = LESSON_MODE_TEMPLATES.get(
            lesson.generation_mode,
            LESSON_MODE_TEMPLATES[Lesson.GenerationMode.QUICK_LESSON],
        )

        lesson_steps = build_lesson_steps(lesson, content)

    return render(
        request,
        "core/public_course_detail.html",
        {
            "course": course,
            "published_sessions": published_sessions,
            "lesson": lesson,
            "content": content,
            "mode_template": mode_template,
            "lesson_steps": lesson_steps,
            "is_public": True,
        },
    )

def public_course_detail(request, course_slug, lesson_slug=None):
    course = get_object_or_404(
        Course,
        slug=course_slug,
        status=Course.Status.PUBLISHED,
    )

    published_sessions = (
        CourseOutlineItem.objects.filter(
            course=course,
            lesson__isnull=False,
            lesson__publication_status=Lesson.PublicationStatus.PUBLISHED,
            lesson__generation_status=Lesson.GenerationStatus.COMPLETED,
        )
        .select_related("lesson")
        .order_by(
            "week_number",
            "position",
            "session_number",
        )
    )

    lesson = None
    content = {}
    mode_template = None
    lesson_steps = []

    if lesson_slug:
        lesson = get_object_or_404(
            Lesson,
            slug=lesson_slug,
            course=course,
            outline_item__course=course,
            publication_status=Lesson.PublicationStatus.PUBLISHED,
            generation_status=Lesson.GenerationStatus.COMPLETED,
        )

        content = lesson.presentation_content
        if not isinstance(content, dict):
            content = {}

        mode_template = LESSON_MODE_TEMPLATES.get(
            lesson.generation_mode,
            LESSON_MODE_TEMPLATES[
                Lesson.GenerationMode.QUICK_LESSON
            ],
        )

        lesson_steps = build_lesson_steps(lesson, content)

    return render(
        request,
        "core/public_course_detail.html",
        {
            "course": course,
            "published_sessions": published_sessions,
            "lesson": lesson,
            "content": content,
            "mode_template": mode_template,
            "lesson_steps": lesson_steps,
            "is_public": True,
        },
    )

@login_required
def course_outline(request, course_id):
    course = get_object_or_404(
        Course,
        id=course_id,
        creator=request.user,
    )

    outline_items = (
        CourseOutlineItem.objects.filter(course=course)
        .select_related("lesson")
        .order_by("week_number", "position")
    )

    total_sessions = outline_items.count()

    completed_sessions = outline_items.filter(
        status__in=[
            CourseOutlineItem.Status.READY_FOR_REVIEW,
            CourseOutlineItem.Status.APPROVED,
        ]
    ).count()

    generating_sessions = outline_items.filter(
        status=CourseOutlineItem.Status.GENERATING
    ).count()

    failed_sessions = outline_items.filter(
        status=CourseOutlineItem.Status.FAILED
    ).count()

    progress_percent = (
        round(completed_sessions * 100 / total_sessions)
        if total_sessions
        else 0
    )

    return render(
        request,
        "core/course_outline.html",
        {
            "course": course,
            "outline_items": outline_items,
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "generating_sessions": generating_sessions,
            "failed_sessions": failed_sessions,
            "progress_percent": progress_percent,
        },
    )
@login_required
@require_POST
def toggle_course_publication(request, course_id):
    course = get_object_or_404(
        Course,
        id=course_id,
        creator=request.user,
    )

    if course.status == Course.Status.PUBLISHED:
        course.status = Course.Status.DRAFT
        course.save(update_fields=["status"])

        messages.success(
            request,
            "Course unpublished. Its public page is no longer accessible.",
        )
    else:
        published_sessions = CourseOutlineItem.objects.filter(
            course=course,
            lesson__isnull=False,
            lesson__publication_status=Lesson.PublicationStatus.PUBLISHED,
            lesson__generation_status=Lesson.GenerationStatus.COMPLETED,
        ).exists()

        if not published_sessions:
            messages.error(
                request,
                "Publish at least one completed lesson before publishing this course.",
            )
            return redirect(
                "core:course_outline",
                course_id=course.id,
            )

        course.status = Course.Status.PUBLISHED
        course.save(update_fields=["status"])

        messages.success(
            request,
            "Course published successfully.",
        )

    return redirect("core:course_outline", course_id=course.id)

@login_required
def edit_lesson(request, lesson_id):
    import logging

    from .section_development import (
        SectionDevelopmentError,
        develop_section_content,
    )

    logger = logging.getLogger(__name__)

    lesson = get_object_or_404(
        Lesson,
        id=lesson_id,
        creator=request.user,
    )

    if lesson.generation_status != Lesson.GenerationStatus.COMPLETED:
        messages.warning(
            request,
            "Only completed lessons can be edited.",
        )
        return redirect("core:lesson_detail", lesson_id=lesson.id)

    content = lesson.presentation_content
    if not isinstance(content, dict):
        content = {}

    sections = content.get("sections", [])
    questions = content.get("questions", [])

    if not isinstance(sections, list):
        sections = []

    if not isinstance(questions, list):
        questions = []

    details_form = LessonDetailsForm(
        initial={
            "title": lesson.title,
            "learning_notes": lesson.learning_notes,
            "teaching_notes": lesson.teaching_notes,
        }
    )

    section_form = LessonSectionForm()
    question_form = LessonQuestionForm()

    # These values hold an AI draft for the current request only.
    # Developing a section must not save the lesson automatically.
    developed_section_index = None
    developed_section_content = None
    developed_section_heading = None

    if request.method == "POST":
        form_type = request.POST.get("form_type")

        if form_type == "move_section":
            try:
                index = int(request.POST.get("index", ""))
                direction = request.POST.get("direction", "")
            except (TypeError, ValueError):
                raise Http404

            if index < 0 or index >= len(sections):
                raise Http404

            if direction == "up" and index > 0:
                target_index = index - 1
            elif direction == "down" and index < len(sections) - 1:
                target_index = index + 1
            else:
                return redirect(
                    "core:edit_lesson",
                    lesson_id=lesson.id,
                )

            sections[index], sections[target_index] = (
                sections[target_index],
                sections[index],
            )

            content["sections"] = sections
            lesson.presentation_content = content
            lesson.save(
                update_fields=["presentation_content", "updated_at"]
            )

            messages.success(request, "Lesson section order updated.")
            return redirect("core:edit_lesson", lesson_id=lesson.id)

        elif form_type == "develop_section":
            try:
                index = int(request.POST.get("index", ""))
            except (TypeError, ValueError):
                raise Http404

            if index < 0 or index >= len(sections):
                raise Http404

            # Use the current editor values so unsaved changes are included.
            heading = request.POST.get("heading", "").strip()
            existing_content = request.POST.get("content", "").strip()

            if not heading or not existing_content:
                messages.error(
                    request,
                    "Enter a section heading and some content before "
                    "developing it further.",
                )
            else:
                try:
                    course = getattr(lesson, "course", None)
                    learner_level = getattr(
                        course,
                        "learner_level",
                        "",
                    )

                    neighboring_headings = [
                        section.get("heading", "")
                        for position, section in enumerate(sections)
                        if position != index
                        and isinstance(section, dict)
                        and section.get("heading")
                    ]

                    developed_content = develop_section_content(
                        heading=heading,
                        existing_content=existing_content,
                        lesson_title=lesson.title,
                        lesson_topic=getattr(lesson, "topic", ""),
                        learner_level=str(learner_level or ""),
                        learning_notes=lesson.learning_notes or "",
                        neighboring_headings=neighboring_headings,
                    )

                    # Keep the AI result in the form as a draft.
                    # Do not update lesson.presentation_content here.
                    developed_section_index = index
                    developed_section_content = developed_content
                    developed_section_heading = heading

                    messages.success(
                        request,
                        "The AI draft is ready. Review it and select "
                        "Save section when you're satisfied.",
                    )

                except SectionDevelopmentError as exc:
                    messages.error(request, str(exc))

                except Exception:
                    logger.exception(
                        "Unexpected error developing lesson section %s "
                        "for lesson %s.",
                        index,
                        lesson.id,
                    )
                    messages.error(
                        request,
                        "Something went wrong while developing this section. "
                        "Your saved lesson content has not been changed.",
                    )

        elif form_type == "add_section":
            section_form = LessonSectionForm(request.POST)

            if section_form.is_valid():
                sections.append({
                    "heading": section_form.cleaned_data["heading"],
                    "content": section_form.cleaned_data["content"],
                })

                content["sections"] = sections
                lesson.presentation_content = content
                lesson.save(
                    update_fields=["presentation_content", "updated_at"]
                )

                messages.success(request, "Lesson section added.")
                return redirect("core:edit_lesson", lesson_id=lesson.id)

        elif form_type == "add_question":
            question_form = LessonQuestionForm(request.POST)

            if question_form.is_valid():
                cleaned = question_form.cleaned_data
                options = [
                    option.strip()
                    for option in cleaned["options"].splitlines()
                    if option.strip()
                ]

                questions.append({
                    "question": cleaned["question"],
                    "question_type": cleaned["question_type"],
                    "options": options,
                    "answer": cleaned["answer"],
                    "explanation": cleaned["explanation"],
                    "hint": cleaned["hint"],
                    "section_heading": cleaned["section_heading"],
                })

                content["questions"] = questions
                lesson.presentation_content = content
                lesson.save(
                    update_fields=["presentation_content", "updated_at"]
                )

                messages.success(request, "Quiz question added.")
                return redirect("core:edit_lesson", lesson_id=lesson.id)

        elif form_type == "details":
            details_form = LessonDetailsForm(request.POST)

            if details_form.is_valid():
                lesson.title = details_form.cleaned_data["title"]
                lesson.learning_notes = (
                    details_form.cleaned_data["learning_notes"]
                )
                lesson.teaching_notes = (
                    details_form.cleaned_data["teaching_notes"]
                )

                lesson.save(
                    update_fields=[
                        "title",
                        "learning_notes",
                        "teaching_notes",
                        "updated_at",
                    ]
                )

                messages.success(request, "Lesson details updated.")
                return redirect("core:edit_lesson", lesson_id=lesson.id)

        elif form_type == "delete_question":
            try:
                index = int(request.POST.get("index", ""))
            except (TypeError, ValueError):
                raise Http404

            if index < 0 or index >= len(questions):
                raise Http404

            questions.pop(index)

            content["questions"] = questions
            lesson.presentation_content = content
            lesson.save(
                update_fields=["presentation_content", "updated_at"]
            )

            messages.success(request, "Quiz question deleted.")
            return redirect("core:edit_lesson", lesson_id=lesson.id)

        elif form_type == "delete_section":
            try:
                index = int(request.POST.get("index", ""))
            except (TypeError, ValueError):
                raise Http404

            if index < 0 or index >= len(sections):
                raise Http404

            sections.pop(index)

            content["sections"] = sections
            lesson.presentation_content = content
            lesson.save(
                update_fields=["presentation_content", "updated_at"]
            )

            messages.success(request, "Lesson section deleted.")
            return redirect("core:edit_lesson", lesson_id=lesson.id)

        elif form_type == "section":
            try:
                index = int(request.POST.get("index", ""))
            except (TypeError, ValueError):
                raise Http404

            if index < 0 or index >= len(sections):
                raise Http404

            section_form = LessonSectionForm(request.POST)

            if section_form.is_valid():
                sections[index] = {
                    **(
                        sections[index]
                        if isinstance(sections[index], dict)
                        else {}
                    ),
                    "heading": section_form.cleaned_data["heading"],
                    "content": section_form.cleaned_data["content"],
                }

                content["sections"] = sections
                lesson.presentation_content = content
                lesson.save(
                    update_fields=["presentation_content", "updated_at"]
                )

                messages.success(request, "Lesson section updated.")
                return redirect("core:edit_lesson", lesson_id=lesson.id)

        elif form_type == "move_question":
            try:
                index = int(request.POST.get("index", ""))
            except (TypeError, ValueError):
                raise Http404

            direction = request.POST.get("direction", "")

            if index < 0 or index >= len(questions):
                raise Http404

            if direction == "up" and index > 0:
                target_index = index - 1
            elif direction == "down" and index < len(questions) - 1:
                target_index = index + 1
            else:
                return redirect(
                    "core:edit_lesson",
                    lesson_id=lesson.id,
                )

            questions[index], questions[target_index] = (
                questions[target_index],
                questions[index],
            )

            content["questions"] = questions
            lesson.presentation_content = content
            lesson.save(
                update_fields=["presentation_content", "updated_at"]
            )

            messages.success(request, "Quiz question order updated.")
            return redirect("core:edit_lesson", lesson_id=lesson.id)

        elif form_type == "question":
            try:
                index = int(request.POST.get("index", ""))
            except (TypeError, ValueError):
                raise Http404

            if index < 0 or index >= len(questions):
                raise Http404

            question_form = LessonQuestionForm(request.POST)

            if question_form.is_valid():
                cleaned = question_form.cleaned_data
                options = [
                    option.strip()
                    for option in cleaned["options"].splitlines()
                    if option.strip()
                ]

                questions[index] = {
                    **(
                        questions[index]
                        if isinstance(questions[index], dict)
                        else {}
                    ),
                    "question": cleaned["question"],
                    "question_type": cleaned["question_type"],
                    "options": options,
                    "answer": cleaned["answer"],
                    "explanation": cleaned["explanation"],
                    "hint": cleaned["hint"],
                    "section_heading": cleaned["section_heading"],
                }

                content["questions"] = questions
                lesson.presentation_content = content
                lesson.save(
                    update_fields=["presentation_content", "updated_at"]
                )

                messages.success(request, "Quiz question updated.")
                return redirect("core:edit_lesson", lesson_id=lesson.id)

        else:
            raise Http404

    # Build section forms for BOTH GET and POST requests.
    # This block must remain outside the POST handler.
    section_forms = []

    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            continue

        is_developed = developed_section_index == index

        initial_heading = (
            developed_section_heading
            if is_developed
            else section.get("heading", "")
        )

        initial_content = (
            developed_section_content
            if is_developed
            else section.get("content", "")
        )

        if (
            request.method == "POST"
            and request.POST.get("form_type") == "section"
            and request.POST.get("index") == str(index)
        ):
            form = section_form
        else:
            form = LessonSectionForm(
                initial={
                    "heading": initial_heading,
                    "content": initial_content,
                }
            )

        section_forms.append({
            "index": index,
            "form": form,
            "is_developed": is_developed,
        })

    # Build question forms for BOTH GET and POST requests.
    question_forms = []

    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            continue

        if (
            request.method == "POST"
            and request.POST.get("form_type") == "question"
            and request.POST.get("index") == str(index)
        ):
            form = question_form
        else:
            options = question.get("options", [])
            if not isinstance(options, list):
                options = []

            form = LessonQuestionForm(
                initial={
                    "question": question.get("question", ""),
                    "question_type": question.get(
                        "question_type",
                        "multiple_choice",
                    ),
                    "options": "\n".join(options),
                    "answer": question.get("answer", ""),
                    "explanation": question.get("explanation", ""),
                    "hint": question.get("hint", ""),
                    "section_heading": question.get(
                        "section_heading",
                        "",
                    ),
                }
            )

        question_forms.append({
            "index": index,
            "form": form,
        })

    return render(
        request,
        "core/lessons/edit_lesson.html",
        {
            "lesson": lesson,
            "details_form": details_form,
            "section_forms": section_forms,
            "question_forms": question_forms,
            "section_form": section_form,
            "question_form": question_form,
            "developed_section_index": developed_section_index,
        },
    )

@login_required
@require_POST
def delete_lesson(request, lesson_id):
    lesson = get_object_or_404(
        Lesson,
        id=lesson_id,
        creator=request.user,
    )

    course_id = lesson.course_id
    outline_item = lesson.outline_item

    # Allow a deleted course session to be generated again.
    if outline_item:
        outline_item.status = CourseOutlineItem.Status.PLANNED
        outline_item.approved_at = None
        outline_item.generation_error = ""
        outline_item.save(
            update_fields=[
                "status",
                "approved_at",
                "generation_error",
                "updated_at",
            ]
        )

    lesson.delete()
    messages.success(request, "Lesson deleted successfully.")

    if course_id:
        return redirect("core:course_outline", course_id=course_id)

    return redirect("core:library")


@login_required
@require_POST
def delete_course(request, course_id):
    course = get_object_or_404(
        Course,
        id=course_id,
        creator=request.user,
    )

    course.delete()
    messages.success(
        request,
        "Course and its associated lessons and outline deleted.",
    )

    return redirect("core:library")

@login_required
def export_lesson_docx(request, lesson_id):
    lesson = get_object_or_404(
        Lesson,
        id=lesson_id,
        creator=request.user,
    )

    document = Document()
    document.add_heading(
        lesson.title or lesson.topic or "Lesson Notes",
        0,
    )

    if lesson.topic:
        document.add_paragraph(f"Topic: {lesson.topic}")

    document.add_paragraph(
        f"Learner level: {lesson.get_learner_level_display()}"
    )
    document.add_paragraph(f"Duration: {lesson.duration_minutes} minutes")

    content = lesson.presentation_content or {}

    def add_text(value):
        """Add readable text without exposing raw dictionaries."""
        if value is None:
            return

        if isinstance(value, str):
            if value.strip():
                document.add_paragraph(value.strip())
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    add_structured_item(item)
                else:
                    add_text(item)

    def add_bullets(items):
        for item in items:
            if isinstance(item, dict):
                add_structured_item(item)
            else:
                document.add_paragraph(str(item), style="List Bullet")

    def add_structured_item(item):
        """Format known content fields instead of printing dictionaries."""
        if not isinstance(item, dict):
            add_text(item)
            return

        heading = (
            item.get("heading")
            or item.get("title")
            or item.get("question")
        )

        if heading:
            document.add_heading(str(heading), level=2)

        for key, value in item.items():
            if key in {"heading", "title", "question"}:
                continue

            if key in {"content", "instructions", "explanation",
                       "speaker_notes", "activity", "assignment"}:
                add_text(value)

            elif key in {"options", "bullet_points", "learning_objectives",
                         "learning_goals"}:
                add_bullets(value if isinstance(value, list) else [value])

            elif key == "answer":
                paragraph = document.add_paragraph()
                paragraph.add_run("Answer: ").bold = True
                paragraph.add_run(str(value))

            elif key == "hint":
                paragraph = document.add_paragraph()
                paragraph.add_run("Hint: ").bold = True
                paragraph.add_run(str(value))

            elif key == "sessions" and isinstance(value, list):
                for session in value:
                    add_structured_item(session)

            elif key in {"week_number", "session_number"}:
                continue

    if lesson.learning_notes:
        document.add_heading("Lesson Content", level=1)
        document.add_paragraph(lesson.learning_notes)

    # Read the structured content using known content categories.
    if isinstance(content, dict):
        sections = content.get("sections", [])
        if sections:
            document.add_heading("Lesson Sections", level=1)
            add_bullets(sections)

        objectives = content.get("learning_objectives", [])
        if objectives:
            document.add_heading("Learning Objectives", level=1)
            add_bullets(objectives)

        for key, heading in [
            ("key_points", "Key Points"),
            ("examples", "Examples"),
            ("fun_facts", "Fun Facts"),
        ]:
            items = content.get(key, [])
            if items:
                document.add_heading(heading, level=1)
                add_bullets(items)

        questions = content.get("questions", [])
        if questions:
            document.add_heading("Review Questions", level=1)
            for index, question in enumerate(questions, start=1):
                document.add_paragraph(
                    f"{index}. {question.get('question', 'Question')}"
                )
                for option in question.get("options", []):
                    document.add_paragraph(
                        str(option),
                        style="List Bullet",
                    )
                if question.get("answer"):
                    paragraph = document.add_paragraph()
                    paragraph.add_run("Answer: ").bold = True
                    paragraph.add_run(str(question["answer"]))
                if question.get("explanation"):
                    paragraph = document.add_paragraph()
                    paragraph.add_run("Explanation: ").bold = True
                    paragraph.add_run(str(question["explanation"]))

        activities = content.get("activities", [])
        if activities:
            document.add_heading("Activities", level=1)
            add_bullets(activities)

        assignment = content.get("assignment")
        if assignment:
            document.add_heading("Assignment", level=1)
            add_text(assignment)

        conclusion = content.get("conclusion")
        if conclusion:
            document.add_heading("Conclusion", level=1)
            add_text(conclusion)

    if lesson.teaching_notes:
        document.add_heading("Teaching Notes", level=1)
        document.add_paragraph(lesson.teaching_notes)

    buffer = BytesIO()
    document.save(buffer)
    buffer.seek(0)

    filename = f"coursepilot_lesson_{lesson.id}.docx"

    response = HttpResponse(
        buffer.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )

    return response

@login_required
def export_lesson_pptx(request, lesson_id):
    import random
    from io import BytesIO

    from django.http import Http404, HttpResponse
    from django.shortcuts import get_object_or_404
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.util import Inches as PptxInches, Pt as PptxPt

    lesson = get_object_or_404(
        Lesson,
        id=lesson_id,
        creator=request.user,
    )

    # Preserve the existing access rules.

    if lesson.generation_status != Lesson.GenerationStatus.COMPLETED:
        raise Http404

    content = lesson.presentation_content
    if not isinstance(content, dict):
        content = {}

    presentation = Presentation()
    presentation.slide_width = PptxInches(13.333)
    presentation.slide_height = PptxInches(7.5)

    # Select a random theme for each download.
    themes = [
        {
            "name": "Academic Blue",
            "cover": (25, 43, 72),
            "accent": (48, 100, 190),
            "title": (25, 43, 72),
            "body": (45, 52, 64),
            "muted": (105, 115, 130),
            "light": (239, 244, 250),
            "background": (255, 255, 255),
            "cover_text": (220, 229, 243),
        },
        {
            "name": "Forest & Cream",
            "cover": (35, 65, 54),
            "accent": (69, 125, 94),
            "title": (35, 65, 54),
            "body": (55, 60, 53),
            "muted": (112, 120, 107),
            "light": (226, 233, 218),
            "background": (250, 248, 239),
            "cover_text": (224, 237, 224),
        },
        {
            "name": "Charcoal & Amber",
            "cover": (39, 42, 48),
            "accent": (232, 160, 55),
            "title": (39, 42, 48),
            "body": (57, 59, 64),
            "muted": (115, 117, 123),
            "light": (239, 231, 216),
            "background": (255, 253, 248),
            "cover_text": (245, 224, 185),
        },
        {
            "name": "Modern Teal",
            "cover": (25, 62, 69),
            "accent": (29, 145, 145),
            "title": (25, 62, 69),
            "body": (44, 58, 62),
            "muted": (100, 119, 123),
            "light": (222, 239, 237),
            "background": (248, 252, 251),
            "cover_text": (210, 236, 234),
        },
        {
            "name": "Royal Purple",
            "cover": (54, 43, 82),
            "accent": (125, 91, 190),
            "title": (54, 43, 82),
            "body": (54, 53, 65),
            "muted": (112, 108, 130),
            "light": (235, 229, 246),
            "background": (252, 250, 255),
            "cover_text": (229, 218, 249),
        },
    ]

    theme = random.choice(themes)

    def color(key):
        return RGBColor(*theme[key])

    COVER = color("cover")
    ACCENT = color("accent")
    TITLE = color("title")
    BODY = color("body")
    MUTED = color("muted")
    LIGHT = color("light")
    BACKGROUND = color("background")
    COVER_TEXT = color("cover_text")
    WHITE = RGBColor(255, 255, 255)

    TITLE_SIZE = 30
    BODY_SIZE = 21

    def clean_text(value):
        if value is None or isinstance(value, (dict, list)):
            return ""
        return str(value).strip()

    def get_items(key):
        value = content.get(key, [])
        if not isinstance(value, list):
            value = [value] if value else []

        result = []
        for item in value:
            if isinstance(item, dict):
                text = clean_text(item.get("description", ""))
            else:
                text = clean_text(item)

            if text:
                result.append(text)

        return result

    def add_notes(slide, notes=""):
        notes = clean_text(notes)
        if not notes:
            return

        try:
            notes_frame = slide.notes_slide.notes_text_frame
            if notes_frame is not None:
                notes_frame.text = notes
        except (AttributeError, NotImplementedError):
            pass

    def add_footer(slide):
        line = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            PptxInches(0.6),
            PptxInches(7.05),
            PptxInches(12.13),
            PptxInches(0.025),
        )
        line.fill.solid()
        line.fill.fore_color.rgb = LIGHT
        line.line.fill.background()

        footer = slide.shapes.add_textbox(
            PptxInches(0.65),
            PptxInches(7.1),
            PptxInches(12),
            PptxInches(0.22),
        )
        frame = footer.text_frame
        frame.word_wrap = False

        paragraph = frame.paragraphs[0]
        paragraph.text = "COURSEPILOT  |  LESSON PRESENTATION"
        paragraph.font.name = "Aptos"
        paragraph.font.size = PptxPt(9)
        paragraph.font.color.rgb = MUTED

        paragraph = frame.add_paragraph()
        paragraph.text = f"{len(presentation.slides):02d}"
        paragraph.alignment = PP_ALIGN.RIGHT
        paragraph.font.name = "Aptos"
        paragraph.font.size = PptxPt(9)
        paragraph.font.color.rgb = MUTED

    def add_accent(slide, x, y, width, height=0.06):
        shape = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            PptxInches(x),
            PptxInches(y),
            PptxInches(width),
            PptxInches(height),
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = ACCENT
        shape.line.fill.background()

    def add_cover():
        slide = presentation.slides.add_slide(
            presentation.slide_layouts[6]
        )
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = COVER

        # Decorative accent blocks.
        add_accent(slide, 0.9, 1.05, 1.1, 0.09)
        add_accent(slide, 10.9, 5.8, 1.3, 0.09)

        title_box = slide.shapes.add_textbox(
            PptxInches(0.95),
            PptxInches(1.5),
            PptxInches(11.3),
            PptxInches(1.8),
        )
        frame = title_box.text_frame
        frame.word_wrap = True
        frame.vertical_anchor = MSO_ANCHOR.MIDDLE

        title = frame.paragraphs[0]
        title.text = (
            clean_text(lesson.title or lesson.topic) or "Lesson"
        )
        title.font.name = "Aptos Display"
        title.font.size = PptxPt(36)
        title.font.bold = True
        title.font.color.rgb = WHITE

        topic = clean_text(lesson.topic)
        if topic and topic != clean_text(lesson.title):
            subtitle = frame.add_paragraph()
            subtitle.text = topic
            subtitle.font.name = "Aptos"
            subtitle.font.size = PptxPt(20)
            subtitle.font.color.rgb = COVER_TEXT
            subtitle.space_before = PptxPt(12)

        try:
            level = lesson.get_learner_level_display()
        except (AttributeError, TypeError):
            level = clean_text(lesson.learner_level)

        details = []
        if level:
            details.append(f"Learner level: {level}")
        if lesson.duration_minutes:
            details.append(
                f"Duration: {lesson.duration_minutes} minutes"
            )

        detail_box = slide.shapes.add_textbox(
            PptxInches(0.98),
            PptxInches(4.25),
            PptxInches(10.8),
            PptxInches(1.1),
        )
        detail_frame = detail_box.text_frame
        detail_frame.word_wrap = True

        for index, item in enumerate(details):
            paragraph = (
                detail_frame.paragraphs[0]
                if index == 0
                else detail_frame.add_paragraph()
            )
            paragraph.text = item
            paragraph.font.name = "Aptos"
            paragraph.font.size = PptxPt(16)
            paragraph.font.color.rgb = COVER_TEXT
            paragraph.space_after = PptxPt(9)

        brand = slide.shapes.add_textbox(
            PptxInches(0.98),
            PptxInches(6.45),
            PptxInches(6),
            PptxInches(0.4),
        )
        paragraph = brand.text_frame.paragraphs[0]
        paragraph.text = "Prepared with CoursePilot"
        paragraph.font.name = "Aptos"
        paragraph.font.size = PptxPt(12)
        paragraph.font.color.rgb = COVER_TEXT

        add_notes(slide, content.get("introduction", ""))

    def add_content_slide(title, items, notes=""):
        items = [
            clean_text(item)
            for item in items
            if clean_text(item)
        ]
        if not items:
            return

        # Split long text into readable chunks.
        paragraphs = []
        for item in items:
            words = item.split()
            chunk = ""

            for word in words:
                candidate = f"{chunk} {word}".strip()
                if len(candidate) > 240 and chunk:
                    paragraphs.append(chunk)
                    chunk = word
                else:
                    chunk = candidate

            if chunk:
                paragraphs.append(chunk)

        # No more than five content items per slide.
        groups = [
            paragraphs[index:index + 5]
            for index in range(0, len(paragraphs), 5)
        ]

        for group_index, group in enumerate(groups, start=1):
            slide = presentation.slides.add_slide(
                presentation.slide_layouts[6]
            )
            slide.background.fill.solid()
            slide.background.fill.fore_color.rgb = BACKGROUND

            # A slim accent panel gives each theme its identity.
            add_accent(slide, 0, 0, 0.12, 7.5)

            title_box = slide.shapes.add_textbox(
                PptxInches(0.75),
                PptxInches(0.45),
                PptxInches(11.8),
                PptxInches(0.85),
            )
            title_frame = title_box.text_frame
            title_frame.word_wrap = True

            heading = title_frame.paragraphs[0]
            heading.text = (
                f"{clean_text(title)} ({group_index})"
                if len(groups) > 1
                else clean_text(title) or "Lesson Content"
            )
            heading.font.name = "Aptos Display"
            heading.font.size = PptxPt(TITLE_SIZE)
            heading.font.bold = True
            heading.font.color.rgb = TITLE

            add_accent(slide, 0.78, 1.38, 1.05)

            body_box = slide.shapes.add_textbox(
                PptxInches(0.9),
                PptxInches(1.75),
                PptxInches(11.45),
                PptxInches(4.95),
            )
            frame = body_box.text_frame
            frame.clear()
            frame.word_wrap = True
            frame.vertical_anchor = MSO_ANCHOR.TOP
            frame.margin_left = PptxInches(0.12)
            frame.margin_right = PptxInches(0.12)
            frame.margin_top = PptxInches(0.08)
            frame.margin_bottom = PptxInches(0.08)

            for index, item in enumerate(group):
                paragraph = (
                    frame.paragraphs[0]
                    if index == 0
                    else frame.add_paragraph()
                )
                paragraph.text = item
                paragraph.level = 0
                paragraph.font.name = "Aptos"
                paragraph.font.size = PptxPt(BODY_SIZE)
                paragraph.font.color.rgb = BODY
                paragraph.space_after = PptxPt(17)
                paragraph.line_spacing = 1.15
                paragraph.bullet = True

            add_footer(slide)
            add_notes(slide, notes if group_index == 1 else "")

    def add_questions():
        questions = content.get("questions", [])
        if not isinstance(questions, list):
            return

        for index, question in enumerate(questions, start=1):
            if not isinstance(question, dict):
                continue

            question_text = clean_text(question.get("question"))
            if not question_text:
                continue

            options = question.get("options", [])
            if not isinstance(options, list):
                options = []

            items = [question_text]
            for option_index, option in enumerate(options):
                option = clean_text(option)
                if option:
                    label = (
                        chr(65 + option_index)
                        if option_index < 26
                        else str(option_index + 1)
                    )
                    items.append(f"{label}. {option}")

            answer = clean_text(question.get("answer"))
            explanation = clean_text(question.get("explanation"))

            notes = "\n".join(
                value for value in (
                    f"Suggested answer: {answer}" if answer else "",
                    f"Explanation: {explanation}" if explanation else "",
                )
                if value
            )

            add_content_slide(
                f"Review Question {index}",
                items,
                notes=notes,
            )

    # 1. Cover.
    add_cover()

    # 2. Learning objectives.
    objectives = get_items("learning_objectives")
    if objectives:
        add_content_slide("Learning Objectives", objectives)

    # 3. Introduction.
    introduction = clean_text(content.get("introduction"))
    if introduction:
        add_content_slide("Introduction", [introduction])

    # 4. Main lesson: prefer generated presentation slides.
    generated_slides = content.get("presentation_slides", [])
    if not isinstance(generated_slides, list):
        generated_slides = []

    valid_slides = [
        item for item in generated_slides
        if isinstance(item, dict) and clean_text(item.get("title"))
    ]

    if valid_slides:
        for item in valid_slides:
            bullets = item.get("bullet_points", [])
            if not isinstance(bullets, list):
                bullets = [bullets]

            add_content_slide(
                item.get("title", "Lesson Content"),
                bullets,
                notes=item.get("speaker_notes", ""),
            )
    else:
        sections = content.get("sections", [])
        if isinstance(sections, list):
            for index, section in enumerate(sections, start=1):
                if not isinstance(section, dict):
                    continue

                heading = clean_text(section.get("heading")) or (
                    f"Section {index}"
                )
                body = clean_text(section.get("content"))

                if body:
                    paragraphs = [
                        part.strip()
                        for part in body.splitlines()
                        if part.strip()
                    ]
                    add_content_slide(heading, paragraphs)

    # 5. Supporting content.
    for key, heading in (
        ("key_points", "Key Takeaways"),
        ("examples", "Practical Examples"),
        ("fun_facts", "Did You Know?"),
    ):
        items = get_items(key)
        if items:
            add_content_slide(heading, items)

    # 6. Class activities.
    activities = content.get("activities", [])
    if isinstance(activities, list):
        for index, activity in enumerate(activities, start=1):
            if not isinstance(activity, dict):
                continue

            heading = clean_text(activity.get("title")) or (
                f"Class Activity {index}"
            )
            instructions = clean_text(activity.get("instructions"))

            if instructions:
                add_content_slide(heading, [instructions])

    # 7. Review questions.
    add_questions()

    # 8. Assignment.
    assignment = clean_text(content.get("assignment"))
    if assignment:
        add_content_slide("Assignment", [assignment])

    # 9. Conclusion.
    conclusion = clean_text(content.get("conclusion"))
    if conclusion:
        add_content_slide("Conclusion", [conclusion])

    # Fallback for lessons with no structured content.
    if len(presentation.slides) == 1:
        fallback = clean_text(
            lesson.learning_notes or lesson.topic
        )
        add_content_slide(
            "Lesson Content",
            [fallback or "No lesson content available."],
        )

    output = BytesIO()
    presentation.save(output)
    output.seek(0)

    filename = clean_text(lesson.title) or "coursepilot-lesson"
    safe_filename = "".join(
        char if char.isalnum() or char in ("-", "_") else "_"
        for char in filename
    ).strip("_") or "coursepilot-lesson"

    response = HttpResponse(
        output.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "presentationml.presentation"
        ),
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{safe_filename}.pptx"'
    )
    return response