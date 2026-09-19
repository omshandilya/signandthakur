from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.catalog.forms import ServiceForm
from apps.catalog.models import Service, ServiceDocumentRequirement
from apps.catalog.services import (
    add_document_requirement,
    create_service,
    delete_document_requirement,
    delete_service,
    get_active_services,
    get_all_services,
    get_service_by_id,
    update_service,
)

User = get_user_model()


class CatalogModelTests(TestCase):
    """Test Service and ServiceDocumentRequirement models."""

    def test_create_service(self):
        service = Service.objects.create(
            name='GST Registration',
            description='End-to-end GST registration support.',
            price=Decimal('1999.00'),
            is_active=True
        )
        self.assertEqual(str(service), 'GST Registration (₹1999.00)')
        self.assertTrue(service.is_active)

    def test_document_requirement_cascade_delete(self):
        service = Service.objects.create(
            name='Income Tax Return',
            price=Decimal('1499.00')
        )
        req1 = ServiceDocumentRequirement.objects.create(
            service=service,
            name='Form 16'
        )
        req2 = ServiceDocumentRequirement.objects.create(
            service=service,
            name='Bank Statement'
        )
        self.assertEqual(str(req1), 'Income Tax Return: Form 16')
        self.assertEqual(service.document_requirements.count(), 2)

        # Deleting service should cascade-delete its document requirements
        service.delete()
        self.assertEqual(ServiceDocumentRequirement.objects.count(), 0)


class CatalogServiceTests(TestCase):
    """Test business services in apps.catalog.services."""

    def setUp(self):
        self.service1 = create_service(
            name='Audit & Assurance',
            description='Statutory audits.',
            price=Decimal('15000.00'),
            is_active=True,
            requirements=['Balance Sheet', 'P&L Statement']
        )
        self.service2 = create_service(
            name='Company Incorporation',
            description='Private limited registration.',
            price=Decimal('8000.00'),
            is_active=False,
            requirements=['PAN Cards of Directors', 'Electricity Bill']
        )

    def test_get_active_services(self):
        active = get_active_services()
        self.assertIn(self.service1, active)
        self.assertNotIn(self.service2, active)
        self.assertEqual(active.count(), 1)

    def test_get_all_services(self):
        all_services = get_all_services()
        self.assertEqual(all_services.count(), 2)

    def test_create_service_with_requirements(self):
        service = create_service(
            name='Trademark Registration',
            description='Brand protection.',
            price=Decimal('4500.00'),
            is_active=True,
            requirements=['Logo file', 'Power of Attorney', '   ']  # whitespace ignored
        )
        self.assertEqual(service.document_requirements.count(), 2)
        req_names = list(service.document_requirements.values_list('name', flat=True))
        self.assertIn('Logo file', req_names)
        self.assertIn('Power of Attorney', req_names)

    def test_update_service(self):
        updated = update_service(self.service1, price=Decimal('18000.00'), is_active=False)
        self.assertEqual(updated.price, Decimal('18000.00'))
        self.assertFalse(updated.is_active)

    def test_delete_service(self):
        service_id = self.service2.id
        delete_service(self.service2)
        self.assertFalse(Service.objects.filter(id=service_id).exists())

    def test_add_and_delete_document_requirement(self):
        req = add_document_requirement(self.service1, 'GSTIN Certificate')
        self.assertEqual(req.name, 'GSTIN Certificate')
        self.assertEqual(self.service1.document_requirements.count(), 3)

        delete_document_requirement(req.id)
        self.assertEqual(self.service1.document_requirements.count(), 2)


