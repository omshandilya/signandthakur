"""URL patterns for the dashboards application."""

from django.urls import path
from .views import (
    AdminDashboardView,
    ClientDashboardView,
    DashboardIndexView,
    EmployeeDashboardView,
)

app_name = 'dashboards'

urlpatterns = [
    path('', DashboardIndexView.as_view(), name='index'),
    path('client/', ClientDashboardView.as_view(), name='client'),
    path('employee/', EmployeeDashboardView.as_view(), name='employee'),
    path('admin/', AdminDashboardView.as_view(), name='admin'),
]
