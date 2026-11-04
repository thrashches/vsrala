from django.db import migrations

STANDARD_TYPES = (
    ('road_cycling', 'Шоссейный велосипед', 10),
    ('mtb', 'Горный велосипед', 20),
    ('gravel', 'Кроссовый велосипед', 30),
    ('track_cycling', 'Трековый велосипед', 40),
    ('running', 'Бег', 50),
    ('swimming', 'Заплыв', 60),
    ('walking', 'Ходьба', 70),
    ('skiing', 'Лыжи', 80),
    ('rowing', 'Гребля', 90),
)


def seed_types(apps, schema_editor):
    ActivityType = apps.get_model('activities', 'ActivityType')
    for slug, name, sort_order in STANDARD_TYPES:
        obj = ActivityType.objects.filter(name=name).first()
        if obj is None:
            obj = ActivityType.objects.filter(slug=slug).first()
        if obj is None:
            ActivityType.objects.create(name=name, slug=slug, sort_order=sort_order)
            continue
        changed = False
        if obj.slug != slug:
            obj.slug = slug
            changed = True
        if obj.name != name:
            obj.name = name
            changed = True
        if obj.sort_order != sort_order:
            obj.sort_order = sort_order
            changed = True
        if changed:
            obj.save()


def unseed_types(apps, schema_editor):
    # Keep rows; only clear seed-managed slugs is risky. No-op reverse.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('activities', '0015_activitytype_slug_sort_order'),
    ]

    operations = [
        migrations.RunPython(seed_types, unseed_types),
    ]
