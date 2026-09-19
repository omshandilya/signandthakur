"""URL patterns for the requests application."""

from django.urls import path
from .views import (
    AdminAssignRequestView,
    AdminRequestListView,
    RequestCreateView,
    RequestDetailView,
    RequestListView,
)

app_name = 'requests'

urlpatterns = [
    path('', RequestListView.as_view(), name='list'),
    path('create/', RequestCreateView.as_view(), name='create'),
    path('<int:pk>/', RequestDetailView.as_view(), name='detail'),
    path('<int:pk>/assign/', AdminAssignRequestView.as_view(), name='assign'),
    path('manage/', AdminRequestListView.as_view(), name='admin_list'),
]
