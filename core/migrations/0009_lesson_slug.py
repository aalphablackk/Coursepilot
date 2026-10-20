
import django.db.models.deletion
from django.db import migrations, models
from django.utils.text import slugify


def populate_lesson_slugs(apps, schema_editor):
    Lesson = apps.get_model("core", "Lesson")
    database = schema_editor.connection.alias

    used_slugs = set()

    lessons = (
        Lesson.objects.using(database)
        .only("id", "title", "topic", "slug")
        .order_by("created_at", "id")
    )

    for lesson in lessons.iterator():
        base = slugify(lesson.title or lesson.topic or "lesson") or "lesson"
        candidate = base[:255]
        counter = 2

        while candidate in used_slugs:
            suffix = f"-{counter}"
            candidate = f"{base[:255 - len(suffix)]}{suffix}"
            counter += 1

        used_slugs.add(candidate)

        Lesson.objects.using(database).filter(pk=lesson.pk).update(
            slug=candidate
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_lesson_publication_status_lesson_published_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="lesson",
            name="slug",
            field=models.SlugField(
                max_length=255,
                blank=True,
                default="",
                db_index=False,
            ),
            preserve_default=False,
        ),
        migrations.RunPython(
            populate_lesson_slugs,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="lesson",
            name="slug",
            field=models.SlugField(
                max_length=255,
                unique=True,
                blank=True,
                db_index=False,
            ),
        ),
    ]
