"""Deterministic analytics-target detection over a validated AppSpec."""

from __future__ import annotations

from app.services.app_spec import AppSpec, Entity, SpecField

_AMOUNT_HINTS = ("amount", "price", "total", "revenue", "cost", "fee", "value", "quantity", "qty")
_TX_HINTS = (
    "order",
    "booking",
    "reservation",
    "appointment",
    "invoice",
    "transaction",
    "enrollment",
    "ticket",
    "subscription",
    "payment",
    "expense",
    "sale",
    "purchase",
    "charge",
)


def find_transaction_entity(spec: AppSpec) -> Entity | None:
    for e in spec.entities:
        if any(h in e.name.lower() for h in _TX_HINTS):
            return e
    return None


def numeric_fields(entity: Entity) -> list[SpecField]:
    return [f for f in entity.fields if f.type in ("int", "float")]


def primary_metric_field(entity: Entity) -> SpecField | None:
    """Prefer a field that looks like money/quantity; fall back to the first numeric field."""
    nums = numeric_fields(entity)
    for f in nums:
        if any(h in f.name.lower() for h in _AMOUNT_HINTS):
            return f
    return nums[0] if nums else None


def datetime_field(entity: Entity) -> SpecField | None:
    for f in entity.fields:
        if f.type in ("date", "datetime"):
            return f
    return None


class AnalyticsTarget:
    def __init__(self, entity: Entity, metric_field: SpecField, time_field: SpecField | None):
        self.entity = entity
        self.metric_field = metric_field
        self.time_field = time_field


def resolve_analytics_target(spec: AppSpec) -> AnalyticsTarget | None:
    """Pick the single most useful entity+field to build real analytics from."""
    tx = find_transaction_entity(spec)
    candidates = [tx] if tx else []
    candidates += [e for e in spec.entities if e is not tx]
    for e in candidates:
        metric = primary_metric_field(e)
        if metric:
            return AnalyticsTarget(e, metric, datetime_field(e))
    return None
