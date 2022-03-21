from django.shortcuts import render
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView
from activities.models import Activity
from django.contrib.auth.mixins import LoginRequiredMixin
from profiles.models import Follow
import folium
from django.http import HttpResponse
from PIL import Image
import io
from activities.utils import get_map


class FeedView(LoginRequiredMixin, ListView):
    model = Activity
    template_name = 'feed/index.html'
    paginate_by = 50

    def get_queryset(self):
        queryset = super(FeedView, self).get_queryset()
        user = self.request.user
        follows = user.follows.all()
        return queryset.filter(profile__in=follows)


class ActivityDetailView(LoginRequiredMixin, DetailView):
    model = Activity
    template_name = 'activities/detail.html'

    def get_context_data(self, **kwargs):
        context = super(ActivityDetailView, self).get_context_data(**kwargs)
        if self.object.track_file:
            folium_map = get_map(self.object.track_file.path)
            context['map'] = folium_map
        return context


class ActivityUploadView(LoginRequiredMixin, CreateView):
    model = Activity
    template_name = 'activities/upload.html'


class ActivityCreateView(LoginRequiredMixin, CreateView):
    model = Activity
    template_name = 'activities/create.html'


def test(request):
    start_coords = (46.9540700, 142.7360300)
    folium_map = folium.Map(location=start_coords, zoom_start=14)
    img = folium_map._to_png(5)
    output = Image.open(io.BytesIO(img))
    output.save('media/pictures/test.png')

    return HttpResponse(folium_map._repr_html_())
