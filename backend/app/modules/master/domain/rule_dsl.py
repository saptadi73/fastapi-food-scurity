"""DSL v1 validation only: no evaluation, imports or action execution."""
import math
from typing import Any


class RuleDSLValidationError(ValueError):
    pass


# Canonical ingestion units; no food-safety threshold is hardcoded here.
NUMERIC_FIELDS = frozenset({"temperature", "duration_minutes", "humidity", "remaining_minutes", "speed"})
TEXT_FIELDS = frozenset({"storage_type", "status"})
OPERATORS = frozenset({"eq", "ne", "gt", "gte", "lt", "lte"})
ACTION_FIELDS = {
    "alarm": {"code", "severity"},
    "notification": {"channel", "template"},
    "change_status": {"status"},
    "create_incident": {"code"},
    "create_recall": {"reason"},
    "discard_package": {"reason"},
    "create_audit": {"code"},
}


def validate_rule_dsl(condition: Any, action: Any) -> None:
    """Raise on unknown fields/operators, malformed trees and unbounded complexity."""
    nodes = 0

    def fail():
        raise RuleDSLValidationError("Invalid rule DSL v1")

    def visit(node, depth):
        nonlocal nodes
        nodes += 1
        if nodes > 100 or depth > 8 or type(node) is not dict:
            fail()
        if set(node) in ({"all"}, {"any"}):
            children = next(iter(node.values()))
            if type(children) is not list or not 1 <= len(children) <= 20:
                fail()
            for child in children:
                visit(child, depth + 1)
            return
        if set(node) != {"field", "op", "value"}:
            fail()
        field, op, value = node["field"], node["op"], node["value"]
        if type(field) is not str or type(op) is not str or op not in OPERATORS:
            fail()
        if field in NUMERIC_FIELDS:
            if type(value) not in (int, float) or not -1e12 <= value <= 1e12 or not math.isfinite(value):
                fail()
        elif field in TEXT_FIELDS:
            if op not in {"eq", "ne"} or type(value) is not str or not value.strip() or len(value) > 200:
                fail()
        else:
            fail()

    visit(condition, 1)
    if type(action) is not dict or set(action) != {"dsl_version", "steps"}:
        fail()
    if type(action["dsl_version"]) is not int or action["dsl_version"] != 1:
        fail()
    steps = action["steps"]
    if type(steps) is not list or not 1 <= len(steps) <= 10:
        fail()
    for step in steps:
        if type(step) is not dict or type(step.get("type")) is not str:
            fail()
        fields = ACTION_FIELDS.get(step["type"])
        if fields is None or set(step) != fields | {"type"}:
            fail()
        if any(type(step[key]) is not str or not step[key].strip() or len(step[key]) > 200 for key in fields):
            fail()
        if step["type"] == "alarm" and step["severity"] not in {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}:
            fail()
        if step["type"] == "notification" and step["channel"] not in {"dashboard", "email", "whatsapp", "telegram"}:
            fail()
