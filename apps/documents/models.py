"""Documents app models.

Defines confirmation document uploaded exclusively by staff accountants
upon completing service requests.
"""

from django.conf import settings
from django.db import models
from .storage import document_upload_path, get_private_document_storage


class Document(models.Model):
    """Confirmation certificate or document uploaded for a service request."""

    request = models.ForeignKey(
        'service_requests.ServiceRequest',
        on_delete=models.CASCADE,
        related_name='documents',
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_documents',
    )
    file = models.FileField(
        upload_to=document_upload_path,
        storage=get_private_document_storage,
    )
    original_name = models.CharField(max_length=255)
    size = models.PositiveIntegerField(help_text="File size in bytes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'

    def __str__(self):
        return f"{self.original_name} (Request #{self.request_id})"

    @property
    def formatted_size(self) -> str:
        """Return human-readable file size string."""
        if self.size >= 1024 * 1024:
            return f"{self.size / (1024 * 1024):.2f} MB"
        elif self.size >= 1024:
            return f"{self.size / 1024:.1f} KB"
        return f"{self.size} B"
