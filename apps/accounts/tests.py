import datetime
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from apps.accounts.forms import (
    AdminPasswordResetForm,
    ClientSignupForm,
    EmployeeCreationForm,
    LoginForm,
)
from apps.accounts.permissions import RoleRequiredMixin, role_required
from apps.accounts.services import (
    create_employee,
    get_employees_list,
    get_redirect_url_for_role,
    register_client,
    reset_user_password,
)

User = get_user_model()


class UserModelTests(TestCase):
    """Test custom User model fields, roles, and helper methods."""

    def test_create_client_role(self):
        user = User.objects.create_user(
            username='client@test.com',
            email='client@test.com',
            password='TestPassword123!',
            role=User.Role.CLIENT,
            phone='9876543210',
            date_of_birth=datetime.date(1995, 5, 10),
            first_name='Aarav',
            last_name='Sharma'
        )
        self.assertEqual(user.role, User.Role.CLIENT)
        self.assertTrue(user.is_client())
        self.assertFalse(user.is_employee())
        self.assertFalse(user.is_admin_user())
        self.assertEqual(user.display_name, 'Aarav Sharma')
        self.assertIn('Aarav Sharma', str(user))

    def test_create_employee_role(self):
        user = User.objects.create_user(
            username='employee@test.com',
            email='employee@test.com',
            password='TestPassword123!',
            role=User.Role.EMPLOYEE,
            first_name='Priya'
        )
        self.assertEqual(user.role, User.Role.EMPLOYEE)
        self.assertFalse(user.is_client())
        self.assertTrue(user.is_employee())
        self.assertFalse(user.is_admin_user())

    def test_create_admin_role(self):
        user = User.objects.create_superuser(
            username='admin@test.com',
            email='admin@test.com',
            password='TestPassword123!',
            role=User.Role.ADMIN
        )
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.is_admin_user())
        self.assertTrue(user.is_superuser)


class ClientSignupTests(TestCase):
    """Test client self-registration form, service, and view."""

    def setUp(self):
        self.client = Client()
        self.signup_url = reverse('accounts:signup')

    def test_signup_form_valid(self):
        form_data = {
            'name': 'Rohan Gupta',
            'email': 'rohan@example.com',
            'phone': '9988776655',
            'date_of_birth': '1990-01-15',
            'password': 'StrongPassword123!',
            'confirm_password': 'StrongPassword123!',
        }
        form = ClientSignupForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_signup_form_passwords_mismatch(self):
        form_data = {
            'name': 'Rohan Gupta',
            'email': 'rohan@example.com',
            'phone': '9988776655',
            'date_of_birth': '1990-01-15',
            'password': 'StrongPassword123!',
            'confirm_password': 'DifferentPassword123!',
        }
        form = ClientSignupForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('confirm_password', form.errors)

    def test_signup_form_duplicate_email(self):
        User.objects.create_user(
            username='existing@example.com',
            email='existing@example.com',
            password='Password123!'
        )
        form_data = {
            'name': 'Duplicate User',
            'email': 'existing@example.com',
            'phone': '9988776655',
            'date_of_birth': '1990-01-15',
            'password': 'StrongPassword123!',
            'confirm_password': 'StrongPassword123!',
        }
        form = ClientSignupForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_client_self_registration_view(self):
        payload = {
            'name': 'Ananya Sen',
            'email': 'ananya@example.com',
            'phone': '9123456780',
            'date_of_birth': '1992-08-20',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!',
        }
        response = self.client.post(self.signup_url, data=payload)
        # Should redirect to client dashboard
        self.assertRedirects(response, reverse('dashboards:client'))

        # Verify user in database has CLIENT role
        created_user = User.objects.get(email='ananya@example.com')
        self.assertEqual(created_user.role, User.Role.CLIENT)
        self.assertEqual(created_user.first_name, 'Ananya')
        self.assertEqual(created_user.last_name, 'Sen')
        self.assertEqual(created_user.phone, '9123456780')


