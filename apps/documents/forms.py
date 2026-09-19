"""Documents forms.

Form for staff accountants to upload confirmation documents.
"""

from django import forms
from .services import validate_document_file


class DocumentUploadForm(forms.Form):
    """Form for employee to upload a confirmation document."""

    document_file = forms.FileField(
        label="Confirmation Document",
        help_text="Upload certificate, tax return, or confirmation document (PDF, PNG, JPG; max 10 MB).",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/*',
        }),
    )

    def clean_document_file(self):
        uploaded_file = self.cleaned_data.get('document_file')
        validate_document_file(uploaded_file)
        return uploaded_file
