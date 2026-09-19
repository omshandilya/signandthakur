"""Comprehensive tests for the documents application.

Covers:
- Document model, random filename generation, size formatting.
- File validation: max size (10 MB), allowed extensions (PDF, images), rejection of disallowed extensions.
- Upload permissions: only assigned employee (or admin) can upload; client and unassigned employee denied.
- Upload effect: completes request via complete_request(), status transitions from ASSIGNED to COMPLETED.
- Re-upload: adds a new Document version, client gets latest.
- Download permissions:
  - Request client CAN download when COMPLETED.
  - Request client CANNOT download when not COMPLETED.
  - Another client CANNOT download someone else's file (403 Forbidden).
  - Assigned employee CAN download.
  - Another employee CANNOT download (403 Forbidden).
  - Admin CAN always download.
- Streaming: FileResponse with original_name attachment.
"""

import os
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import FileResponse
from django.test import Client, TestCase
from django.urls import reverse

from apps.catalog.models import Service
from apps.documents.models import Document
from apps.documents.services import (
    can_user_download_document,
    get_latest_document_for_request,
    upload_confirmation_document,
    validate_document_file,
)
from apps.requests.models import ServiceRequest
from apps.requests.services import assign_request, create_request

User = get_user_model()


def make_user(email, role, first_name='Test', last_name='User'):
    return User.objects.create_user(
        username=email,
        email=email,
        password='TestPassword123!',
        role=role,
        first_name=first_name,
        last_name=last_name,
    )


def make_service(name='ITR Filing', price=Decimal('1500.00')):
    return Service.objects.create(
        name=name,
        description=f'Description for {name}',
        price=price,
        is_active=True,
    )


def make_sample_pdf(name='tax_return_ack.pdf', content=b'%PDF-1.4 sample pdf content'):
    return SimpleUploadedFile(name, content, content_type='application/pdf')


def make_sample_image(name='receipt.png', content=b'\x89PNG\r\n\x1a\n fake image content'):
    return SimpleUploadedFile(name, content, content_type='image/png')


class DocumentModelTests(TestCase):
    """Test Document model creation, random filenames, and string representation."""

    def setUp(self):
        self.client_user = make_user('client@test.com', User.Role.CLIENT)
        self.employee = make_user('emp@test.com', User.Role.EMPLOYEE)
        self.admin = make_user('admin@test.com', User.Role.ADMIN)
        self.service = make_service()

        self.req = create_request(self.client_user, self.service)
        assign_request(self.req, self.employee, by_admin=self.admin)

    def test_random_file_name_used_on_disk(self):
        """File name on disk must be a random UUID and never the user's original name."""
        original_name = "secret_client_file_v1.pdf"
        file = make_sample_pdf(original_name)

        doc = upload_confirmation_document(self.req, file, self.employee)

        # Original name preserved in model field
        self.assertEqual(doc.original_name, original_name)

        # File name on disk must NOT contain the original name
        disk_filename = os.path.basename(doc.file.name)
        self.assertNotIn('secret_client_file', disk_filename)
        self.assertTrue(disk_filename.endswith('.pdf'))
        # Must be in confirmation_docs directory
        self.assertTrue(doc.file.name.startswith('confirmation_docs'))

    def test_formatted_size_helper(self):
        file = make_sample_pdf('doc.pdf', content=b'a' * 2048)
        doc = upload_confirmation_document(self.req, file, self.employee)
        self.assertIn('KB', doc.formatted_size)

        large_doc = Document(original_name='large.pdf', size=2 * 1024 * 1024)
        self.assertEqual(large_doc.formatted_size, '2.00 MB')

        small_doc = Document(original_name='small.pdf', size=500)
        self.assertEqual(small_doc.formatted_size, '500 B')


class DocumentValidationTests(TestCase):
    """Test file type and max size validation."""

    def test_accepts_valid_pdf_and_images(self):
        for name in ['report.pdf', 'scan.jpg', 'filing.jpeg', 'doc.png', 'cert.webp']:
            file = SimpleUploadedFile(name, b'valid content', content_type='application/octet-stream')
            try:
                validate_document_file(file)
            except ValidationError:
                self.fail(f"validate_document_file unexpectedly rejected valid file '{name}'")

    def test_rejects_disallowed_file_types(self):
        for name in ['script.exe', 'macro.docx', 'data.csv', 'archive.zip', 'text.txt']:
            file = SimpleUploadedFile(name, b'content', content_type='application/octet-stream')
            with self.assertRaises(ValidationError) as ctx:
                validate_document_file(file)
            self.assertIn('Unsupported file format', str(ctx.exception))

    def test_rejects_file_exceeding_10mb(self):
        # 11 MB fake file
        large_size = 11 * 1024 * 1024
        file = SimpleUploadedFile('huge.pdf', b'x', content_type='application/pdf')
        file.size = large_size

        with self.assertRaises(ValidationError) as ctx:
            validate_document_file(file)
        self.assertIn('exceeds the maximum allowed limit', str(ctx.exception))


