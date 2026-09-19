"""Catalog forms with Bootstrap 5 styling."""

from django import forms
from django.forms import inlineformset_factory
from .models import Service, ServiceDocumentRequirement


class ServiceForm(forms.ModelForm):
    """Admin form to create and modify services."""

    class Meta:
        model = Service
        fields = ['name', 'description', 'price', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. GST Registration & Filing',
                'required': True,
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Explain what this service includes, timelines, and deliverables...',
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00',
                'required': True,
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }
        labels = {
            'is_active': 'Active & visible in client catalog',
        }


class ServiceDocumentRequirementForm(forms.ModelForm):
    """Form to define a document requirement item."""

    class Meta:
        model = ServiceDocumentRequirement
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. PAN Card, Form 16, 3-Month Bank Statement',
            }),
        }


RequirementFormSet = inlineformset_factory(
    Service,
    ServiceDocumentRequirement,
    form=ServiceDocumentRequirementForm,
    fields=['name'],
    extra=2,
    can_delete=True
)
