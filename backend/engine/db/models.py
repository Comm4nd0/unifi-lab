"""Worker-side SQLAlchemy models.

Must match the Django migrations on the corresponding tables. A drift
test in ``tests/contract/`` compares the two at CI time.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class InformExchange(Base):
    __tablename__ = "devices_informexchange"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices_virtualdevice.id", ondelete="CASCADE")
    )
    exchange_type: Mapped[str] = mapped_column(String(32))
    payload_in: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    payload_out: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    exchanged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
