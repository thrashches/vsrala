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

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()
    follows = models.ManyToManyField('Profile', through='Follow',
                                     through_fields=('user', 'following'),
                                     verbose_name='подписки')


class Follow(models.Model):
    class Meta:
        verbose_name = 'подписка'
        verbose_name_plural = 'подписки'

    user = models.ForeignKey(Profile, on_delete=models.CASCADE,
                             verbose_name='кто подписался')
    following = models.ForeignKey(Profile, related_name='followers', on_delete=models.CASCADE,
                                  verbose_name='на кого подписался')

    def __str__(self):
        return f'{self.user.email} подписан на {self.following.email}'
