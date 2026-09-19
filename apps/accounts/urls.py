"""URL patterns for the accounts application."""

from django.urls import path
from .views import (
    AdminPasswordResetView,
    ClientSignupView,
    CustomLoginView,
    CustomLogoutView,
    EmployeeCreateView,
    EmployeeListView,
)

app_name = 'accounts'

urlpatterns = [
    path('signup/', ClientSignupView.as_view(), name='signup'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path('employees/', EmployeeListView.as_view(), name='employee_list'),
    path('employees/create/', EmployeeCreateView.as_view(), name='employee_create'),
    path('users/<int:user_id>/reset-password/', AdminPasswordResetView.as_view(), name='admin_password_reset'),
]
