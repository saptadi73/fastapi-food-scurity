from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.master.domain.rule_dsl import validate_rule_dsl


class RuleInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True, revalidate_instances='always')


class AlarmRuleInput(RuleInput):
    rule_code: str = Field(min_length=1, max_length=50)
    rule_name: str = Field(min_length=1, max_length=200)
    rule_category: str = Field(min_length=1, max_length=100)
    priority: Literal['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']
    condition: dict[str, Any]
    action: dict[str, Any]

    @model_validator(mode='after')
    def valid_dsl(self):
        validate_rule_dsl(self.condition, self.action)
        return self


class HoldingRuleInput(RuleInput):
    food_category: str = Field(min_length=1, max_length=100)
    maximum_minutes: int = Field(gt=0)
    warning_minutes: int = Field(ge=0)
    discard_minutes: int = Field(gt=0)

    @model_validator(mode='after')
    def valid_times(self):
        if not self.warning_minutes <= self.maximum_minutes <= self.discard_minutes:
            raise ValueError('Require warning <= maximum <= discard')
        return self
