# Generated by Django 4.0.3 on 2022-03-13 19:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('activities', '0002_activity'),
    ]

    operations = [
        migrations.AddField(
            model_name='activity',
            name='track_file',
            field=models.FileField(blank=True, null=True, upload_to='activities', verbose_name='файл тренировки'),
        ),
    ]