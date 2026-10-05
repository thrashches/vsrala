from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0007_activity_extended_metrics_and_profile_ftp'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='max_heart_rate',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='максимальный пульс'),
        ),
        migrations.AddField(
            model_name='profile',
            name='hr_zones',
            field=models.JSONField(blank=True, default=list, null=True, verbose_name='зоны пульса'),
        ),
        migrations.AddField(
            model_name='profile',
            name='power_zones',
            field=models.JSONField(blank=True, default=list, null=True, verbose_name='зоны мощности'),
        ),
    ]
