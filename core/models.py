from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class NovelStatus(Enum):
    CREATED = "created"
    NAVIGATING_PLOT = "navigating_plot"
    BUILDING_CHARACTERS = "building_characters"
    AWAITING_PLOT_APPROVAL = "awaiting_plot_approval"
    DRAFTING = "drafting"
    AUDITING = "auditing"
    AWAITING_CHAPTER1_APPROVAL = "awaiting_chapter1_approval"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CharacterRelationship:
    target_name: str          # tên nhân vật kia
    type: str                 # "friend" | "rival" | "mentor" | "enemy" | "romantic"
    dynamic: str              # mô tả 1 câu về dynamic cụ thể


@dataclass
class CharacterProfile:
    id: str
    name: str
    role: str                       # protagonist / antagonist / supporting
    personality_traits: List[str]
    speech_pattern: str
    backstory: str
    goals: List[str]
    current_state: str = ""
    core_value: str = ""            # Tầng 1: điều nhân vật không bao giờ thỏa hiệp
    fear: str = ""                  # Tầng 1: nỗi sợ lớn nhất → nguồn conflict
    weakness: str = ""              # Tầng 3: giới hạn/điểm yếu tạo drama
    catchphrase: str = ""           # Tầng 7: câu nói/biểu hiện đặc trưng
    relationships: List[CharacterRelationship] = field(default_factory=list)


@dataclass
class Chapter:
    id: str
    number: int
    title: str
    opening_hook: str
    ending_cliffhanger: str
    pov_character: str
    outline_beats: List[str]        # Story beats để Draft Master follow
    content: str = ""
    audit_passed: bool = False
    audit_notes: str = ""


@dataclass
class StoryBlueprint:
    title: str
    premise: str
    genre: str = "isekai"
    target_chapters: int = 3
    words_per_chapter: int = 4500
    chapters: List[Chapter] = field(default_factory=list)
    characters: List[CharacterProfile] = field(default_factory=list)
    world_summary: str = ""
    style_config: Optional[dict] = None


@dataclass
class NovelProject:
    id: str
    user_prompt: str
    blueprint: Optional[StoryBlueprint] = None
    status: NovelStatus = NovelStatus.CREATED
    current_chapter: int = 0
    output_path: str = ""
