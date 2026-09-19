from django.contrib import admin
from .models import RequestStatusHistory, ServiceRequest


class StatusHistoryInline(admin.TabularInline):
    model = RequestStatusHistory
    extra = 0
    readonly_fields = ('from_status', 'to_status', 'changed_by', 'timestamp')
    can_delete = False


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'service', 'status', 'assigned_to', 'price_at_request', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('client__username', 'client__email', 'service__name')
    readonly_fields = ('price_at_request', 'created_at', 'assigned_at', 'completed_at')
    inlines = [StatusHistoryInline]


@admin.register(RequestStatusHistory)
class RequestStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('request', 'from_status', 'to_status', 'changed_by', 'timestamp')
    readonly_fields = ('request', 'from_status', 'to_status', 'changed_by', 'timestamp')
