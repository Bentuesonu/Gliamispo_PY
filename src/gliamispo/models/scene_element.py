from dataclasses import dataclass, field
from enum import Enum
import time


class BreakdownCategory(Enum):
    CAST = "Cast"
    EXTRAS = "Extras"
    STUNTS = "Stunts"
    INTIMACY = "Intimacy"
    VEHICLES = "Vehicles"
    PROPS = "Props"
    SPECIAL_FX = "Special FX"
    WARDROBE = "Wardrobe"
    MAKEUP = "Makeup"
    LIVESTOCK = "Livestock"
    ANIMAL_HANDLERS = "Animal Handlers"
    MUSIC = "Music"
    SOUND = "Sound"
    SET_DRESSING = "Set Dressing"
    GREENERY = "Greenery"
    SPECIAL_EQUIPMENT = "Special Equipment"
    SECURITY = "Security"
    ADDITIONAL_LABOR = "Additional Labor"
    VFX = "VFX"
    MECHANICAL_FX = "Mechanical FX"
    NOTES = "Notes"


VALID_CATEGORIES_SQL = ", ".join(f"'{c.value}'" for c in BreakdownCategory)


@dataclass
class SceneElement:
    id: int = 0
    scene_id: int = 0
    category: str = ""
    element_name: str = ""
    quantity: int = 1
    notes: str = ""
    ai_suggested: int = 0
    ai_confidence: float = None
    ai_model_version: str = "v0.0.0"
    detection_method: str = "vocabulary"
    user_verified: int = 0
    user_modified: int = 0
    original_category: str = None
    modified_at: int = None
    created_at: int = field(default_factory=lambda: int(time.time()))
