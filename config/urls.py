"""URL Configuration for the CA firm portal."""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.dashboards.urls', namespace='root_dashboards')),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('catalog/', include('apps.catalog.urls', namespace='catalog')),
    path('requests/', include('apps.requests.urls', namespace='requests')),
    path('documents/', include('apps.documents.urls', namespace='documents')),
    path('dashboard/', include('apps.dashboards.urls', namespace='dashboards')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
