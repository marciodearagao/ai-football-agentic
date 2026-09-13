from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import Any

from app.usage.models import AgentType, UsageRecord, UsageTotals
from app.usage.pricing import estimate_cost


class UsageTracker:
    def __init__(self) -> None:
        self.records: list[UsageRecord] = []

    def record(self, record: UsageRecord) -> None:
        self.records.append(record)

    def record_provider_attempt(
        self,
        *,
        agent_id: str,
        agent_type: AgentType,
        model: str | None,
        used_fallback: bool,
        response_metadata: object | None = None,
    ) -> UsageRecord:
        response_model = _read_value(response_metadata, "model")
        usage = _read_value(response_metadata, "usage")
        resolved_model = response_model if isinstance(response_model, str) else model
        input_tokens = _read_optional_int(usage, "prompt_tokens", "input_tokens")
        output_tokens = _read_optional_int(
            usage, "completion_tokens", "output_tokens"
        )
        total_tokens = _read_optional_int(usage, "total_tokens")
        prompt_details = _read_value(usage, "prompt_tokens_details")
        cached_tokens = _read_optional_int(prompt_details, "cached_tokens")
        if cached_tokens is None:
            cached_tokens = _read_optional_int(usage, "cached_tokens")
        if (
            input_tokens is not None
            and output_tokens is not None
            and total_tokens is not None
            and total_tokens != input_tokens + output_tokens
        ):
            total_tokens = None
        if (
            cached_tokens is not None
            and input_tokens is not None
            and cached_tokens > input_tokens
        ):
            cached_tokens = None
        record = UsageRecord(
            agent_id=agent_id,
            agent_type=agent_type,
            model=resolved_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cached_tokens=cached_tokens,
            estimated_cost=estimate_cost(
                resolved_model,
                input_tokens,
                output_tokens,
            ),
            used_fallback=used_fallback,
        )
        self.record(record)
        return record

    def match_totals(self) -> UsageTotals:
        return self._aggregate(self.records)

    def totals_for_agent(self, agent_id: str) -> UsageTotals:
        return self._aggregate(
            record for record in self.records if record.agent_id == agent_id
        )

    def totals_for_agent_type(self, agent_type: AgentType) -> UsageTotals:
        return self._aggregate(
            record for record in self.records if record.agent_type is agent_type
        )

    @staticmethod
    def _aggregate(records: Iterable[UsageRecord]) -> UsageTotals:
        records = list(records)
        known_costs = [
            record.estimated_cost
            for record in records
            if record.estimated_cost is not None
        ]
        if not records:
            estimated_cost: Decimal | None = Decimal("0")
        elif len(known_costs) == len(records):
            estimated_cost = sum(known_costs, start=Decimal("0"))
        else:
            estimated_cost = None

        return UsageTotals(
            calls=len(records),
            input_tokens=sum(record.input_tokens or 0 for record in records),
            output_tokens=sum(record.output_tokens or 0 for record in records),
            total_tokens=sum(record.total_tokens or 0 for record in records),
            cached_tokens=sum(record.cached_tokens or 0 for record in records),
            estimated_cost=estimated_cost,
        )


def _read_value(source: object | None, field: str) -> Any:
    if source is None:
        return None
    if isinstance(source, Mapping):
        return source.get(field)
    return getattr(source, field, None)


def _read_optional_int(source: object | None, *fields: str) -> int | None:
    for field in fields:
        value = _read_value(source, field)
        if value is not None:
            try:
                normalized = int(value)
            except (TypeError, ValueError):
                return None
            return normalized if normalized >= 0 else None
    return None