class LoginAndRedirectTests(TestCase):
    """Test login and role-tailored redirects."""

    def setUp(self):
        self.client = Client()
        self.login_url = reverse('accounts:login')

        self.client_user = User.objects.create_user(
            username='client@portal.com',
            email='client@portal.com',
            password='Password123!',
            role=User.Role.CLIENT
        )
        self.employee_user = User.objects.create_user(
            username='emp@portal.com',
            email='emp@portal.com',
            password='Password123!',
            role=User.Role.EMPLOYEE
        )
        self.admin_user = User.objects.create_user(
            username='admin@portal.com',
            email='admin@portal.com',
            password='Password123!',
            role=User.Role.ADMIN
        )

    def test_role_redirect_helper(self):
        self.assertEqual(get_redirect_url_for_role(self.client_user), reverse('dashboards:client'))
        self.assertEqual(get_redirect_url_for_role(self.employee_user), reverse('dashboards:employee'))
        self.assertEqual(get_redirect_url_for_role(self.admin_user), reverse('dashboards:admin'))

    def test_client_login_redirect(self):
        response = self.client.post(self.login_url, {
            'username': 'client@portal.com',
            'password': 'Password123!'
        })
        self.assertRedirects(response, reverse('dashboards:client'))

    def test_employee_login_redirect(self):
        response = self.client.post(self.login_url, {
            'username': 'emp@portal.com',
            'password': 'Password123!'
        })
        self.assertRedirects(response, reverse('dashboards:employee'))

    def test_admin_login_redirect(self):
        response = self.client.post(self.login_url, {
            'username': 'admin@portal.com',
            'password': 'Password123!'
        })
        self.assertRedirects(response, reverse('dashboards:admin'))

    def test_login_respects_next_parameter(self):
        target = '/dashboard/client/'
        response = self.client.post(f"{self.login_url}?next={target}", {
            'username': 'client@portal.com',
            'password': 'Password123!'
        })
        self.assertRedirects(response, target)

    def test_logout(self):
        self.client.login(username='client@portal.com', password='Password123!')
        logout_response = self.client.post(reverse('accounts:logout'))
        self.assertRedirects(logout_response, reverse('accounts:login'))


