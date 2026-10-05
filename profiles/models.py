from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """Define a model manager for User model with no username field."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """Create and save a User with the given email and password."""
        if not email:
            raise ValueError('The given email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular User with the given email and password."""
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class Profile(AbstractUser):
    username = None
    email = models.EmailField(_('email address'), unique=True)
    photo = models.ImageField(upload_to='pictures', blank=True, null=True, verbose_name='фото профиля')
    telegram = models.CharField(max_length=255, blank=True, verbose_name='Telegram')
    instagram = models.CharField(max_length=255, blank=True, verbose_name='Instagram')
    vk = models.CharField(max_length=255, blank=True, verbose_name='VK')
    is_public = models.BooleanField(default=True, verbose_name='открытый профиль')
    ftp = models.PositiveIntegerField(blank=True, null=True, verbose_name='FTP')
    max_heart_rate = models.PositiveIntegerField(
        blank=True, null=True, verbose_name='максимальный пульс',
    )
    hr_zones = models.JSONField(blank=True, null=True, default=list, verbose_name='зоны пульса')
    power_zones = models.JSONField(blank=True, null=True, default=list, verbose_name='зоны мощности')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()
    follows = models.ManyToManyField('Profile', through='Follow',
                                     through_fields=('user', 'following'),
                                     verbose_name='подписки')

    @property
    def display_name(self):
        return (self.first_name or '').strip() or self.email


class Follow(models.Model):
    class Meta:
        verbose_name = 'подписка'
        verbose_name_plural = 'подписки'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'following'],
                name='profiles_follow_user_following_uniq',
            ),
        ]

    user = models.ForeignKey(Profile, on_delete=models.CASCADE,
                             verbose_name='кто подписался')
    following = models.ForeignKey(Profile, related_name='followers', on_delete=models.CASCADE,
                                  verbose_name='на кого подписался')

    def clean(self):
        if self.user_id and self.following_id and self.user_id == self.following_id:
            raise ValidationError('Нельзя подписаться на себя')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.user.email} подписан на {self.following.email}'


class FollowRequest(models.Model):
    class Meta:
        verbose_name = 'запрос на подписку'
        verbose_name_plural = 'запросы на подписку'
        constraints = [
            models.UniqueConstraint(
                fields=['from_user', 'to_user'],
                name='profiles_followrequest_from_to_uniq',
            ),
        ]

    from_user = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='outgoing_follow_requests',
        verbose_name='кто запросил',
    )
    to_user = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='incoming_follow_requests',
        verbose_name='кому запрос',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='создан')

    def clean(self):
        if self.from_user_id and self.to_user_id and self.from_user_id == self.to_user_id:
            raise ValidationError('Нельзя отправить запрос самому себе')
        if (
            self.from_user_id
            and self.to_user_id
            and Follow.objects.filter(user_id=self.from_user_id, following_id=self.to_user_id).exists()
        ):
            raise ValidationError('Подписка уже существует')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.from_user.email} → {self.to_user.email}'
