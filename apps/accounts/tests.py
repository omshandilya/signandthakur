from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class UserModelTests(TestCase):
    def test_create_client_user(self):
        user = User.objects.create_user(
            username='client1',
            email='client1@example.com',
            password='password123',
            role=User.Role.CLIENT,
            phone='1234567890'
        )
        self.assertTrue(user.is_client())
        self.assertFalse(user.is_employee())
        self.assertFalse(user.is_admin_user())

    def test_create_employee_user(self):
        user = User.objects.create_user(
            username='employee1',
            email='employee1@example.com',
            password='password123',
            role=User.Role.EMPLOYEE
        )
        self.assertFalse(user.is_client())
        self.assertTrue(user.is_employee())

    def test_create_admin_user(self):
        user = User.objects.create_superuser(
            username='admin1',
            email='admin1@example.com',
            password='password123',
            role=User.Role.ADMIN
        )
        self.assertTrue(user.is_admin_user())
        self.assertTrue(user.is_superuser)
