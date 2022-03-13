from django.shortcuts import render
from django.views.generic.list import ListView
from activities.models import Activity
from django.contrib.auth.mixins import LoginRequiredMixin
from profiles.models import Follow


class FeedView(LoginRequiredMixin, ListView):
    model = Activity
    template_name = 'feed/index.html'
    paginate_by = 50

    def get_queryset(self):
        queryset = super(FeedView, self).get_queryset()
        user = self.request.user
        follows = user.follows.all()
        return queryset.filter(profile__in=follows)
