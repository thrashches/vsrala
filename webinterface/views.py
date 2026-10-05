import json

from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView
from django.views.generic.list import ListView

from activities.comments import (
    COMMENT_TEXT_MAX_LENGTH,
    can_delete_comment,
    can_edit_comment,
    comment_count_label,
    create_comment,
    serialize_comment,
    update_comment,
)
from activities.forms import ActivityUploadForm
from activities.leaderboard import VALID_METRICS, VALID_WEEKS, weekly_leaders
from activities.models import Activity, ActivityComment, ActivityReaction, ActivityType
from activities.parsers import TrackParseError, parse_track
from activities.reactions import reaction_summary_for_activities, toggle_reaction
from activities.year_stats import build_year_stats
from integrations.forms import IntervalsConnectForm
from integrations.intervals_client import IntervalsApiError
from integrations.models import IntervalsConnection
from integrations.sync import connect_profile, disconnect_profile
from integrations.tasks import sync_connection
from profiles.forms import DeleteAccountForm, PasswordChangeForm, ProfileSettingsForm
from profiles.models import Follow, FollowRequest, Profile


def _weekly_leaders_context(user):
    return {
        'activity_types': ActivityType.objects.order_by('name'),
        'weekly_leaders': weekly_leaders(user, metric='distance', week='current'),
        'weekly_leaders_api_url': reverse('webinterface:weekly_leaders_api'),
    }


def _user_can_view_activity(user, activity):
    if activity.profile_id == user.pk:
        return True
    if activity.profile.is_public:
        return True
    return user.follows.filter(pk=activity.profile_id).exists()


def _attach_reactions(activities, user):
    activity_list = list(activities)
    summaries = reaction_summary_for_activities(
        [a.pk for a in activity_list],
        user,
    )
    for activity in activity_list:
        summary = summaries.get(activity.pk, {'counts': [], 'mine': None})
        activity.reaction_counts = summary['counts']
        activity.my_reaction = summary['mine']
    return activity_list


def _reaction_choices():
    return ActivityReaction.EMOJI_CHOICES


def _attach_comment_counts(activities):
    activity_list = list(activities)
    ids = [a.pk for a in activity_list]
    counts = {}
    if ids:
        counts = dict(
            ActivityComment.objects.filter(activity_id__in=ids)
            .values('activity_id')
            .annotate(c=Count('id'))
            .values_list('activity_id', 'c')
        )
    for activity in activity_list:
        count = counts.get(activity.pk, 0)
        activity.comment_count = count
        activity.comment_count_label = comment_count_label(count)
    return activity_list


def _parse_comment_payload(request):
    text = (request.POST.get('text') or '').strip()
    action = (request.POST.get('action') or '').strip()
    if (not text or not action) and request.content_type and 'application/json' in request.content_type:
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}
        if not text:
            text = (payload.get('text') or '').strip()
        if not action:
            action = (payload.get('action') or '').strip()
    return text, action


