"""Catalog views.

Adheres to thin views: queries and mutations are delegated to services.py.
"""

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.permissions import RoleRequiredMixin
from .forms import RequirementFormSet, ServiceForm
from .models import Service
from .services import (
    delete_service,
    get_active_services,
    get_all_services,
    get_service_by_id,
)


class ServiceCatalogView(TemplateView):
    """Client-facing catalog listing all active services and document checklists."""

    template_name = 'catalog/service_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['services'] = get_active_services()
        return context


class AdminServiceListView(RoleRequiredMixin, TemplateView):
    """Admin-only view listing all services (active and inactive)."""

    allowed_roles = ['ADMIN']
    template_name = 'catalog/admin_service_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['services'] = get_all_services()
        return context


class AdminServiceCreateView(RoleRequiredMixin, View):
    """Admin-only view to create a service and specify required documents."""

    allowed_roles = ['ADMIN']
    template_name = 'catalog/admin_service_form.html'

    def get(self, request):
        form = ServiceForm()
        formset = RequirementFormSet()
        return render(request, self.template_name, {
            'form': form,
            'formset': formset,
            'is_create': True,
        })

    def post(self, request):
        form = ServiceForm(request.POST)
        formset = RequirementFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                service = form.save()
                formset.instance = service
                formset.save()

            messages.success(request, f"Service '{service.name}' created successfully.")
            return redirect('catalog:admin_list')

        return render(request, self.template_name, {
            'form': form,
            'formset': formset,
            'is_create': True,
        })


class AdminServiceUpdateView(RoleRequiredMixin, View):
    """Admin-only view to edit a service and its required documents."""

    allowed_roles = ['ADMIN']
    template_name = 'catalog/admin_service_form.html'

    def get(self, request, pk):
        service = get_object_or_404(Service, pk=pk)
        form = ServiceForm(instance=service)
        formset = RequirementFormSet(instance=service)
        return render(request, self.template_name, {
            'form': form,
            'formset': formset,
            'service': service,
            'is_create': False,
        })

    def post(self, request, pk):
        service = get_object_or_404(Service, pk=pk)
        form = ServiceForm(request.POST, instance=service)
        formset = RequirementFormSet(request.POST, instance=service)

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                service = form.save()
                formset.save()

            messages.success(request, f"Service '{service.name}' updated successfully.")
            return redirect('catalog:admin_list')

        return render(request, self.template_name, {
            'form': form,
            'formset': formset,
            'service': service,
            'is_create': False,
        })


class AdminServiceDeleteView(RoleRequiredMixin, View):
    """Admin-only view to delete a service."""

    allowed_roles = ['ADMIN']
    template_name = 'catalog/admin_service_confirm_delete.html'

    def get(self, request, pk):
        service = get_object_or_404(Service, pk=pk)
        return render(request, self.template_name, {'service': service})

    def post(self, request, pk):
        service = get_object_or_404(Service, pk=pk)
        name = service.name
        delete_service(service)
        messages.success(request, f"Service '{name}' has been deleted.")
        return redirect('catalog:admin_list')
