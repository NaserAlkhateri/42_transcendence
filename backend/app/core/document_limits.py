import re

DOCUMENT_MAX_BYTES = 5 * 1024 * 1024
DOCUMENT_UPLOAD_PATH = re.compile(
    r"/api/v1/organizations/[0-9a-fA-F-]{36}/documents/?"
)
