"""Security regression tests for access-control gaps across the CA firm portal.

Tests every identified gap:
1. Client ID guessing on request detail — other client gets 404.
2. Employee sees only their own assigned requests.
3. Admin-only URLs directly hit by client/employee return 403.
4. Open-redirect prevention on 'next' POST parameters.
5. AdminPasswordResetView cannot reset another admin's password (404).
6. LatestDocumentDownloadView returns 404 (not 403) for other clients
   so they cannot confirm existence of another client's request.
7. DocumentDownloadView direct pk access by other client returns 403.
8. Employee cannot upload for requests not assigned to them.
"""

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from apps.catalog.models import Service
from apps.documents.services import upload_confirmation_document
from apps.requests.models import ServiceRequest
from apps.requests.services import assign_request, create_request

User = get_user_model()


def make_user(email, role, first_name='Test', last_name='User'):
    return User.objects.create_user(
        username=email, email=email, password='TestPassword123!',
        role=role, first_name=first_name, last_name=last_name,
    )


def make_service(name='ITR Filing'):
    return Service.objects.create(
        name=name, description='Test service', price=Decimal('1500.00'), is_active=True
    )


def make_pdf(name='doc.pdf'):
    return SimpleUploadedFile(name, b'%PDF-1.4 test content', content_type='application/pdf')


class RequestDetailAccessControlTests(TestCase):
    """A client cannot see another client's request by guessing the ID."""

    def setUp(self):
        self.client1 = make_user('c1@test.com', User.Role.CLIENT, 'Alice')
        self.client2 = make_user('c2@test.com', User.Role.CLIENT, 'Bob')
        self.employee = make_user('emp@test.com', User.Role.EMPLOYEE)
        self.admin = make_user('admin@test.com', User.Role.ADMIN)
        self.service = make_service()

        self.req1 = create_request(self.client1, self.service)
        self.req2 = create_request(self.client2, make_service('GST Return'))

        self.http_client = Client()

    def test_client_cannot_view_another_clients_request_by_id(self):
        """Accessing another client's request via URL ID returns 404."""
        self.http_client.force_login(self.client1)
        response = self.http_client.get(reverse('requests:detail', args=[self.req2.pk]))
        self.assertEqual(response.status_code, 404)

    def test_client_can_view_own_request(self):
        """Owning client can view their own request."""
        self.http_client.force_login(self.client1)
        response = self.http_client.get(reverse('requests:detail', args=[self.req1.pk]))
        self.assertEqual(response.status_code, 200)

    def test_employee_cannot_view_unassigned_request(self):
        """An employee can only view requests assigned to them."""
        assign_request(self.req1, self.employee, by_admin=self.admin)
        # req2 is NOT assigned to this employee
        self.http_client.force_login(self.employee)
        response = self.http_client.get(reverse('requests:detail', args=[self.req2.pk]))
        self.assertEqual(response.status_code, 404)

    def test_employee_can_view_assigned_request(self):
        """Employee can view a request that is assigned to them."""
        assign_request(self.req1, self.employee, by_admin=self.admin)
        self.http_client.force_login(self.employee)
        response = self.http_client.get(reverse('requests:detail', args=[self.req1.pk]))
        self.assertEqual(response.status_code, 200)

    def test_admin_can_view_any_request(self):
        """Admin can view any request regardless of ownership."""
        self.http_client.force_login(self.admin)
        self.assertEqual(
            self.http_client.get(reverse('requests:detail', args=[self.req1.pk])).status_code, 200
        )
        self.assertEqual(
            self.http_client.get(reverse('requests:detail', args=[self.req2.pk])).status_code, 200
        )


