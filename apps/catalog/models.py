from django.db import models


class Service(models.Model):
    """CA Firm service offering (e.g., GST Registration, ITR Filing, Audit)."""

    name = models.CharField(max_length=200, help_text="Name of the CA service.")
    description = models.TextField(blank=True, help_text="Detailed scope and details of the service.")
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Service fee in INR.")
    is_active = models.BooleanField(
        default=True,
        help_text="Designates whether this service is currently visible to clients."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Service'
        verbose_name_plural = 'Services'

    def __str__(self):
        return f"{self.name} (₹{self.price})"


class ServiceDocumentRequirement(models.Model):
    """Documents required from client for a given service.

    Informational checklist shown to the client before initiating a request.
    Clients do NOT upload these directly.
    """

    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='document_requirements'
    )
    name = models.CharField(
        max_length=255,
        help_text="Name/description of document required (e.g. PAN Card, Form 16, Bank Statement)."
    )

    class Meta:
        ordering = ['id']
        verbose_name = 'Document Requirement'
        verbose_name_plural = 'Document Requirements'

    def __str__(self):
        return f"{self.service.name}: {self.name}"
