"""Catalog business services.

Encapsulates all querying, creation, updating, and requirements management
for CA services to keep views thin.
"""

from typing import Iterable, Optional
from django.db import transaction
from django.db.models import QuerySet
from .models import Service, ServiceDocumentRequirement


def get_active_services() -> QuerySet[Service]:
    """Retrieve all active services with prefetched document requirements."""
    return (
        Service.objects.filter(is_active=True)
        .prefetch_related('document_requirements')
        .order_by('name')
    )


def get_all_services() -> QuerySet[Service]:
    """Retrieve all services (active and inactive) for admin management."""
    return (
        Service.objects.all()
        .prefetch_related('document_requirements')
        .order_by('name')
    )


def get_service_by_id(service_id: int) -> Service:
    """Fetch single service with requirements by ID."""
    return Service.objects.prefetch_related('document_requirements').get(pk=service_id)


@transaction.atomic
def create_service(
    name: str,
    description: str,
    price,
    is_active: bool = True,
    requirements: Optional[Iterable[str]] = None
) -> Service:
    """Create a new service offering and its initial document requirements."""
    service = Service.objects.create(
        name=name.strip(),
        description=(description or '').strip(),
        price=price,
        is_active=is_active
    )

    if requirements:
        req_objs = [
            ServiceDocumentRequirement(service=service, name=req_name.strip())
            for req_name in requirements
            if req_name and req_name.strip()
        ]
        if req_objs:
            ServiceDocumentRequirement.objects.bulk_create(req_objs)

    return service


@transaction.atomic
def update_service(service: Service, **fields) -> Service:
    """Update fields on a service."""
    for field_name, value in fields.items():
        if hasattr(service, field_name):
            if isinstance(value, str):
                value = value.strip()
            setattr(service, field_name, value)
    service.save()
    return service


@transaction.atomic
def delete_service(service: Service) -> None:
    """Delete a service offering."""
    service.delete()


def add_document_requirement(service: Service, name: str) -> ServiceDocumentRequirement:
    """Attach a required document item to a service."""
    return ServiceDocumentRequirement.objects.create(
        service=service,
        name=name.strip()
    )


def delete_document_requirement(requirement_id: int) -> None:
    """Remove a document requirement item."""
    ServiceDocumentRequirement.objects.filter(pk=requirement_id).delete()