class RoleAccessControlTests(TestCase):
    """Test RoleRequiredMixin and role_required decorator enforcement."""

    def setUp(self):
        self.client = Client()
        self.client_user = User.objects.create_user(
            username='client_user@portal.com',
            email='client_user@portal.com',
            password='Password123!',
            role=User.Role.CLIENT
        )
        self.employee_user = User.objects.create_user(
            username='emp_user@portal.com',
            email='emp_user@portal.com',
            password='Password123!',
            role=User.Role.EMPLOYEE
        )
        self.admin_user = User.objects.create_user(
            username='admin_user@portal.com',
            email='admin_user@portal.com',
            password='Password123!',
            role=User.Role.ADMIN
        )

    def test_unauthenticated_user_redirected_to_login(self):
        response = self.client.get(reverse('accounts:employee_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)

    def test_client_forbidden_from_admin_and_employee_views(self):
        self.client.login(username='client_user@portal.com', password='Password123!')

        # Client cannot access employee list
        res1 = self.client.get(reverse('accounts:employee_list'))
        self.assertEqual(res1.status_code, 403)

        # Client cannot access employee dashboard
        res2 = self.client.get(reverse('dashboards:employee'))
        self.assertEqual(res2.status_code, 403)

        # Client cannot access admin dashboard
        res3 = self.client.get(reverse('dashboards:admin'))
        self.assertEqual(res3.status_code, 403)

        # Client CAN access client dashboard
        res4 = self.client.get(reverse('dashboards:client'))
        self.assertEqual(res4.status_code, 200)

    def test_employee_forbidden_from_admin_views(self):
        self.client.login(username='emp_user@portal.com', password='Password123!')

        # Employee cannot access admin views
        res1 = self.client.get(reverse('accounts:employee_list'))
        self.assertEqual(res1.status_code, 403)

        res2 = self.client.get(reverse('accounts:employee_create'))
        self.assertEqual(res2.status_code, 403)

        res3 = self.client.get(reverse('dashboards:admin'))
        self.assertEqual(res3.status_code, 403)

        # Employee CAN access employee dashboard
        res4 = self.client.get(reverse('dashboards:employee'))
        self.assertEqual(res4.status_code, 200)

    def test_admin_has_full_access(self):
        self.client.login(username='admin_user@portal.com', password='Password123!')

        res1 = self.client.get(reverse('accounts:employee_list'))
        self.assertEqual(res1.status_code, 200)

        res2 = self.client.get(reverse('accounts:employee_create'))
        self.assertEqual(res2.status_code, 200)

        res3 = self.client.get(reverse('dashboards:admin'))
        self.assertEqual(res3.status_code, 200)

    def test_role_required_decorator_directly(self):
        factory = RequestFactory()

        @role_required('ADMIN')
        def sample_admin_view(request):
            return "SUCCESS"

        # Anonymous request
        from django.contrib.auth.models import AnonymousUser
        anon_request = factory.get('/fake-url/')
        anon_request.user = AnonymousUser()
        response = sample_admin_view(anon_request)
        self.assertEqual(response.status_code, 302)

        # Client request -> raises PermissionDenied
        client_request = factory.get('/fake-url/')
        client_request.user = self.client_user
        with self.assertRaises(PermissionDenied):
            sample_admin_view(client_request)

        # Admin request -> executes
        admin_request = factory.get('/fake-url/')
        admin_request.user = self.admin_user
        result = sample_admin_view(admin_request)
        self.assertEqual(result, "SUCCESS")


class EmployeeManagementTests(TestCase):
    """Test admin employee provisioning and listing."""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='boss@portal.com',
            email='boss@portal.com',
            password='AdminPassword123!',
            role=User.Role.ADMIN
        )
        self.non_admin = User.objects.create_user(
            username='client_bob@portal.com',
            email='client_bob@portal.com',
            password='Password123!',
            role=User.Role.CLIENT
        )

    def test_service_create_employee_requires_admin(self):
        with self.assertRaises(ValidationError):
            create_employee(
                name='Staff Member',
                email='staff@portal.com',
                phone='9876543210',
                date_of_birth=None,
                temporary_password='TempPassword123!',
                created_by=self.non_admin
            )

    def test_admin_create_employee_view(self):
        self.client.login(username='boss@portal.com', password='AdminPassword123!')

        payload = {
            'name': 'Kavita Iyer',
            'email': 'kavita@portal.com',
            'phone': '9811223344',
            'date_of_birth': '1996-03-12',
            'temporary_password': 'TempPassword123!',
            'confirm_password': 'TempPassword123!',
        }
        response = self.client.post(reverse('accounts:employee_create'), data=payload)
        self.assertRedirects(response, reverse('accounts:employee_list'))

        employee = User.objects.get(email='kavita@portal.com')
        self.assertEqual(employee.role, User.Role.EMPLOYEE)
        self.assertEqual(employee.first_name, 'Kavita')
        self.assertEqual(employee.last_name, 'Iyer')
        self.assertTrue(employee.check_password('TempPassword123!'))

    def test_employee_list_view_shows_employees(self):
        create_employee(
            name='Test Staff',
            email='teststaff@portal.com',
            phone='1234567890',
            date_of_birth=None,
            temporary_password='TempPassword123!',
            created_by=self.admin
        )
        self.client.login(username='boss@portal.com', password='AdminPassword123!')
        response = self.client.get(reverse('accounts:employee_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Staff')
        self.assertContains(response, 'teststaff@portal.com')


class AdminPasswordResetTests(TestCase):
    """Test admin ability to reset any user's password."""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin_boss@portal.com',
            email='admin_boss@portal.com',
            password='AdminPassword123!',
            role=User.Role.ADMIN
        )
        self.target_user = User.objects.create_user(
            username='client_to_reset@portal.com',
            email='client_to_reset@portal.com',
            password='OldPassword123!',
            role=User.Role.CLIENT
        )
        self.non_admin = User.objects.create_user(
            username='other_client@portal.com',
            email='other_client@portal.com',
            password='Password123!',
            role=User.Role.CLIENT
        )

    def test_non_admin_cannot_access_password_reset(self):
        self.client.login(username='other_client@portal.com', password='Password123!')
        url = reverse('accounts:admin_password_reset', kwargs={'user_id': self.target_user.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_service_reset_password_requires_admin(self):
        with self.assertRaises(ValidationError):
            reset_user_password(
                user=self.target_user,
                new_password='NewPassword123!',
                reset_by=self.non_admin
            )

    def test_admin_resets_user_password_view(self):
        self.client.login(username='admin_boss@portal.com', password='AdminPassword123!')
        url = reverse('accounts:admin_password_reset', kwargs={'user_id': self.target_user.pk})

        payload = {
            'new_password': 'BrandNewPassword123!',
            'confirm_password': 'BrandNewPassword123!',
        }
        response = self.client.post(url, data=payload)
        self.assertRedirects(response, reverse('accounts:employee_list'))

        # Verify old password fails and new password succeeds
        self.target_user.refresh_from_db()
        self.assertFalse(self.target_user.check_password('OldPassword123!'))
        self.assertTrue(self.target_user.check_password('BrandNewPassword123!'))
