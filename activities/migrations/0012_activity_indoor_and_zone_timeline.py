from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('activities', '0011_activity_extended_metrics_and_profile_ftp'),
    ]

    operations = [
        migrations.AddField(
            model_name='activity',
            name='is_indoor',
            field=models.BooleanField(default=False, verbose_name='indoor'),
        ),
        migrations.AddField(
            model_name='activity',
            name='zone_stream',
            field=models.CharField(blank=True, default='', max_length=16, verbose_name='поток для таймлайна зон'),
        ),
        migrations.AddField(
            model_name='activity',
            name='zone_timeline',
            field=models.ImageField(blank=True, null=True, upload_to='activity_timelines', verbose_name='таймлайн зон'),
        ),
    ]
