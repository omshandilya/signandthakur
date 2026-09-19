"""Accounts forms with Bootstrap 5 widgets and validation."""

from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()


class ClientSignupForm(forms.Form):
    """Client self-registration form."""

    name = forms.CharField(
        label="Full Name",
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your full name',
            'required': True,
        })
    )
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'name@example.com',
            'required': True,
        })
    )
    phone = forms.CharField(
        label="Phone Number",
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+91 98765 43210',
            'required': True,
        })
    )
    date_of_birth = forms.DateField(
        label="Date of Birth",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'required': True,
        })
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'At least 8 characters',
            'required': True,
        })
    )
    confirm_password = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Re-enter your password',
            'required': True,
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email address already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password:
            if password != confirm_password:
                self.add_error('confirm_password', "Passwords do not match.")
            else:
                validate_password(password)

        return cleaned_data


class LoginForm(forms.Form):
    """User authentication form."""

    username = forms.CharField(
        label="Email / Username",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your registered email or username',
            'required': True,
            'autofocus': True,
        })
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password',
            'required': True,
        })
    )

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')

        if username and password:
            # First attempt direct authentication
            self.user_cache = authenticate(self.request, username=username.strip(), password=password)

            # If failed, attempt matching email (case-insensitive) to username
            if self.user_cache is None:
                user_match = User.objects.filter(email__iexact=username.strip()).first()
                if user_match:
                    self.user_cache = authenticate(self.request, username=user_match.username, password=password)

            if self.user_cache is None:
                raise ValidationError("Invalid email/username or password. Please try again.")
            elif not self.user_cache.is_active:
                raise ValidationError("This account is currently inactive. Please contact support.")

        return cleaned_data

    def get_user(self):
        return self.user_cache


class EmployeeCreationForm(forms.Form):
    """Admin-only form to create new employee profiles."""

    name = forms.CharField(
        label="Full Name",
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Employee full name',
            'required': True,
        })
    )
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'employee@firm.com',
            'required': True,
        })
    )
    phone = forms.CharField(
        label="Phone Number",
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+91 98765 43210',
            'required': True,
        })
    )
    date_of_birth = forms.DateField(
        label="Date of Birth",
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
        })
    )
    temporary_password = forms.CharField(
        label="Temporary Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Temporary initial password',
            'required': True,
        })
    )
    confirm_password = forms.CharField(
        label="Confirm Temporary Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm temporary password',
            'required': True,
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email address already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        temp_pw = cleaned_data.get('temporary_password')
        confirm_pw = cleaned_data.get('confirm_password')

        if temp_pw and confirm_pw:
            if temp_pw != confirm_pw:
                self.add_error('confirm_password', "Passwords do not match.")
            else:
                validate_password(temp_pw)

        return cleaned_data


class AdminPasswordResetForm(forms.Form):
    """Admin-only form to reset password for any user."""

    new_password = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter new password',
            'required': True,
        })
    )
    confirm_password = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password',
            'required': True,
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        new_pw = cleaned_data.get('new_password')
        confirm_pw = cleaned_data.get('confirm_password')

        if new_pw and confirm_pw:
            if new_pw != confirm_pw:
                self.add_error('confirm_password', "Passwords do not match.")
            else:
                validate_password(new_pw)

        return cleaned_data
