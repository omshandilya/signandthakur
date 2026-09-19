"""Accounts business services.

All business logic for user management, role assignments, and password operations
resides here to keep views thin.
"""

from typing import Optional
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse

User = get_user_model()


def parse_full_name(full_name: str) -> tuple[str, str]:
    """Split a full name string into first_name and last_name."""
    parts = (full_name or '').strip().split(maxsplit=1)
    if not parts:
        return '', ''
    if len(parts) == 1:
        return parts[0], ''
    return parts[0], parts[1]


@transaction.atomic
def register_client(
    name: str,
    email: str,
    phone: str,
    date_of_birth,
    password: str
) -> User:
    """Self-register a new CLIENT account.

    Only clients are allowed to self-register.
    """
    normalized_email = email.strip().lower()
    if User.objects.filter(email__iexact=normalized_email).exists():
        raise ValidationError("An account with this email address already exists.")

    first_name, last_name = parse_full_name(name)

    user = User(
        username=normalized_email,
        email=normalized_email,
        first_name=first_name,
        last_name=last_name,
        phone=phone.strip(),
        date_of_birth=date_of_birth,
        role=User.Role.CLIENT,
        is_active=True,
    )
    user.set_password(password)
    user.save()
    return user


@transaction.atomic
def create_employee(
    name: str,
    email: str,
    phone: str,
    date_of_birth,
    temporary_password: str,
    created_by: Optional[User] = None
) -> User:
    """Admin-only service to provision an EMPLOYEE account.

    Employees cannot self-register; they must be created by an Admin.
    """
    if created_by and not created_by.is_admin_user():
        raise ValidationError("Only an administrator can create employee accounts.")

    normalized_email = email.strip().lower()
    if User.objects.filter(email__iexact=normalized_email).exists():
        raise ValidationError("An account with this email address already exists.")

    first_name, last_name = parse_full_name(name)

    user = User(
        username=normalized_email,
        email=normalized_email,
        first_name=first_name,
        last_name=last_name,
        phone=phone.strip(),
        date_of_birth=date_of_birth,
        role=User.Role.EMPLOYEE,
        is_staff=False,
        is_active=True,
    )
    user.set_password(temporary_password)
    user.save()
    return user


@transaction.atomic
def reset_user_password(
    user: User,
    new_password: str,
    reset_by: Optional[User] = None
) -> User:
    """Admin service to set a new password for any user account."""
    if reset_by and not reset_by.is_admin_user():
        raise ValidationError("Only an administrator can reset another user's password.")

    user.set_password(new_password)
    user.save()
    return user


def get_employees_list():
    """Return all active and inactive employees ordered by registration date."""
    return User.objects.filter(role=User.Role.EMPLOYEE).order_by('-date_joined')


def get_user_by_id(user_id: int) -> User:
    """Fetch user by ID."""
    return User.objects.get(pk=user_id)


def get_redirect_url_for_role(user: User) -> str:
    """Return the appropriate dashboard URL based on the user's role."""
    if not user.is_authenticated:
        return reverse('accounts:login')

    if user.is_admin_user():
        return reverse('dashboards:admin')
    elif user.is_employee():
        return reverse('dashboards:employee')
    elif user.is_client():
        return reverse('dashboards:client')
    return reverse('dashboards:index')
