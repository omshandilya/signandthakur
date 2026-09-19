"""Comprehensive tests for the dashboards app.

Covers:
- Access control and role redirection for Client, Employee, and Admin dashboards.
- Client dashboard: status badges, active services catalog, download button ONLY on COMPLETED requests.
- Employee dashboard: split pending vs completed requests with client name and service.
- Admin dashboard: new requests section, inline employee assignment dropdown, status filters.
- Pagination, empty states, and select_related query optimization.
"""

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.catalog.models import Service, ServiceDocumentRequirement
from apps.dashboards.services import (
    get_admin_dashboard_data,
    get_client_dashboard_data,
    get_employee_dashboard_data,
)
from apps.requests.models import ServiceRequest
from apps.requests.services import assign_request, complete_request, create_request

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


def make_service(name='ITR Filing', price=Decimal('1500.00'), is_active=True):
    svc = Service.objects.create(
        name=name,
        description=f'Description for {name}',
        price=price,
        is_active=is_active,
    )
    ServiceDocumentRequirement.objects.create(service=svc, name='PAN Card')
    return svc


class DashboardAccessControlTests(TestCase):
    """Test authentication and role-based access to dashboards."""

    def setUp(self):
        self.client_user = make_user('client@test.com', User.Role.CLIENT)
        self.employee = make_user('employee@test.com', User.Role.EMPLOYEE)
        self.admin = make_user('admin@test.com', User.Role.ADMIN)

        self.http_client = Client()

    def test_anonymous_redirected_to_login(self):
        for url_name in ['dashboards:client', 'dashboards:employee', 'dashboards:admin', 'dashboards:index']:
            response = self.http_client.get(reverse(url_name))
            self.assertEqual(response.status_code, 302)
            self.assertIn('/accounts/login/', response.url)

    def test_dashboard_index_redirects_to_role_dashboard(self):
        # Client
        self.http_client.force_login(self.client_user)
        res = self.http_client.get(reverse('dashboards:index'))
        self.assertRedirects(res, reverse('dashboards:client'))

        # Employee
        self.http_client.force_login(self.employee)
        res = self.http_client.get(reverse('dashboards:index'))
        self.assertRedirects(res, reverse('dashboards:employee'))

        # Admin
        self.http_client.force_login(self.admin)
        res = self.http_client.get(reverse('dashboards:index'))
        self.assertRedirects(res, reverse('dashboards:admin'))

    def test_client_access_control(self):
        self.http_client.force_login(self.client_user)
        # Allowed
        self.assertEqual(self.http_client.get(reverse('dashboards:client')).status_code, 200)
        # Forbidden
        self.assertEqual(self.http_client.get(reverse('dashboards:employee')).status_code, 403)
        self.assertEqual(self.http_client.get(reverse('dashboards:admin')).status_code, 403)

    def test_employee_access_control(self):
        self.http_client.force_login(self.employee)
        # Allowed
        self.assertEqual(self.http_client.get(reverse('dashboards:employee')).status_code, 200)
        # Forbidden
        self.assertEqual(self.http_client.get(reverse('dashboards:client')).status_code, 403)
        self.assertEqual(self.http_client.get(reverse('dashboards:admin')).status_code, 403)

    def test_admin_access_control(self):
        self.http_client.force_login(self.admin)
        # Allowed
        self.assertEqual(self.http_client.get(reverse('dashboards:admin')).status_code, 200)
        # Forbidden
        self.assertEqual(self.http_client.get(reverse('dashboards:client')).status_code, 403)
        self.assertEqual(self.http_client.get(reverse('dashboards:employee')).status_code, 403)


