from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from activities.models import Activity, ActivityReaction, ActivityType
from activities.parsers import TrackParseError
from activities.services import create_activity_from_upload
from profiles.forms import ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_TYPES, MAX_PHOTO_SIZE
from profiles.models import FollowRequest, Profile
from profiles.photo_preview import apply_photo_preview, clear_photo_preview
from profiles.zones import (
    HR_ZONE_NAMES,
    POWER_ZONE_NAMES,
    default_hr_zones,
    default_power_zones,
    normalize_zones,
)
from routes.models import Route
from routes.services import (
    create_route_from_activity,
    create_route_from_gpx,
    enqueue_surface_enrichment,
)


class EmailAuthTokenSerializer(serializers.Serializer):
    email = serializers.EmailField(label='Email', write_only=True)
    password = serializers.CharField(
        label='Password',
        style={'input_type': 'password'},
        trim_whitespace=False,
        write_only=True,
    )

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        user = authenticate(
            request=self.context.get('request'),
            username=email,
            password=password,
        )
        if not user:
            raise serializers.ValidationError(
                'Неверный email или пароль',
                code='authorization',
            )
        attrs['user'] = user
        return attrs


class AuthTokenResponseSerializer(serializers.Serializer):
    token = serializers.CharField()
    user_id = serializers.IntegerField()
    email = serializers.EmailField()
    display_name = serializers.CharField()


class StatusSerializer(serializers.Serializer):
    status = serializers.CharField()


class ConnectedSerializer(serializers.Serializer):
    connected = serializers.BooleanField()
    sync_queued = serializers.BooleanField(required=False)


class FollowToggleResponseSerializer(serializers.Serializer):
    is_following = serializers.BooleanField()
    request_pending = serializers.BooleanField()
    followers_count = serializers.IntegerField()




class ReactionSummarySerializer(serializers.Serializer):
    counts = serializers.ListField(child=serializers.DictField())
    mine = serializers.CharField(allow_null=True, required=False)


class CommentActionResponseSerializer(serializers.Serializer):
    comment = serializers.DictField(required=False)
    comment_count = serializers.IntegerField()
    comment_count_label = serializers.CharField()
    id = serializers.IntegerField(required=False)


class GarminSyncZonesResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    ftp = serializers.IntegerField(allow_null=True, required=False)


class ProfileBriefSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = ('id', 'display_name', 'photo_url', 'is_public')

    @extend_schema_field(OpenApiTypes.URI)
    def get_photo_url(self, obj):
        return obj.avatar_url


class ProfileSearchSerializer(ProfileBriefSerializer):
    is_following = serializers.BooleanField(read_only=True)
    request_pending = serializers.BooleanField(read_only=True)

    class Meta(ProfileBriefSerializer.Meta):
        fields = ProfileBriefSerializer.Meta.fields + (
            'is_following',
            'request_pending',
        )


class ActivityTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityType
        fields = ('id', 'name')


class ActivityListSerializer(serializers.ModelSerializer):
    profile = ProfileBriefSerializer(read_only=True)
    activity_type = ActivityTypeSerializer(read_only=True)
    duration_display = serializers.CharField(read_only=True)
    duration_active_display = serializers.CharField(read_only=True)
    map_preview_url = serializers.SerializerMethodField()
    reaction_counts = serializers.SerializerMethodField()
    my_reaction = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    medias = serializers.SerializerMethodField()

    class Meta:
        model = Activity
        fields = (
            'id', 'title', 'description', 'profile', 'activity_type',
            'duration', 'duration_display', 'duration_active', 'duration_active_display',
            'distance', 'avg_speed', 'avg_moving_speed', 'max_speed',
            'avg_hr', 'max_hr', 'avg_power', 'max_power', 'normalized_power',
            'tss', 'avg_cadence', 'max_cadence',
            'elevation_gain', 'elevation_loss', 'elevation_min', 'elevation_max',
            'is_indoor', 'map_preview_url', 'started_at', 'created_at',
            'external_source', 'calories', 'device_name',
            'reaction_counts', 'my_reaction', 'comment_count', 'medias',
        )

    @extend_schema_field(OpenApiTypes.URI)
    def get_map_preview_url(self, obj):
        if obj.map_preview:
            try:
                return obj.map_preview.url
            except ValueError:
                pass
        return None

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_reaction_counts(self, obj):
        return getattr(obj, 'reaction_counts', [])

    @extend_schema_field(OpenApiTypes.STR)
    def get_my_reaction(self, obj):
        return getattr(obj, 'my_reaction', None)

    @extend_schema_field(OpenApiTypes.INT)
    def get_comment_count(self, obj):
        return getattr(obj, 'comment_count', 0)

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_medias(self, obj):
        if not hasattr(obj, 'medias'):
            return []
        result = []
        for media in obj.medias.all():
            url = None
            if media.image:
                try:
                    url = media.image.url
                except ValueError:
                    pass
            result.append({'id': media.pk, 'url': url, 'title': media.title or ''})
        return result


