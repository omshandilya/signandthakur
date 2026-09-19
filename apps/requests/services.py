"""Service request business services.

All status transitions, ownership checks, and business rules live here.
Views remain thin and only handle HTTP/form concerns.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import RequestStatusHistory, ServiceRequest

User = get_user_model()


# ──────────────────────────────────────────────
# Internal helper
# ──────────────────────────────────────────────

def _record_history(service_request: ServiceRequest, from_status: str, to_status: str, changed_by) -> None:
    RequestStatusHistory.objects.create(
        request=service_request,
        from_status=from_status,
        to_status=to_status,
        changed_by=changed_by,
    )


# ──────────────────────────────────────────────
# Creation
# ──────────────────────────────────────────────

@transaction.atomic
def create_request(client, service) -> ServiceRequest:
    """Client submits a new service request.

    Rules:
    - `client` must have role CLIENT.
    - The service must be active.
    - Client may not have an open (PENDING or ASSIGNED) request for the same service.
    - Price is copied from the catalog at this moment.
    """
    from apps.catalog.models import Service as CatalogService

    if not client.is_client():
        raise PermissionDenied("Only clients can submit service requests.")

    if not service.is_active:
        raise ValidationError("This service is no longer available.")

    # Duplicate open request check
    already_open = ServiceRequest.objects.filter(
        client=client,
        service=service,
        status__in=[ServiceRequest.Status.PENDING, ServiceRequest.Status.ASSIGNED],
    ).exists()
    if already_open:
        raise ValidationError(
            "You already have an open request for this service. "
            "Please wait for it to be completed before submitting another."
        )

    return ServiceRequest.objects.create(
        client=client,
        service=service,
        status=ServiceRequest.Status.PENDING,
        price_at_request=service.price,
    )


# ──────────────────────────────────────────────
# Assignment
# ──────────────────────────────────────────────

@transaction.atomic
def assign_request(service_request: ServiceRequest, employee, by_admin) -> ServiceRequest:
    """Admin assigns an open PENDING request to an employee.

    Rules:
    - `by_admin` must be an admin user.
    - `employee` must have role EMPLOYEE.
    - Request must be in PENDING status.
    """
    if not by_admin.is_admin_user():
        raise PermissionDenied("Only administrators can assign requests.")

    if not employee.is_employee():
        raise ValidationError("The assigned user must be an employee.")

    if not service_request.can_transition_to(ServiceRequest.Status.ASSIGNED):
        raise ValidationError(
            f"Cannot assign a request that is already '{service_request.get_status_display()}'. "
            f"Only PENDING requests can be assigned."
        )

    from_status = service_request.status
    service_request.status = ServiceRequest.Status.ASSIGNED
    service_request.assigned_to = employee
    service_request.assigned_at = timezone.now()
    service_request.save(update_fields=['status', 'assigned_to', 'assigned_at'])
    _record_history(service_request, from_status, ServiceRequest.Status.ASSIGNED, by_admin)
    return service_request


# ──────────────────────────────────────────────
# Completion
# ──────────────────────────────────────────────

@transaction.atomic
def complete_request(service_request: ServiceRequest, document, by_employee) -> ServiceRequest:
    """Assigned employee marks a request complete and attaches a confirmation document.

    Rules:
    - `by_employee` must be the exact employee assigned to this request.
    - Request must be in ASSIGNED status.
    - A confirmation document must be provided (handled by documents app).
    """
    if not by_employee.is_employee() and not by_employee.is_admin_user():
        raise PermissionDenied("Only employees or admins can complete requests.")

    if not service_request.can_transition_to(ServiceRequest.Status.COMPLETED):
        raise ValidationError(
            f"Cannot complete a request with status '{service_request.get_status_display()}'. "
            f"Only ASSIGNED requests can be completed."
        )

    if service_request.assigned_to_id != by_employee.id and not by_employee.is_admin_user():
        raise PermissionDenied("You can only complete requests that are assigned to you.")

    if document is None:
        raise ValidationError("A confirmation document must be uploaded to complete a request.")

    from_status = service_request.status
    service_request.status = ServiceRequest.Status.COMPLETED
    service_request.completed_at = timezone.now()
    service_request.save(update_fields=['status', 'completed_at'])
    _record_history(service_request, from_status, ServiceRequest.Status.COMPLETED, by_employee)
    return service_request


# ──────────────────────────────────────────────
# Querysets  (role-filtered per CLAUDE.md)
# ──────────────────────────────────────────────

def get_requests_for_user(user):
    """Return requests the user is allowed to see based on their role."""
    qs = (
        ServiceRequest.objects
        .select_related('client', 'service', 'assigned_to')
        .prefetch_related('status_history')
    )
    if user.is_client():
        return qs.filter(client=user)
    elif user.is_employee():
        return qs.filter(assigned_to=user)
    elif user.is_admin_user():
        return qs.all()
    return ServiceRequest.objects.none()


def get_request_detail(request_id: int, user) -> ServiceRequest:
    """Fetch a single request visible to the user (raises if unauthorized)."""
    qs = get_requests_for_user(user)
    return qs.get(pk=request_id)


def get_pending_requests():
    """All unassigned PENDING requests for admin dashboard."""
    return (
        ServiceRequest.objects
        .filter(status=ServiceRequest.Status.PENDING)
        .select_related('client', 'service')
        .order_by('created_at')
    )


def get_employees_for_assignment():
    """Active employees available for request assignment."""
    return User.objects.filter(role=User.Role.EMPLOYEE, is_active=True).order_by('first_name', 'last_name')
