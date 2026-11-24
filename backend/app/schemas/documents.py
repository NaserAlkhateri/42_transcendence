import uuid
from datetime import datetime

from pydantic import BaseModel, computed_field


class DocumentOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    file_name: str
    content_type: str
    size_bytes: int
    created_at: datetime
    deleted_at: datetime | None
    purged_at: datetime | None

    @computed_field
    @property
    def removal_pending(self) -> bool:
        return self.deleted_at is not None and self.purged_at is None