class ClientCatalogViewTests(TestCase):
    """Test client-facing catalog view."""

    def setUp(self):
        self.client = Client()
        self.catalog_url = reverse('catalog:list')

        self.active_service = create_service(
            name='GST Return Filing',
            description='Monthly and quarterly GST return filing.',
            price=Decimal('999.00'),
            is_active=True,
            requirements=['Sales Invoices', 'Purchase Invoices']
        )
        self.inactive_service = create_service(
            name='Legacy Advisory Service',
            description='Discontinued advisory.',
            price=Decimal('5000.00'),
            is_active=False,
            requirements=['Historical Records']
        )

        self.client_user = User.objects.create_user(
            username='client_viewer@example.com',
            email='client_viewer@example.com',
            password='Password123!',
            role=User.Role.CLIENT
        )

    def test_catalog_accessible_publicly(self):
        response = self.client.get(self.catalog_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'catalog/service_list.html')
        self.assertContains(response, 'GST Return Filing')
        self.assertContains(response, '999.00')
        self.assertContains(response, 'Sales Invoices')
        self.assertContains(response, 'Purchase Invoices')
        # Inactive service must be hidden
        self.assertNotContains(response, 'Legacy Advisory Service')

    def test_catalog_shows_request_button_for_authenticated_client(self):
        self.client.login(username='client_viewer@example.com', password='Password123!')
        response = self.client.get(self.catalog_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Request This Service')
        self.assertContains(response, f'/requests/create/?service={self.active_service.id}')


class AdminCatalogAccessControlTests(TestCase):
    """Test role restrictions on admin catalog management pages."""

    def setUp(self):
        self.client = Client()
        self.service = create_service(
            name='Payroll Compliance',
            description='PF and ESI filings.',
            price=Decimal('3000.00'),
            is_active=True
        )

        self.client_user = User.objects.create_user(
            username='regular_client@test.com',
            email='regular_client@test.com',
            password='Password123!',
            role=User.Role.CLIENT
        )
        self.employee_user = User.objects.create_user(
            username='staff_member@test.com',
            email='staff_member@test.com',
            password='Password123!',
            role=User.Role.EMPLOYEE
        )
        self.admin_user = User.objects.create_user(
            username='firm_admin@test.com',
            email='firm_admin@test.com',
            password='Password123!',
            role=User.Role.ADMIN
        )

        self.admin_urls = [
            reverse('catalog:admin_list'),
            reverse('catalog:admin_create'),
            reverse('catalog:admin_edit', kwargs={'pk': self.service.pk}),
            reverse('catalog:admin_delete', kwargs={'pk': self.service.pk}),
        ]

    def test_anonymous_redirected_to_login(self):
        for url in self.admin_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, f"Failed for {url}")
            self.assertIn(reverse('accounts:login'), response.url)

    def test_client_denied_access(self):
        self.client.login(username='regular_client@test.com', password='Password123!')
        for url in self.admin_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403, f"Client should be 403 on {url}")

    def test_employee_denied_access(self):
        self.client.login(username='staff_member@test.com', password='Password123!')
        for url in self.admin_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403, f"Employee should be 403 on {url}")

    def test_admin_granted_access(self):
        self.client.login(username='firm_admin@test.com', password='Password123!')
        for url in self.admin_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"Admin should have access to {url}")


class AdminCatalogCRUDTests(TestCase):
    """Test admin CRUD actions: create, update, and delete services."""

    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username='ca_owner@test.com',
            email='ca_owner@test.com',
            password='Password123!',
            role=User.Role.ADMIN
        )
        self.client.login(username='ca_owner@test.com', password='Password123!')

    def test_admin_create_service_with_formset(self):
        payload = {
            'name': 'ROC Annual Filing',
            'description': 'Annual compliance filing with Registrar of Companies.',
            'price': '6500.00',
            'is_active': 'on',
            # Formset management form
            'document_requirements-TOTAL_FORMS': '2',
            'document_requirements-INITIAL_FORMS': '0',
            'document_requirements-MIN_NUM_FORMS': '0',
            'document_requirements-MAX_NUM_FORMS': '1000',
            # Requirement forms
            'document_requirements-0-name': 'Audited Financial Statements',
            'document_requirements-1-name': 'Directors Report',
        }
        response = self.client.post(reverse('catalog:admin_create'), data=payload)
        self.assertRedirects(response, reverse('catalog:admin_list'))

        service = Service.objects.get(name='ROC Annual Filing')
        self.assertEqual(service.price, Decimal('6500.00'))
        self.assertTrue(service.is_active)
        self.assertEqual(service.document_requirements.count(), 2)

    def test_admin_update_service_and_remove_requirement(self):
        service = create_service(
            name='TDS Return Filing',
            description='Quarterly TDS statement.',
            price=Decimal('1200.00'),
            is_active=True,
            requirements=['Challan Receipts', 'Deductee Details']
        )
        req1, req2 = list(service.document_requirements.all())

        payload = {
            'name': 'TDS Return Filing (Revised)',
            'description': 'Updated quarterly TDS filing.',
            'price': '1500.00',
            'is_active': 'on',
            # Formset management
            'document_requirements-TOTAL_FORMS': '2',
            'document_requirements-INITIAL_FORMS': '2',
            'document_requirements-MIN_NUM_FORMS': '0',
            'document_requirements-MAX_NUM_FORMS': '1000',
            # Keep req1
            'document_requirements-0-id': str(req1.id),
            'document_requirements-0-name': 'Challan Receipts & BSR Code',
            # Delete req2
            'document_requirements-1-id': str(req2.id),
            'document_requirements-1-name': req2.name,
            'document_requirements-1-DELETE': 'on',
        }
        url = reverse('catalog:admin_edit', kwargs={'pk': service.pk})
        response = self.client.post(url, data=payload)
        self.assertRedirects(response, reverse('catalog:admin_list'))

        service.refresh_from_db()
        self.assertEqual(service.name, 'TDS Return Filing (Revised)')
        self.assertEqual(service.price, Decimal('1500.00'))
        self.assertEqual(service.document_requirements.count(), 1)
        self.assertEqual(service.document_requirements.first().name, 'Challan Receipts & BSR Code')

    def test_admin_delete_service(self):
        service = create_service(
            name='Service To Delete',
            description='Will be removed.',
            price=Decimal('500.00')
        )
        url = reverse('catalog:admin_delete', kwargs={'pk': service.pk})
        response = self.client.post(url)
        self.assertRedirects(response, reverse('catalog:admin_list'))
        self.assertFalse(Service.objects.filter(pk=service.pk).exists())
