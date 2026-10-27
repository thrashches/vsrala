from django.urls import path

from api import views

urlpatterns = [
    path('auth/token/', views.ObtainAuthTokenView.as_view(), name='api_token'),
    path('auth/logout/', views.LogoutView.as_view(), name='api_logout'),

    path('activities/', views.ActivityListCreateView.as_view(), name='api_activity_list'),
    path('activities/<int:pk>/', views.ActivityDetailView.as_view(), name='api_activity_detail'),
    path(
        'activities/<int:pk>/download/',
        views.ActivityDownloadView.as_view(),
        name='api_activity_download',
    ),
    path(
        'activities/<int:pk>/react/',
        views.ActivityReactView.as_view(),
        name='api_activity_react',
    ),
    path(
        'activities/<int:pk>/comments/',
        views.ActivityCommentListCreateView.as_view(),
        name='api_activity_comments',
    ),
    path(
        'activities/<int:pk>/comments/<int:comment_id>/',
        views.ActivityCommentDetailView.as_view(),
        name='api_activity_comment_detail',
    ),

    path('leaders/weekly/', views.WeeklyLeadersView.as_view(), name='api_weekly_leaders'),

    path('people/search/', views.PeopleSearchView.as_view(), name='api_people_search'),
    path('people/requests/', views.FollowRequestListView.as_view(), name='api_follow_requests'),
    path(
        'people/requests/<int:pk>/accept/',
        views.FollowRequestAcceptView.as_view(),
        name='api_follow_request_accept',
    ),
    path(
        'people/requests/<int:pk>/reject/',
        views.FollowRequestRejectView.as_view(),
        name='api_follow_request_reject',
    ),
    path('people/<int:pk>/', views.ProfileDetailView.as_view(), name='api_profile_detail'),
    path(
        'people/<int:pk>/following/',
        views.ProfileFollowingView.as_view(),
        name='api_profile_following',
    ),
    path(
        'people/<int:pk>/followers/',
        views.ProfileFollowersView.as_view(),
        name='api_profile_followers',
    ),
    path(
        'people/<int:pk>/follow/',
        views.ProfileFollowToggleView.as_view(),
        name='api_profile_follow',
    ),

    path('me/', views.MeView.as_view(), name='api_me'),
    path('me/password/', views.MePasswordView.as_view(), name='api_me_password'),
    path('me/delete/', views.MeDeleteView.as_view(), name='api_me_delete'),
    path(
        'me/integrations/intervals/connect/',
        views.IntervalsConnectView.as_view(),
        name='api_intervals_connect',
    ),
    path(
        'me/integrations/intervals/disconnect/',
        views.IntervalsDisconnectView.as_view(),
        name='api_intervals_disconnect',
    ),
    path(
        'me/integrations/garmin/connect/',
        views.GarminConnectView.as_view(),
        name='api_garmin_connect',
    ),
    path(
        'me/integrations/garmin/disconnect/',
        views.GarminDisconnectView.as_view(),
        name='api_garmin_disconnect',
    ),
    path(
        'me/integrations/garmin/sync-power-zones/',
        views.GarminSyncPowerZonesView.as_view(),
        name='api_garmin_sync_power_zones',
    ),

    path('routes/', views.RouteListCreateView.as_view(), name='api_route_list'),
    path(
        'routes/from-activity/<int:activity_id>/',
        views.RouteFromActivityView.as_view(),
        name='api_route_from_activity',
    ),
    path('routes/<int:pk>/', views.RouteDetailView.as_view(), name='api_route_detail'),
    path(
        'routes/<int:pk>/gpx/',
        views.RouteGpxDownloadView.as_view(),
        name='api_route_gpx',
    ),
]