class ActivityDetailSerializer(ActivityListSerializer):
    track_points = serializers.JSONField(read_only=True)
    streams = serializers.JSONField(read_only=True)
    zone_timeline_url = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()
    hr_zone_rows = serializers.SerializerMethodField()
    power_zone_rows = serializers.SerializerMethodField()
    best_efforts = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    has_hr_stream = serializers.SerializerMethodField()
    has_power_stream = serializers.SerializerMethodField()
    hr_zones_configured = serializers.SerializerMethodField()
    power_zones_configured = serializers.SerializerMethodField()
    reaction_choices = serializers.SerializerMethodField()

    class Meta(ActivityListSerializer.Meta):
        fields = ActivityListSerializer.Meta.fields + (
            'track_points', 'streams', 'zone_timeline_url', 'zone_stream',
            'comments', 'hr_zone_rows', 'power_zone_rows', 'best_efforts',
            'is_owner', 'has_hr_stream', 'has_power_stream',
            'hr_zones_configured', 'power_zones_configured',
            'aerobic_training_effect', 'anaerobic_training_effect',
            'avg_temperature', 'vo2max', 'external_id', 'external_refs',
            'reaction_choices',
        )

    def get_zone_timeline_url(self, obj):
        if obj.zone_timeline:
            try:
                return obj.zone_timeline.url
            except ValueError:
                pass
        return None

    def get_comments(self, obj):
        request = self.context.get('request')
        user = request.user if request else None
        from activities.comments import serialize_comment

        comments = list(obj.comments.select_related('profile').all())
        return [serialize_comment(c, user) for c in comments]

    def get_hr_zone_rows(self, obj):
        return self.context.get('hr_zone_rows', [])

    def get_power_zone_rows(self, obj):
        return self.context.get('power_zone_rows', [])

    def get_best_efforts(self, obj):
        return self.context.get('best_efforts', [])

    def get_is_owner(self, obj):
        request = self.context.get('request')
        return bool(request and obj.profile_id == request.user.pk)

    def get_has_hr_stream(self, obj):
        return self.context.get('has_hr_stream', False)

    def get_has_power_stream(self, obj):
        return self.context.get('has_power_stream', False)

    def get_hr_zones_configured(self, obj):
        return self.context.get('hr_zones_configured', False)

    def get_power_zones_configured(self, obj):
        return self.context.get('power_zones_configured', False)

    def get_reaction_choices(self, obj):
        return [{'emoji': e, 'label': l} for e, l in ActivityReaction.EMOJI_CHOICES]


class ActivityUploadSerializer(serializers.Serializer):
    track_file = serializers.FileField()
    title = serializers.CharField(required=False, allow_blank=True, max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, max_length=3000)
    activity_type = serializers.PrimaryKeyRelatedField(
        queryset=ActivityType.objects.all(),
        required=False,
        allow_null=True,
    )

    def validate_track_file(self, track_file):
        name = track_file.name.lower()
        if not any(name.endswith(ext) for ext in ('.gpx', '.fit')):
            raise serializers.ValidationError('Поддерживаются только файлы .gpx и .fit')
        if track_file.size > 50 * 1024 * 1024:
            raise serializers.ValidationError('Файл слишком большой (макс. 50 МБ)')
        return track_file

    def create(self, validated_data):
        try:
            return create_activity_from_upload(
                profile=self.context['request'].user,
                track_file=validated_data['track_file'],
                title=validated_data.get('title') or '',
                description=validated_data.get('description') or '',
                activity_type=validated_data.get('activity_type'),
            )
        except TrackParseError as exc:
            raise serializers.ValidationError({'track_file': [str(exc)]}) from exc


class ActivityUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = ('title', 'description', 'activity_type')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].required = False
        self.fields['description'].required = False
        self.fields['activity_type'].required = False
        self.fields['activity_type'].allow_null = True


class ReactionSerializer(serializers.Serializer):
    emoji = serializers.ChoiceField(choices=[c[0] for c in ActivityReaction.EMOJI_CHOICES])


class CommentCreateSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=2000)

    def validate_text(self, value):
        text = (value or '').strip()
        if not text:
            raise serializers.ValidationError('Текст комментария пуст')
        return text


class CommentUpdateSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=2000)

    def validate_text(self, value):
        text = (value or '').strip()
        if not text:
            raise serializers.ValidationError('Текст комментария пуст')
        return text


class ZoneItemSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True)
    min = serializers.IntegerField(required=False, allow_null=True)
    max = serializers.IntegerField(required=False, allow_null=True)


class MeSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    photo_url = serializers.SerializerMethodField()
    intervals_connected = serializers.SerializerMethodField()
    garmin_connected = serializers.SerializerMethodField()
    power_zones = ZoneItemSerializer(many=True, required=False)
    hr_zones = ZoneItemSerializer(many=True, required=False)
    recalculate_zones = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = Profile
        fields = (
            'id', 'email', 'first_name', 'display_name', 'photo', 'photo_url',
            'telegram', 'instagram', 'vk', 'ftp', 'max_heart_rate', 'is_public',
            'power_zones', 'hr_zones', 'recalculate_zones',
            'intervals_connected', 'garmin_connected',
        )
        extra_kwargs = {
            'photo': {'write_only': True, 'required': False},
            'email': {'required': False},
            'first_name': {'required': False},
        }

    def get_photo_url(self, obj):
        return obj.avatar_url

    def get_intervals_connected(self, obj):
        try:
            return bool(obj.intervals_connection and obj.intervals_connection.is_active)
        except Exception:
            return False

    def get_garmin_connected(self, obj):
        try:
            return bool(obj.garmin_connection and obj.garmin_connection.is_active)
        except Exception:
            return False

    def validate_email(self, email):
        email = Profile.objects.normalize_email(email)
        qs = Profile.objects.filter(email__iexact=email)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Пользователь с такой почтой уже существует')
        return email

    def validate_photo(self, photo):
        if not photo:
            return photo
        content_type = getattr(photo, 'content_type', None)
        if content_type and content_type not in ALLOWED_IMAGE_TYPES:
            raise serializers.ValidationError(
                'Поддерживаются JPEG (.jpg/.jpeg), PNG, GIF и WebP'
            )
        name = getattr(photo, 'name', '') or ''
        import os
        ext = os.path.splitext(name)[1].lower()
        if ext and ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise serializers.ValidationError(
                'Поддерживаются JPEG (.jpg/.jpeg), PNG, GIF и WebP'
            )
        if photo.size > MAX_PHOTO_SIZE:
            raise serializers.ValidationError('Файл слишком большой (макс. 5 МБ)')
        return photo

    def update(self, instance, validated_data):
        recalculate = validated_data.pop('recalculate_zones', False)
        power_zones = validated_data.pop('power_zones', serializers.empty)
        hr_zones = validated_data.pop('hr_zones', serializers.empty)
        photo = validated_data.pop('photo', serializers.empty)
        photo_changed = photo is not serializers.empty

        old_ftp = instance.ftp
        old_max_hr = instance.max_heart_rate

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        ftp = instance.ftp
        max_hr = instance.max_heart_rate

        if recalculate:
            instance.power_zones = default_power_zones(ftp) if ftp else []
            instance.hr_zones = default_hr_zones(max_hr) if max_hr else []
        else:
            if ftp != old_ftp:
                instance.power_zones = default_power_zones(ftp) if ftp else []
            elif power_zones is not serializers.empty:
                zones = normalize_zones(power_zones, names=POWER_ZONE_NAMES)
                instance.power_zones = zones or []

            if max_hr != old_max_hr:
                instance.hr_zones = default_hr_zones(max_hr) if max_hr else []
            elif hr_zones is not serializers.empty:
                zones = normalize_zones(hr_zones, names=HR_ZONE_NAMES)
                instance.hr_zones = zones or []

        if photo_changed:
            instance.photo = photo

        instance.save()
        if photo_changed:
            if instance.photo:
                apply_photo_preview(instance)
            else:
                clear_photo_preview(instance)
        return instance


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password1 = serializers.CharField(write_only=True)
    new_password2 = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Неверный текущий пароль')
        return value

    def validate(self, attrs):
        if attrs['new_password1'] != attrs['new_password2']:
            raise serializers.ValidationError({'new_password2': 'Пароли не совпадают'})
        validate_password(attrs['new_password1'], self.context['request'].user)
        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password1'])
        user.save()
        return user


class DeleteAccountSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Неверный пароль')
        return value


class ApiKeySerializer(serializers.Serializer):
    api_key = serializers.CharField(write_only=True, min_length=1)


class ProfileDetailSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    photo_url = serializers.SerializerMethodField()
    is_own_profile = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()
    request_pending = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    year_stats = serializers.SerializerMethodField()
    activities = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = (
            'id', 'display_name', 'photo_url', 'telegram', 'instagram', 'vk',
            'is_public', 'is_own_profile', 'is_following', 'request_pending',
            'following_count', 'followers_count', 'year_stats', 'activities',
        )

    def get_photo_url(self, obj):
        return obj.avatar_url

    def get_is_own_profile(self, obj):
        request = self.context.get('request')
        return bool(request and obj.pk == request.user.pk)

    def get_is_following(self, obj):
        return self.context.get('is_following', False)

    def get_request_pending(self, obj):
        return self.context.get('request_pending', False)

    def get_following_count(self, obj):
        return obj.follows.count()

    def get_followers_count(self, obj):
        return obj.followers.count()

    def get_year_stats(self, obj):
        return self.context.get('year_stats')

    def get_activities(self, obj):
        activities = self.context.get('activities', [])
        return ActivityListSerializer(
            activities, many=True, context=self.context,
        ).data


class FollowRequestSerializer(serializers.ModelSerializer):
    from_user = ProfileBriefSerializer(read_only=True)

    class Meta:
        model = FollowRequest
        fields = ('id', 'from_user', 'created_at')


class RouteListSerializer(serializers.ModelSerializer):
    profile = ProfileBriefSerializer(read_only=True)
    map_preview_url = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Route
        fields = (
            'id', 'title', 'description', 'visibility', 'distance',
            'elevation_gain', 'elevation_loss', 'map_preview_url',
            'surface_status', 'created_at', 'profile', 'is_owner',
        )

    @extend_schema_field(OpenApiTypes.URI)
    def get_map_preview_url(self, obj):
        if obj.map_preview:
            try:
                return obj.map_preview.url
            except ValueError:
                pass
        return None

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_owner(self, obj):
        request = self.context.get('request')
        return bool(request and obj.profile_id == request.user.pk)


class RouteDetailSerializer(RouteListSerializer):
    track_points = serializers.JSONField(read_only=True)
    surface_segments = serializers.JSONField(read_only=True)
    surface_summary = serializers.SerializerMethodField()

    class Meta(RouteListSerializer.Meta):
        fields = RouteListSerializer.Meta.fields + (
            'track_points', 'surface_segments', 'surface_summary',
            'source_activity_id',
        )

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_surface_summary(self, obj):
        return obj.surface_summary()


class RouteUploadSerializer(serializers.Serializer):
    source_gpx = serializers.FileField()
    title = serializers.CharField(required=False, allow_blank=True, max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, max_length=3000)
    visibility = serializers.ChoiceField(
        choices=Route.Visibility.choices,
        default=Route.Visibility.PRIVATE,
        required=False,
    )

    def validate_source_gpx(self, f):
        name = f.name.lower()
        if not name.endswith('.gpx'):
            raise serializers.ValidationError('Поддерживаются только файлы .gpx')
        if f.size > 50 * 1024 * 1024:
            raise serializers.ValidationError('Файл слишком большой (макс. 50 МБ)')
        return f

    def create(self, validated_data):
        gpx = validated_data['source_gpx']
        gpx.seek(0)
        file_bytes = gpx.read()
        try:
            route = create_route_from_gpx(
                profile=self.context['request'].user,
                file_bytes=file_bytes,
                filename=gpx.name,
                title=validated_data.get('title') or '',
                description=validated_data.get('description') or '',
                visibility=validated_data.get('visibility') or Route.Visibility.PRIVATE,
            )
        except TrackParseError as exc:
            raise serializers.ValidationError({'source_gpx': [str(exc)]}) from exc
        enqueue_surface_enrichment(route.pk)
        return route


class RouteUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = ('title', 'description', 'visibility')


class RouteFromActivitySerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True, max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, max_length=3000)
    visibility = serializers.ChoiceField(
        choices=Route.Visibility.choices,
        default=Route.Visibility.PRIVATE,
        required=False,
    )
    start_idx = serializers.IntegerField(min_value=0)
    end_idx = serializers.IntegerField(min_value=0)

    def validate(self, attrs):
        start = attrs.get('start_idx')
        end = attrs.get('end_idx')
        if start is not None and end is not None and end < start:
            attrs['start_idx'], attrs['end_idx'] = end, start
        return attrs

    def create(self, validated_data):
        activity = self.context['activity']
        try:
            route = create_route_from_activity(
                profile=self.context['request'].user,
                activity=activity,
                start_idx=validated_data['start_idx'],
                end_idx=validated_data['end_idx'],
                title=validated_data.get('title') or '',
                description=validated_data.get('description') or '',
                visibility=validated_data.get('visibility') or Route.Visibility.PRIVATE,
            )
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        enqueue_surface_enrichment(route.pk)
        return route
