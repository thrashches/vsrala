from django.test import TestCase
from profiles.models import Profile
from activities.models import ActivityType, Activity
from datetime import timedelta, datetime


class ActivityModelTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.profile = Profile.objects.create(email='test@mail.ru')
        activity_types = [
            ActivityType(name='Шоссейный велосипед'),
            ActivityType(name='Горный велосипед'),
            ActivityType(name='Трековый велосипед'),
            ActivityType(name='Кроссовый велосипед'),
            ActivityType(name='Бег'),
            ActivityType(name='Заплыв'),
        ]
        cls.activity_types = ActivityType.objects.bulk_create(activity_types)

    def test_create_activity_model(self):
        activity_type = self.activity_types[0]
        Activity.objects.create(
            profile=self.profile,
            duration=timedelta(hours=2),
            activity_type=activity_type,
            distance=50.05,
            started_at=datetime.now()
        )
        activities = Activity.objects.all()
        assert activities.count() == 1, 'Не удалось создать тренировку!'
