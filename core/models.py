
import uuid

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.text import slugify


class Course(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title) or "course"
            self.slug = f"{base_slug}-{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Lesson(models.Model):
    class GenerationMode(models.TextChoices):
        QUICK_LESSON = "quick_lesson", "Quick Lesson"
        SUMMARY = "summary", "Structured Summary"
        PRESENTATION = "presentation", "Presentation Notes"
        CUSTOM_CONTENT = "custom_content", "Custom Content"

    class DetailLevel(models.TextChoices):
        CONCISE = "concise", "Concise"
        STANDARD = "standard", "Standard"
        DETAILED = "detailed", "Detailed"

    class NotesFormat(models.TextChoices):
        LEARNING = "learning", "Detailed Learning Notes"
        TEACHING = "teaching", "Teaching Notes"
        BOTH = "both", "Both"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lessons",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="lessons",
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

    ai_provider = models.CharField(max_length=30, blank=True)
    is_saved = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title
