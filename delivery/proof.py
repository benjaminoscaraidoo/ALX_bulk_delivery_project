"""Private proof storage and image validation."""
import io
import uuid
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from PIL import Image, ImageOps
from rest_framework.exceptions import ValidationError


def proof_storage():
    return FileSystemStorage(location=settings.DELIVERY_PROOF_ROOT)


def clean_photo(upload):
    if upload.size > 5 * 1024 * 1024:
        raise ValidationError('Delivery photo must be no larger than 5 MB.')
    try:
        with Image.open(upload) as image:
            if image.format not in ['JPEG', 'PNG'] or image.width * image.height > 20_000_000:
                raise ValueError()
            image.load()
            image = ImageOps.exif_transpose(image).convert('RGB')
            image.thumbnail((2000, 2000))
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=85)
    except (OSError, ValueError, Image.DecompressionBombError):
        raise ValidationError('Upload a valid JPEG or PNG photo, up to 20 megapixels.')
    return ContentFile(output.getvalue(), name=f'{uuid.uuid4().hex}.jpg')
