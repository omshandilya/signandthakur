"""Documents business services.

Implements file validation, secure upload handling with request completion,
and role-based download permissions per CLAUDE.md and business rules.
"""

import os
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.requests.models import ServiceRequest
from apps.requests.services import complete_request
from .models import Document


def validate_document_file(uploaded_file):
    """Validate uploaded document extension and size.

    Rules:
    - Allowed extensions: PDF and images (.pdf, .jpg, .jpeg, .png, .webp).
    - Maximum size: 10 MB.
    """
    if not uploaded_file:
        raise ValidationError("No file was uploaded.")

    max_size = getattr(settings, 'MAX_UPLOAD_SIZE', 10 * 1024 * 1024)
    if uploaded_file.size > max_size:
        max_mb = max_size / (1024 * 1024)
        raise ValidationError(f"File size exceeds the maximum allowed limit of {max_mb:.0f} MB.")

    allowed_exts = getattr(
        settings,
        'ALLOWED_DOCUMENT_EXTENSIONS',
        ['.pdf', '.jpg', '.jpeg', '.png', '.webp']
    )
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in allowed_exts:
        formatted_exts = ", ".join(allowed_exts)
        raise ValidationError(
            f"Unsupported file format '{ext}'. Allowed file types are: {formatted_exts}."
        )


@transaction.atomic
def upload_confirmation_document(service_request: ServiceRequest, uploaded_file, employee_user) -> Document:
    """Upload a confirmation document for a service request.

    Rules:
    - Only the assigned employee (or admin) can upload.
    - Request must be in ASSIGNED or COMPLETED status.
    - If request is ASSIGNED, uploading completes the request via complete_request().
    - If request is already COMPLETED, re-upload adds a new Document version.
    """
    if not employee_user.is_employee() and not employee_user.is_admin_user():
        raise PermissionDenied("Only staff employees or administrators can upload confirmation documents.")

    if service_request.status == ServiceRequest.Status.PENDING:
        raise ValidationError("Cannot upload confirmation documents for a pending, unassigned request.")

    if service_request.assigned_to_id != employee_user.id and not employee_user.is_admin_user():
        raise PermissionDenied("Only the assigned employee can upload documents for this request.")

    # Validate file size and type
    validate_document_file(uploaded_file)

    # Save document record
    document = Document(
        request=service_request,
        uploaded_by=employee_user,
        file=uploaded_file,
        original_name=uploaded_file.name,
        size=uploaded_file.size,
    )
    document.save()

    # Complete request if in ASSIGNED status
    if service_request.status == ServiceRequest.Status.ASSIGNED:
        complete_request(
            service_request=service_request,
            document=document,
            by_employee=employee_user,
        )

    return document


def can_user_download_document(user, document: Document) -> bool:
    """Check if the given user has permission to download this document.

    Rules:
    - Admin: can always download.
    - Assigned employee: can always download.
    - Client: can download ONLY if request.client == user AND request.status == COMPLETED.
    - Anyone else: denied.
    """
    if not user.is_authenticated:
        return False

    if user.is_admin_user():
        return True

    req = document.request
    if req.assigned_to_id == user.id:
        return True

    if req.client_id == user.id and req.status == ServiceRequest.Status.COMPLETED:
        return True

    return False


def get_latest_document_for_request(service_request: ServiceRequest) -> Document | None:
    """Return the latest uploaded confirmation document for this request, or None."""
    return service_request.documents.first()
