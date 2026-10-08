from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('activities', '0012_activity_indoor_and_zone_timeline'),
    ]

    operations = [
        migrations.AddField(
            model_name='activity',
            name='map_preview',
            field=models.ImageField(
                blank=True, null=True, upload_to='activity_maps',
                verbose_name='превью карты',
            ),
        ),
    ]
