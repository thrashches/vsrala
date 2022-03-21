from django.urls import path
from .views import FeedView, test, ActivityDetailView


app_name = 'webinterface'

urlpatterns = [
    path('', FeedView.as_view(), name='feed'),
    path('activities/<int:pk>/', ActivityDetailView.as_view(), name='activity_detail'),
    path('test/', test)
]