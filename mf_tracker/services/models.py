from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ScoreComponents:
    raw_weights: Dict[str, float]
    normalized_weights: Dict[str, float]
    used_periods: List[str]
    coverage: float


@dataclass
class FundMetrics:
    name: str
    code: str
    current_nav: Optional[float]
    as_of_date: Optional[str]
    current_date: Optional[str]
    period_source_dates: Dict[str, Optional[str]] = field(default_factory=dict)
    dates: Dict[str, Optional[str]] = field(default_factory=dict)
    returns: Dict[str, Optional[float]] = field(default_factory=dict)
    consistency_score: Optional[float] = None
    score_components: Dict[str, object] = field(default_factory=dict)
    score_method_version: str = "v2_reweighted_missing"
    year_breakdown: Dict[str, Dict[str, object]] = field(default_factory=dict)
    data_completeness: float = 0.0
    is_stale: bool = False
    is_portfolio: bool = False

