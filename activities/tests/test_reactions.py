from datetime import datetime, timedelta

from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse

from activities.models import Activity, ActivityReaction
from activities.reactions import reaction_summary_for_activities, toggle_reaction
from profiles.models import Follow, Profile


class ActivityReactionModelTest(TestCase):
    def setUp(self):
        self.owner = Profile.objects.create_user(email='owner@example.com', password='testpass123')
        self.user = Profile.objects.create_user(email='user@example.com', password='testpass123')
        self.activity = Activity.objects.create(
            profile=self.owner,
            duration=timedelta(hours=1),
            distance=20,
            started_at=datetime.now(),
        )

    def test_unique_per_user_activity(self):
        ActivityReaction.objects.create(
            activity=self.activity,
            profile=self.user,
            emoji=ActivityReaction.EMOJI_LIKE,
        )
        with self.assertRaises(IntegrityError):
            ActivityReaction.objects.create(
                activity=self.activity,
                profile=self.user,
                emoji=ActivityReaction.EMOJI_FIRE,
            )


class ActivityReactionToggleTest(TestCase):
    def setUp(self):
        self.owner = Profile.objects.create_user(email='owner@example.com', password='testpass123')
        self.user = Profile.objects.create_user(email='user@example.com', password='testpass123')
        self.other = Profile.objects.create_user(email='other@example.com', password='testpass123')
        self.activity = Activity.objects.create(
            profile=self.owner,
            duration=timedelta(hours=1),
            distance=20,
            started_at=datetime.now(),
        )

    def test_set_change_and_remove(self):
        summary = toggle_reaction(self.activity, self.user, ActivityReaction.EMOJI_LIKE)
        self.assertEqual(summary['mine'], ActivityReaction.EMOJI_LIKE)
        self.assertEqual(summary['counts'], [{'emoji': ActivityReaction.EMOJI_LIKE, 'count': 1}])

        summary = toggle_reaction(self.activity, self.user, ActivityReaction.EMOJI_FIRE)
        self.assertEqual(summary['mine'], ActivityReaction.EMOJI_FIRE)
        self.assertEqual(ActivityReaction.objects.filter(activity=self.activity).count(), 1)
        self.assertEqual(summary['counts'], [{'emoji': ActivityReaction.EMOJI_FIRE, 'count': 1}])

        summary = toggle_reaction(self.activity, self.user, ActivityReaction.EMOJI_FIRE)
        self.assertIsNone(summary['mine'])
        self.assertEqual(summary['counts'], [])
        self.assertEqual(ActivityReaction.objects.filter(activity=self.activity).count(), 0)

    def test_aggregation(self):
        toggle_reaction(self.activity, self.user, ActivityReaction.EMOJI_HEART)
        toggle_reaction(self.activity, self.other, ActivityReaction.EMOJI_HEART)
        toggle_reaction(self.activity, self.owner, ActivityReaction.EMOJI_CLAP)

        summary = reaction_summary_for_activities([self.activity.pk], self.user)[self.activity.pk]
        self.assertEqual(summary['mine'], ActivityReaction.EMOJI_HEART)
        counts = {item['emoji']: item['count'] for item in summary['counts']}
        self.assertEqual(counts[ActivityReaction.EMOJI_HEART], 2)
        self.assertEqual(counts[ActivityReaction.EMOJI_CLAP], 1)


class ActivityReactViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.public_owner = Profile.objects.create_user(
            email='public@example.com', password='testpass123', is_public=True,
        )
        self.private_owner = Profile.objects.create_user(
            email='private@example.com', password='testpass123', is_public=False,
        )
        self.user = Profile.objects.create_user(email='user@example.com', password='testpass123')
        self.stranger = Profile.objects.create_user(email='stranger@example.com', password='testpass123')
        self.public_activity = Activity.objects.create(
            profile=self.public_owner,
            duration=timedelta(hours=1),
            distance=20,
            started_at=datetime.now(),
        )
        self.private_activity = Activity.objects.create(
            profile=self.private_owner,
            title='Приватная',
            duration=timedelta(hours=1),
            distance=10,
            started_at=datetime.now(),
        )

    def _react(self, activity, emoji):
        return self.client.post(
            reverse('webinterface:activity_react', kwargs={'pk': activity.pk}),
            {'emoji': emoji},
            HTTP_ACCEPT='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def test_react_toggle_via_api(self):
        self.client.login(email='user@example.com', password='testpass123')

        response = self._react(self.public_activity, ActivityReaction.EMOJI_BANANA)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['mine'], ActivityReaction.EMOJI_BANANA)
        self.assertEqual(data['counts'][0]['count'], 1)

        response = self._react(self.public_activity, ActivityReaction.EMOJI_BANANA)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data['mine'])
        self.assertEqual(data['counts'], [])

    def test_private_activity_requires_follow(self):
        self.client.login(email='stranger@example.com', password='testpass123')
        response = self._react(self.private_activity, ActivityReaction.EMOJI_LIKE)
        self.assertEqual(response.status_code, 404)

        Follow.objects.create(user=self.stranger, following=self.private_owner)
        response = self._react(self.private_activity, ActivityReaction.EMOJI_LIKE)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['mine'], ActivityReaction.EMOJI_LIKE)

    def test_invalid_emoji(self):
        self.client.login(email='user@example.com', password='testpass123')
        response = self._react(self.public_activity, '🚀')
        self.assertEqual(response.status_code, 400)
