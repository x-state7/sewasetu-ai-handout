"""Validate limited-size age-proof documents and save under opaque names.

Header/footer checks stop extension spoofing but cannot prove document authenticity;
future document verification must be a distinct process.
"""

import os
import re
import secrets
from pathlib import Path

MAX_FILE_BYTES = 5 * 1024 * 1024
_EXTS = {"pdf", "png", "jpg", "jpeg"}

class InvalidDocument(ValueError):
    pass


def _file_type(content):
    if content.startswith(b"%PDF-") and b"%%EOF" in content[-2048:]:
        return "pdf"
    if content.startswith(b"\x89PNG\r\n\x1a\n") and content.rstrip().endswith(b"IEND\xaeB`\x82"):
        return "png"
    if content.startswith(b"\xff\xd8\xff") and content.endswith(b"\xff\xd9"):
        return "jpg"
    return None


def validate_document(filename, content):
    if not isinstance(filename, str) or not isinstance(content, bytes):
        raise InvalidDocument("Choose a JPG, PNG or PDF file")
    # Never trust a user-supplied path/name; only its final suffix is used for checking.
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in _EXTS:
        raise InvalidDocument("Document must be JPG, PNG or PDF")
    if not content or len(content) > MAX_FILE_BYTES:
        raise InvalidDocument("Document must be nonempty and at most 5 MB")
    detected = _file_type(content)
    if detected is None or ("jpg" if extension == "jpeg" else extension) != detected:
        raise InvalidDocument("File contents do not match an accepted JPG, PNG or PDF")
    return detected


def save_document(upload_dir, filename, content):
    ext = validate_document(filename, content)
    directory = Path(upload_dir).resolve()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    # An opaque name prevents overwriting and exposing the applicant's mobile number.
    basename = secrets.token_hex(20) + "." + ext
    path = directory / basename
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(path), flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(content)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return str(path)
