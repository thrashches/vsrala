from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from .views import (
    FeedView,
    ActivityCommentActionView,
    ActivityCommentCreateView,
    ActivityDetailView,
    ActivityReactView,
    MyActivitiesView,
    ActivityUploadView,
    ProfileSettingsView,
    PeopleSearchView,
    PeopleSearchApiView,
    ProfileDetailView,
    ProfileFollowingView,
    ProfileFollowersView,
    ProfileFollowToggleView,
    FollowRequestsView,
    FollowRequestActionView,
    WeeklyLeadersApiView,
)


app_name = 'webinterface'

urlpatterns = [
    path('', FeedView.as_view(), name='feed'),
    path('activities/upload/', ActivityUploadView.as_view(), name='activity_upload'),
    path('activities/my/', MyActivitiesView.as_view(), name='my_activities'),
    path('activities/<int:pk>/', ActivityDetailView.as_view(), name='activity_detail'),
    path('activities/<int:pk>/react/', ActivityReactView.as_view(), name='activity_react'),
    path('activities/<int:pk>/comments/', ActivityCommentCreateView.as_view(), name='activity_comment_create'),
    path(
        'activities/<int:pk>/comments/<int:comment_id>/',
        ActivityCommentActionView.as_view(),
        name='activity_comment_action',
    ),
    path('leaders/api/weekly/', WeeklyLeadersApiView.as_view(), name='weekly_leaders_api'),
    path('people/', PeopleSearchView.as_view(), name='people_search'),
    path('people/api/search/', PeopleSearchApiView.as_view(), name='people_search_api'),
    path('people/requests/', FollowRequestsView.as_view(), name='follow_requests'),
    path(
        'people/requests/<int:pk>/<str:action>/',
        FollowRequestActionView.as_view(),
        name='follow_request_action',
    ),
    path('people/<int:pk>/', ProfileDetailView.as_view(), name='profile_detail'),
    path('people/<int:pk>/following/', ProfileFollowingView.as_view(), name='profile_following'),
    path('people/<int:pk>/followers/', ProfileFollowersView.as_view(), name='profile_followers'),
    path('people/<int:pk>/follow/', ProfileFollowToggleView.as_view(), name='profile_follow'),
    path('settings/', ProfileSettingsView.as_view(), name='settings'),
    path('login/', LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
]
