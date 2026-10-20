
import uuid

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.text import slugify

def generate_unique_slug(instance, value, field_name="slug"):
    base_slug = slugify(value) or "item"
    slug = base_slug
    model_class = instance.__class__
    counter = 2

    queryset = model_class.objects.all()

    if instance.pk:
        queryset = queryset.exclude(pk=instance.pk)

    while queryset.filter(**{field_name: slug}).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug

class AIConfiguration(models.Model):
    class Provider(models.TextChoices):
        GEMINI = "gemini", "Google Gemini"
        OPENAI = "openai", "OpenAI"

    active_provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        default=Provider.GEMINI,
    )

    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Keep the singleton configuration record.
        return None

    @classmethod
    def get_active_provider(cls):
        config, _ = cls.objects.get_or_create(pk=1)
        return config.active_provider

    def __str__(self):
        return f"Active AI Provider: {self.get_active_provider_display()}"

    class Meta:
        verbose_name = "AI Provider Configuration"
        verbose_name_plural = "AI Provider Configuration"
class Course(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
    class OutlineStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        GENERATING = "generating", "Generating Outline"
        READY_FOR_REVIEW = "ready_for_review", "Ready for Review"
        APPROVED = "approved", "Approved"
        FAILED = "failed", "Failed"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="courses",
    )

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)

    learner_level = models.CharField(
        max_length=20,
        choices=[
            ("beginner", "Beginner / Primary"),
            ("intermediate", "Intermediate / Secondary"),
            ("advanced", "Advanced / Tertiary"),
        ],
        default="intermediate",
    )

    duration_weeks = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(52)],
    )
    classes_per_week = models.PositiveSmallIntegerField(
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(14)],
    )
    class_duration_minutes = models.PositiveSmallIntegerField(
        default=60,
        validators=[MinValueValidator(5), MaxValueValidator(480)],
    )

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    outline_status = models.CharField(
        max_length=20,
        choices=OutlineStatus.choices,
        default=OutlineStatus.DRAFT,
        db_index=True,
    )

    outline_approved_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_unique_slug(self, self.title)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class CourseOutlineItem(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        GENERATING = "generating", "Generating"
        READY_FOR_REVIEW = "ready_for_review", "Ready for Review"
        APPROVED = "approved", "Approved"
        FAILED = "failed", "Failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="outline_items",
    )

    week_number = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(52)],
    )

    session_number = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(728)],
    )

    position = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(14)],
    )

    title = models.CharField(max_length=250)
    topic = models.CharField(max_length=250)
    learning_objectives = models.JSONField(default=list, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED,
        db_index=True,
    )

    approved_at = models.DateTimeField(null=True, blank=True)
    generation_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["week_number", "position"]
        constraints = [
            models.UniqueConstraint(
                fields=["course", "session_number"],
                name="unique_course_session_number",
            ),
            models.UniqueConstraint(
                fields=["course", "week_number", "position"],
                name="unique_course_week_position",
            ),
        ]

    def __str__(self):
        return (
            f"{self.course.title}: "
            f"Week {self.week_number}, Session {self.session_number}"
        )

class Lesson(models.Model):
    class GenerationMode(models.TextChoices):
        QUICK_LESSON = "quick_lesson", "Quick Lesson"
        SUMMARY = "summary", "Structured Summary"
        PRESENTATION = "presentation", "Presentation Notes"
        CUSTOM_CONTENT = "custom_content", "Custom Content"
        FULL_COURSE = "full_course", "Full Course"

    class GenerationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        GENERATING = "generating", "Generating"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    class PublicationStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    class DetailLevel(models.TextChoices):
        CONCISE = "concise", "Concise"
        STANDARD = "standard", "Standard"
        DETAILED = "detailed", "Detailed"

    class NotesFormat(models.TextChoices):
        LEARNING = "learning", "Detailed Learning Notes"
        TEACHING = "teaching", "Teaching Notes"
        BOTH = "both", "Both"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(
        max_length=255,
        unique=True,
        blank=True,
        db_index=False,
    )

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="lessons",
        null=True,
        blank=True,
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="lessons",
        null=True,
        blank=True,
    )
    outline_item = models.OneToOneField(
        CourseOutlineItem,
        on_delete=models.SET_NULL,
        related_name="lesson",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=250)
    topic = models.CharField(max_length=250, blank=True)
    source_text = models.TextField(blank=True)

    generation_mode = models.CharField(
        max_length=20,
        choices=GenerationMode.choices,
        default=GenerationMode.QUICK_LESSON,
    )
    learner_level = models.CharField(
        max_length=20,
        choices=Course._meta.get_field("learner_level").choices,
        default="intermediate",
    )
    duration_minutes = models.PositiveSmallIntegerField(
        default=60,
        validators=[MinValueValidator(5), MaxValueValidator(480)],
    )
    detail_level = models.CharField(
        max_length=10,
        choices=DetailLevel.choices,
        default=DetailLevel.STANDARD,
    )
    notes_format = models.CharField(
        max_length=10,
        choices=NotesFormat.choices,
        default=NotesFormat.BOTH,
    )


    learning_notes = models.TextField(blank=True)
    teaching_notes = models.TextField(blank=True)
    presentation_content = models.JSONField(default=dict, blank=True)

    generation_status = models.CharField(
        max_length=12,
        choices=GenerationStatus.choices,
        default=GenerationStatus.PENDING,
        db_index=True,
    )

    generation_progress = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    generation_stage = models.CharField(
        max_length=100,
        blank=True,
        default="Waiting to start",
    )

    generation_error = models.TextField(blank=True)
    generation_started_at = models.DateTimeField(null=True, blank=True)
    generation_completed_at = models.DateTimeField(null=True, blank=True)


    ai_provider = models.CharField(max_length=30, blank=True)
    is_saved = models.BooleanField(default=True)

    publication_status = models.CharField(
        max_length=12,
        choices=PublicationStatus.choices,
        default=PublicationStatus.DRAFT,
        db_index=True,
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title
    def save(self, *args, **kwargs):
        if not self.slug:
            slug_source = self.title or self.topic or "lesson"
            self.slug = generate_unique_slug(self, slug_source)

        super().save(*args, **kwargs)
