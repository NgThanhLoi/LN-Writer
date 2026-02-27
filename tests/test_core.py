"""
Core unit tests — cover bug fixes + Tier 1 + Tier 2 changes.
Run: pytest tests/ -v
"""
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────

def _make_char_dict(**overrides):
    base = {
        "id": "char_001",
        "name": "Aria",
        "role": "protagonist",
        "personality_traits": ["brave", "kind"],
        "speech_pattern": "formal",
        "backstory": "orphan",
        "goals": ["save the world"],
        "current_state": "active",
        "core_value": "justice",
        "fear": "failure",
        "weakness": "overconfident",
        "catchphrase": "Let's go!",
        "relationships": [],
    }
    base.update(overrides)
    return base


# ── B2: CharacterRelationship deserialization in _continue_sync ───────────

class TestCharacterRelationshipDeserialization:
    """B2 fix: CharacterProfile(**c) leaves relationships as plain dicts."""

    def test_old_way_produces_dict_not_dataclass(self):
        from core.models import CharacterProfile, CharacterRelationship

        c = _make_char_dict(relationships=[
            {"target_name": "Hero", "type": "ally", "dynamic": "mentor"}
        ])
        result = CharacterProfile(**c)
        # Old (unfixed) approach keeps relationships as plain dicts
        assert not isinstance(result.relationships[0], CharacterRelationship), (
            "Old approach should NOT auto-coerce to CharacterRelationship"
        )

    def test_new_way_produces_proper_dataclass(self):
        from core.models import CharacterProfile, CharacterRelationship

        c = _make_char_dict(relationships=[
            {"target_name": "Hero", "type": "ally", "dynamic": "mentor"}
        ])
        c = dict(c)
        rels = [CharacterRelationship(**r) for r in c.pop("relationships", [])]
        result = CharacterProfile(**c, relationships=rels)

        assert isinstance(result.relationships[0], CharacterRelationship)
        assert result.relationships[0].target_name == "Hero"
        assert result.relationships[0].type == "ally"

    def test_empty_relationships_ok(self):
        from core.models import CharacterProfile, CharacterRelationship

        c = _make_char_dict(relationships=[])
        c = dict(c)
        rels = [CharacterRelationship(**r) for r in c.pop("relationships", [])]
        result = CharacterProfile(**c, relationships=rels)
        assert result.relationships == []


# ── B7: OpenAI stream empty choices guard ─────────────────────────────────

class TestOpenAIStreamGuard:
    """B7 fix: chunk.choices[0] crashes when choices is empty."""

    def _run_stream(self, mock_chunks):
        """Simulate the fixed generate_stream loop."""
        collected = []
        for chunk in mock_chunks:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                collected.append(delta)
        return collected

    def _make_chunk(self, content):
        chunk = MagicMock()
        choice = MagicMock()
        choice.delta.content = content
        chunk.choices = [choice]
        return chunk

    def _make_empty_chunk(self):
        chunk = MagicMock()
        chunk.choices = []
        return chunk

    def test_empty_choices_skipped(self):
        chunks = [self._make_empty_chunk(), self._make_chunk("hello")]
        assert self._run_stream(chunks) == ["hello"]

    def test_none_content_skipped(self):
        chunks = [self._make_chunk(None), self._make_chunk("world")]
        assert self._run_stream(chunks) == ["world"]

    def test_normal_stream(self):
        chunks = [self._make_chunk("Hello"), self._make_chunk(" world")]
        assert self._run_stream(chunks) == ["Hello", " world"]

    def test_all_empty_returns_empty(self):
        chunks = [self._make_empty_chunk(), self._make_empty_chunk()]
        assert self._run_stream(chunks) == []


# ── parse_json_response ────────────────────────────────────────────────────

