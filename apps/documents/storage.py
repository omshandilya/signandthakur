"""Storage configuration for private confirmation documents.

Ensures files are not publicly accessible and uses the configured backend
(local filesystem in dev, Cloudinary or S3-compatible storage in production).
"""

import os
import uuid
from django.conf import settings
from django.core.files.storage import FileSystemStorage, get_storage_class


def get_private_document_storage():
    """Return storage instance for documents based on settings."""
    backend_path = getattr(
        settings,
        'DOCUMENT_STORAGE_BACKEND',
        'django.core.files.storage.FileSystemStorage'
    )
    if backend_path == 'django.core.files.storage.FileSystemStorage':
        private_root = getattr(
            settings,
            'PRIVATE_MEDIA_ROOT',
            settings.BASE_DIR / 'private_media'
        )
        # base_url=None ensures no public URL is generated or served directly
        return FileSystemStorage(location=str(private_root), base_url=None)

    storage_cls = get_storage_class(backend_path)
    return storage_cls()


def document_upload_path(instance, filename):
    """Generate a random UUID filename, preserving only the lowercase extension.

    Never uses the user's original file name on disk.
    """
    ext = os.path.splitext(filename)[1].lower()
    random_filename = f"{uuid.uuid4().hex}{ext}"
    return os.path.join('confirmation_docs', random_filename)
