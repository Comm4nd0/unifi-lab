"""Worker-side SQLAlchemy models.

Must match the Django migrations on the corresponding tables. The drift
test in ``tests/contract/test_orm_drift.py`` compares the two at CI time.

- ``VirtualDevice`` — read-only from the worker's perspective (Django writes).
- ``InformExchange`` — fully worker-owned.
- ``ControllerTarget`` — read-only; worker decrypts creds in-process for
  the auto-adopt loop.
- ``TrafficProfile`` — read-only; worker reads active rows for the
  traffic ticker.
- ``FlowRecord`` — worker-owned (traffic ticker writes here).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ControllerTarget(Base):
    __tablename__ = "controllers_controllertarget"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(32))
    inform_url: Mapped[str] = mapped_column(Text)
    api_url: Mapped[str] = mapped_column(Text)
    api_username: Mapped[str] = mapped_column(Text)
    api_password: Mapped[str] = mapped_column(Text)
    verify_tls: Mapped[bool] = mapped_column(Boolean)
    is_active: Mapped[bool] = mapped_column(Boolean)
    health: Mapped[str] = mapped_column(String(32))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VirtualDevice(Base):
    __tablename__ = "devices_virtualdevice"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    mac_address: Mapped[str] = mapped_column(String(17))
    serial_number: Mapped[str] = mapped_column(String(64))
    model_code: Mapped[str] = mapped_column(String(32))
    firmware_version: Mapped[str] = mapped_column(String(32))
    hostname: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32))
    inform_key: Mapped[str] = mapped_column(Text)
    inform_key_rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    controller_target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("controllers_controllertarget.id", ondelete="RESTRICT"),
        nullable=True,
    )
    fleet_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fleets_fleet.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_config_applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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


class TrafficProfile(Base):
    __tablename__ = "traffic_trafficprofile"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    source_yaml: Mapped[str] = mapped_column(Text)
    parsed_json: Mapped[dict] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FlowRecord(Base):
    __tablename__ = "traffic_flowrecord"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices_virtualdevice.id", ondelete="CASCADE")
    )
    protocol: Mapped[str] = mapped_column(String(8))
    src_ip: Mapped[str] = mapped_column(String(39))  # GenericIPAddressField → varchar(39)
    dst_ip: Mapped[str] = mapped_column(String(39))
    src_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dst_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bytes_tx: Mapped[int] = mapped_column(BigInteger)
    bytes_rx: Mapped[int] = mapped_column(BigInteger)
    application: Mapped[str] = mapped_column(String(64))
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    blocked: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


__all__ = [
    "Base",
    "ControllerTarget",
    "FlowRecord",
    "InformExchange",
    "STATE_PENDING",
    "TrafficProfile",
    "VirtualDevice",
]

STATE_PENDING = "pending"
