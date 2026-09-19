"""URL patterns for the documents application."""

from django.urls import path
from .views import (
    DocumentDownloadView,
    DocumentUploadView,
    LatestDocumentDownloadView,
)

app_name = 'documents'

urlpatterns = [
    path('upload/<int:request_pk>/', DocumentUploadView.as_view(), name='upload'),
    path('<int:pk>/download/', DocumentDownloadView.as_view(), name='download'),
    path('request/<int:request_pk>/download/', LatestDocumentDownloadView.as_view(), name='download_request_latest'),
]
