"""Dashboards views.

Provides thin views for Client, Employee, and Admin role dashboards.
All business rules, querysets, and data aggregation live in services.py.
"""

from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView
from apps.accounts.permissions import RoleRequiredMixin
from apps.accounts.services import get_redirect_url_for_role
from .services import (
    get_admin_dashboard_data,
    get_client_dashboard_data,
    get_employee_dashboard_data,
)


class DashboardIndexView(View):
    """Dynamic entry point directing authenticated users to their role dashboard."""

    def get(self, request):
        return redirect(get_redirect_url_for_role(request.user))


class ClientDashboardView(RoleRequiredMixin, TemplateView):
    """Client portal dashboard.

    Displays client's requests with status badges, active services catalog,
    and download button for completed requests.
    """

    allowed_roles = ['CLIENT']
    template_name = 'dashboards/client.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = self.request.GET.get('page', 1)
        data = get_client_dashboard_data(self.request.user, page=page)
        context.update(data)
        return context


class EmployeeDashboardView(RoleRequiredMixin, TemplateView):
    """Employee portal dashboard.

    Displays requests assigned to the logged-in employee, split into
    pending/in-progress and completed requests.
    """

    allowed_roles = ['EMPLOYEE']
    template_name = 'dashboards/employee.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pending_page = self.request.GET.get('pending_page', 1)
        completed_page = self.request.GET.get('completed_page', 1)
        data = get_employee_dashboard_data(
            self.request.user,
            pending_page=pending_page,
            completed_page=completed_page,
        )
        context.update(data)
        return context


class AdminDashboardView(RoleRequiredMixin, TemplateView):
    """Admin portal dashboard.

    Displays all requests filtered by status, a new unassigned requests section
    with quick inline employee assignment dropdown, and overall firm metrics.
    """

    allowed_roles = ['ADMIN']
    template_name = 'dashboards/admin.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        status_filter = self.request.GET.get('status', '').strip().upper()
        page = self.request.GET.get('page', 1)
        data = get_admin_dashboard_data(
            self.request.user,
            status_filter=status_filter,
            page=page,
        )
        context.update(data)
        return context
