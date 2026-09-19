from django.conf import settings
from django.db import models


class ServiceRequest(models.Model):
    """A client's request for a CA firm service."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        ASSIGNED = 'ASSIGNED', 'Assigned'
        COMPLETED = 'COMPLETED', 'Completed'

    # Allowed forward-only transitions
    VALID_TRANSITIONS = {
        Status.PENDING: {Status.ASSIGNED},
        Status.ASSIGNED: {Status.COMPLETED},
        Status.COMPLETED: set(),
    }

    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='service_requests',
        limit_choices_to={'role': 'CLIENT'},
    )
    service = models.ForeignKey(
        'catalog.Service',
        on_delete=models.PROTECT,
        related_name='service_requests',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_requests',
        limit_choices_to={'role': 'EMPLOYEE'},
    )
    # Price is locked at submission time; catalog price changes don't affect existing requests
    price_at_request = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Service Request'
        verbose_name_plural = 'Service Requests'

    def __str__(self):
        return f"#{self.pk} {self.service.name} — {self.client} [{self.get_status_display()}]"

    def is_open(self):
        """Return True if the request is not yet completed."""
        return self.status != self.Status.COMPLETED

    def can_transition_to(self, new_status: str) -> bool:
        """Validate whether a transition from the current status is allowed."""
        return new_status in self.VALID_TRANSITIONS.get(self.status, set())


class RequestStatusHistory(models.Model):
    """Audit trail of every status change on a service request."""

    request = models.ForeignKey(
        ServiceRequest,
        on_delete=models.CASCADE,
        related_name='status_history',
    )
    from_status = models.CharField(max_length=20, choices=ServiceRequest.Status.choices)
    to_status = models.CharField(max_length=20, choices=ServiceRequest.Status.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='status_changes',
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp', 'id']
        verbose_name = 'Status History Entry'
        verbose_name_plural = 'Status History'

    def __str__(self):
        return (
            f"Request #{self.request_id}: {self.from_status} → {self.to_status} "
            f"by {self.changed_by} at {self.timestamp:%Y-%m-%d %H:%M}"
        )
