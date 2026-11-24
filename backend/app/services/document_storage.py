from functools import lru_cache
from io import BytesIO

import urllib3
from minio import Minio
from minio.error import MinioException, S3Error

from app.core.config import get_settings
from app.core.document_limits import DOCUMENT_MAX_BYTES
from app.core.errors import ApiError


def storage_unavailable() -> ApiError:
    return ApiError(503, "document_storage_unavailable", "Licence document storage is temporarily unavailable.")


class DocumentStorage:
    def __init__(self, client: Minio, bucket: str):
        self.client = client
        self.bucket = bucket

    def put(self, key: str, data: bytes, media_type: str) -> None:
        try:
            if not self.client.bucket_exists(self.bucket):
                try:
                    self.client.make_bucket(self.bucket)
                except S3Error as exc:
                    if exc.code != "BucketAlreadyOwnedByYou":
                        raise
            self.client.put_object(self.bucket, key, BytesIO(data), len(data), content_type=media_type)
        except (MinioException, urllib3.exceptions.HTTPError, OSError) as exc:
            raise storage_unavailable() from exc

    def get(self, key: str, expected_size: int) -> bytes:
        try:
            response = self.client.get_object(self.bucket, key)
            try:
                data = response.read(DOCUMENT_MAX_BYTES + 1)
            finally:
                response.close()
                response.release_conn()
            if len(data) != expected_size or len(data) > DOCUMENT_MAX_BYTES:
                raise storage_unavailable()
            return data
        except (MinioException, urllib3.exceptions.HTTPError, OSError) as exc:
            raise storage_unavailable() from exc

    def remove(self, key: str) -> None:
        try:
            self.client.remove_object(self.bucket, key)
        except (MinioException, urllib3.exceptions.HTTPError, OSError) as exc:
            raise storage_unavailable() from exc


@lru_cache
def get_document_storage() -> DocumentStorage:
    settings = get_settings()
    if not (settings.minio_endpoint and settings.minio_access_key and settings.minio_secret_key):
        raise storage_unavailable()
    client = Minio(
        settings.minio_endpoint, access_key=settings.minio_access_key, secret_key=settings.minio_secret_key,
        secure=settings.minio_secure, region="us-east-1",
        http_client=urllib3.PoolManager(timeout=urllib3.Timeout(connect=3, read=10), retries=False),
    )
    return DocumentStorage(client, settings.minio_documents_bucket)
