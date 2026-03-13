from dataclasses import dataclass, field
import time
from gliamispo.models.eighths import Eighths


@dataclass
class Scene:
    id: int = 0
    project_id: int = 0
    scene_number: str = ""
    location: str = ""
    int_ext: str = "INT"
    day_night: str = "GIORNO"
    page_start_whole: int = 1
    page_start_eighths: int = 0
    page_end_whole: int = 1
    page_end_eighths: int = 0
    synopsis: str = None
    story_day: int = 1
    requires_intimacy_coordinator: int = 0
    estimated_crew_size: int = None
    special_requirements: str = None
    parser_used: str = None
    parser_confidence: float = None
    parsed_at: int = None
    manual_shooting_hours: float = 0.0
    is_locked: int = 0
    created_at: int = field(default_factory=lambda: int(time.time()))

    @property
    def page_start_decimal(self):
        return self.page_start_whole + self.page_start_eighths / 8.0

    @property
    def page_end_decimal(self):
        return self.page_end_whole + self.page_end_eighths / 8.0

    @property
    def duration_eighths(self):
        end = Eighths(self.page_end_whole, self.page_end_eighths)
        start = Eighths(self.page_start_whole, self.page_start_eighths)
        return end - start
