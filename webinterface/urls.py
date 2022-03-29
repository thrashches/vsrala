from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from .views import FeedView, test, ActivityDetailView, MyActivitiesView


app_name = 'webinterface'

urlpatterns = [
    path('', FeedView.as_view(), name='feed'),
    path('activities/<int:pk>/', ActivityDetailView.as_view(), name='activity_detail'),
    path('activities/my/', MyActivitiesView.as_view(), name='my_activities'),
    path('login/', LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),

    # Test url
    path('test/', test)
]