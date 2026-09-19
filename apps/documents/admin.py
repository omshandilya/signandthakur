from django.contrib import admin
from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'original_name', 'request', 'uploaded_by', 'formatted_size', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('original_name', 'request__pk', 'uploaded_by__username', 'uploaded_by__email')
    readonly_fields = ('original_name', 'size', 'created_at', 'formatted_size')