class RequestListIsolationTests(TestCase):
    """Queryset isolation — role-filtered lists."""

    def setUp(self):
        self.client1 = make_user('c1@test.com', User.Role.CLIENT)
        self.client2 = make_user('c2@test.com', User.Role.CLIENT)
        self.employee = make_user('emp@test.com', User.Role.EMPLOYEE)
        self.admin = make_user('admin@test.com', User.Role.ADMIN)
        self.service = make_service()

        self.req1 = create_request(self.client1, self.service)
        self.req2 = create_request(self.client2, make_service('GST'))
        assign_request(self.req1, self.employee, by_admin=self.admin)

        self.http_client = Client()

    def test_client_list_shows_only_own_requests(self):
        self.http_client.force_login(self.client1)
        response = self.http_client.get(reverse('requests:list'))
        self.assertEqual(response.status_code, 200)
        ids = [r.pk for r in response.context['requests']]
        self.assertIn(self.req1.pk, ids)
        self.assertNotIn(self.req2.pk, ids)

    def test_employee_list_shows_only_assigned_requests(self):
        self.http_client.force_login(self.employee)
        response = self.http_client.get(reverse('requests:list'))
        self.assertEqual(response.status_code, 200)
        ids = [r.pk for r in response.context['requests']]
        self.assertIn(self.req1.pk, ids)
        self.assertNotIn(self.req2.pk, ids)


class AdminOnlyURLsTests(TestCase):
    """Non-admin roles cannot directly access admin-only URLs."""

    def setUp(self):
        self.client_user = make_user('c@test.com', User.Role.CLIENT)
        self.employee = make_user('e@test.com', User.Role.EMPLOYEE)
        self.admin = make_user('a@test.com', User.Role.ADMIN)
        self.http_client = Client()

    def _assert_403(self, user, url):
        self.http_client.force_login(user)
        response = self.http_client.get(url)
        self.assertEqual(response.status_code, 403,
            f"Expected 403 for {user.role} on {url}, got {response.status_code}")

    def test_client_cannot_access_admin_request_list(self):
        self._assert_403(self.client_user, reverse('requests:admin_list'))

    def test_employee_cannot_access_admin_request_list(self):
        self._assert_403(self.employee, reverse('requests:admin_list'))

    def test_client_cannot_access_catalog_admin(self):
        self._assert_403(self.client_user, reverse('catalog:admin_list'))

    def test_employee_cannot_access_catalog_admin(self):
        self._assert_403(self.employee, reverse('catalog:admin_list'))

    def test_client_cannot_access_employee_list(self):
        self._assert_403(self.client_user, reverse('accounts:employee_list'))

    def test_employee_cannot_access_employee_list(self):
        self._assert_403(self.employee, reverse('accounts:employee_list'))

    def test_client_cannot_access_employee_create(self):
        self._assert_403(self.client_user, reverse('accounts:employee_create'))

    def test_employee_cannot_access_employee_create(self):
        self._assert_403(self.employee, reverse('accounts:employee_create'))

    def test_client_cannot_access_admin_dashboard(self):
        self._assert_403(self.client_user, reverse('dashboards:admin'))

    def test_employee_cannot_access_admin_dashboard(self):
        self._assert_403(self.employee, reverse('dashboards:admin'))

    def test_client_cannot_access_employee_dashboard(self):
        self._assert_403(self.client_user, reverse('dashboards:employee'))

    def test_admin_cannot_access_client_dashboard(self):
        self._assert_403(self.admin, reverse('dashboards:client'))


