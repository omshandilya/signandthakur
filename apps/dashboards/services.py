"""Dashboards services.

Business rules for aggregating metrics, status counts, workloads,
and paginated querysets for CLIENT, EMPLOYEE, and ADMIN dashboards.

All querysets strictly enforce role permissions and ownership per CLAUDE.md.
"""

from django.core.paginator import Paginator
from apps.catalog.models import Service
from apps.requests.models import ServiceRequest
from apps.requests.services import get_employees_for_assignment


def get_client_dashboard_data(client_user, page=1, per_page=10):
    """Retrieve all data required for the client dashboard.

    - Paginated list of client's requests with select_related
    - Active services catalog with document requirements
    - Summary metrics
    """
    requests_qs = (
        ServiceRequest.objects
        .filter(client=client_user)
        .select_related('service', 'assigned_to')
        .order_by('-created_at')
    )

    paginator = Paginator(requests_qs, per_page)
    requests_page = paginator.get_page(page)

    active_services = (
        Service.objects
        .filter(is_active=True)
        .prefetch_related('document_requirements')
        .order_by('name')
    )

    total_requests = requests_qs.count()
    pending_count = requests_qs.filter(status=ServiceRequest.Status.PENDING).count()
    assigned_count = requests_qs.filter(status=ServiceRequest.Status.ASSIGNED).count()
    completed_count = requests_qs.filter(status=ServiceRequest.Status.COMPLETED).count()

    return {
        'requests_page': requests_page,
        'active_services': active_services,
        'total_requests': total_requests,
        'pending_count': pending_count,
        'assigned_count': assigned_count,
        'completed_count': completed_count,
    }


def get_employee_dashboard_data(employee_user, pending_page=1, completed_page=1, per_page=10):
    """Retrieve all data required for the employee dashboard.

    - Split into pending (ASSIGNED status) and completed requests assigned to this employee
    - Uses select_related('client', 'service')
    - Paginated lists for both sections
    """
    assigned_base = (
        ServiceRequest.objects
        .filter(assigned_to=employee_user)
        .select_related('client', 'service')
    )

    # Pending/In-progress tasks for this employee
    pending_qs = (
        assigned_base
        .filter(status=ServiceRequest.Status.ASSIGNED)
        .order_by('-assigned_at', '-created_at')
    )
    pending_paginator = Paginator(pending_qs, per_page)
    pending_page_obj = pending_paginator.get_page(pending_page)

    # Completed tasks for this employee
    completed_qs = (
        assigned_base
        .filter(status=ServiceRequest.Status.COMPLETED)
        .order_by('-completed_at', '-created_at')
    )
    completed_paginator = Paginator(completed_qs, per_page)
    completed_page_obj = completed_paginator.get_page(completed_page)

    pending_count = pending_qs.count()
    completed_count = completed_qs.count()

    return {
        'pending_page_obj': pending_page_obj,
        'completed_page_obj': completed_page_obj,
        'pending_count': pending_count,
        'completed_count': completed_count,
        'total_assigned': pending_count + completed_count,
    }


def get_admin_dashboard_data(admin_user, status_filter='', page=1, per_page=10):
    """Retrieve all data required for the admin dashboard.

    - New requests section (unassigned PENDING requests)
    - Available employees list for the inline assign dropdown
    - All requests filtered by status with select_related
    - Paginated requests list
    - Summary metrics across the firm
    """
    # New requests needing assignment
    new_requests = (
        ServiceRequest.objects
        .filter(status=ServiceRequest.Status.PENDING)
        .select_related('client', 'service')
        .order_by('-created_at')
    )

    # Employees for assignment dropdown
    employees = get_employees_for_assignment()

    # All requests query
    all_requests_qs = (
        ServiceRequest.objects
        .all()
        .select_related('client', 'service', 'assigned_to')
        .order_by('-created_at')
    )

    # Metrics before filtering
    total_requests = all_requests_qs.count()
    pending_count = all_requests_qs.filter(status=ServiceRequest.Status.PENDING).count()
    assigned_count = all_requests_qs.filter(status=ServiceRequest.Status.ASSIGNED).count()
    completed_count = all_requests_qs.filter(status=ServiceRequest.Status.COMPLETED).count()

    # Apply status filter
    valid_statuses = [
        ServiceRequest.Status.PENDING,
        ServiceRequest.Status.ASSIGNED,
        ServiceRequest.Status.COMPLETED,
    ]
    if status_filter in valid_statuses:
        filtered_qs = all_requests_qs.filter(status=status_filter)
    else:
        status_filter = ''
        filtered_qs = all_requests_qs

    paginator = Paginator(filtered_qs, per_page)
    requests_page = paginator.get_page(page)

    return {
        'new_requests': new_requests,
        'employees': employees,
        'requests_page': requests_page,
        'status_filter': status_filter,
        'total_requests': total_requests,
        'pending_count': pending_count,
        'assigned_count': assigned_count,
        'completed_count': completed_count,
        'total_employees': employees.count(),
    }