class DocumentUploadServiceTests(TestCase):
    """Test upload business logic and state transitions."""

    def setUp(self):
        self.client_user = make_user('client@test.com', User.Role.CLIENT)
        self.other_client = make_user('other_client@test.com', User.Role.CLIENT)
        self.employee = make_user('emp@test.com', User.Role.EMPLOYEE)
        self.other_employee = make_user('other_emp@test.com', User.Role.EMPLOYEE)
        self.admin = make_user('admin@test.com', User.Role.ADMIN)

        self.service = make_service()
        self.req = create_request(self.client_user, self.service)

    def test_cannot_upload_for_pending_request(self):
        """Cannot upload confirmation documents for a pending (unassigned) request."""
        file = make_sample_pdf()
        with self.assertRaises(ValidationError) as ctx:
            upload_confirmation_document(self.req, file, self.employee)
        self.assertIn('Cannot upload confirmation documents for a pending', str(ctx.exception))

    def test_client_cannot_upload(self):
        """Clients must never be able to upload confirmation documents."""
        assign_request(self.req, self.employee, by_admin=self.admin)
        file = make_sample_pdf()
        with self.assertRaises(PermissionDenied):
            upload_confirmation_document(self.req, file, self.client_user)

    def test_unassigned_employee_cannot_upload(self):
        """Only the employee assigned to the request can upload."""
        assign_request(self.req, self.employee, by_admin=self.admin)
        file = make_sample_pdf()
        with self.assertRaises(PermissionDenied) as ctx:
            upload_confirmation_document(self.req, file, self.other_employee)
        self.assertIn('Only the assigned employee can upload', str(ctx.exception))

    def test_assigned_employee_upload_completes_request(self):
        """Uploading by the assigned employee marks request COMPLETED and sets timestamps."""
        assign_request(self.req, self.employee, by_admin=self.admin)
        self.assertEqual(self.req.status, ServiceRequest.Status.ASSIGNED)

        file = make_sample_pdf('acknowledgment.pdf')
        doc = upload_confirmation_document(self.req, file, self.employee)

        self.req.refresh_from_db()
        self.assertEqual(self.req.status, ServiceRequest.Status.COMPLETED)
        self.assertIsNotNone(self.req.completed_at)
        self.assertEqual(doc.request, self.req)
        self.assertEqual(doc.uploaded_by, self.employee)

        # Status history recorded
        latest_history = self.req.status_history.last()
        self.assertEqual(latest_history.from_status, ServiceRequest.Status.ASSIGNED)
        self.assertEqual(latest_history.to_status, ServiceRequest.Status.COMPLETED)
        self.assertEqual(latest_history.changed_by, self.employee)

    def test_reupload_adds_new_document_and_client_sees_latest(self):
        """Re-uploading adds a second Document version; get_latest_document returns the newest."""
        assign_request(self.req, self.employee, by_admin=self.admin)

        # First upload
        file1 = make_sample_pdf('v1.pdf', b'Version 1 content')
        doc1 = upload_confirmation_document(self.req, file1, self.employee)

        # Second upload (re-upload)
        file2 = make_sample_pdf('v2_revised.pdf', b'Version 2 revised content')
        doc2 = upload_confirmation_document(self.req, file2, self.employee)

        self.assertEqual(self.req.documents.count(), 2)
        latest_doc = get_latest_document_for_request(self.req)
        self.assertEqual(latest_doc.pk, doc2.pk)
        self.assertEqual(latest_doc.original_name, 'v2_revised.pdf')


