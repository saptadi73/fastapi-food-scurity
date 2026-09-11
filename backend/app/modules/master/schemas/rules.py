from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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

    @field_validator('rule_code', 'rule_name', 'rule_category')
    @classmethod
    def valid_text(cls, value):
        if '\x00' in value:
            raise ValueError('Rule text cannot contain NUL')
        try:
            value.encode('utf-8')
        except UnicodeEncodeError:
            raise ValueError('Rule text must be valid UTF-8') from None
        return value

    @model_validator(mode='after')
    def valid_dsl(self):
        validate_rule_dsl(self.condition, self.action)
        return self


class HoldingRuleInput(RuleInput):
    food_category: str = Field(min_length=1, max_length=100)
    maximum_minutes: int = Field(gt=0, le=2147483647)
    warning_minutes: int = Field(ge=0, le=2147483647)
    discard_minutes: int = Field(gt=0, le=2147483647)

    @field_validator('food_category')
    @classmethod
    def valid_category(cls, value):
        if '\x00' in value:
            raise ValueError('Food category cannot contain NUL')
        try:
            value.encode('utf-8')
        except UnicodeEncodeError:
            raise ValueError('Food category must be valid UTF-8') from None
        return value

    @model_validator(mode='after')
    def valid_times(self):
        if not self.warning_minutes <= self.maximum_minutes <= self.discard_minutes:
            raise ValueError('Require warning <= maximum <= discard')
        return self
