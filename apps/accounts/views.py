"""Accounts views.

Adheres to the thin views principle: all business rules and mutations are
delegated to services.py.
"""

from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from .forms import (
    AdminPasswordResetForm,
    ClientSignupForm,
    EmployeeCreationForm,
    LoginForm,
)
from .permissions import RoleRequiredMixin
from .services import (
    create_employee,
    get_employees_list,
    get_redirect_url_for_role,
    get_user_by_id,
    register_client,
    reset_user_password,
)


class ClientSignupView(View):
    """Client self-registration view."""

    template_name = 'accounts/signup.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(get_redirect_url_for_role(request.user))
        form = ClientSignupForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        if request.user.is_authenticated:
            return redirect(get_redirect_url_for_role(request.user))

        form = ClientSignupForm(request.POST)
        if form.is_valid():
            user = register_client(
                name=form.cleaned_data['name'],
                email=form.cleaned_data['email'],
                phone=form.cleaned_data['phone'],
                date_of_birth=form.cleaned_data['date_of_birth'],
                password=form.cleaned_data['password'],
            )
            # Log in client immediately upon successful registration
            login(request, user)
            messages.success(request, f"Welcome to the portal, {user.display_name}! Your client account has been created.")
            return redirect(get_redirect_url_for_role(user))

        return render(request, self.template_name, {'form': form})


class CustomLoginView(View):
    """User authentication view routing users to role-tailored dashboards."""

    template_name = 'accounts/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(get_redirect_url_for_role(request.user))
        form = LoginForm(request=request)
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        if request.user.is_authenticated:
            return redirect(get_redirect_url_for_role(request.user))

        form = LoginForm(request.POST, request=request)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Logged in successfully. Welcome back, {user.display_name}!")

            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect(get_redirect_url_for_role(user))

        return render(request, self.template_name, {'form': form})


class CustomLogoutView(View):
    """Log out the current user and redirect to login."""

    def get(self, request):
        logout(request)
        messages.info(request, "You have been logged out successfully.")
        return redirect('accounts:login')

    def post(self, request):
        logout(request)
        messages.info(request, "You have been logged out successfully.")
        return redirect('accounts:login')


class EmployeeListView(RoleRequiredMixin, TemplateView):
    """Admin-only view to inspect the employee roster."""

    allowed_roles = ['ADMIN']
    template_name = 'accounts/employee_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['employees'] = get_employees_list()
        return context


class EmployeeCreateView(RoleRequiredMixin, View):
    """Admin-only view to provision a new employee account."""

    allowed_roles = ['ADMIN']
    template_name = 'accounts/employee_create.html'

    def get(self, request):
        form = EmployeeCreationForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = EmployeeCreationForm(request.POST)
        if form.is_valid():
            employee = create_employee(
                name=form.cleaned_data['name'],
                email=form.cleaned_data['email'],
                phone=form.cleaned_data['phone'],
                date_of_birth=form.cleaned_data['date_of_birth'],
                temporary_password=form.cleaned_data['temporary_password'],
                created_by=request.user,
            )
            messages.success(request, f"Employee '{employee.display_name}' successfully created.")
            return redirect('accounts:employee_list')

        return render(request, self.template_name, {'form': form})


class AdminPasswordResetView(RoleRequiredMixin, View):
    """Admin-only view to reset password for any user account."""

    allowed_roles = ['ADMIN']
    template_name = 'accounts/password_reset.html'

    def get(self, request, user_id):
        target_user = get_object_or_404(get_user_id_queryset(), pk=user_id)
        form = AdminPasswordResetForm()
        return render(request, self.template_name, {
            'form': form,
            'target_user': target_user,
        })

    def post(self, request, user_id):
        target_user = get_object_or_404(get_user_id_queryset(), pk=user_id)
        form = AdminPasswordResetForm(request.POST)
        if form.is_valid():
            reset_user_password(
                user=target_user,
                new_password=form.cleaned_data['new_password'],
                reset_by=request.user,
            )
            messages.success(request, f"Password for {target_user.display_name} ({target_user.email}) has been reset successfully.")
            return redirect('accounts:employee_list')

        return render(request, self.template_name, {
            'form': form,
            'target_user': target_user,
        })


def get_user_id_queryset():
    """Return users that the admin can reset passwords for (non-admin users only).

    Admins are not manageable through this endpoint — they must use the
    Django shell or admin site. This prevents an admin from inadvertently
    locking out another admin via URL manipulation.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.exclude(role=User.Role.ADMIN)
