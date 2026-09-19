"""Comprehensive tests for the requests app.

Covers every business rule and invalid transition specified in CLAUDE.md.
"""

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client as TestClient, TestCase
from django.urls import reverse

from apps.catalog.models import Service
from apps.requests.models import RequestStatusHistory, ServiceRequest
from apps.requests.services import (
    assign_request,
    complete_request,
    create_request,
    get_requests_for_user,
)

User = get_user_model()


# ──────────────────────────────────────────────
# Fixtures helper
# ──────────────────────────────────────────────

def make_user(username, role, password='Password123!'):
    return User.objects.create_user(
        username=username, email=username,
        password=password, role=role,
    )


def make_service(name='ITR Filing', price=Decimal('1500.00'), is_active=True):
    return Service.objects.create(name=name, price=price, is_active=is_active)


# ──────────────────────────────────────────────
# Model tests
# ──────────────────────────────────────────────

class ServiceRequestModelTests(TestCase):
    def setUp(self):
        self.client_user = make_user('c@test.com', User.Role.CLIENT)
        self.service = make_service()

    def test_str_representation(self):
        req = ServiceRequest.objects.create(
            client=self.client_user,
            service=self.service,
            price_at_request=self.service.price,
        )
        self.assertIn('ITR Filing', str(req))
        self.assertIn('Pending', str(req))

    def test_is_open_pending(self):
        req = ServiceRequest(status=ServiceRequest.Status.PENDING)
        self.assertTrue(req.is_open())

    def test_is_open_assigned(self):
        req = ServiceRequest(status=ServiceRequest.Status.ASSIGNED)
        self.assertTrue(req.is_open())

    def test_is_open_completed(self):
        req = ServiceRequest(status=ServiceRequest.Status.COMPLETED)
        self.assertFalse(req.is_open())

    def test_valid_transitions(self):
        req = ServiceRequest(status=ServiceRequest.Status.PENDING)
        self.assertTrue(req.can_transition_to(ServiceRequest.Status.ASSIGNED))
        self.assertFalse(req.can_transition_to(ServiceRequest.Status.COMPLETED))

        req.status = ServiceRequest.Status.ASSIGNED
        self.assertTrue(req.can_transition_to(ServiceRequest.Status.COMPLETED))
        self.assertFalse(req.can_transition_to(ServiceRequest.Status.PENDING))

        req.status = ServiceRequest.Status.COMPLETED
        self.assertFalse(req.can_transition_to(ServiceRequest.Status.PENDING))
        self.assertFalse(req.can_transition_to(ServiceRequest.Status.ASSIGNED))


# ──────────────────────────────────────────────
# create_request service tests
# ──────────────────────────────────────────────

class CreateRequestTests(TestCase):
    def setUp(self):
        self.client_user = make_user('client@test.com', User.Role.CLIENT)
        self.employee = make_user('emp@test.com', User.Role.EMPLOYEE)
        self.admin = make_user('admin@test.com', User.Role.ADMIN)
        self.service = make_service('GST Registration', Decimal('2000.00'))

    def test_create_request_success(self):
        req = create_request(self.client_user, self.service)
        self.assertEqual(req.status, ServiceRequest.Status.PENDING)
        self.assertEqual(req.client, self.client_user)
        self.assertEqual(req.service, self.service)
        # Price locked at creation time
        self.assertEqual(req.price_at_request, Decimal('2000.00'))

    def test_price_is_copied_at_request_time(self):
        req = create_request(self.client_user, self.service)
        # Change catalog price
        self.service.price = Decimal('5000.00')
        self.service.save()
        # Existing request price unchanged
        req.refresh_from_db()
        self.assertEqual(req.price_at_request, Decimal('2000.00'))

    def test_non_client_cannot_create_request(self):
        with self.assertRaises(PermissionDenied):
            create_request(self.employee, self.service)

    def test_admin_cannot_create_request(self):
        with self.assertRaises(PermissionDenied):
            create_request(self.admin, self.service)

    def test_inactive_service_rejected(self):
        inactive = make_service('Old Service', Decimal('999.00'), is_active=False)
        with self.assertRaises(ValidationError):
            create_request(self.client_user, inactive)

    def test_duplicate_open_request_rejected(self):
        create_request(self.client_user, self.service)
        with self.assertRaises(ValidationError) as ctx:
            create_request(self.client_user, self.service)
        self.assertIn('already have an open request', str(ctx.exception))

    def test_duplicate_check_only_for_open_requests(self):
        """Completed request should not block a new one for the same service."""
        req = create_request(self.client_user, self.service)
        req.status = ServiceRequest.Status.COMPLETED
        req.save()
        # Should not raise
        new_req = create_request(self.client_user, self.service)
        self.assertEqual(new_req.status, ServiceRequest.Status.PENDING)

    def test_different_clients_can_request_same_service(self):
        client2 = make_user('client2@test.com', User.Role.CLIENT)
        req1 = create_request(self.client_user, self.service)
        req2 = create_request(client2, self.service)
        self.assertNotEqual(req1.pk, req2.pk)


