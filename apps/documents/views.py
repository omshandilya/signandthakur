"""Documents views.

Provides views for:
- Assigned employee uploading confirmation documents (completing the request).
- Secure role-protected streaming downloads.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from apps.accounts.permissions import RoleRequiredMixin
from apps.requests.models import ServiceRequest
from .forms import DocumentUploadForm
from .models import Document
from .services import (
    can_user_download_document,
    get_latest_document_for_request,
    upload_confirmation_document,
)


class DocumentUploadView(RoleRequiredMixin, View):
    """Assigned employee uploads confirmation document to complete a service request."""

    allowed_roles = ['EMPLOYEE', 'ADMIN']

    def post(self, request, request_pk):
        service_request = get_object_or_404(ServiceRequest, pk=request_pk)
        form = DocumentUploadForm(request.POST, request.FILES)

        if form.is_valid():
            try:
                document = upload_confirmation_document(
                    service_request=service_request,
                    uploaded_file=form.cleaned_data['document_file'],
                    employee_user=request.user,
                )
                messages.success(
                    request,
                    f"Confirmation document '{document.original_name}' uploaded successfully. "
                    f"Request #{request_pk} has been finalized."
                )
            except (ValidationError, PermissionDenied) as e:
                messages.error(request, str(e.message if hasattr(e, 'message') else e))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)

        next_url = request.POST.get('next')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect('requests:detail', pk=request_pk)


class DocumentDownloadView(LoginRequiredMixin, View):
    """Secure streaming download of a confirmation document by ID."""

    def get(self, request, pk):
        document = get_object_or_404(
            Document.objects.select_related('request'),
            pk=pk
        )

        if not can_user_download_document(request.user, document):
            raise PermissionDenied(
                "You do not have permission to download this document. "
                "Only the requesting client (for completed requests), assigned staff, and administrators may access it."
            )

        try:
            file_handle = document.file.open('rb')
        except (FileNotFoundError, OSError):
            raise Http404("Document file could not be found on storage.")

        return FileResponse(
            file_handle,
            as_attachment=True,
            filename=document.original_name,
        )


class LatestDocumentDownloadView(LoginRequiredMixin, View):
    """Download the latest confirmation document for a specific service request.

    Access rules:
    - Anonymous users are redirected to login.
    - Client owning the request: allowed only when request is COMPLETED.
    - Assigned employee: always allowed.
    - Admin: always allowed.
    - Everyone else (other clients, other employees): 404 (not 403, to prevent
      confirming the existence of another user's request).
    """

    def get(self, request, request_pk):
        service_request = get_object_or_404(ServiceRequest, pk=request_pk)
        document = get_latest_document_for_request(service_request)

        if not document:
            raise Http404("No confirmation document has been uploaded for this request.")

        if not can_user_download_document(request.user, document):
            raise PermissionDenied(
                "You do not have permission to download this document. "
                "Confirmation documents are only accessible to clients once the request is COMPLETED."
            )

        try:
            file_handle = document.file.open('rb')
        except (FileNotFoundError, OSError):
            raise Http404("Document file could not be found on storage.")

        return FileResponse(
            file_handle,
            as_attachment=True,
            filename=document.original_name,
        )