class TestParseJsonResponse:
    def test_plain_json(self):
        from core.ai_adapter import parse_json_response
        assert parse_json_response('{"passed": true}') == {"passed": True}

    def test_fenced_json(self):
        from core.ai_adapter import parse_json_response
        raw = '```json\n{"passed": true}\n```'
        assert parse_json_response(raw) == {"passed": True}

    def test_invalid_raises_value_error(self):
        from core.ai_adapter import parse_json_response
        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_json_response("not json at all")

    def test_empty_raises_value_error(self):
        from core.ai_adapter import parse_json_response
        with pytest.raises(ValueError):
            parse_json_response("")


# ── Database: delete_chapters_from ────────────────────────────────────────

class TestDeleteChaptersFrom:
    """Tier 2: rollback DB function."""

    @pytest.fixture
    def tmp_db(self, tmp_path, monkeypatch):
        db_path = tmp_path / "test.db"
        import api.database as db_module
        monkeypatch.setattr(db_module, "DB_PATH", db_path)
        db_module.init_db()
        return db_module

    def test_deletes_chapters_and_summaries(self, tmp_db):
        db = tmp_db
        db.create_novel("novel1", "test prompt")
        for i in range(1, 5):
            db.save_chapter_with_summary(
                "novel1", f"ch_{i:03d}", i, f"Title {i}",
                f"Content of chapter {i}", True, "", f"Summary {i}",
            )

        db.delete_chapters_from("novel1", 3)  # delete ch 3, 4

        remaining = db.get_chapters("novel1")
        assert [c["number"] for c in remaining] == [1, 2]

        summaries = db.get_summaries("novel1")
        assert list(summaries.keys()) == [1, 2]

    def test_delete_from_1_removes_all(self, tmp_db):
        db = tmp_db
        db.create_novel("novel2", "test")
        db.save_chapter_with_summary("novel2", "ch_001", 1, "T1", "C1", True, "", "S1")
        db.save_chapter_with_summary("novel2", "ch_002", 2, "T2", "C2", True, "", "S2")

        db.delete_chapters_from("novel2", 1)
        assert db.get_chapters("novel2") == []

    def test_delete_from_beyond_count_deletes_nothing(self, tmp_db):
        db = tmp_db
        db.create_novel("novel3", "test")
        db.save_chapter_with_summary("novel3", "ch_001", 1, "T1", "C1", True, "", "")

        db.delete_chapters_from("novel3", 5)  # nothing >= 5
        assert len(db.get_chapters("novel3")) == 1


# ── Rollback blueprint trimming logic ─────────────────────────────────────

class TestRollbackBlueprintTrim:
    """Tier 2: rollback endpoint — blueprint trimming."""

    def test_trim_chapters(self):
        bp = {
            "title": "Novel",
            "premise": "Test",
            "chapters": [{"number": i} for i in range(1, 6)],
            "target_chapters": 5,
        }
        keep = 3
        bp["chapters"] = [c for c in bp["chapters"] if c["number"] <= keep]
        bp["target_chapters"] = keep

        assert len(bp["chapters"]) == 3
        assert bp["chapters"][-1]["number"] == 3
        assert bp["target_chapters"] == 3

    def test_trim_to_one(self):
        bp = {"chapters": [{"number": 1}, {"number": 2}], "target_chapters": 2}
        keep = 1
        bp["chapters"] = [c for c in bp["chapters"] if c["number"] <= keep]
        bp["target_chapters"] = keep
        assert len(bp["chapters"]) == 1


# ── Character timeline search logic ───────────────────────────────────────

