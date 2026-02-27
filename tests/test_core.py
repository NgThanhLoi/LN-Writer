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


# ── ContentRefiner sanity check (50% guard) ───────────────────────────────

class TestContentRefinerSanityCheck:
    """content_refiner.py: if refined < 50% of original words, keep original."""

    def _apply_sanity(self, original: str, refined: str) -> str:
        """Mirrors the sanity check logic in ContentRefinerAgent.run()."""
        original_words = len(original.split())
        refined_words = len(refined.split())
        if refined_words < original_words * 0.5:
            return original
        return refined

    def test_refined_above_threshold_returns_refined(self):
        original = " ".join(["word"] * 100)   # 100 words
        refined  = " ".join(["word"] * 80)    # 80 words — 80% of original
        assert self._apply_sanity(original, refined) == refined

    def test_refined_below_threshold_returns_original(self):
        original = " ".join(["word"] * 100)
        refined  = " ".join(["word"] * 40)    # 40 words — 40% of original
        assert self._apply_sanity(original, refined) == original

    def test_refined_exactly_50_percent_returns_refined(self):
        # Boundary: exactly 50% is NOT less-than, so refined is accepted
        original = " ".join(["word"] * 100)
        refined  = " ".join(["word"] * 50)
        assert self._apply_sanity(original, refined) == refined

    def test_refined_one_below_threshold_returns_original(self):
        original = " ".join(["word"] * 100)
        refined  = " ".join(["word"] * 49)    # 49 < 50 → keep original
        assert self._apply_sanity(original, refined) == original


# ── GENRE_REFINEMENT_HINTS completeness ───────────────────────────────────

class TestGenreRefinementHints:
    """refiner_prompts.py: all 6 genres present with non-empty content."""

    EXPECTED_GENRES = {"isekai", "tu_tien", "xuyen_khong", "romance", "kinh_di", "hanh_dong"}

    def test_all_6_genres_present(self):
        from core.prompts.refiner_prompts import GENRE_REFINEMENT_HINTS
        assert set(GENRE_REFINEMENT_HINTS.keys()) == self.EXPECTED_GENRES

    def test_all_hints_non_empty(self):
        from core.prompts.refiner_prompts import GENRE_REFINEMENT_HINTS
        for genre, hint in GENRE_REFINEMENT_HINTS.items():
            assert hint.strip(), f"Hint for '{genre}' is empty"

    def test_unknown_genre_uses_fallback(self):
        from core.prompts.refiner_prompts import GENRE_REFINEMENT_HINTS
        FALLBACK = "isekai"
        unknown = GENRE_REFINEMENT_HINTS.get("xyzzy", GENRE_REFINEMENT_HINTS[FALLBACK])
        assert unknown == GENRE_REFINEMENT_HINTS[FALLBACK]


# ── BlueprintExtractor: content truncation ────────────────────────────────

class TestBlueprintExtractorTruncation:
    """blueprint_extractor.py: content > 200k chars → head + tail truncation."""

    LIMIT = 200_000
    HALF  = 100_000
    CONNECTOR = "[...nội dung giữa bị cắt bớt để fit context...]"

    def _truncate(self, content: str) -> str:
        """Mirrors the truncation logic in BlueprintExtractorAgent.run()."""
        if len(content) > self.LIMIT:
            return (
                content[:self.HALF]
                + "\n\n[...nội dung giữa bị cắt bớt để fit context...]\n\n"
                + content[-self.HALF:]
            )
        return content

    def test_short_content_unchanged(self):
        content = "A" * 100
        assert self._truncate(content) == content

    def test_exactly_at_limit_unchanged(self):
        content = "A" * self.LIMIT
        assert self._truncate(content) == content

    def test_over_limit_is_truncated(self):
        content = "A" * self.HALF + "B" * self.HALF + "C" * 1000
        result = self._truncate(content)
        assert len(result) < len(content)

    def test_head_and_tail_preserved(self):
        head = "H" * self.HALF
        tail = "T" * self.HALF
        content = head + "M" * 1000 + tail
        result = self._truncate(content)
        assert result.startswith(head)
        assert result.endswith(tail)

    def test_connector_present_in_truncated(self):
        content = "X" * (self.LIMIT + 1000)
        result = self._truncate(content)
        assert self.CONNECTOR in result


# ── BlueprintExtractor: chapter stub numbering ────────────────────────────

class TestBlueprintExtractorChapterStubs:
    """blueprint_extractor.py: new chapter stubs are numbered from existing_count+1."""

    def _make_stubs(self, existing_count: int, num_new: int, cliffhanger: str = ""):
        """Mirrors the stub-creation logic in BlueprintExtractorAgent.run()."""
        start_num = existing_count + 1
        return [
            {
                "number": start_num + i - 1,
                "opening_hook": cliffhanger if i == 1 else "",
            }
            for i in range(1, num_new + 1)
        ]

    def test_stubs_start_after_existing(self):
        stubs = self._make_stubs(existing_count=5, num_new=3)
        assert stubs[0]["number"] == 6
        assert stubs[-1]["number"] == 8

    def test_stubs_numbered_sequentially(self):
        stubs = self._make_stubs(existing_count=0, num_new=5)
        numbers = [s["number"] for s in stubs]
        assert numbers == [1, 2, 3, 4, 5]

    def test_first_stub_has_cliffhanger(self):
        cliff = "Hắn đứng trước cửa hang, không biết bên trong ẩn chứa gì."
        stubs = self._make_stubs(existing_count=10, num_new=3, cliffhanger=cliff)
        assert stubs[0]["opening_hook"] == cliff
        assert stubs[1]["opening_hook"] == ""
        assert stubs[2]["opening_hook"] == ""

    def test_zero_existing_starts_at_1(self):
        stubs = self._make_stubs(existing_count=0, num_new=1)
        assert stubs[0]["number"] == 1