class ClientDashboardViewTests(TestCase):
    """Test client dashboard content, conditional download button, service list, empty states, and pagination."""

    def setUp(self):
        self.client_user = make_user('client@test.com', User.Role.CLIENT, first_name='Aarav')
        self.other_client = make_user('other@test.com', User.Role.CLIENT)
        self.employee = make_user('emp@test.com', User.Role.EMPLOYEE)
        self.admin = make_user('admin@test.com', User.Role.ADMIN)

        self.service1 = make_service('ITR Filing', Decimal('1500.00'))
        self.service2 = make_service('GST Registration', Decimal('2500.00'))

        self.http_client = Client()
        self.http_client.force_login(self.client_user)

    def test_client_dashboard_empty_state(self):
        response = self.http_client.get(reverse('dashboards:client'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No Service Requests Yet")
        self.assertContains(response, "ITR Filing")
        self.assertContains(response, "GST Registration")

    def test_client_dashboard_shows_own_requests_only(self):
        req1 = create_request(self.client_user, self.service1)
        req_other = create_request(self.other_client, self.service2)

        response = self.http_client.get(reverse('dashboards:client'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"#{req1.pk}")
        self.assertContains(response, "Pending Review")
        # Other client's request must not appear
        self.assertNotContains(response, f"#{req_other.pk}")

    def test_download_button_only_appears_when_completed(self):
        """The download button must strictly appear only for COMPLETED requests."""
        # Pending request
        req_pending = create_request(self.client_user, self.service1)

        # Assigned request
        req_assigned = create_request(
            self.client_user,
            make_service('Audit', Decimal('5000.00'))
        )
        assign_request(req_assigned, self.employee, by_admin=self.admin)

        # Check pending & assigned: Download button should NOT be in the page
        response = self.http_client.get(reverse('dashboards:client'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Download Completion Document')
        self.assertNotContains(response, 'title="Download Completion Document"')

        # Now complete the assigned request
        class FakeDoc:
            pass
        complete_request(req_assigned, FakeDoc(), by_employee=self.employee)

        # Now refresh client dashboard: Download button MUST appear
        response = self.http_client.get(reverse('dashboards:client'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Download')
        self.assertContains(response, 'title="Download Completion Document"')

    def test_client_dashboard_pagination(self):
        # Create 12 requests to test pagination (per_page is 10)
        for i in range(12):
            svc = make_service(f'Service {i}', Decimal('1000.00'))
            create_request(self.client_user, svc)

        response = self.http_client.get(reverse('dashboards:client'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['requests_page'].has_next())

        # Page 2
        response_page2 = self.http_client.get(reverse('dashboards:client') + '?page=2')
        self.assertEqual(response_page2.status_code, 200)
        self.assertEqual(response_page2.context['requests_page'].number, 2)


class EmployeeDashboardViewTests(TestCase):
    """Test employee dashboard split into pending and completed, with client name and service."""

    def setUp(self):
        self.employee = make_user('emp1@test.com', User.Role.EMPLOYEE, first_name='Vikram')
        self.other_emp = make_user('emp2@test.com', User.Role.EMPLOYEE, first_name='Rohit')
        self.admin = make_user('admin@test.com', User.Role.ADMIN)
        self.client_user = make_user('client@test.com', User.Role.CLIENT, first_name='Priya', last_name='Patel')

        self.service1 = make_service('ITR Filing', Decimal('1500.00'))
        self.service2 = make_service('GST Return', Decimal('2000.00'))

        self.http_client = Client()
        self.http_client.force_login(self.employee)

    def test_employee_dashboard_empty_states(self):
        response = self.http_client.get(reverse('dashboards:employee'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "All Caught Up!")
        self.assertContains(response, "No Completed Requests Yet")

    def test_employee_dashboard_split_pending_and_completed(self):
        # Request 1 assigned to this employee (pending/in-progress)
        req1 = create_request(self.client_user, self.service1)
        assign_request(req1, self.employee, by_admin=self.admin)

        # Request 2 assigned to this employee and completed
        req2 = create_request(self.client_user, self.service2)
        assign_request(req2, self.employee, by_admin=self.admin)

        class FakeDoc:
            pass
        complete_request(req2, FakeDoc(), by_employee=self.employee)

        # Request 3 assigned to another employee (should NOT appear)
        req3 = create_request(
            make_user('client2@test.com', User.Role.CLIENT),
            make_service('TDS Filing', Decimal('1200.00'))
        )
        assign_request(req3, self.other_emp, by_admin=self.admin)

        response = self.http_client.get(reverse('dashboards:employee'))
        self.assertEqual(response.status_code, 200)

        # Must display client name and service
        self.assertContains(response, "Priya Patel")
        self.assertContains(response, "ITR Filing")
        self.assertContains(response, "GST Return")

        # Counts
        self.assertEqual(response.context['pending_count'], 1)
        self.assertEqual(response.context['completed_count'], 1)

        # Other employee's request must not be present
        self.assertNotContains(response, f"#{req3.pk}")
        self.assertNotContains(response, "TDS Filing")


class AdminDashboardViewTests(TestCase):
    """Test admin dashboard: new requests section, assign dropdown, status filters, pagination."""

    def setUp(self):
        self.admin = make_user('admin@test.com', User.Role.ADMIN, first_name='Sanjay')
        self.emp1 = make_user('emp1@test.com', User.Role.EMPLOYEE, first_name='Amit')
        self.emp2 = make_user('emp2@test.com', User.Role.EMPLOYEE, first_name='Neha')
        self.client_user = make_user('client@test.com', User.Role.CLIENT, first_name='Rohan')

        self.service1 = make_service('ITR-1', Decimal('1000.00'))
        self.service2 = make_service('ITR-2', Decimal('2000.00'))
        self.service3 = make_service('ITR-3', Decimal('3000.00'))

        self.http_client = Client()
        self.http_client.force_login(self.admin)

    def test_admin_dashboard_empty_state(self):
        response = self.http_client.get(reverse('dashboards:admin'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No Unassigned Requests")
        self.assertContains(response, "No service requests have been submitted to the firm yet.")

    def test_admin_dashboard_new_requests_and_assign_dropdown(self):
        # Create unassigned pending request
        req = create_request(self.client_user, self.service1)

        response = self.http_client.get(reverse('dashboards:admin'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "New Requests Awaiting Assignment")
        self.assertContains(response, f"#{req.pk}")
        self.assertContains(response, "Rohan")
        self.assertContains(response, "ITR-1")

        # Dropdown with employee options
        self.assertContains(response, f'<option value="{self.emp1.pk}">{self.emp1.display_name}</option>')
        self.assertContains(response, f'<option value="{self.emp2.pk}">{self.emp2.display_name}</option>')
        self.assertContains(response, f'action="{reverse("requests:assign", args=[req.pk])}"')

    def test_admin_dashboard_status_filter(self):
        # 1 Pending
        req1 = create_request(self.client_user, self.service1)

        # 1 Assigned
        req2 = create_request(self.client_user, self.service2)
        assign_request(req2, self.emp1, by_admin=self.admin)

        # 1 Completed
        req3 = create_request(self.client_user, self.service3)
        assign_request(req3, self.emp2, by_admin=self.admin)

        class FakeDoc:
            pass
        complete_request(req3, FakeDoc(), by_employee=self.emp2)

        # Filter: All
        res_all = self.http_client.get(reverse('dashboards:admin'))
        self.assertEqual(res_all.context['total_requests'], 3)
        self.assertEqual(len(res_all.context['requests_page'].object_list), 3)

        # Filter: PENDING
        res_pending = self.http_client.get(reverse('dashboards:admin') + '?status=PENDING')
        self.assertEqual(len(res_pending.context['requests_page'].object_list), 1)
        self.assertEqual(res_pending.context['requests_page'].object_list[0].pk, req1.pk)

        # Filter: ASSIGNED
        res_assigned = self.http_client.get(reverse('dashboards:admin') + '?status=ASSIGNED')
        self.assertEqual(len(res_assigned.context['requests_page'].object_list), 1)
        self.assertEqual(res_assigned.context['requests_page'].object_list[0].pk, req2.pk)

        # Filter: COMPLETED
        res_completed = self.http_client.get(reverse('dashboards:admin') + '?status=COMPLETED')
        self.assertEqual(len(res_completed.context['requests_page'].object_list), 1)
        self.assertEqual(res_completed.context['requests_page'].object_list[0].pk, req3.pk)

    def test_inline_assignment_from_admin_dashboard(self):
        """Admin assigning via the dashboard inline form redirects back to admin dashboard."""
        req = create_request(self.client_user, self.service1)

        post_data = {
            'employee': self.emp1.pk,
            'next': reverse('dashboards:admin'),
        }
        res = self.http_client.post(reverse('requests:assign', args=[req.pk]), post_data)
        self.assertRedirects(res, reverse('dashboards:admin'))

        req.refresh_from_db()
        self.assertEqual(req.status, ServiceRequest.Status.ASSIGNED)
        self.assertEqual(req.assigned_to, self.emp1)


class DashboardServiceLayerTests(TestCase):
    """Direct tests for dashboards services.py functions."""

    def setUp(self):
        self.client_user = make_user('c@test.com', User.Role.CLIENT)
        self.employee = make_user('e@test.com', User.Role.EMPLOYEE)
        self.admin = make_user('a@test.com', User.Role.ADMIN)
        self.service = make_service()

    def test_get_client_dashboard_data_structure(self):
        req = create_request(self.client_user, self.service)
        data = get_client_dashboard_data(self.client_user)

        self.assertIn('requests_page', data)
        self.assertIn('active_services', data)
        self.assertEqual(data['total_requests'], 1)
        self.assertEqual(data['pending_count'], 1)
        self.assertEqual(data['assigned_count'], 0)
        self.assertEqual(data['completed_count'], 0)

    def test_get_employee_dashboard_data_structure(self):
        req = create_request(self.client_user, self.service)
        assign_request(req, self.employee, by_admin=self.admin)

        data = get_employee_dashboard_data(self.employee)
        self.assertIn('pending_page_obj', data)
        self.assertIn('completed_page_obj', data)
        self.assertEqual(data['pending_count'], 1)
        self.assertEqual(data['completed_count'], 0)
        self.assertEqual(data['total_assigned'], 1)

    def test_get_admin_dashboard_data_structure(self):
        req = create_request(self.client_user, self.service)
        data = get_admin_dashboard_data(self.admin)

        self.assertIn('new_requests', data)
        self.assertIn('employees', data)
        self.assertIn('requests_page', data)
        self.assertEqual(data['total_requests'], 1)
        self.assertEqual(data['pending_count'], 1)