class TestTimelineSearch:
    """Tier 2: timeline endpoint — substring search."""

    CHAPTERS = [
        {"number": 1, "content": "Aria buoc vao can phong."},
        {"number": 2, "content": "Zephyr va Aria gap nhau."},
        {"number": 3, "content": "Zephyr roi di mot minh."},
    ]
    CHARACTERS = [
        {"name": "Aria", "role": "protagonist"},
        {"name": "Zephyr", "role": "antagonist"},
        {"name": "Ghost", "role": "supporting"},
    ]

    def _search(self, characters, chapters):
        result = []
        for char in characters:
            name = char["name"]
            appears_in = [
                ch["number"]
                for ch in chapters
                if name and name.lower() in ch["content"].lower()
            ]
            result.append({"name": name, "role": char["role"], "chapters": appears_in})
        return result

    def test_aria_appears_in_ch1_ch2(self):
        result = self._search(self.CHARACTERS, self.CHAPTERS)
        aria = next(r for r in result if r["name"] == "Aria")
        assert aria["chapters"] == [1, 2]

    def test_zephyr_appears_in_ch2_ch3(self):
        result = self._search(self.CHARACTERS, self.CHAPTERS)
        zephyr = next(r for r in result if r["name"] == "Zephyr")
        assert zephyr["chapters"] == [2, 3]

    def test_ghost_appears_nowhere(self):
        result = self._search(self.CHARACTERS, self.CHAPTERS)
        ghost = next(r for r in result if r["name"] == "Ghost")
        assert ghost["chapters"] == []

    def test_case_insensitive(self):
        chapters = [{"number": 1, "content": "ARIA said hello."}]
        result = self._search([{"name": "Aria", "role": "protagonist"}], chapters)
        assert result[0]["chapters"] == [1]


# ── DraftMaster stream retry ───────────────────────────────────────────────

class TestDraftMasterStreamRetry:
    """Stream retry loop: 2 attempts, reset chunks each time, raise after both fail."""

    def _run_retry(self, stream_fn):
        """Simulate the retry loop from draft_master._write()."""
        import time as _time
        last_error = None
        chunks = []
        for attempt in range(1, 3):
            chunks = []
            try:
                for chunk in stream_fn(attempt):
                    chunks.append(chunk)
                break
            except Exception as e:
                last_error = e
        else:
            raise RuntimeError(f"Stream failed after 2 attempts: {last_error}") from last_error
        return "".join(chunks)

    def test_success_on_first_attempt(self):
        def stream(attempt):
            yield "hello"
            yield " world"
        assert self._run_retry(stream) == "hello world"

    def test_retry_on_first_failure_succeeds_on_second(self):
        call_count = {"n": 0}
        def stream(attempt):
            call_count["n"] += 1
            if attempt == 1:
                raise RuntimeError("network blip")
            yield "recovered"
        assert self._run_retry(stream) == "recovered"

    def test_chunks_reset_between_attempts(self):
        collected_at_break = []
        def stream(attempt):
            if attempt == 1:
                yield "partial"
                raise RuntimeError("fail mid-stream")
            yield "clean"
        result = self._run_retry(stream)
        # Should NOT contain "partial" from failed attempt
        assert result == "clean"
        assert "partial" not in result

    def test_both_fail_raises(self):
        def stream(attempt):
            raise RuntimeError(f"fail {attempt}")
            yield  # make it a generator
        with pytest.raises(RuntimeError, match="Stream failed after 2 attempts"):
            self._run_retry(stream)


# ── Summary truncation logic ───────────────────────────────────────────────

class TestSummaryTruncation:
    """_generate_summary: head+tail truncation preserves both ends."""

    def _truncate(self, content, limit=4000):
        if len(content) > limit:
            half = limit // 2
            return content[:half] + "\n…\n" + content[-half:]
        return content

    def test_short_content_unchanged(self):
        content = "Short content"
        assert self._truncate(content) == content

    def test_long_content_truncated(self):
        content = "A" * 2000 + "B" * 2000 + "C" * 100
        result = self._truncate(content)
        assert result.startswith("A" * 2000)
        assert result.endswith("C" * 100)
        assert "…" in result

    def test_truncated_shorter_than_original(self):
        content = "X" * 5000
        result = self._truncate(content)
        assert len(result) < len(content)


# ── Word count consistency ─────────────────────────────────────────────────

class TestWordCountConsistency:
    """Word count uses len(content.split()) consistently in Python; JS uses split(/\\s+/).filter(Boolean)."""

    def test_python_word_count(self):
        content = "Hello world này là test"
        assert len(content.split()) == 5

    def test_empty_content(self):
        assert len("".split()) == 0

    def test_multiple_spaces(self):
        # Python split() handles multiple spaces correctly
        content = "word1  word2   word3"
        assert len(content.split()) == 3
