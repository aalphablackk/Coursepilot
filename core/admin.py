
from django.contrib import admin

from .models import Course, Lesson
from django.contrib import admin
from .models import AIConfiguration


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
    fields = ("title", "generation_mode", "learner_level", "duration_minutes")
    show_change_link = True


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "creator",
        "learner_level",
        "status",
        "duration_weeks",
        "updated_at",
    )
    list_filter = ("status", "learner_level", "created_at")
    search_fields = ("title", "description", "creator__username", "creator__email")
    readonly_fields = ("id", "created_at", "updated_at", "published_at")
    prepopulated_fields = {}
    inlines = [LessonInline]


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "creator",
        "course",
        "generation_mode",
        "learner_level",
        "ai_provider",
        "updated_at",
    )
    list_filter = ("generation_mode", "learner_level", "detail_level", "ai_provider")
    search_fields = ("title", "topic", "creator__username", "creator__email")
    readonly_fields = ("id", "created_at", "updated_at")



@admin.register(AIConfiguration)
class AIConfigurationAdmin(admin.ModelAdmin):
    list_display = ("active_provider", "updated_at")

    def has_add_permission(self, request):
        return not AIConfiguration.objects.filter(pk=1).exists()

    def has_delete_permission(self, request, obj=None):
        return False