"""Dashboards views.

Provides entry points for Client, Employee, and Admin role dashboards.
"""

from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView
from apps.accounts.permissions import RoleRequiredMixin
from apps.accounts.services import get_redirect_url_for_role


class DashboardIndexView(View):
    """Dynamic entry point directing authenticated users to their role dashboard."""

    def get(self, request):
        return redirect(get_redirect_url_for_role(request.user))


class ClientDashboardView(RoleRequiredMixin, TemplateView):
    """Client portal dashboard."""

    allowed_roles = ['CLIENT']
    template_name = 'dashboards/client.html'


class EmployeeDashboardView(RoleRequiredMixin, TemplateView):
    """Employee portal dashboard."""

    allowed_roles = ['EMPLOYEE']
    template_name = 'dashboards/employee.html'


class AdminDashboardView(RoleRequiredMixin, TemplateView):
    """Admin portal dashboard."""

    allowed_roles = ['ADMIN']
    template_name = 'dashboards/admin.html'
