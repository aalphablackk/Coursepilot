
from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("generate/", views.generate, name="generate"),
    path("lessons/<uuid:lesson_id>/",views.lesson_detail,name="lesson_detail",),
    path("library/", views.library, name="library"),
    path("lessons/<uuid:lesson_id>/edit/",views.edit_lesson,name="edit_lesson",),
    path("courses/<uuid:course_id>/outline/",views.course_outline,name="course_outline",),
    path("courses/<uuid:course_id>/sessions/<uuid:outline_item_id>/generate/",views.generate_course_session,name="generate_course_session",),
    path("lessons/<uuid:lesson_id>/generation-status/",views.lesson_generation_status,name="lesson_generation_status",),
    path("lessons/<uuid:lesson_id>/delete/",views.delete_lesson,name="delete_lesson",),
    path("courses/<uuid:course_id>/delete/",views.delete_course,name="delete_course",),
    path("lessons/<uuid:lesson_id>/export/",views.export_lesson_docx,name="export_lesson_docx",),
    path("lessons/<uuid:lesson_id>/export/pptx/",views.export_lesson_pptx,name="export_lesson_pptx",),
    path("lessons/<uuid:lesson_id>/publish/",views.toggle_lesson_publication,name="toggle_lesson_publication",),
    path(
    "public/lessons/<slug:slug>/",
        views.public_lesson_detail,
        name="public_lesson_detail",
    ),
    path(
        "public/courses/<slug:course_slug>/",
        views.public_course_detail,
        name="public_course_detail",
    ),
    path(
        "public/courses/<slug:course_slug>/<slug:lesson_slug>/",
        views.public_course_detail,
        name="public_course_session",
    ),
    path(
        "courses/<uuid:course_id>/publication/",
        views.toggle_course_publication,
        name="toggle_course_publication",
    ),
]