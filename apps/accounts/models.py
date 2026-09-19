from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model supporting CLIENT, EMPLOYEE, and ADMIN roles."""

    class Role(models.TextChoices):
        CLIENT = 'CLIENT', 'Client'
        EMPLOYEE = 'EMPLOYEE', 'Employee'
        ADMIN = 'ADMIN', 'Admin'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CLIENT,
        help_text="Role determining user permissions across the portal."
    )
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    def is_client(self):
        return self.role == self.Role.CLIENT

    def is_employee(self):
        return self.role == self.Role.EMPLOYEE

    def is_admin_user(self):
        return self.role == self.Role.ADMIN or self.is_superuser
