import pytest

from app.modules.master.domain.rule_dsl import RuleDSLValidationError, validate_rule_dsl

CONDITION = {"field": "temperature", "op": "gt", "value": 5}
ACTION = {"dsl_version": 1, "steps": [{"type": "alarm", "code": "TEMP_HIGH", "severity": "HIGH"}]}


def test_rule_condition_and_actions():
    validate_rule_dsl({"all": [CONDITION, {"field": "duration_minutes", "op": "gte", "value": 15},
                               {"field": "storage_type", "op": "eq", "value": "COLD_STORAGE"}]}, ACTION)
    validate_rule_dsl({"any": [CONDITION]}, {"dsl_version": 1, "steps": [
        {"type": "notification", "channel": "email", "template": "alert"},
        {"type": "change_status", "status": "UNSAFE"}, {"type": "create_incident", "code": "TEST"},
        {"type": "create_recall", "reason": "TEST"}, {"type": "discard_package", "reason": "TEST"},
        {"type": "create_audit", "code": "TEST"},
    ]})


@pytest.mark.parametrize('condition', [
    {}, [], {"all": []}, {"all": [CONDITION], "any": [CONDITION]},
    {**CONDITION, "field": "__import__('os')"}, {**CONDITION, "op": "eval"},
    {**CONDITION, "value": True}, {**CONDITION, "value": float('nan')},
    {**CONDITION, "value": float('inf')}, {**CONDITION, "value": "5"},
    {**CONDITION, "extra": 1}, {**CONDITION, "field": []},
    {"field": "storage_type", "op": "gt", "value": "COLD"},
    {"any": [CONDITION] * 21}, {"all": [{"all": [CONDITION] * 20}] * 6},
])
def test_invalid_condition(condition):
    with pytest.raises(RuleDSLValidationError):
        validate_rule_dsl(condition, ACTION)


def test_depth_limit():
    condition = CONDITION
    for _ in range(8):
        condition = {"all": [condition]}
    with pytest.raises(RuleDSLValidationError):
        validate_rule_dsl(condition, ACTION)


@pytest.mark.parametrize('action', [
    {}, {"dsl_version": True, "steps": ACTION['steps']}, {"dsl_version": 2, "steps": ACTION['steps']},
    {"dsl_version": 1, "steps": []}, {"dsl_version": 1, "steps": ACTION['steps'] * 11},
    {"dsl_version": 1, "steps": [{"type": "shell", "command": "anything"}]},
    {"dsl_version": 1, "steps": [{"type": "notification", "channel": "unknown", "template": "test"}]},
    {"dsl_version": 1, "steps": [{"type": "alarm", "code": "", "severity": "HIGH"}]},
])
def test_invalid_action(action):
    with pytest.raises(RuleDSLValidationError):
        validate_rule_dsl(CONDITION, action)
