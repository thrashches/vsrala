from django.db.models import Count, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema

from activities.best_efforts import build_best_efforts
from activities.comments import (
    can_delete_comment,
    can_edit_comment,
    comment_count_label,
    create_comment,
    serialize_comment,
    update_comment,
)
from activities.leaderboard import VALID_METRICS, VALID_WEEKS, weekly_leaders
from activities.models import Activity, ActivityComment, ActivityType
from activities.reactions import reaction_summary_for_activities, toggle_reaction
from activities.year_stats import build_year_stats
from activities.zone_distribution import compute_zone_distribution, stream_has_data
from api.permissions import (
    CanViewActivity,
    CanViewRoute,
    IsActivityOwner,
    IsRouteOwner,
    user_can_view_activity,
    visible_activities_for,
)
from api.serializers import (
    ActivityDetailSerializer,
    ActivityListSerializer,
    ActivityUpdateSerializer,
    ActivityUploadSerializer,
    ApiKeySerializer,
    AuthTokenResponseSerializer,
    CommentActionResponseSerializer,
    CommentCreateSerializer,
    CommentUpdateSerializer,
    ConnectedSerializer,
    DeleteAccountSerializer,
    EmailAuthTokenSerializer,
    FollowRequestSerializer,
    FollowToggleResponseSerializer,
    GarminSyncZonesResponseSerializer,
    MeSerializer,
    PasswordChangeSerializer,
    ProfileDetailSerializer,
    ProfileSearchSerializer,
    ReactionSerializer,
    ReactionSummarySerializer,
    RouteDetailSerializer,
    RouteFromActivitySerializer,
    RouteListSerializer,
    RouteUpdateSerializer,
    RouteUploadSerializer,
    StatusSerializer,
)
from integrations import garmin_sync as garmin_sync_service
from integrations.garmin_client import GarminApiError
from integrations.intervals_client import IntervalsApiError
from integrations.models import GarminConnection
from integrations.sync import connect_profile, disconnect_profile
from integrations.tasks import sync_connection, sync_garmin_connection
from profiles.models import FollowRequest, Profile
from profiles.services import (
    accept_follow_request,
    reject_follow_request,
    toggle_follow,
)
from profiles.zones import resolve_hr_zones, resolve_power_zones
from routes.models import Route
from routes.services import route_gpx_stream
from django.core.exceptions import ValidationError as DjangoValidationError


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
        activity.comment_count = counts.get(activity.pk, 0)
    return activity_list


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


class ObtainAuthTokenView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=['auth'],
        request=EmailAuthTokenSerializer,
        responses={200: AuthTokenResponseSerializer},
        summary='Получить API-токен',
    )
    def post(self, request):
        serializer = EmailAuthTokenSerializer(
            data=request.data, context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'email': user.email,
            'display_name': user.display_name,
        })


