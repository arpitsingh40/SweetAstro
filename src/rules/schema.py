"""
Rule Schema and Validation Models.
Pydantic models representing machine-readable classical Vedic astrology rules.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class RuleSource(BaseModel):
    book: str
    chapter: int
    verse: Optional[str] = None
    commentary: Optional[str] = None


class RuleCondition(BaseModel):
    entity: str  # e.g., "7th_lord", "Venus", "Saturn", "Jupiter", "7th_house", "transit_jupiter"
    condition_type: str  # "in_house", "in_sign", "aspects_house", "aspects_planet", "dignity_is", "is_combust", "dasha_lord_is", etc.
    target: Optional[str] = None
    values: Optional[List[str]] = None


class ClassicalRule(BaseModel):
    rule_id: str
    domain: str = "Marriage"
    category: str  # "promise", "delay", "timing_dasha", "timing_transit", "jaimini", "stability"
    source: RuleSource
    required_charts: List[str] = Field(default_factory=lambda: ["D1"])
    conditions: List[RuleCondition]
    result: str
    base_weight: float
    timing_capability: bool = False
    timing_resolution: str = "none"  # "none", "year", "quarter", "month"
    interpretation: str
    exceptions: Optional[List[str]] = None
    exception_conditions: Optional[List[RuleCondition]] = None
