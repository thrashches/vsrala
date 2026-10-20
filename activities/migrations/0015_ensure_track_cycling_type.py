from django.db import migrations


TRACK_CYCLING_TYPE_NAME = 'Трековый велосипед'


def ensure_track_cycling_type(apps, schema_editor):
    ActivityType = apps.get_model('activities', 'ActivityType')
    ActivityType.objects.get_or_create(name=TRACK_CYCLING_TYPE_NAME)


def noop_reverse(apps, schema_editor):
    # Keep the type: existing activities may reference it.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('activities', '0014_track_training_fields'),
    ]

    operations = [
        migrations.RunPython(ensure_track_cycling_type, noop_reverse),
    ]
