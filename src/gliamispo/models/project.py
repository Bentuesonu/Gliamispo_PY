from dataclasses import dataclass, field
import time


@dataclass
class Project:
    id: int = 0
    title: str = ""
    director: str = None
    production_company: str = None
    created_date: int = field(default_factory=lambda: int(time.time()))
    last_modified: int = field(default_factory=lambda: int(time.time()))
    language: str = None
    currency: str = None
    ml_enabled: int = 1
    ml_min_confidence: float = 0.60
    total_budget: float = None
    contingency_percent: float = 10.0
    hours_per_shooting_day: float = 10.0