class AdminPasswordResetScopeTests(TestCase):
    """Admin can only reset passwords for non-admin users."""

    def setUp(self):
        self.admin1 = make_user('admin1@test.com', User.Role.ADMIN)
        self.admin2 = make_user('admin2@test.com', User.Role.ADMIN)
        self.employee = make_user('emp@test.com', User.Role.EMPLOYEE)
        self.http_client = Client()

    def test_admin_can_reset_employee_password(self):
        self.http_client.force_login(self.admin1)
        response = self.http_client.get(
            reverse('accounts:admin_password_reset', args=[self.employee.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_admin_cannot_reset_another_admins_password(self):
        """Admin cannot reset another admin's password — returns 404."""
        self.http_client.force_login(self.admin1)
        response = self.http_client.get(
            reverse('accounts:admin_password_reset', args=[self.admin2.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_admin_cannot_reset_own_password_via_this_endpoint(self):
        """Admin cannot reset their own password via admin reset endpoint."""
        self.http_client.force_login(self.admin1)
        response = self.http_client.get(
            reverse('accounts:admin_password_reset', args=[self.admin1.pk])
        )
        self.assertEqual(response.status_code, 404)


class OpenRedirectPreventionTests(TestCase):
    """The 'next' POST parameter must only redirect to internal paths."""

    def setUp(self):
        self.admin = make_user('admin@test.com', User.Role.ADMIN)
        self.employee = make_user('emp@test.com', User.Role.EMPLOYEE)
        self.client_user = make_user('c@test.com', User.Role.CLIENT)
        self.service = make_service()
        self.req = create_request(self.client_user, self.service)
        assign_request(self.req, self.employee, by_admin=self.admin)
        self.http_client = Client()

    def test_assign_next_external_url_not_followed(self):
        """External 'next' URL on assign must NOT redirect off-site."""
        self.http_client.force_login(self.admin)
        response = self.http_client.post(
            reverse('requests:assign', args=[self.req.pk]),
            {'employee': self.employee.pk, 'next': 'http://evil.com/steal'}
        )
        # Should redirect to the detail page, not evil.com
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('evil.com', response['Location'])

    def test_assign_next_internal_url_is_followed(self):
        """Internal relative 'next' URL on assign IS followed."""
        internal_url = reverse('dashboards:admin')
        self.http_client.force_login(self.admin)
        response = self.http_client.post(
            reverse('requests:assign', args=[self.req.pk]),
            {'employee': self.employee.pk, 'next': internal_url}
        )
        self.assertRedirects(response, internal_url)

    def test_document_upload_next_external_url_not_followed(self):
        """External 'next' URL on document upload must NOT redirect off-site."""
        self.http_client.force_login(self.employee)
        pdf = make_pdf()
        response = self.http_client.post(
            reverse('documents:upload', args=[self.req.pk]),
            {'document_file': pdf, 'next': 'http://evil.com/phish'}
        )
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('evil.com', response['Location'])


class DocumentAccessIsolationTests(TestCase):
    """Document access — other clients/employees are denied."""

    def setUp(self):
        self.client1 = make_user('c1@test.com', User.Role.CLIENT)
        self.client2 = make_user('c2@test.com', User.Role.CLIENT)
        self.employee = make_user('emp@test.com', User.Role.EMPLOYEE)
        self.other_employee = make_user('emp2@test.com', User.Role.EMPLOYEE)
        self.admin = make_user('admin@test.com', User.Role.ADMIN)

        self.service = make_service()
        self.req = create_request(self.client1, self.service)
        assign_request(self.req, self.employee, by_admin=self.admin)

        self.doc = upload_confirmation_document(self.req, make_pdf('filing.pdf'), self.employee)
        self.http_client = Client()

    def test_other_client_document_download_returns_403(self):
        """Direct document download by another client returns 403."""
        self.http_client.force_login(self.client2)
        response = self.http_client.get(reverse('documents:download', args=[self.doc.pk]))
        self.assertEqual(response.status_code, 403)

    def test_other_client_latest_document_download_returns_403(self):
        """LatestDocumentDownloadView returns 403 for other clients."""
        self.http_client.force_login(self.client2)
        response = self.http_client.get(
            reverse('documents:download_request_latest', args=[self.req.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_owner_client_can_download_when_completed(self):
        """Owning client gets 200 on their completed request document."""
        self.http_client.force_login(self.client1)
        response = self.http_client.get(reverse('documents:download', args=[self.doc.pk]))
        self.assertEqual(response.status_code, 200)

    def test_other_employee_cannot_download(self):
        """Unassigned employee cannot download (403)."""
        self.http_client.force_login(self.other_employee)
        response = self.http_client.get(reverse('documents:download', args=[self.doc.pk]))
        self.assertEqual(response.status_code, 403)

    def test_other_employee_cannot_upload_to_another_employees_request(self):
        """Unassigned employee gets 403 from the upload service layer."""
        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            upload_confirmation_document(self.req, make_pdf('v2.pdf'), self.other_employee)

    def test_owner_client_cannot_access_latest_if_not_completed(self):
        """Client cannot download via latest endpoint if request is still ASSIGNED (403)."""
        # Reset status to ASSIGNED for testing
        self.req.status = ServiceRequest.Status.ASSIGNED
        self.req.save()

        self.http_client.force_login(self.client1)
        response = self.http_client.get(
            reverse('documents:download_request_latest', args=[self.req.pk])
        )
        self.assertEqual(response.status_code, 403)
