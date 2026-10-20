
import logging

from django.utils import timezone

from .models import Lesson
from .services import generate_lesson, LessonGenerationError

logger = logging.getLogger(__name__)


def clean_generated_text(value):
    if isinstance(value, str):
        return value.replace("—", ", ").replace("  ", " ").strip()

    if isinstance(value, list):
        return [clean_generated_text(item) for item in value]

    if isinstance(value, dict):
        return {
            key: clean_generated_text(item)
            for key, item in value.items()
        }

    return value


def serialize_lesson_output(output):
    return clean_generated_text({
        "sections": [
            {"heading": section.heading, "content": section.content}
            for section in output.sections
        ],
        "learning_objectives": [
            objective.description
            for objective in output.learning_objectives
        ],
        "key_points": output.key_points,
        "examples": output.examples,
        "fun_facts": output.fun_facts,
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
            for question in output.questions
        ],
        "activities": [
            {
                "title": activity.title,
                "instructions": activity.instructions,
                "activity_type": activity.activity_type,
            }
            for activity in output.activities
        ],
        "assignment": output.assignment,
        "conclusion": output.conclusion,
        "presentation_slides": [
            {
                "title": slide.title,
                "bullet_points": slide.bullet_points,
                "speaker_notes": slide.speaker_notes,
            }
            for slide in output.presentation_slides
        ],
        "course_weeks": [
            {
                "week_number": week.week_number,
                "title": week.title,
                "learning_goals": week.learning_goals,
                "sessions": [
                    {
                        "session_number": session.session_number,
                        "title": session.title,
                        "topic": session.topic,
                        "learning_objectives": session.learning_objectives,
                        "content": session.content,
                        "activity": session.activity,
                        "assignment": session.assignment,
                        "teaching_notes": session.teaching_notes,
                    }
                    for session in week.sessions
                ],
            }
            for week in output.course_weeks
        ],
        "sources": output.sources,
    })


def generate_lesson_directly(lesson_id, data):
    """Generate and save a lesson without a Celery worker."""
    try:
        lesson = Lesson.objects.get(pk=lesson_id)

        lesson.generation_status = Lesson.GenerationStatus.GENERATING
        lesson.generation_progress = 5
        lesson.generation_stage = "Preparing generation request"
        lesson.generation_started_at = timezone.now()
        lesson.generation_completed_at = None
        lesson.generation_error = ""
        lesson.save()

        Lesson.objects.filter(pk=lesson_id).update(
            generation_progress=15,
            generation_stage="Sending request to the AI provider",
        )

        output, provider_response = generate_lesson(data)

        Lesson.objects.filter(pk=lesson_id).update(
            generation_progress=85,
            generation_stage="Preparing and saving your lesson",
        )

        lesson.refresh_from_db()
        lesson.title = output.title
        lesson.learning_notes = output.introduction
        lesson.teaching_notes = output.teaching_notes
        lesson.presentation_content = serialize_lesson_output(output)
        lesson.ai_provider = provider_response.provider
        lesson.generation_status = Lesson.GenerationStatus.COMPLETED
        lesson.generation_progress = 100
        lesson.generation_stage = "Completed"
        lesson.generation_error = ""
        lesson.generation_completed_at = timezone.now()
        lesson.save()

        return lesson

    except Exception as exc:
        logger.exception(
            "Lesson generation failed for lesson %s",
            lesson_id,
        )

        error_message = (
            str(exc)
            if isinstance(exc, LessonGenerationError)
            else "We couldn't generate this lesson. Please try again."
        )

        Lesson.objects.filter(pk=lesson_id).update(
            generation_status=Lesson.GenerationStatus.FAILED,
            generation_stage="Generation failed",
            generation_error=error_message,
            generation_completed_at=timezone.now(),
        )

        return None