class FeedView(LoginRequiredMixin, ListView):
    model = Activity
    template_name = 'feed/index.html'
    paginate_by = 50
    context_object_name = 'activities'

    def get_queryset(self):
        user = self.request.user
        follows = user.follows.all()
        return (
            Activity.objects.filter(
                Q(profile=user) | Q(profile__in=follows)
            )
            .select_related('profile', 'activity_type')
            .prefetch_related('medias')
            .order_by('-started_at')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        activities = _attach_reactions(context['activities'], self.request.user)
        context['activities'] = _attach_comment_counts(activities)
        context['reaction_choices'] = _reaction_choices()
        context.update(_weekly_leaders_context(self.request.user))
        return context


class MyActivitiesView(LoginRequiredMixin, ListView):
    model = Activity
    template_name = 'feed/index.html'
    paginate_by = 50
    context_object_name = 'activities'

    def get_queryset(self):
        return (
            Activity.objects.filter(profile=self.request.user)
            .select_related('profile', 'activity_type')
            .prefetch_related('medias')
            .order_by('-started_at')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        activities = _attach_reactions(context['activities'], self.request.user)
        context['activities'] = _attach_comment_counts(activities)
        context['reaction_choices'] = _reaction_choices()
        context.update(_weekly_leaders_context(self.request.user))
        return context


class WeeklyLeadersApiView(LoginRequiredMixin, View):
    def get(self, request):
        metric = request.GET.get('metric', 'distance')
        week = request.GET.get('week', 'current')
        if metric not in VALID_METRICS or week not in VALID_WEEKS:
            return HttpResponseBadRequest('Invalid metric or week')

        sport_raw = request.GET.get('sport', '').strip()
        sport_id = None
        if sport_raw:
            try:
                sport_id = int(sport_raw)
            except ValueError:
                return HttpResponseBadRequest('Invalid sport')
            if not ActivityType.objects.filter(pk=sport_id).exists():
                return HttpResponseBadRequest('Unknown sport')

        payload = weekly_leaders(
            request.user,
            sport_id=sport_id,
            metric=metric,
            week=week,
        )
        return JsonResponse(payload)


class ActivityDetailView(LoginRequiredMixin, DetailView):
    model = Activity
    template_name = 'activities/detail.html'
    context_object_name = 'activity'

    def get_queryset(self):
        return (
            Activity.objects.select_related('profile', 'activity_type')
            .prefetch_related('medias', 'comments__profile')
        )

    def get_object(self, queryset=None):
        activity = super().get_object(queryset)
        if not _user_can_view_activity(self.request.user, activity):
            raise Http404
        return activity

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        points = self.object.track_points or []
        context['track_points_json'] = json.dumps(points)
        context['streams_json'] = json.dumps(self.object.streams or {})
        _attach_reactions([self.object], self.request.user)
        context['reaction_choices'] = _reaction_choices()
        comments = list(self.object.comments.select_related('profile').all())
        for comment in comments:
            comment.can_edit = can_edit_comment(comment, self.request.user)
            comment.can_delete = can_delete_comment(comment, self.request.user)
        context['comments'] = comments
        context['comment_text_max_length'] = COMMENT_TEXT_MAX_LENGTH
        return context


class ActivityReactView(LoginRequiredMixin, View):
    def post(self, request, pk):
        activity = get_object_or_404(
            Activity.objects.select_related('profile'),
            pk=pk,
        )
        if not _user_can_view_activity(request.user, activity):
            raise Http404

        emoji = (request.POST.get('emoji') or '').strip()
        if not emoji and request.content_type and 'application/json' in request.content_type:
            try:
                payload = json.loads(request.body.decode('utf-8') or '{}')
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = {}
            emoji = (payload.get('emoji') or '').strip()

        if emoji not in ActivityReaction.ALLOWED_EMOJIS:
            return JsonResponse({'error': 'Некорректная реакция'}, status=400)

        try:
            summary = toggle_reaction(activity, request.user, emoji)
        except ValueError:
            return JsonResponse({'error': 'Некорректная реакция'}, status=400)

        return JsonResponse({
            'counts': summary['counts'],
            'mine': summary['mine'],
        })


class ActivityCommentCreateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        activity = get_object_or_404(
            Activity.objects.select_related('profile'),
            pk=pk,
        )
        if not _user_can_view_activity(request.user, activity):
            raise Http404

        text, _action = _parse_comment_payload(request)
        try:
            comment = create_comment(activity, request.user, text)
        except ValueError as exc:
            if str(exc) == 'too_long':
                return JsonResponse({'error': 'Слишком длинный комментарий'}, status=400)
            return JsonResponse({'error': 'Введите текст комментария'}, status=400)

        return JsonResponse({
            'comment': serialize_comment(comment, request.user),
            'comment_count': activity.comments.count(),
            'comment_count_label': comment_count_label(activity.comments.count()),
        })


class ActivityCommentActionView(LoginRequiredMixin, View):
    def post(self, request, pk, comment_id):
        activity = get_object_or_404(
            Activity.objects.select_related('profile'),
            pk=pk,
        )
        if not _user_can_view_activity(request.user, activity):
            raise Http404

        comment = get_object_or_404(
            ActivityComment.objects.select_related('profile', 'activity'),
            pk=comment_id,
            activity=activity,
        )
        text, action = _parse_comment_payload(request)
        if action == 'edit':
            if not can_edit_comment(comment, request.user):
                return JsonResponse({'error': 'Недостаточно прав'}, status=403)
            try:
                update_comment(comment, text)
            except ValueError as exc:
                if str(exc) == 'too_long':
                    return JsonResponse({'error': 'Слишком длинный комментарий'}, status=400)
                return JsonResponse({'error': 'Введите текст комментария'}, status=400)
            return JsonResponse({
                'comment': serialize_comment(comment, request.user),
                'comment_count': activity.comments.count(),
                'comment_count_label': comment_count_label(activity.comments.count()),
            })

        if action == 'delete':
            if not can_delete_comment(comment, request.user):
                return JsonResponse({'error': 'Недостаточно прав'}, status=403)
            comment.delete()
            count = activity.comments.count()
            return JsonResponse({
                'deleted': True,
                'id': comment_id,
                'comment_count': count,
                'comment_count_label': comment_count_label(count),
            })

        return JsonResponse({'error': 'Некорректное действие'}, status=400)


class ProfileSettingsView(LoginRequiredMixin, View):
    template_name = 'settings/index.html'

    def get(self, request):
        return render(request, self.template_name, self._context(request))

    def post(self, request):
        action = request.POST.get('action', 'profile')
        profile_form = ProfileSettingsForm(
            instance=request.user,
            data=request.POST if action == 'profile' else None,
            files=request.FILES if action == 'profile' else None,
        )
        password_form = PasswordChangeForm(
            user=request.user,
            data=request.POST if action == 'password' else None,
        )
        delete_form = DeleteAccountForm(
            user=request.user,
            data=request.POST if action == 'delete' else None,
        )
        intervals_form = IntervalsConnectForm(
            data=request.POST if action == 'intervals_connect' else None,
        )

        if action == 'profile':
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Настройки сохранены')
                return redirect('webinterface:settings')
            password_form = PasswordChangeForm(user=request.user)
            delete_form = DeleteAccountForm(user=request.user)
            intervals_form = IntervalsConnectForm()
        elif action == 'password':
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                messages.success(request, 'Пароль изменён')
                return redirect('webinterface:settings')
            profile_form = ProfileSettingsForm(instance=request.user)
            delete_form = DeleteAccountForm(user=request.user)
            intervals_form = IntervalsConnectForm()
        elif action == 'delete':
            if delete_form.is_valid():
                user = request.user
                logout(request)
                user.delete()
                messages.success(request, 'Профиль удалён')
                return redirect('webinterface:login')
            profile_form = ProfileSettingsForm(instance=request.user)
            password_form = PasswordChangeForm(user=request.user)
            intervals_form = IntervalsConnectForm()
        elif action == 'intervals_connect':
            if intervals_form.is_valid():
                try:
                    connection = connect_profile(
                        request.user,
                        intervals_form.cleaned_data['api_key'],
                    )
                except IntervalsApiError as exc:
                    intervals_form.add_error(None, f'Не удалось подключиться: {exc}')
                else:
                    try:
                        sync_connection.delay(connection.pk, initial=True)
                    except Exception:
                        messages.warning(
                            request,
                            'Intervals.icu подключён, но очередь синхронизации недоступна. '
                            'Запустите Redis и Celery worker.',
                        )
                        return redirect('webinterface:settings')
                    messages.success(
                        request,
                        'Intervals.icu подключён. Начата загрузка тренировок за последние 6 месяцев.',
                    )
                    return redirect('webinterface:settings')
            profile_form = ProfileSettingsForm(instance=request.user)
            password_form = PasswordChangeForm(user=request.user)
            delete_form = DeleteAccountForm(user=request.user)
        elif action == 'intervals_disconnect':
            disconnect_profile(request.user)
            messages.success(request, 'Intervals.icu отключён')
            return redirect('webinterface:settings')
        else:
            return redirect('webinterface:settings')

        return render(request, self.template_name, {
            'profile_form': profile_form,
            'password_form': password_form,
            'delete_form': delete_form,
            'intervals_form': intervals_form,
            'intervals_connection': self._intervals_connection(request.user),
            'active_action': action,
        })

    def _intervals_connection(self, user):
        try:
            return user.intervals_connection
        except IntervalsConnection.DoesNotExist:
            return None

    def _context(self, request):
        return {
            'profile_form': ProfileSettingsForm(instance=request.user),
            'password_form': PasswordChangeForm(user=request.user),
            'delete_form': DeleteAccountForm(user=request.user),
            'intervals_form': IntervalsConnectForm(),
            'intervals_connection': self._intervals_connection(request.user),
            'active_action': None,
        }


class ActivityUploadView(LoginRequiredMixin, CreateView):
    model = Activity
    form_class = ActivityUploadForm
    template_name = 'activities/upload.html'

    def form_valid(self, form):
        from datetime import datetime, timezone
        from io import BytesIO

        from django.core.files.base import ContentFile

        activity = form.save(commit=False)
        activity.profile = self.request.user
        track_file = form.cleaned_data['track_file']
        filename = track_file.name

        # Read bytes once: FitFile closes the underlying handle, so we cannot
        # seek/reuse the uploaded file after parsing.
        track_file.seek(0)
        file_bytes = track_file.read()

        # Need a temporary started_at before first save.
        activity.started_at = datetime.now(timezone.utc)

        try:
            parsed = parse_track(BytesIO(file_bytes), filename=filename)
        except TrackParseError as exc:
            form.add_error('track_file', str(exc))
            return self.form_invalid(form)

        activity.apply_parsed_track(parsed)
        activity.track_file = ContentFile(file_bytes, name=filename)
        activity.save()
        from activities.zone_timeline import apply_zone_timeline
        apply_zone_timeline(activity)
        self.object = activity
        messages.success(self.request, 'Тренировка загружена')
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse('webinterface:activity_detail', kwargs={'pk': self.object.pk})


def _profile_photo_url(profile):
    if profile.photo:
        return profile.photo.url
    return None


def _visible_activities_for(viewer, owner):
    qs = (
        Activity.objects.filter(profile=owner)
        .select_related('profile', 'activity_type')
        .prefetch_related('medias')
    )
    if owner.pk == viewer.pk or owner.is_public:
        return qs
    if viewer.follows.filter(pk=owner.pk).exists():
        return qs
    return qs.none()


def _annotate_following(viewer, profiles):
    profile_ids = [p.pk for p in profiles]
    following_ids = set(
        viewer.follows.filter(pk__in=profile_ids).values_list('pk', flat=True)
    )
    pending_ids = set(
        FollowRequest.objects.filter(
            from_user=viewer, to_user_id__in=profile_ids,
        ).values_list('to_user_id', flat=True)
    )
    for profile in profiles:
        profile.is_following = profile.pk in following_ids
        profile.request_pending = profile.pk in pending_ids
    return profiles


class PeopleSearchView(LoginRequiredMixin, View):
    template_name = 'people/search.html'

    def get(self, request):
        return render(request, self.template_name)


class PeopleSearchApiView(LoginRequiredMixin, View):
    def get(self, request):
        q = (request.GET.get('q') or '').strip()
        if not q:
            return JsonResponse({'results': []})

        profiles = list(
            Profile.objects.filter(
                Q(first_name__icontains=q) | Q(email__icontains=q)
            )
            .exclude(pk=request.user.pk)
            .order_by('first_name', 'email')[:20]
        )
        _annotate_following(request.user, profiles)
        results = [
            {
                'id': p.pk,
                'display_name': p.display_name,
                'photo_url': _profile_photo_url(p),
                'is_following': p.is_following,
                'request_pending': p.request_pending,
                'is_public': p.is_public,
                'profile_url': reverse('webinterface:profile_detail', kwargs={'pk': p.pk}),
                'follow_url': reverse('webinterface:profile_follow', kwargs={'pk': p.pk}),
            }
            for p in profiles
        ]
        return JsonResponse({'results': results})


class ProfileDetailView(LoginRequiredMixin, DetailView):
    model = Profile
    template_name = 'people/profile.html'
    context_object_name = 'profile'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.object
        viewer = self.request.user
        context['is_own_profile'] = profile.pk == viewer.pk
        if context['is_own_profile']:
            profile.is_following = False
            profile.request_pending = False
        else:
            profile.is_following = viewer.follows.filter(pk=profile.pk).exists()
            profile.request_pending = FollowRequest.objects.filter(
                from_user=viewer, to_user=profile,
            ).exists()
        context['is_following'] = profile.is_following
        context['request_pending'] = profile.request_pending
        context['following_count'] = profile.follows.count()
        context['followers_count'] = profile.followers.count()
        visible = _visible_activities_for(viewer, profile)
        context['activities'] = visible[:50]
        can_see_activities = (
            context['is_own_profile']
            or profile.is_public
            or context['is_following']
        )
        if can_see_activities:
            year_stats = build_year_stats(visible)
            year_stats['selected'] = year_stats['by_year'][year_stats['selected_year']]
            # JSON keys must be strings for the client-side year switcher.
            by_year_json = {
                str(year): stats for year, stats in year_stats['by_year'].items()
            }
            context['year_stats'] = year_stats
            context['year_stats_json'] = json.dumps(by_year_json, ensure_ascii=False)
        else:
            context['year_stats'] = None
        return context


class ProfileFollowingView(LoginRequiredMixin, ListView):
    template_name = 'people/list.html'
    context_object_name = 'profiles'
    paginate_by = 50

    def dispatch(self, request, *args, **kwargs):
        self.profile = get_object_or_404(Profile, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return self.profile.follows.all().order_by('first_name', 'email')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profiles = list(context['profiles'])
        _annotate_following(self.request.user, profiles)
        context['profiles'] = profiles
        context['profile'] = self.profile
        context['list_title'] = 'Подписки'
        context['list_kind'] = 'following'
        return context


class ProfileFollowersView(LoginRequiredMixin, ListView):
    template_name = 'people/list.html'
    context_object_name = 'profiles'
    paginate_by = 50

    def dispatch(self, request, *args, **kwargs):
        self.profile = get_object_or_404(Profile, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Profile.objects.filter(
            pk__in=self.profile.followers.values_list('user_id', flat=True)
        ).order_by('first_name', 'email')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profiles = list(context['profiles'])
        _annotate_following(self.request.user, profiles)
        context['profiles'] = profiles
        context['profile'] = self.profile
        context['list_title'] = 'Подписчики'
        context['list_kind'] = 'followers'
        return context


class ProfileFollowToggleView(LoginRequiredMixin, View):
    def post(self, request, pk):
        target = get_object_or_404(Profile, pk=pk)
        if target.pk == request.user.pk:
            if self._wants_json(request):
                return JsonResponse({'error': 'Нельзя подписаться на себя'}, status=400)
            return HttpResponseBadRequest('Нельзя подписаться на себя')

        follow = Follow.objects.filter(user=request.user, following=target).first()
        pending = FollowRequest.objects.filter(from_user=request.user, to_user=target).first()
        is_following = False
        request_pending = False

        if follow:
            follow.delete()
            if pending:
                pending.delete()
        elif pending:
            pending.delete()
        else:
            they_follow_me = Follow.objects.filter(
                user=target, following=request.user,
            ).exists()
            if target.is_public or they_follow_me:
                Follow.objects.create(user=request.user, following=target)
                is_following = True
            else:
                FollowRequest.objects.create(from_user=request.user, to_user=target)
                request_pending = True

        if self._wants_json(request):
            return JsonResponse({
                'is_following': is_following,
                'request_pending': request_pending,
                'followers_count': target.followers.count(),
            })

        next_url = request.POST.get('next') or reverse(
            'webinterface:profile_detail', kwargs={'pk': target.pk}
        )
        return redirect(next_url)

    def _wants_json(self, request):
        accept = request.headers.get('Accept', '')
        return 'application/json' in accept or request.headers.get('X-Requested-With') == 'XMLHttpRequest'


class FollowRequestsView(LoginRequiredMixin, ListView):
    template_name = 'people/follow_requests.html'
    context_object_name = 'follow_requests'
    paginate_by = 50

    def get_queryset(self):
        return (
            FollowRequest.objects.filter(to_user=self.request.user)
            .select_related('from_user')
            .order_by('-created_at')
        )


class FollowRequestActionView(LoginRequiredMixin, View):
    def post(self, request, pk, action):
        follow_request = get_object_or_404(
            FollowRequest, pk=pk, to_user=request.user,
        )
        if action == 'accept':
            Follow.objects.get_or_create(
                user=follow_request.from_user,
                following=follow_request.to_user,
            )
            follow_request.delete()
        elif action == 'reject':
            follow_request.delete()
        else:
            return HttpResponseBadRequest('Неизвестное действие')

        next_url = request.POST.get('next') or reverse('webinterface:follow_requests')
        return redirect(next_url)
