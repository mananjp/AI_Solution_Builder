"""Cross-database SQLAlchemy type aliases for local SQLite and Postgres."""

from __future__ import annotations

import uuid

from sqlalchemy import JSON as _JSON
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator


class UUID(TypeDecorator):
    """UUID value stored as a string for SQLite and as Postgres UUID in production."""

    impl = String
    cache_ok = True

    def __init__(self, as_uuid: bool = True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.as_uuid = as_uuid

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PGUUID

            return PGUUID(as_uuid=self.as_uuid)
        return String(36)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))

    def copy(self, **kw):
        return UUID(as_uuid=self.as_uuid)


class JSONB(_JSON):
    """JSON type compatible with both SQLite and Postgres-backed schemas."""

    __visit_name__ = "JSON"
    cache_ok = True
