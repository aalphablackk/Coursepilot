
from django.db import transaction

from core.course_outline_generator import (
    DEFAULT_WEEKS_PER_BATCH,
    CourseOutlineGenerationError,
    generate_course_outline_batch,
)
from core.models import Course, CourseOutlineItem


def generate_and_save_course_outline(course, data):
    """Generate the outline in batches and save each successful batch."""

    course.outline_status = Course.OutlineStatus.GENERATING
    course.save(update_fields=["outline_status", "updated_at"])

    try:
        total_weeks = course.duration_weeks

        for start_week in range(
            1, total_weeks + 1, DEFAULT_WEEKS_PER_BATCH
        ):
            weeks, _response = generate_course_outline_batch(
                data,
                start_week=start_week,
                week_count=DEFAULT_WEEKS_PER_BATCH,
            )

            # Each successful batch is saved atomically.
            with transaction.atomic():
                for week in weeks:
                    for position, session in enumerate(
                        week["sessions"], start=1
                    ):
                        CourseOutlineItem.objects.update_or_create(
                            course=course,
                            session_number=session["session_number"],
                            defaults={
                                "week_number": week["week_number"],
                                "position": position,
                                "title": session["title"],
                                "topic": session["topic"],
                                "learning_objectives": (
                                    session["learning_objectives"]
                                ),
                                "status": (
                                    CourseOutlineItem.Status.PLANNED
                                ),
                                "generation_error": "",
                            },
                        )

        course.outline_status = Course.OutlineStatus.READY_FOR_REVIEW
        course.save(update_fields=["outline_status", "updated_at"])

    except Exception:
        course.outline_status = Course.OutlineStatus.FAILED
        course.save(update_fields=["outline_status", "updated_at"])
        raise

    return course