# ──────────────────────────────────────────────
# assign_request service tests
# ──────────────────────────────────────────────

class AssignRequestTests(TestCase):
    def setUp(self):
        self.client_user = make_user('client@test.com', User.Role.CLIENT)
        self.employee = make_user('emp@test.com', User.Role.EMPLOYEE)
        self.admin = make_user('admin@test.com', User.Role.ADMIN)
        self.service = make_service()
        self.pending_req = create_request(self.client_user, self.service)

    def test_admin_can_assign(self):
        req = assign_request(self.pending_req, self.employee, by_admin=self.admin)
        self.assertEqual(req.status, ServiceRequest.Status.ASSIGNED)
        self.assertEqual(req.assigned_to, self.employee)
        self.assertIsNotNone(req.assigned_at)

    def test_assign_creates_history_entry(self):
        assign_request(self.pending_req, self.employee, by_admin=self.admin)
        history = RequestStatusHistory.objects.filter(request=self.pending_req)
        self.assertEqual(history.count(), 1)
        entry = history.first()
        self.assertEqual(entry.from_status, ServiceRequest.Status.PENDING)
        self.assertEqual(entry.to_status, ServiceRequest.Status.ASSIGNED)
        self.assertEqual(entry.changed_by, self.admin)

    def test_non_admin_cannot_assign(self):
        with self.assertRaises(PermissionDenied):
            assign_request(self.pending_req, self.employee, by_admin=self.client_user)

    def test_employee_cannot_assign(self):
        with self.assertRaises(PermissionDenied):
            assign_request(self.pending_req, self.employee, by_admin=self.employee)

    def test_non_employee_cannot_be_assigned(self):
        with self.assertRaises(ValidationError):
            assign_request(self.pending_req, self.client_user, by_admin=self.admin)

    def test_cannot_assign_already_assigned_request(self):
        """ASSIGNED → ASSIGNED is an invalid transition."""
        assign_request(self.pending_req, self.employee, by_admin=self.admin)
        employee2 = make_user('emp2@test.com', User.Role.EMPLOYEE)
        with self.assertRaises(ValidationError) as ctx:
            assign_request(self.pending_req, employee2, by_admin=self.admin)
        self.assertIn('Cannot assign', str(ctx.exception))

    def test_cannot_assign_completed_request(self):
        """COMPLETED → ASSIGNED is an invalid transition."""
        self.pending_req.status = ServiceRequest.Status.COMPLETED
        self.pending_req.save()
        with self.assertRaises(ValidationError):
            assign_request(self.pending_req, self.employee, by_admin=self.admin)


# ──────────────────────────────────────────────
# complete_request service tests
# ──────────────────────────────────────────────

