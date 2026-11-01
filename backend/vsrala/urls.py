"""vsrala URL Configuration."""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='api_schema'),
    path(
        'api/docs/',
        SpectacularSwaggerView.as_view(url_name='api_schema'),
        name='api_swagger',
    ),
    path(
        'api/redoc/',
        SpectacularRedocView.as_view(url_name='api_schema'),
        name='api_redoc',
    ),
    path('api/', include('api.urls')),
]

# Legacy Django templates UI. Disabled in Docker (nginx serves React SPA).
# Keep enabled by default for local tests that reverse('webinterface:...').
if getattr(settings, 'ENABLE_LEGACY_UI', True):
    urlpatterns += [
        path('', include('webinterface.urls', namespace='webinterface')),
    ]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
