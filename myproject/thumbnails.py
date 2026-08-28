"""Generate-once, cache-to-disk thumbnails for ImageField uploads.

Used by any module rendering a grid/table of images (itemmaster's item
images, preorder's job images, ...) — those were serving the original
full-resolution file for a 40-160px thumbnail, downloading and decoding
every byte of a possibly multi-MB photo just to shrink it with CSS. This
resizes once on first request and reuses the cached file afterward; the
full-page viewer still uses the original.
"""
import os

from django.conf import settings

THUMB_MAX_SIZE = (300, 300)


def get_or_create_thumbnail(image_field, max_size=THUMB_MAX_SIZE):
    """Given a Django ImageField file instance, return the URL of a resized
    version — generating and caching it to disk on first call. Returns
    None if there's no file, or if Pillow can't read it (corrupt upload
    etc.) — callers should fall back to the original in that case."""
    if not image_field:
        return None

    original_name = image_field.name  # path relative to MEDIA_ROOT
    directory, filename = os.path.split(original_name)
    thumb_rel_path = os.path.join(directory, 'thumbs', filename)
    thumb_abs_path = os.path.join(settings.MEDIA_ROOT, thumb_rel_path)

    if os.path.isfile(thumb_abs_path):
        return settings.MEDIA_URL + thumb_rel_path.replace(os.sep, '/')

    original_abs_path = os.path.join(settings.MEDIA_ROOT, original_name)
    if not os.path.isfile(original_abs_path):
        return None

    try:
        from PIL import Image
        os.makedirs(os.path.dirname(thumb_abs_path), exist_ok=True)
        with Image.open(original_abs_path) as img:
            img.thumbnail(max_size)
            # Preserve the original format (keeps PNG transparency etc.)
            img.save(thumb_abs_path, format=img.format)
    except Exception:
        return None

    return settings.MEDIA_URL + thumb_rel_path.replace(os.sep, '/')
