"""Contract test — Django ORM and SQLAlchemy async mirror stay in sync.

The engine worker writes to a small subset of tables via SQLAlchemy async
(``engine/db/models.py``) for performance. Django owns the migrations for
those same tables. This test ensures the two mappings match on column
names and nullability, catching drift at CI time rather than at runtime.

Failure modes caught:
- Column added in Django migration but not mirrored on the SQLAlchemy side.
- Column dropped in Django migration but still referenced by SQLAlchemy.
- Nullability flipped on one side and not the other.

Type drift is not enforced here — Django and SQLAlchemy represent the
same underlying column slightly differently (e.g., TextField vs String,
UUIDField vs UUID), and an overly-strict match creates false positives.
"""

from __future__ import annotations

import pytest
from django.apps import apps as django_apps
from sqlalchemy.orm import DeclarativeBase

from engine.db.models import Base


def _django_columns(model) -> dict[str, bool]:  # type: ignore[no-untyped-def]
    """Map of column_name -> nullable for a Django model, skipping pure relations."""
    cols: dict[str, bool] = {}
    for f in model._meta.get_fields():
        if not hasattr(f, "column") or getattr(f, "many_to_many", False):
            continue
        column = f.column
        if not column:
            continue
        cols[column] = bool(getattr(f, "null", False))
    return cols


def _sqlalchemy_columns(model: type[DeclarativeBase]) -> dict[str, bool]:
    table = model.__table__  # type: ignore[attr-defined]
    return {col.name: bool(col.nullable) for col in table.columns}


# Map SQLAlchemy mirror classes to their owning Django (app_label, model_name).
MIRROR_MAP = [
    ("devices", "InformExchange"),
    ("devices", "VirtualDevice"),
]


@pytest.mark.parametrize(("app_label", "model_name"), MIRROR_MAP)
def test_no_column_drift(app_label: str, model_name: str) -> None:
    django_model = django_apps.get_model(app_label, model_name)

    sqlalchemy_model = next(
        mapper.class_ for mapper in Base.registry.mappers if mapper.class_.__name__ == model_name
    )

    django_cols = _django_columns(django_model)
    sqla_cols = _sqlalchemy_columns(sqlalchemy_model)

    extra_in_django = set(django_cols) - set(sqla_cols)
    extra_in_sqla = set(sqla_cols) - set(django_cols)
    nullability_mismatch = {
        name: (django_cols[name], sqla_cols[name])
        for name in django_cols.keys() & sqla_cols.keys()
        if django_cols[name] != sqla_cols[name]
    }

    assert not extra_in_django, (
        f"SQLAlchemy mirror for {model_name} is missing: {sorted(extra_in_django)}"
    )
    assert not extra_in_sqla, (
        f"SQLAlchemy mirror for {model_name} has stale columns not in Django: "
        f"{sorted(extra_in_sqla)}"
    )
    assert not nullability_mismatch, f"Nullability mismatch on {model_name}: {nullability_mismatch}"
