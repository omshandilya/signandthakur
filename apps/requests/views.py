"""Requests views — thin; all business logic is in services.py."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.permissions import RoleRequiredMixin
from apps.catalog.models import Service

from .forms import AssignRequestForm
from .models import ServiceRequest
from .services import (
    assign_request,
    create_request,
    get_employees_for_assignment,
    get_pending_requests,
    get_request_detail,
    get_requests_for_user,
)


class RequestListView(RoleRequiredMixin, TemplateView):
    """Role-filtered request list.

    - CLIENT: their own requests
    - EMPLOYEE: requests assigned to them
    - ADMIN: all requests
    """

    allowed_roles = ['CLIENT', 'EMPLOYEE', 'ADMIN']
    template_name = 'requests/request_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['requests'] = get_requests_for_user(self.request.user)
        return context


class RequestCreateView(RoleRequiredMixin, View):
    """Client submits a new service request."""

    allowed_roles = ['CLIENT']
    template_name = 'requests/request_create.html'

    def get(self, request):
        service_id = request.GET.get('service')
        service = get_object_or_404(Service, pk=service_id, is_active=True) if service_id else None
        active_services = Service.objects.filter(is_active=True).order_by('name')
        return render(request, self.template_name, {
            'service': service,
            'active_services': active_services,
        })

    def post(self, request):
        service_id = request.POST.get('service')
        if not service_id:
            messages.error(request, "Please select a service.")
            return redirect('requests:create')

        service = get_object_or_404(Service, pk=service_id, is_active=True)
        try:
            service_request = create_request(client=request.user, service=service)
            messages.success(
                request,
                f"Your request for '{service.name}' has been submitted successfully. "
                f"We will assign it to a team member shortly."
            )
            return redirect('requests:detail', pk=service_request.pk)
        except (ValidationError, PermissionDenied) as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
            return redirect('requests:create')


class RequestDetailView(RoleRequiredMixin, View):
    """View a single service request (role-filtered)."""

    allowed_roles = ['CLIENT', 'EMPLOYEE', 'ADMIN']
    template_name = 'requests/request_detail.html'

    def get(self, request, pk):
        service_request = get_object_or_404(
            get_requests_for_user(request.user), pk=pk
        )
        assign_form = None
        if request.user.is_admin_user() and service_request.status == ServiceRequest.Status.PENDING:
            assign_form = AssignRequestForm(
                employees_qs=get_employees_for_assignment()
            )

        # Upload permission: Assigned employee (or admin) when request is ASSIGNED or COMPLETED
        can_upload = (
            (service_request.assigned_to_id == request.user.id or request.user.is_admin_user())
            and service_request.status in [ServiceRequest.Status.ASSIGNED, ServiceRequest.Status.COMPLETED]
        )

        from apps.documents.forms import DocumentUploadForm
        upload_form = DocumentUploadForm() if can_upload else None

        # Download permission: Admin, assigned employee, or owning client if COMPLETED
        can_download = (
            request.user.is_admin_user()
            or service_request.assigned_to_id == request.user.id
            or (service_request.client_id == request.user.id and service_request.status == ServiceRequest.Status.COMPLETED)
        )

        return render(request, self.template_name, {
            'service_request': service_request,
            'assign_form': assign_form,
            'upload_form': upload_form,
            'can_upload': can_upload,
            'can_download': can_download,
            'documents': service_request.documents.select_related('uploaded_by').all(),
            'history': service_request.status_history.select_related('changed_by').all(),
        })


class AdminAssignRequestView(RoleRequiredMixin, View):
    """Admin assigns a PENDING request to an employee."""

    allowed_roles = ['ADMIN']

    def post(self, request, pk):
        service_request = get_object_or_404(ServiceRequest, pk=pk)
        form = AssignRequestForm(
            request.POST,
            employees_qs=get_employees_for_assignment()
        )
        if form.is_valid():
            try:
                assign_request(
                    service_request=service_request,
                    employee=form.cleaned_data['employee'],
                    by_admin=request.user,
                )
                messages.success(
                    request,
                    f"Request #{pk} assigned to {form.cleaned_data['employee'].display_name}."
                )
            except (ValidationError, PermissionDenied) as e:
                messages.error(request, str(e.message if hasattr(e, 'message') else e))
        else:
            messages.error(request, "Please select a valid employee.")

        next_url = request.POST.get('next')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect('requests:detail', pk=pk)


class AdminRequestListView(RoleRequiredMixin, TemplateView):
    """Admin-only full request management view with all statuses."""

    allowed_roles = ['ADMIN']
    template_name = 'requests/admin_request_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pending_requests'] = get_pending_requests()
        context['all_requests'] = get_requests_for_user(self.request.user)
        return context
