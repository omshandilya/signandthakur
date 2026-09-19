"""Role-based permissions mixin and decorator.

Ensures views can be protected with explicit role requirements:
CLIENT, EMPLOYEE, or ADMIN.
"""

from functools import wraps
from typing import Iterable, Union
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib.auth.views import redirect_to_login
from django.conf import settings


def _normalize_roles(roles: Union[Iterable[str], str]) -> set:
    """Normalize roles into a set of uppercase role strings."""
    if isinstance(roles, str):
        return {roles.upper()}
    normalized = set()
    for role in roles:
        if isinstance(role, (list, tuple, set)):
            normalized.update(r.upper() for r in role)
        else:
            normalized.add(str(role).upper())
    return normalized


def user_has_role(user, allowed_roles: Union[Iterable[str], str]) -> bool:
    """Check if the user is authenticated and has at least one of the allowed roles."""
    if not user.is_authenticated:
        return False
    roles_set = _normalize_roles(allowed_roles)
    if 'ADMIN' in roles_set and user.is_superuser:
        return True
    return getattr(user, 'role', '').upper() in roles_set


class RoleRequiredMixin(AccessMixin):
    """Class-based view mixin ensuring user has one of the allowed roles.

    If unauthenticated, redirects to login.
    If authenticated but lacks required role, raises PermissionDenied (HTTP 403).
    """
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if not user_has_role(request.user, self.allowed_roles):
            raise PermissionDenied("You do not have permission to access this page.")

        return super().dispatch(request, *args, **kwargs)


def role_required(*allowed_roles):
    """Function-based view decorator ensuring user has one of the allowed roles.

    Usage:
        @role_required('ADMIN')
        @role_required('EMPLOYEE', 'ADMIN')
        @role_required(['CLIENT'])
    """
    roles_set = _normalize_roles(allowed_roles)

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)

            if not user_has_role(request.user, roles_set):
                raise PermissionDenied("You do not have permission to access this page.")

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
