from datetime import datetime, timedelta

from django.test import Client, TestCase
from django.urls import reverse

from activities.comments import (
    can_delete_comment,
    can_edit_comment,
    comment_count_label,
    create_comment,
)
from activities.models import Activity, ActivityComment
from profiles.models import Profile


class CommentHelpersTest(TestCase):
    def test_count_label_plural(self):
        self.assertEqual(comment_count_label(0), '0 комментариев')
        self.assertEqual(comment_count_label(1), '1 комментарий')
        self.assertEqual(comment_count_label(2), '2 комментария')
        self.assertEqual(comment_count_label(5), '5 комментариев')
        self.assertEqual(comment_count_label(11), '11 комментариев')
        self.assertEqual(comment_count_label(21), '21 комментарий')


class ActivityCommentPermissionsTest(TestCase):
    def setUp(self):
        self.owner = Profile.objects.create_user(email='owner@example.com', password='testpass123')
        self.author = Profile.objects.create_user(email='author@example.com', password='testpass123')
        self.other = Profile.objects.create_user(email='other@example.com', password='testpass123')
        self.activity = Activity.objects.create(
            profile=self.owner,
            duration=timedelta(hours=1),
            distance=20,
            started_at=datetime.now(),
        )
        self.comment = ActivityComment.objects.create(
            activity=self.activity,
            profile=self.author,
            text='Привет',
        )

    def test_edit_only_author(self):
        self.assertTrue(can_edit_comment(self.comment, self.author))
        self.assertFalse(can_edit_comment(self.comment, self.owner))
        self.assertFalse(can_edit_comment(self.comment, self.other))

    def test_delete_author_or_owner(self):
        self.assertTrue(can_delete_comment(self.comment, self.author))
        self.assertTrue(can_delete_comment(self.comment, self.owner))
        self.assertFalse(can_delete_comment(self.comment, self.other))

    def test_create_comment_strips_text(self):
        comment = create_comment(self.activity, self.author, '  текст  ')
        self.assertEqual(comment.text, 'текст')


class ActivityCommentViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = Profile.objects.create_user(
            email='owner@example.com', password='testpass123', is_public=True,
        )
        self.author = Profile.objects.create_user(email='author@example.com', password='testpass123')
        self.other = Profile.objects.create_user(email='other@example.com', password='testpass123')
        self.private_owner = Profile.objects.create_user(
            email='private@example.com', password='testpass123', is_public=False,
        )
        self.activity = Activity.objects.create(
            profile=self.owner,
            duration=timedelta(hours=1),
            distance=20,
            started_at=datetime.now(),
            title='Публичная',
        )
        self.private_activity = Activity.objects.create(
            profile=self.private_owner,
            duration=timedelta(hours=1),
            distance=10,
            started_at=datetime.now(),
            title='Приватная',
        )

    def test_create_comment(self):
        self.client.login(email='author@example.com', password='testpass123')
        url = reverse('webinterface:activity_comment_create', kwargs={'pk': self.activity.pk})
        response = self.client.post(url, {'text': 'Отличная тренировка'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['comment']['text'], 'Отличная тренировка')
        self.assertEqual(data['comment_count'], 1)
        self.assertTrue(
            ActivityComment.objects.filter(activity=self.activity, profile=self.author).exists()
        )

    def test_edit_own_comment(self):
        comment = ActivityComment.objects.create(
            activity=self.activity, profile=self.author, text='Старый',
        )
        self.client.login(email='author@example.com', password='testpass123')
        url = reverse(
            'webinterface:activity_comment_action',
            kwargs={'pk': self.activity.pk, 'comment_id': comment.pk},
        )
        response = self.client.post(url, {'action': 'edit', 'text': 'Новый'})
        self.assertEqual(response.status_code, 200)
        comment.refresh_from_db()
        self.assertEqual(comment.text, 'Новый')

    def test_edit_forbidden_for_non_author(self):
        comment = ActivityComment.objects.create(
            activity=self.activity, profile=self.author, text='Старый',
        )
        self.client.login(email='owner@example.com', password='testpass123')
        url = reverse(
            'webinterface:activity_comment_action',
            kwargs={'pk': self.activity.pk, 'comment_id': comment.pk},
        )
        response = self.client.post(url, {'action': 'edit', 'text': 'Хак'})
        self.assertEqual(response.status_code, 403)
        comment.refresh_from_db()
        self.assertEqual(comment.text, 'Старый')

    def test_delete_by_author(self):
        comment = ActivityComment.objects.create(
            activity=self.activity, profile=self.author, text='Удалить',
        )
        self.client.login(email='author@example.com', password='testpass123')
        url = reverse(
            'webinterface:activity_comment_action',
            kwargs={'pk': self.activity.pk, 'comment_id': comment.pk},
        )
        response = self.client.post(url, {'action': 'delete'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ActivityComment.objects.filter(pk=comment.pk).exists())

    def test_delete_by_activity_owner(self):
        comment = ActivityComment.objects.create(
            activity=self.activity, profile=self.author, text='Удалить',
        )
        self.client.login(email='owner@example.com', password='testpass123')
        url = reverse(
            'webinterface:activity_comment_action',
            kwargs={'pk': self.activity.pk, 'comment_id': comment.pk},
        )
        response = self.client.post(url, {'action': 'delete'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ActivityComment.objects.filter(pk=comment.pk).exists())

    def test_delete_forbidden_for_other(self):
        comment = ActivityComment.objects.create(
            activity=self.activity, profile=self.author, text='Оставить',
        )
        self.client.login(email='other@example.com', password='testpass123')
        url = reverse(
            'webinterface:activity_comment_action',
            kwargs={'pk': self.activity.pk, 'comment_id': comment.pk},
        )
        response = self.client.post(url, {'action': 'delete'})
        self.assertEqual(response.status_code, 403)
        self.assertTrue(ActivityComment.objects.filter(pk=comment.pk).exists())

    def test_private_activity_comment_404(self):
        self.client.login(email='other@example.com', password='testpass123')
        url = reverse(
            'webinterface:activity_comment_create',
            kwargs={'pk': self.private_activity.pk},
        )
        response = self.client.post(url, {'text': 'Нельзя'})
        self.assertEqual(response.status_code, 404)

    def test_feed_shows_comment_count(self):
        ActivityComment.objects.create(
            activity=self.activity, profile=self.author, text='Раз',
        )
        ActivityComment.objects.create(
            activity=self.activity, profile=self.owner, text='Два',
        )
        self.client.login(email='author@example.com', password='testpass123')
        response = self.client.get(reverse('webinterface:feed'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'activity-comments-btn')
        self.assertContains(response, 'aria-label="2 комментария"')
        self.assertNotContains(response, 'Подробнее')

    def test_detail_shows_comments(self):
        ActivityComment.objects.create(
            activity=self.activity, profile=self.author, text='Текст комментария',
        )
        self.client.login(email='author@example.com', password='testpass123')
        url = reverse('webinterface:activity_detail', kwargs={'pk': self.activity.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Текст комментария')
        self.assertContains(response, 'id="comments"')
