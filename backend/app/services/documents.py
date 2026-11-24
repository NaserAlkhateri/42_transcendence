import uuid
from io import BytesIO
from urllib.parse import unquote

from PIL import Image
from pypdf import PdfReader
from pypdf.errors import PyPdfError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import OrganizationDocument

DOCUMENT_FORMATS = {
    "application/pdf": ({".pdf"}, b"%PDF-"),
    "image/jpeg": ({".jpg", ".jpeg"}, b"\xff\xd8\xff"),
    "image/png": ({".png"}, b"\x89PNG\r\n\x1a\n"),
}
MAX_ACTIVE_DOCUMENTS = 10
MAX_IMAGE_PIXELS = 20_000_000


def list_documents(db: Session, organization_id: uuid.UUID) -> list[OrganizationDocument]:
    return list(db.scalars(select(OrganizationDocument).where(
        OrganizationDocument.organization_id == organization_id,
    ).order_by(OrganizationDocument.created_at.desc(), OrganizationDocument.id)))


def validate_document(encoded_name: str, media_type: str, contents: bytes) -> str:
    if media_type not in DOCUMENT_FORMATS:
        raise ApiError(415, "unsupported_document_type", "Choose a PDF, JPEG or PNG file.")
    try:
        file_name = unquote(encoded_name, errors="strict").strip()
    except UnicodeError as exc:
        raise ApiError(422, "invalid_document_name", "The file name is invalid.") from exc
    if not 1 <= len(file_name) <= 255 or any(not char.isprintable() or char in "/\\" for char in file_name):
        raise ApiError(422, "invalid_document_name", "Use a file name of up to 255 characters without path separators.")
    extensions, signature = DOCUMENT_FORMATS[media_type]
    if not any(file_name.lower().endswith(ext) for ext in extensions) or not contents.startswith(signature):
        raise ApiError(422, "invalid_document_format", "The file contents must match its PDF, JPEG or PNG extension.")
    try:
        if media_type == "application/pdf":
            pdf = PdfReader(BytesIO(contents), strict=True)
            if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 100:
                raise ValueError("unsupported PDF")
            # Resolve the first page now; a header and a catalog alone are not sufficient.
            pdf.pages[0].mediabox
        else:
            with Image.open(BytesIO(contents), formats=["PNG" if media_type == "image/png" else "JPEG"]) as image:
                if image.width * image.height > MAX_IMAGE_PIXELS or getattr(image, "n_frames", 1) != 1:
                    raise ValueError("unsupported image")
                image.verify()
            with Image.open(BytesIO(contents)) as image:
                image.load()
    except (PyPdfError, Image.DecompressionBombError, OSError, ValueError, SyntaxError,
            TypeError, KeyError, IndexError, RecursionError) as exc:
        raise ApiError(422, "invalid_document_format", "The file is damaged or uses an unsupported format.") from exc
    return file_name
