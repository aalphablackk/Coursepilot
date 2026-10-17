# from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect,get_object_or_404
from django.http import Http404
from .forms import (
    GenerationForm,
    LessonDetailsForm,
    LessonSectionForm,
    LessonQuestionForm,
)
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

logger = logging.getLogger(__name__)


from django.http import JsonResponse


def lesson_generation_status(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)

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

# @login_required


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
                creator=(
                    request.user
                    if request.user.is_authenticated
                    else None
                ),
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



def library(request):
    if request.user.is_authenticated:
        lessons = Lesson.objects.filter(
            Q(creator=request.user) | Q(creator__isnull=True),
            course__isnull=True,
        )
        courses = Course.objects.filter(creator=request.user)
    else:
        lessons = Lesson.objects.filter(
            creator__isnull=True,
            course__isnull=True,
        )
        courses = Course.objects.none()

    search_query = request.GET.get("q", "").strip()
    selected_status = request.GET.get("status", "").strip()
    selected_mode = request.GET.get("mode", "").strip()

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

    if selected_status in valid_statuses:
        lessons = lessons.filter(generation_status=selected_status)

    if selected_mode in valid_modes:
        lessons = lessons.filter(generation_mode=selected_mode)

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


def lesson_detail(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)

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


    if lesson.creator_id and lesson.creator_id != (
        request.user.id if request.user.is_authenticated else None
    ):
        raise Http404

    content = lesson.presentation_content
    if not isinstance(content, dict):
        content = {}

    mode_template = LESSON_MODE_TEMPLATES.get(
        lesson.generation_mode,
        LESSON_MODE_TEMPLATES[Lesson.GenerationMode.QUICK_LESSON],
    )

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
        },
    )

def course_outline(request, course_id):
    if not request.user.is_authenticated:
        raise Http404

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

# @login_required
def edit_lesson(request, lesson_id):
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

    if request.method == "POST":
        form_type = request.POST.get("form_type")
        if form_type == "add_section":
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

    section_forms = []
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            continue

        section_forms.append({
            "index": index,
            "form": (
                section_form
                if request.method == "POST"
                and request.POST.get("form_type") == "section"
                and request.POST.get("index") == str(index)
                else LessonSectionForm(
                    initial={
                        "heading": section.get("heading", ""),
                        "content": section.get("content", ""),
                    }
                )
            ),
        })

    question_forms = []
    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            continue

        question_forms.append({
            "index": index,
            "form": (
                question_form
                if request.method == "POST"
                and request.POST.get("form_type") == "question"
                and request.POST.get("index") == str(index)
                else LessonQuestionForm(
                    initial={
                        "question": question.get("question", ""),
                        "question_type": question.get(
                            "question_type",
                            "multiple_choice",
                        ),
                        "options": "\n".join(
                            question.get("options", [])
                            if isinstance(question.get("options", []), list)
                            else []
                        ),
                        "answer": question.get("answer", ""),
                        "explanation": question.get("explanation", ""),
                        "hint": question.get("hint", ""),
                        "section_heading": question.get(
                            "section_heading", ""
                        ),
                    }
                )
            ),
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
        },
    )