class LogoutView(APIView):
    @extend_schema(
        tags=['auth'],
        request=None,
        responses={204: OpenApiResponse(description='Токен удалён')},
        summary='Удалить API-токен',
    )
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ActivityListCreateView(generics.ListCreateAPIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ActivityUploadSerializer
        return ActivityListSerializer

    def get_queryset(self):
        user = self.request.user
        scope = self.request.query_params.get('scope', 'feed')
        if scope == 'mine':
            qs = Activity.objects.filter(profile=user)
        else:
            follows = user.follows.all()
            qs = Activity.objects.filter(Q(profile=user) | Q(profile__in=follows))
        return (
            qs.select_related('profile', 'activity_type')
            .prefetch_related('medias')
            .defer('streams', 'track_points')
            .order_by('-started_at')
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        activities = page if page is not None else list(queryset)
        activities = _attach_comment_counts(_attach_reactions(activities, request.user))
        serializer = self.get_serializer(activities, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        activity = serializer.save()
        detail = ActivityDetailSerializer(
            activity, context=self._detail_context(activity),
        )
        return Response(detail.data, status=status.HTTP_201_CREATED)

    def _detail_context(self, activity):
        return _activity_detail_context(self.request, activity)


def _activity_detail_context(request, activity):
    streams = activity.streams or {}
    hr_zones = resolve_hr_zones(activity.profile)
    power_zones = resolve_power_zones(activity.profile)
    has_hr = stream_has_data(streams.get('hr'))
    has_power = stream_has_data(streams.get('power'))
    times = streams.get('time') or []
    _attach_reactions([activity], request.user)
    activity.comment_count = activity.comments.count()
    return {
        'request': request,
        'hr_zone_rows': (
            compute_zone_distribution(streams.get('hr') or [], times, hr_zones)
            if has_hr and hr_zones else []
        ),
        'power_zone_rows': (
            compute_zone_distribution(streams.get('power') or [], times, power_zones)
            if has_power and power_zones else []
        ),
        'best_efforts': build_best_efforts(activity),
        'has_hr_stream': has_hr,
        'has_power_stream': has_power,
        'hr_zones_configured': hr_zones is not None,
        'power_zones_configured': power_zones is not None,
    }


class ActivityDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Activity.objects.select_related('profile', 'activity_type').prefetch_related(
        'medias', 'comments__profile',
    )

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return ActivityUpdateSerializer
        return ActivityDetailSerializer

    def get_permissions(self):
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            return [IsAuthenticated(), IsActivityOwner()]
        return [IsAuthenticated(), CanViewActivity()]

    def get_object(self):
        obj = super().get_object()
        self.check_object_permissions(self.request, obj)
        return obj

    def retrieve(self, request, *args, **kwargs):
        activity = self.get_object()
        serializer = ActivityDetailSerializer(
            activity, context=_activity_detail_context(request, activity),
        )
        return Response(serializer.data)

    def perform_destroy(self, instance):
        instance.delete()


class ActivityDownloadView(APIView):
    permission_classes = [IsAuthenticated, IsActivityOwner]

    @extend_schema(
        tags=['activities'],
        summary='Скачать исходный файл тренировки',
        responses={(200, 'application/octet-stream'): OpenApiTypes.BINARY},
    )
    def get(self, request, pk):
        activity = get_object_or_404(Activity, pk=pk)
        if activity.profile_id != request.user.pk:
            raise NotFound()
        if not activity.track_file:
            raise NotFound()
        filename = activity.track_file.name.rsplit('/', 1)[-1] or 'activity.fit'
        return FileResponse(
            activity.track_file.open('rb'),
            as_attachment=True,
            filename=filename,
            content_type='application/octet-stream',
        )


class ActivityReactView(APIView):
    @extend_schema(
        tags=['activities'],
        request=ReactionSerializer,
        responses={200: ReactionSummarySerializer},
        summary='Поставить / снять реакцию',
    )
    def post(self, request, pk):
        activity = get_object_or_404(
            Activity.objects.select_related('profile'), pk=pk,
        )
        if not user_can_view_activity(request.user, activity):
            raise NotFound()
        serializer = ReactionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = toggle_reaction(activity, request.user, serializer.validated_data['emoji'])
        return Response(result)


class ActivityCommentListCreateView(APIView):
    @extend_schema(
        tags=['activities'],
        request=CommentCreateSerializer,
        responses={201: CommentActionResponseSerializer},
        summary='Добавить комментарий',
    )
    def post(self, request, pk):
        activity = get_object_or_404(
            Activity.objects.select_related('profile'), pk=pk,
        )
        if not user_can_view_activity(request.user, activity):
            raise NotFound()
        serializer = CommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = create_comment(activity, request.user, serializer.validated_data['text'])
        count = activity.comments.count()
        return Response({
            'comment': serialize_comment(comment, request.user),
            'comment_count': count,
            'comment_count_label': comment_count_label(count),
        }, status=status.HTTP_201_CREATED)


class ActivityCommentDetailView(APIView):
    @extend_schema(
        tags=['activities'],
        request=CommentUpdateSerializer,
        responses={200: CommentActionResponseSerializer},
        summary='Редактировать комментарий',
    )
    def patch(self, request, pk, comment_id):
        activity = get_object_or_404(
            Activity.objects.select_related('profile'), pk=pk,
        )
        if not user_can_view_activity(request.user, activity):
            raise NotFound()
        comment = get_object_or_404(ActivityComment, pk=comment_id, activity=activity)
        if not can_edit_comment(comment, request.user):
            raise PermissionDenied()
        serializer = CommentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = update_comment(comment, serializer.validated_data['text'])
        return Response({'comment': serialize_comment(comment, request.user)})

    @extend_schema(
        tags=['activities'],
        responses={200: CommentActionResponseSerializer},
        summary='Удалить комментарий',
    )
    def delete(self, request, pk, comment_id):
        activity = get_object_or_404(
            Activity.objects.select_related('profile'), pk=pk,
        )
        if not user_can_view_activity(request.user, activity):
            raise NotFound()
        comment = get_object_or_404(ActivityComment, pk=comment_id, activity=activity)
        if not can_delete_comment(comment, request.user):
            raise PermissionDenied()
        comment.delete()
        count = activity.comments.count()
        return Response({
            'id': comment_id,
            'comment_count': count,
            'comment_count_label': comment_count_label(count),
        })


class WeeklyLeadersView(APIView):
    @extend_schema(
        tags=['leaders'],
        parameters=[
            OpenApiParameter('metric', OpenApiTypes.STR, enum=list(VALID_METRICS)),
            OpenApiParameter('week', OpenApiTypes.STR, enum=list(VALID_WEEKS)),
            OpenApiParameter('sport', OpenApiTypes.INT, required=False),
        ],
        responses={200: OpenApiTypes.OBJECT},
        summary='Лидеры недели',
    )
    def get(self, request):
        metric = request.query_params.get('metric', 'distance')
        week = request.query_params.get('week', 'current')
        if metric not in VALID_METRICS or week not in VALID_WEEKS:
            raise ValidationError('Invalid metric or week')
        sport_raw = (request.query_params.get('sport') or '').strip()
        sport_id = None
        if sport_raw:
            try:
                sport_id = int(sport_raw)
            except ValueError as exc:
                raise ValidationError('Invalid sport') from exc
            if not ActivityType.objects.filter(pk=sport_id).exists():
                raise ValidationError('Unknown sport')
        return Response(weekly_leaders(
            request.user, sport_id=sport_id, metric=metric, week=week,
        ))


class PeopleSearchView(APIView):
    @extend_schema(
        tags=['people'],
        parameters=[OpenApiParameter('q', OpenApiTypes.STR, required=True)],
        responses={200: ProfileSearchSerializer(many=True)},
        summary='Поиск людей',
    )
    def get(self, request):
        q = (request.query_params.get('q') or '').strip()
        if not q:
            return Response({'results': []})
        profiles = list(
            Profile.objects.filter(
                Q(first_name__icontains=q) | Q(email__icontains=q)
            )
            .exclude(pk=request.user.pk)
            .order_by('first_name', 'email')[:20]
        )
        _annotate_following(request.user, profiles)
        return Response({
            'results': ProfileSearchSerializer(profiles, many=True).data,
        })


class ProfileDetailView(APIView):
    @extend_schema(
        tags=['people'],
        responses={200: ProfileDetailSerializer},
        summary='Профиль пользователя',
    )
    def get(self, request, pk):
        profile = get_object_or_404(Profile, pk=pk)
        viewer = request.user
        is_own = profile.pk == viewer.pk
        is_following = False
        request_pending = False
        if not is_own:
            is_following = viewer.follows.filter(pk=profile.pk).exists()
            request_pending = FollowRequest.objects.filter(
                from_user=viewer, to_user=profile,
            ).exists()
        visible = visible_activities_for(viewer, profile)
        activities = list(
            visible.select_related('profile', 'activity_type')
            .prefetch_related('medias')
            .defer('streams', 'track_points')[:50]
        )
        activities = _attach_comment_counts(_attach_reactions(activities, viewer))
        can_see = is_own or profile.is_public or is_following
        year_stats = None
        if can_see:
            year_stats = build_year_stats(visible)
            year_stats['selected'] = year_stats['by_year'][year_stats['selected_year']]
            year_stats['by_year'] = {
                str(year): stats for year, stats in year_stats['by_year'].items()
            }
        serializer = ProfileDetailSerializer(profile, context={
            'request': request,
            'is_following': is_following,
            'request_pending': request_pending,
            'year_stats': year_stats,
            'activities': activities,
        })
        return Response(serializer.data)


class ProfileFollowingView(generics.ListAPIView):
    serializer_class = ProfileSearchSerializer

    def get_queryset(self):
        profile = get_object_or_404(Profile, pk=self.kwargs['pk'])
        return profile.follows.all().order_by('first_name', 'email')

    def list(self, request, *args, **kwargs):
        queryset = list(self.filter_queryset(self.get_queryset()))
        page = self.paginate_queryset(queryset)
        profiles = page if page is not None else queryset
        _annotate_following(request.user, profiles)
        serializer = self.get_serializer(profiles, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class ProfileFollowersView(generics.ListAPIView):
    serializer_class = ProfileSearchSerializer

    def get_queryset(self):
        profile = get_object_or_404(Profile, pk=self.kwargs['pk'])
        return Profile.objects.filter(
            pk__in=profile.followers.values_list('user_id', flat=True)
        ).order_by('first_name', 'email')

    def list(self, request, *args, **kwargs):
        queryset = list(self.filter_queryset(self.get_queryset()))
        page = self.paginate_queryset(queryset)
        profiles = page if page is not None else queryset
        _annotate_following(request.user, profiles)
        serializer = self.get_serializer(profiles, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class ProfileFollowToggleView(APIView):
    @extend_schema(
        tags=['people'],
        request=None,
        responses={200: FollowToggleResponseSerializer},
        summary='Подписаться / отписаться / отменить запрос',
    )
    def post(self, request, pk):
        target = get_object_or_404(Profile, pk=pk)
        try:
            result = toggle_follow(viewer=request.user, target=target)
        except DjangoValidationError as exc:
            message = '; '.join(exc.messages) if hasattr(exc, 'messages') else str(exc)
            raise ValidationError(message) from exc
        return Response({
            'is_following': result.is_following,
            'request_pending': result.request_pending,
            'followers_count': result.followers_count,
        })


class FollowRequestListView(generics.ListAPIView):
    serializer_class = FollowRequestSerializer

    def get_queryset(self):
        return (
            FollowRequest.objects.filter(to_user=self.request.user)
            .select_related('from_user')
            .order_by('-created_at')
        )


class FollowRequestAcceptView(APIView):
    @extend_schema(tags=['people'], request=None, responses={200: StatusSerializer})
    def post(self, request, pk):
        follow_request = get_object_or_404(
            FollowRequest, pk=pk, to_user=request.user,
        )
        accept_follow_request(follow_request=follow_request)
        return Response({'status': 'accepted'})


class FollowRequestRejectView(APIView):
    @extend_schema(tags=['people'], request=None, responses={200: StatusSerializer})
    def post(self, request, pk):
        follow_request = get_object_or_404(
            FollowRequest, pk=pk, to_user=request.user,
        )
        reject_follow_request(follow_request=follow_request)
        return Response({'status': 'rejected'})


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = MeSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self):
        return self.request.user


class MePasswordView(APIView):
    @extend_schema(
        tags=['me'],
        request=PasswordChangeSerializer,
        responses={200: StatusSerializer},
        summary='Сменить пароль',
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'status': 'password_changed'})


class MeDeleteView(APIView):
    @extend_schema(
        tags=['me'],
        request=DeleteAccountSerializer,
        responses={204: None},
        summary='Удалить аккаунт',
    )
    def post(self, request):
        serializer = DeleteAccountSerializer(
            data=request.data, context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        Token.objects.filter(user=request.user).delete()
        request.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _garmin_connection(user):
    try:
        return user.garmin_connection
    except GarminConnection.DoesNotExist:
        return None


class IntervalsConnectView(APIView):
    @extend_schema(
        tags=['me'],
        request=ApiKeySerializer,
        responses={200: ConnectedSerializer},
        summary='Подключить Intervals.icu',
    )
    def post(self, request):
        serializer = ApiKeySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            connection = connect_profile(
                request.user, serializer.validated_data['api_key'],
            )
        except IntervalsApiError as exc:
            raise ValidationError(f'Не удалось подключиться: {exc}') from exc
        try:
            sync_connection.delay(connection.pk, initial=True)
            sync_queued = True
        except Exception:
            sync_queued = False
        return Response({
            'connected': True,
            'sync_queued': sync_queued,
        })


class IntervalsDisconnectView(APIView):
    @extend_schema(
        tags=['me'],
        request=None,
        responses={200: ConnectedSerializer},
        summary='Отключить Intervals.icu',
    )
    def post(self, request):
        disconnect_profile(request.user)
        return Response({'connected': False})


class GarminConnectView(APIView):
    @extend_schema(
        tags=['me'],
        request=ApiKeySerializer,
        responses={200: ConnectedSerializer},
        summary='Подключить Garmin',
    )
    def post(self, request):
        serializer = ApiKeySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            connection = garmin_sync_service.connect_profile(
                request.user, serializer.validated_data['api_key'],
            )
        except GarminApiError as exc:
            raise ValidationError(f'Не удалось подключиться: {exc}') from exc
        try:
            sync_garmin_connection.delay(connection.pk, initial=True)
            sync_queued = True
        except Exception:
            sync_queued = False
        return Response({
            'connected': True,
            'sync_queued': sync_queued,
        })


class GarminDisconnectView(APIView):
    @extend_schema(
        tags=['me'],
        request=None,
        responses={200: ConnectedSerializer},
        summary='Отключить Garmin',
    )
    def post(self, request):
        garmin_sync_service.disconnect_profile(request.user)
        return Response({'connected': False})


class GarminSyncPowerZonesView(APIView):
    @extend_schema(
        tags=['me'],
        request=None,
        responses={200: GarminSyncZonesResponseSerializer},
        summary='Синхронизировать зоны мощности из Garmin',
    )
    def post(self, request):
        connection = _garmin_connection(request.user)
        if not connection or not connection.is_active:
            raise ValidationError('Сначала подключите Garmin')
        try:
            result = garmin_sync_service.sync_power_zones(connection)
        except GarminApiError as exc:
            raise ValidationError(f'Не удалось синхронизировать зоны: {exc}') from exc
        return Response({
            'status': 'synced',
            'ftp': result.get('ftp'),
        })


class RouteListCreateView(generics.ListCreateAPIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return RouteUploadSerializer
        return RouteListSerializer

    def get_queryset(self):
        user = self.request.user
        tab = self.request.query_params.get('tab', 'mine')
        qs = Route.objects.select_related('profile').defer('track_points', 'surface_segments')
        if tab == 'following':
            following_ids = list(user.follows.values_list('pk', flat=True))
            qs = qs.filter(
                profile_id__in=following_ids,
                visibility__in=[Route.Visibility.FOLLOWERS, Route.Visibility.PUBLIC],
            )
        elif tab == 'public':
            qs = qs.filter(visibility=Route.Visibility.PUBLIC).exclude(profile=user)
        else:
            qs = qs.filter(profile=user)
        return qs.order_by('-created_at')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        route = serializer.save()
        return Response(
            RouteDetailSerializer(route, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class RouteDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Route.objects.select_related('profile', 'source_activity')

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return RouteUpdateSerializer
        return RouteDetailSerializer

    def get_permissions(self):
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            return [IsAuthenticated(), IsRouteOwner()]
        return [IsAuthenticated(), CanViewRoute()]

    def get_object(self):
        obj = super().get_object()
        self.check_object_permissions(self.request, obj)
        return obj


class RouteFromActivityView(APIView):
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    @extend_schema(
        tags=['routes'],
        request=RouteFromActivitySerializer,
        responses={201: RouteDetailSerializer},
        summary='Создать маршрут из тренировки',
    )
    def post(self, request, activity_id):
        activity = get_object_or_404(Activity, pk=activity_id)
        if activity.profile_id != request.user.pk:
            raise NotFound()
        points = activity.track_points or []
        if len(points) < 2:
            raise NotFound()
        serializer = RouteFromActivitySerializer(
            data=request.data,
            context={'request': request, 'activity': activity},
        )
        serializer.is_valid(raise_exception=True)
        route = serializer.save()
        return Response(
            RouteDetailSerializer(route, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class RouteGpxDownloadView(APIView):
    @extend_schema(
        tags=['routes'],
        summary='Скачать GPX маршрута',
        responses={(200, 'application/gpx+xml'): OpenApiTypes.BINARY},
    )
    def get(self, request, pk):
        route = get_object_or_404(Route, pk=pk)
        if not route.is_visible_to(request.user):
            raise NotFound()
        opened = route_gpx_stream(route)
        if opened is None:
            raise NotFound()
        stream, filename = opened
        return FileResponse(
            stream,
            as_attachment=True,
            filename=filename,
            content_type='application/gpx+xml',
        )
