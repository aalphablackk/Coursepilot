
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LessonSection:
    """A section of instructor-ready lesson content."""

    heading: str
    content: str


@dataclass(frozen=True)
class LearningObjective:
    """A measurable learning objective."""

    description: str


@dataclass(frozen=True)
class LessonQuestion:
    """A question used to check learner understanding."""

    question: str
    answer: str = ""
    question_type: str = "short_answer"
    options: list[str] = field(default_factory=list)
    explanation: str = ""
    hint: str = ""
    section_heading: str = ""


@dataclass(frozen=True)
class LessonActivity:
    """An in-class or after-class learning activity."""

    title: str
    instructions: str
    activity_type: str = "class_activity"

@dataclass(frozen=True)
class PresentationSlide:
    """Structured content for one presentation slide."""
    title: str
    bullet_points: list[str] = field(default_factory=list)
    speaker_notes: str = ""



@dataclass(frozen=True)
class CourseSession:
    """One scheduled teaching session within a course."""

    session_number: int
    title: str
    topic: str
    learning_objectives: list[str] = field(default_factory=list)
    content: str = ""
    sections: list[LessonSection] = field(default_factory=list)
    activity: str = ""
    quiz_questions: list[LessonQuestion] = field(default_factory=list)
    assignment: str = ""
    teaching_notes: str = ""



@dataclass(frozen=True)
class CourseWeek:
    """A week containing an ordered set of teaching sessions."""
    week_number: int
    title: str
    learning_goals: list[str] = field(default_factory=list)
    sessions: list[CourseSession] = field(default_factory=list)

@dataclass(frozen=True)
class LessonOutput:
    """Normalized lesson output independent of the AI provider."""

    title: str
    introduction: str = ""
    learning_objectives: list[LearningObjective] = field(
        default_factory=list
    )
    sections: list[LessonSection] = field(default_factory=list)
    key_points: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    fun_facts: list[str] = field(default_factory=list)
    questions: list[LessonQuestion] = field(default_factory=list)
    activities: list[LessonActivity] = field(default_factory=list)
    assignment: str = ""
    conclusion: str = ""
    teaching_notes: str = ""
    presentation_slides: list[PresentationSlide] = field(default_factory=list)
    course_weeks: list[CourseWeek] = field(default_factory=list)
    sources: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