# ── Search snippet logic ───────────────────────────────────────────────────

class TestSearchSnippet:
    """main.py search_novel: snippet boundary conditions."""

    def _extract_snippet(self, content: str, q: str):
        """Mirrors snippet logic in search_novel()."""
        q_lower = q.lower()
        idx = content.lower().find(q_lower)
        if idx == -1:
            return None
        start = max(0, idx - 60)
        end   = min(len(content), idx + len(q) + 60)
        return ("…" if start > 0 else "") + content[start:end] + ("…" if end < len(content) else "")

    def test_match_at_start_no_leading_ellipsis(self):
        content = "Aria bước vào căn phòng tối."
        snippet = self._extract_snippet(content, "Aria")
        assert snippet is not None
        assert not snippet.startswith("…")

    def test_match_at_end_no_trailing_ellipsis(self):
        content = "Một câu chuyện về Aria"
        snippet = self._extract_snippet(content, "Aria")
        assert snippet is not None
        assert not snippet.endswith("…")

    def test_match_in_middle_has_leading_ellipsis(self):
        # content > 60 chars before the match
        prefix = "A" * 80
        content = prefix + "Aria" + "B" * 80
        snippet = self._extract_snippet(content, "Aria")
        assert snippet is not None
        assert snippet.startswith("…")

    def test_match_in_middle_has_trailing_ellipsis(self):
        prefix  = "A" * 80
        content = prefix + "Aria" + "B" * 80
        snippet = self._extract_snippet(content, "Aria")
        assert snippet is not None
        assert snippet.endswith("…")

    def test_no_match_returns_none(self):
        content = "Không có từ đó trong nội dung."
        assert self._extract_snippet(content, "Zephyr") is None

    def test_case_insensitive_find(self):
        content = "ARIA bước vào."
        snippet = self._extract_snippet(content, "aria")
        assert snippet is not None
        assert "ARIA" in snippet


# ── is_continuation DB migration (idempotent) ─────────────────────────────

class TestIsContiunationMigration:
    """database.py: is_continuation column added by init_db(), migration is idempotent."""

    @pytest.fixture
    def tmp_db(self, tmp_path, monkeypatch):
        db_path = tmp_path / "test_migration.db"
        import api.database as db_module
        monkeypatch.setattr(db_module, "DB_PATH", db_path)
        db_module.init_db()
        return db_module, db_path

    def test_column_exists_after_init(self, tmp_db):
        db_module, db_path = tmp_db
        with sqlite3.connect(db_path) as conn:
            cols = [row[1] for row in conn.execute("PRAGMA table_info(novels)").fetchall()]
        assert "is_continuation" in cols

    def test_migration_is_idempotent(self, tmp_db):
        db_module, db_path = tmp_db
        # Running init_db() again must not raise (ALTER TABLE is guarded by try/except)
        db_module.init_db()  # second call — should not blow up
        with sqlite3.connect(db_path) as conn:
            cols = [row[1] for row in conn.execute("PRAGMA table_info(novels)").fetchall()]
        assert "is_continuation" in cols


# ── CheckpointGate cleanup ─────────────────────────────────────────────────

class TestCheckpointGateCleanup:
    """service.py: CheckpointGate.cleanup() removes all state for a novel."""

    def _make_gate_with_data(self, novel_id: str):
        from api.service import CheckpointGate
        gate = CheckpointGate()
        # Inject state directly (avoid asyncio.Event dependency)
        for suffix in (":plot", ":chapter1", ":characters"):
            key = f"{novel_id}{suffix}"
            gate._decisions[key] = "approve"
            gate._data[key] = {"payload": suffix}
        return gate

    def test_cleanup_removes_decisions(self):
        gate = self._make_gate_with_data("novel_abc")
        gate.cleanup("novel_abc")
        for suffix in (":plot", ":chapter1", ":characters"):
            assert f"novel_abc{suffix}" not in gate._decisions

    def test_cleanup_removes_data(self):
        gate = self._make_gate_with_data("novel_abc")
        gate.cleanup("novel_abc")
        for suffix in (":plot", ":chapter1", ":characters"):
            assert f"novel_abc{suffix}" not in gate._data

    def test_cleanup_does_not_affect_other_novel(self):
        gate = self._make_gate_with_data("novel_abc")
        gate._decisions["novel_xyz:plot"] = "approve"
        gate.cleanup("novel_abc")
        assert "novel_xyz:plot" in gate._decisions

    def test_cleanup_missing_key_is_safe(self):
        from api.service import CheckpointGate
        gate = CheckpointGate()
        gate.cleanup("nonexistent_novel")  # must not raise