class DocumentDownloadSecurityTests(TestCase):
    """Test secure role-based access to document downloads."""

    def setUp(self):
        self.client_user = make_user('client@test.com', User.Role.CLIENT)
        self.other_client = make_user('other_client@test.com', User.Role.CLIENT)
        self.employee = make_user('emp@test.com', User.Role.EMPLOYEE)
        self.other_employee = make_user('other_emp@test.com', User.Role.EMPLOYEE)
        self.admin = make_user('admin@test.com', User.Role.ADMIN)

        self.service = make_service()
        self.req = create_request(self.client_user, self.service)
        assign_request(self.req, self.employee, by_admin=self.admin)

        self.file = make_sample_pdf('final_filing.pdf')
        self.doc = upload_confirmation_document(self.req, self.file, self.employee)

        self.http_client = Client()

    def test_anonymous_redirected_to_login(self):
        response = self.http_client.get(reverse('documents:download', args=[self.doc.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_client_can_download_when_completed(self):
        """Owner client can download their confirmation document once request is COMPLETED."""
        self.http_client.force_login(self.client_user)
        response = self.http_client.get(reverse('documents:download', args=[self.doc.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response, FileResponse))
        self.assertIn('attachment; filename="final_filing.pdf"', response['Content-Disposition'])

    def test_other_client_cannot_download_someone_elses_file(self):
        """Another client is strictly denied (403) from downloading someone else's document."""
        self.http_client.force_login(self.other_client)
        response = self.http_client.get(reverse('documents:download', args=[self.doc.pk]))
        self.assertEqual(response.status_code, 403)

        # Also via latest endpoint
        response_latest = self.http_client.get(
            reverse('documents:download_request_latest', args=[self.req.pk])
        )
        self.assertEqual(response_latest.status_code, 403)

    def test_client_cannot_download_if_not_completed(self):
        """If request is not COMPLETED, client cannot download."""
        # Manually alter status to ASSIGNED for permission testing
        self.req.status = ServiceRequest.Status.ASSIGNED
        self.req.save()

        self.assertFalse(can_user_download_document(self.client_user, self.doc))

        self.http_client.force_login(self.client_user)
        response = self.http_client.get(reverse('documents:download', args=[self.doc.pk]))
        self.assertEqual(response.status_code, 403)

    def test_assigned_employee_can_download(self):
        """The employee assigned to the request can download."""
        self.http_client.force_login(self.employee)
        response = self.http_client.get(reverse('documents:download', args=[self.doc.pk]))
        self.assertEqual(response.status_code, 200)

    def test_other_employee_cannot_download(self):
        """An unassigned employee is denied from downloading."""
        self.http_client.force_login(self.other_employee)
        response = self.http_client.get(reverse('documents:download', args=[self.doc.pk]))
        self.assertEqual(response.status_code, 403)

    def test_admin_can_always_download(self):
        """Administrators can always download any document."""
        self.http_client.force_login(self.admin)
        response = self.http_client.get(reverse('documents:download', args=[self.doc.pk]))
        self.assertEqual(response.status_code, 200)

    def test_latest_document_download_endpoint(self):
        """Test the request-level latest download endpoint."""
        self.http_client.force_login(self.client_user)
        response = self.http_client.get(
            reverse('documents:download_request_latest', args=[self.req.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment; filename="final_filing.pdf"', response['Content-Disposition'])


class DocumentUploadViewTests(TestCase):
    """Test DocumentUploadView HTTP endpoint."""

    def setUp(self):
        self.client_user = make_user('client@test.com', User.Role.CLIENT)
        self.employee = make_user('emp@test.com', User.Role.EMPLOYEE)
        self.other_employee = make_user('other_emp@test.com', User.Role.EMPLOYEE)
        self.admin = make_user('admin@test.com', User.Role.ADMIN)

        self.service = make_service()
        self.req = create_request(self.client_user, self.service)
        assign_request(self.req, self.employee, by_admin=self.admin)

        self.http_client = Client()

    def test_client_cannot_post_to_upload_view(self):
        self.http_client.force_login(self.client_user)
        file = make_sample_pdf()
        response = self.http_client.post(
            reverse('documents:upload', args=[self.req.pk]),
            {'document_file': file}
        )
        self.assertEqual(response.status_code, 403)

    def test_assigned_employee_successful_post(self):
        self.http_client.force_login(self.employee)
        file = make_sample_pdf('completed_filing.pdf')
        response = self.http_client.post(
            reverse('documents:upload', args=[self.req.pk]),
            {'document_file': file}
        )
        self.assertRedirects(response, reverse('requests:detail', args=[self.req.pk]))

        self.req.refresh_from_db()
        self.assertEqual(self.req.status, ServiceRequest.Status.COMPLETED)
        self.assertEqual(self.req.documents.count(), 1)
