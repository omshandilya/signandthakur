from django.contrib import admin
from .models import Service, ServiceDocumentRequirement


class ServiceDocumentRequirementInline(admin.TabularInline):
    model = ServiceDocumentRequirement
    extra = 1


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'is_active', 'requirements_count', 'updated_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    inlines = [ServiceDocumentRequirementInline]

    def requirements_count(self, obj):
        return obj.document_requirements.count()
    requirements_count.short_description = 'Required Documents'


@admin.register(ServiceDocumentRequirement)
class ServiceDocumentRequirementAdmin(admin.ModelAdmin):
    list_display = ('name', 'service')
    list_filter = ('service',)
    search_fields = ('name', 'service__name')
