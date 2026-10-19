"""Image upload pipeline: validate, strip all metadata by re-encoding, resize, compress."""
import io
import warnings

from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = 50_000_000  # decompression-bomb guard
MAX_UPLOAD = 15 * 1024 * 1024
ALLOWED = {"JPEG", "PNG", "WEBP"}


class ImageRejected(Exception):
    pass


def _open(data):
    if not data or len(data) > MAX_UPLOAD:
        raise ImageRejected("Image is empty or larger than 15 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            im = Image.open(io.BytesIO(data))
            fmt = im.format
            im.verify()
            im = Image.open(io.BytesIO(data))  # reopen after verify
            im.load()
    except Exception:
        raise ImageRejected("This file is not a valid image.")
    if fmt not in ALLOWED:
        raise ImageRejected("Only JPEG, PNG or WebP images are accepted.")
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    return im.convert("RGB")


def _jpeg(im, q):
    b = io.BytesIO()
    im.save(b, "JPEG", quality=q, optimize=True, progressive=True)  # no exif passed => metadata stripped
    return b.getvalue()


def _fit(im, box):
    im = im.copy()
    im.thumbnail(box, Image.LANCZOS)
    return im


def process_photo(data):
    """-> (thumb_jpeg, full_jpeg)"""
    im = _open(data)
    return _jpeg(_fit(im, (300, 300)), 78), _jpeg(_fit(im, (900, 900)), 82)


def process_cat_image(data):
    """Section / branch image for the customer tiles: one 400 px JPEG, metadata-free."""
    return _jpeg(_fit(_open(data), (400, 400)), 80)


def process_logo(data):
    im = _open(data)
    if im.height > 120:
        im = im.resize((max(1, int(im.width * 120 / im.height)), 120), Image.LANCZOS)
    b = io.BytesIO()
    im.save(b, "PNG", optimize=True)
    return b.getvalue()


def process_background(data, kind):
    """kind: 'mobile' (<=300 KB) or 'desktop' (<=400 KB), JPEG, metadata-free."""
    im = _open(data)
    box, limit = ((900, 1600), 300) if kind == "mobile" else ((1600, 1000), 400)
    im = _fit(im, box)
    out = b""
    for q in range(90, 35, -5):
        out = _jpeg(im, q)
        if len(out) <= limit * 1024:
            break
    return out
