from django.db import models


class ActivityMedia(models.Model):
    class Meta:
        verbose_name = 'фото с тренировки'
        verbose_name_plural = 'фото с тренировки'

    title = models.CharField(max_length=255, blank=True, null=True,
                             verbose_name='название изображения')
    description = models.TextField(max_length=2000, blank=True, null=True,
                                   verbose_name='описание изображения')
    image = models.ImageField(upload_to='pictures', verbose_name='файл изображения')
    activity = models.ForeignKey('activities.Activity', related_name='medias',
                                 on_delete=models.CASCADE,
                                 verbose_name='тренировка')

    def __str__(self):
        return self.image.path
