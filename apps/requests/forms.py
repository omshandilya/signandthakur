"""Requests app forms."""

from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class AssignRequestForm(forms.Form):
    """Admin form to assign a request to an employee."""

    employee = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label='Assign to Employee',
        widget=forms.Select(attrs={'class': 'form-select', 'required': True}),
        empty_label='— Select an employee —',
    )

    def __init__(self, *args, **kwargs):
        employees_qs = kwargs.pop('employees_qs', User.objects.none())
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = employees_qs
