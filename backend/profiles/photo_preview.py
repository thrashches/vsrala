"""Generate optimized WebP avatar previews from Profile.photo originals."""

from __future__ import annotations

import logging
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

PREVIEW_SIZE = 256
PREVIEW_FORMAT = 'WEBP'
PREVIEW_FILENAME = 'avatar_preview.webp'
PREVIEW_QUALITY = 80
PREVIEW_METHOD = 4


def _load_image(file_field) -> Image.Image:
    file_field.open('rb')
    try:
        img = Image.open(file_field)
        img.load()
    finally:
        file_field.close()
    img = ImageOps.exif_transpose(img)
    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
        rgba = img.convert('RGBA')
        background = Image.new('RGB', rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return img.convert('RGB')


def _center_crop_square(img: Image.Image) -> Image.Image:
    width, height = img.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return img.crop((left, top, left + side, top + side))


def build_photo_preview_content(file_field) -> ContentFile | None:
    if not file_field:
        return None
    try:
        img = _load_image(file_field)
    except Exception:
        logger.exception('Failed to open profile photo for preview')
        return None
    square = _center_crop_square(img)
    if square.size[0] != PREVIEW_SIZE:
        square = square.resize((PREVIEW_SIZE, PREVIEW_SIZE), Image.Resampling.LANCZOS)
    buf = BytesIO()
    square.save(
        buf,
        format=PREVIEW_FORMAT,
        quality=PREVIEW_QUALITY,
        method=PREVIEW_METHOD,
    )
    return ContentFile(buf.getvalue(), name=PREVIEW_FILENAME)


def clear_photo_preview(profile, *, save: bool = True) -> None:
    if profile.photo_preview:
        profile.photo_preview.delete(save=False)
    if save and profile.pk:
        profile.save(update_fields=['photo_preview'])


def apply_photo_preview(profile, *, save: bool = True) -> bool:
    """Generate and attach photo_preview from profile.photo. Returns True if set."""
    if not profile.photo:
        clear_photo_preview(profile, save=save)
        return False

    content = build_photo_preview_content(profile.photo)
    old_name = profile.photo_preview.name if profile.photo_preview else ''

    if content is None:
        clear_photo_preview(profile, save=save)
        return False

    if old_name:
        profile.photo_preview.delete(save=False)
    profile.photo_preview.save(PREVIEW_FILENAME, content, save=False)
    if save and profile.pk:
        profile.save(update_fields=['photo_preview'])
    return True
