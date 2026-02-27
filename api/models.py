from pydantic import BaseModel
from typing import Optional, Dict


class NovelListItem(BaseModel):
    id: str
    title: Optional[str] = None
    genre: Optional[str] = None
    status: str
    chapter_count: int
    total_words: int
    created_at: str


class ContinueNovelRequest(BaseModel):
    num_chapters: int = 3
    genre: Optional[str] = None


class ApproveCharactersRequest(BaseModel):
    characters: list[dict]


class StyleConfig(BaseModel):
    tone: str = "neutral"           # "light" | "neutral" | "tense"
    dialogue_ratio: str = "medium"  # "low" | "medium" | "high"
    custom_note: str = ""
    quality_mode: bool = False      # True = run ContentRefiner after DraftMaster


class CreateNovelRequest(BaseModel):
    prompt: str
    num_chapters: int = 3
    words_per_chapter: int = 4500
    genre: str = "isekai"
    style_config: Optional[StyleConfig] = None


class ApproveChapter1Request(BaseModel):
    action: str  # "approve" | "skip" | "regen"


class NovelStatusResponse(BaseModel):
    id: str
    status: str
    current_chapter: int
    title: Optional[str] = None
    premise: Optional[str] = None


class ChapterResponse(BaseModel):
    number: int
    title: str
    content: str
    audit_passed: bool
    audit_notes: str
    word_count: int


class UpdateChapterRequest(BaseModel):
    content: Optional[str] = None
    notes: Optional[str] = None


class RollbackRequest(BaseModel):
    keep_chapters: int  # keep chapters 1..keep_chapters, delete the rest


class ImportNovelRequest(BaseModel):
    mode: str                           # "content" | "description"
    source_content: str = ""            # Mode A: pasted novel text
    description: str = ""              # Mode B: text description of dropped novel
    num_chapters: int = 3
    words_per_chapter: int = 4500
    genre: str = "isekai"              # Mode B only; Mode A auto-detects
    style_config: Optional[StyleConfig] = None


class AgentConfig(BaseModel):
    provider: str   # "gemini" | "openai" | "ollama"
    model: str


class SettingsRequest(BaseModel):
    agents: Dict[str, AgentConfig]
    ollama_base_url: Optional[str] = None
    openai_api_key: Optional[str] = None   # write-only, never returned in GET


class SettingsResponse(BaseModel):
    agents: Dict[str, AgentConfig]
    ollama_base_url: str