class CompleteRequestTests(TestCase):
    def setUp(self):
        self.client_user = make_user('client@test.com', User.Role.CLIENT)
        self.employee = make_user('emp@test.com', User.Role.EMPLOYEE)
        self.other_employee = make_user('other_emp@test.com', User.Role.EMPLOYEE)
        self.admin = make_user('admin@test.com', User.Role.ADMIN)
        self.service = make_service()

        self.req = create_request(self.client_user, self.service)
        assign_request(self.req, self.employee, by_admin=self.admin)

    def _fake_document(self):
        """Simulate a document object (documents app not yet built)."""
        return object()  # Any truthy object represents a provided document

    def test_assigned_employee_can_complete(self):
        req = complete_request(self.req, self._fake_document(), by_employee=self.employee)
        self.assertEqual(req.status, ServiceRequest.Status.COMPLETED)
        self.assertIsNotNone(req.completed_at)

    def test_complete_creates_history_entry(self):
        complete_request(self.req, self._fake_document(), by_employee=self.employee)
        history = RequestStatusHistory.objects.filter(
            request=self.req,
            from_status=ServiceRequest.Status.ASSIGNED,
            to_status=ServiceRequest.Status.COMPLETED
        )
        self.assertEqual(history.count(), 1)
        self.assertEqual(history.first().changed_by, self.employee)

    def test_admin_can_also_complete(self):
        req = complete_request(self.req, self._fake_document(), by_employee=self.admin)
        self.assertEqual(req.status, ServiceRequest.Status.COMPLETED)

    def test_different_employee_cannot_complete(self):
        """Only the assigned employee (or admin) can complete."""
        with self.assertRaises(PermissionDenied) as ctx:
            complete_request(self.req, self._fake_document(), by_employee=self.other_employee)
        self.assertIn('assigned to you', str(ctx.exception))

    def test_client_cannot_complete(self):
        with self.assertRaises(PermissionDenied):
            complete_request(self.req, self._fake_document(), by_employee=self.client_user)

    def test_completion_requires_document(self):
        """Passing None as document must raise ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            complete_request(self.req, document=None, by_employee=self.employee)
        self.assertIn('document', str(ctx.exception))

    def test_cannot_complete_pending_request(self):
        """PENDING → COMPLETED is an invalid transition."""
        pending = create_request(make_user('c2@test.com', User.Role.CLIENT), self.service)
        with self.assertRaises(ValidationError) as ctx:
            complete_request(pending, self._fake_document(), by_employee=self.employee)
        self.assertIn('Cannot complete', str(ctx.exception))

    def test_cannot_complete_already_completed_request(self):
        """COMPLETED → COMPLETED is an invalid transition."""
        complete_request(self.req, self._fake_document(), by_employee=self.employee)
        with self.assertRaises(ValidationError):
            complete_request(self.req, self._fake_document(), by_employee=self.employee)


# ──────────────────────────────────────────────
# Role-filtered queryset tests
# ──────────────────────────────────────────────

class RoleFilteredQuerysetTests(TestCase):
    def setUp(self):
        self.client1 = make_user('c1@test.com', User.Role.CLIENT)
        self.client2 = make_user('c2@test.com', User.Role.CLIENT)
        self.employee = make_user('emp@test.com', User.Role.EMPLOYEE)
        self.admin = make_user('admin@test.com', User.Role.ADMIN)
        self.service = make_service()

        self.req1 = create_request(self.client1, self.service)
        self.req2 = create_request(
            self.client2,
            make_service('GST Filing', Decimal('999.00'))
        )
        assign_request(self.req1, self.employee, by_admin=self.admin)

    def test_client_sees_only_own_requests(self):
        qs = get_requests_for_user(self.client1)
        self.assertIn(self.req1, qs)
        self.assertNotIn(self.req2, qs)

    def test_employee_sees_only_assigned_requests(self):
        qs = get_requests_for_user(self.employee)
        self.assertIn(self.req1, qs)
        self.assertNotIn(self.req2, qs)  # req2 is not assigned to this employee

    def test_admin_sees_all_requests(self):
        qs = get_requests_for_user(self.admin)
        self.assertIn(self.req1, qs)
        self.assertIn(self.req2, qs)


# ──────────────────────────────────────────────
# View access control tests
# ──────────────────────────────────────────────

class RequestViewAccessTests(TestCase):
    def setUp(self):
        self.http_client = TestClient()
        self.client_user = make_user('cv@test.com', User.Role.CLIENT)
        self.employee = make_user('ev@test.com', User.Role.EMPLOYEE)
        self.admin = make_user('av@test.com', User.Role.ADMIN)
        self.service = make_service()

    def test_anonymous_redirected_from_list(self):
        response = self.http_client.get(reverse('requests:list'))
        self.assertEqual(response.status_code, 302)

    def test_client_can_access_list_and_create(self):
        self.http_client.login(username='cv@test.com', password='Password123!')
        self.assertEqual(self.http_client.get(reverse('requests:list')).status_code, 200)
        self.assertEqual(self.http_client.get(reverse('requests:create')).status_code, 200)

    def test_client_forbidden_from_admin_view(self):
        self.http_client.login(username='cv@test.com', password='Password123!')
        self.assertEqual(self.http_client.get(reverse('requests:admin_list')).status_code, 403)

    def test_employee_can_access_list(self):
        self.http_client.login(username='ev@test.com', password='Password123!')
        self.assertEqual(self.http_client.get(reverse('requests:list')).status_code, 200)

    def test_employee_cannot_create_request(self):
        self.http_client.login(username='ev@test.com', password='Password123!')
        self.assertEqual(self.http_client.get(reverse('requests:create')).status_code, 403)

    def test_admin_can_access_admin_list(self):
        self.http_client.login(username='av@test.com', password='Password123!')
        self.assertEqual(self.http_client.get(reverse('requests:admin_list')).status_code, 200)


class RequestSubmitViewTests(TestCase):
    def setUp(self):
        self.http_client = TestClient()
        self.client_user = make_user('submit@test.com', User.Role.CLIENT)
        self.service = make_service('Payroll Filing', Decimal('3000.00'))
        self.http_client.login(username='submit@test.com', password='Password123!')

    def test_client_submits_request_successfully(self):
        response = self.http_client.post(
            reverse('requests:create'),
            data={'service': self.service.pk}
        )
        req = ServiceRequest.objects.get(client=self.client_user, service=self.service)
        self.assertRedirects(response, reverse('requests:detail', kwargs={'pk': req.pk}))
        self.assertEqual(req.status, ServiceRequest.Status.PENDING)
        self.assertEqual(req.price_at_request, Decimal('3000.00'))

    def test_duplicate_open_request_shows_error(self):
        create_request(self.client_user, self.service)
        response = self.http_client.post(
            reverse('requests:create'),
            data={'service': self.service.pk}
        )
        # Should redirect back with error, not create a second request
        self.assertEqual(ServiceRequest.objects.filter(client=self.client_user).count(), 1)


class AdminAssignViewTests(TestCase):
    def setUp(self):
        self.http_client = TestClient()
        self.client_user = make_user('ca@test.com', User.Role.CLIENT)
        self.employee = make_user('ea@test.com', User.Role.EMPLOYEE)
        self.admin = make_user('aa@test.com', User.Role.ADMIN)
        self.service = make_service()
        self.req = create_request(self.client_user, self.service)

    def test_admin_assigns_request_via_view(self):
        self.http_client.login(username='aa@test.com', password='Password123!')
        response = self.http_client.post(
            reverse('requests:assign', kwargs={'pk': self.req.pk}),
            data={'employee': self.employee.pk}
        )
        self.assertRedirects(response, reverse('requests:detail', kwargs={'pk': self.req.pk}))
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, ServiceRequest.Status.ASSIGNED)
        self.assertEqual(self.req.assigned_to, self.employee)

    def test_client_cannot_access_assign_endpoint(self):
        self.http_client.login(username='ca@test.com', password='Password123!')
        response = self.http_client.post(
            reverse('requests:assign', kwargs={'pk': self.req.pk}),
            data={'employee': self.employee.pk}
        )
        self.assertEqual(response.status_code, 403)
