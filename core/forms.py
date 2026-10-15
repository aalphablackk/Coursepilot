
from django import forms

MAX_SOURCE_LENGTH = 50_000


class GenerationForm(forms.Form):
    MODE_CHOICES = [
        ("quick_lesson", "Quick Lesson"),
        ("summary", "Structured Summary"),
        ("presentation", "Presentation Notes"),
        ("custom_content", "Custom Content"),
        ("full_course", "Full Course"),
    ]

    LEVEL_CHOICES = [
        ("beginner", "Beginner / Primary"),
        ("intermediate", "Intermediate / Secondary"),
        ("advanced", "Advanced / Tertiary"),
    ]

    DETAIL_CHOICES = [
        ("concise", "Concise"),
        ("standard", "Standard"),
        ("detailed", "Detailed"),
    ]

    CONTENT_ACTION_CHOICES = [
        ("organize", "Organize my content"),
        ("simplify", "Simplify my content"),
        ("expand", "Expand with explanations and examples"),
        ("improve", "Identify gaps and improve my content"),
    ]

    mode = forms.ChoiceField(
        choices=MODE_CHOICES,
        initial="quick_lesson",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    topic = forms.CharField(
        required=False,
        max_length=250,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. Introduction to computer networks",
        }),
    )

    source_text = forms.CharField(
        required=False,
        max_length=MAX_SOURCE_LENGTH,
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 9,
            "maxlength": MAX_SOURCE_LENGTH,
            "placeholder": (
                "Paste your research, lecture notes, "
                "draft, or course material here..."
            ),
        }),
        error_messages={
            "max_length": "Your material must not exceed 50,000 characters.",
        },
    )

    learner_level = forms.ChoiceField(
        choices=LEVEL_CHOICES,
        required=False,
        initial="intermediate",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    detail_level = forms.ChoiceField(
        choices=DETAIL_CHOICES,
        required=False,
        initial="standard",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    content_action = forms.ChoiceField(
        choices=CONTENT_ACTION_CHOICES,
        required=False,
        initial="organize",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    duration_minutes = forms.IntegerField(
        required=False,
        min_value=5,
        max_value=480,
        initial=60,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "min": 5,
            "max": 480,
        }),
    )

    course_weeks = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=52,
        initial=4,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "min": 1,
            "max": 52,
        }),
    )

    classes_per_week = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=14,
        initial=2,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "min": 1,
            "max": 14,
        }),
    )

    class_duration_minutes = forms.IntegerField(
        required=False,
        min_value=5,
        max_value=480,
        initial=60,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "min": 5,
            "max": 480,
        }),
    )

    use_web_research = forms.BooleanField(
        required=False,
        initial=False,
        label="Use web research to enrich the content",
        widget=forms.CheckboxInput(attrs={
            "class": "form-check-input",
        }),
    )

    def clean(self):
        cleaned_data = super().clean()

        mode = cleaned_data.get("mode")
        topic = (cleaned_data.get("topic") or "").strip()
        source_text = (cleaned_data.get("source_text") or "").strip()

        cleaned_data["topic"] = topic
        cleaned_data["source_text"] = source_text

        # Custom Content must have source material.
        if mode == "custom_content":
            if not source_text:
                self.add_error(
                    "source_text",
                    "Paste your material before continuing.",
                )

        # Other modes need a topic or source material.
        elif mode in {
            "quick_lesson",
            "summary",
            "presentation",
            "full_course",
        }:
            if not topic and not source_text:
                self.add_error(
                    "topic",
                    "Enter a topic or provide source material before continuing.",
                )

        # Single-session modes need a valid class duration.
        if mode in {"quick_lesson", "summary", "presentation"}:
            if (
                cleaned_data.get("duration_minutes") is None
                and "duration_minutes" not in self.errors
            ):
                self.add_error(
                    "duration_minutes",
                    "Enter the class duration.",
                )

        # Full Course needs a complete schedule.
        if mode == "full_course":
            required_schedule_fields = {
                "course_weeks": "Enter the number of weeks.",
                "classes_per_week": "Enter the number of classes per week.",
                "class_duration_minutes": "Enter the duration of each class.",
            }

            for field_name, error_message in required_schedule_fields.items():
                if (
                    cleaned_data.get(field_name) is None
                    and field_name not in self.errors
                ):
                    self.add_error(field_name, error_message)

        return cleaned_data
