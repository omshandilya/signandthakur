"""URL patterns for the catalog application."""

from django.urls import path
from .views import (
    AdminServiceCreateView,
    AdminServiceDeleteView,
    AdminServiceListView,
    AdminServiceUpdateView,
    ServiceCatalogView,
)

app_name = 'catalog'

urlpatterns = [
    path('', ServiceCatalogView.as_view(), name='list'),
    path('manage/', AdminServiceListView.as_view(), name='admin_list'),
    path('manage/create/', AdminServiceCreateView.as_view(), name='admin_create'),
    path('manage/<int:pk>/edit/', AdminServiceUpdateView.as_view(), name='admin_edit'),
    path('manage/<int:pk>/delete/', AdminServiceDeleteView.as_view(), name='admin_delete'),
]
