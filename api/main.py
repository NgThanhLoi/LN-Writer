import asyncio
import json
import logging
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

# Fix Windows console encoding for Vietnamese text in threads
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import api.database as db
from api.models import (
    CreateNovelRequest, ApproveChapter1Request, ContinueNovelRequest,
    ApproveCharactersRequest, NovelListItem, NovelStatusResponse, ChapterResponse,
    SettingsRequest, SettingsResponse, AgentConfig, UpdateChapterRequest, StyleConfig,
    RollbackRequest,
)
from api.service import (
    broadcaster, checkpoint_gate, start_novel_pipeline,
    start_regen_chapter, start_continue_pipeline,
)
from config import GEMINI_API_KEY, CORS_ORIGIN
from core.ai_adapter import init_gemini


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    broadcaster.set_loop(asyncio.get_running_loop())
    if GEMINI_API_KEY:
        init_gemini(GEMINI_API_KEY)
    yield


app = FastAPI(title="LN Writer API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[CORS_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── GET /settings ─────────────────────────────────────────────────────────

@app.get("/settings", response_model=SettingsResponse)
async def get_settings():
    import config
    return SettingsResponse(
        agents={k: AgentConfig(**v) for k, v in config.AGENT_MODEL_CONFIG.items()},
        ollama_base_url=config.OLLAMA_BASE_URL,
    )


# ── POST /settings ─────────────────────────────────────────────────────────

@app.post("/settings")
async def update_settings(req: SettingsRequest):
    import json as _json
    import config as cfg
    from pathlib import Path

    settings_path = Path(__file__).parent.parent / "settings.json"

    # Load existing or start fresh
    existing: dict = {}
    if settings_path.exists():
        try:
            existing = _json.loads(settings_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

    existing["agents"] = {k: v.model_dump() for k, v in req.agents.items()}
    if req.ollama_base_url:
        existing["ollama_base_url"] = req.ollama_base_url

    settings_path.write_text(
        _json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Update OPENAI_API_KEY in .env safely (append/update, never overwrite whole file)
    if req.openai_api_key:
        _update_env_key("OPENAI_API_KEY", req.openai_api_key)
        cfg.OPENAI_API_KEY = req.openai_api_key

    cfg.reload_config()
    return {"ok": True}


def _update_env_key(key: str, value: str) -> None:
    """Safely update or append a single key in .env without overwriting the file."""
    from pathlib import Path
    env_path = Path(__file__).parent.parent / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    found = False
    new_lines = []
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


# ── GET /novels ────────────────────────────────────────────────────────────

@app.get("/novels", response_model=list[NovelListItem])
async def list_novels():
    rows = db.list_novels()
    result = []
    for r in rows:
        title = None
        genre = None
        if r["blueprint_json"]:
            try:
                bp = json.loads(r["blueprint_json"])
                title = bp.get("title")
                genre = bp.get("genre")
            except Exception:
                pass
        result.append(NovelListItem(
            id=r["id"], title=title, genre=genre,
            status=r["status"], chapter_count=r["chapter_count"],
            total_words=r["total_words"], created_at=r["created_at"],
        ))
    return result


# ── DELETE /novels/{id} ────────────────────────────────────────────────────

@app.delete("/novels/{novel_id}", status_code=204)
async def delete_novel(novel_id: str):
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")
    db.delete_novel(novel_id)


# ── POST /novels/{id}/continue ─────────────────────────────────────────────

@app.post("/novels/{novel_id}/continue")
async def continue_novel(novel_id: str, req: ContinueNovelRequest):
    row = db.get_novel(novel_id)
    if not row:
        raise HTTPException(404, "Novel not found")
    if row["status"] != "completed":
        raise HTTPException(400, "Novel must be completed before continuing")
    if not row["blueprint_json"]:
        raise HTTPException(400, "Blueprint not available")

    genre = req.genre
    if not genre and row["blueprint_json"]:
        bp = json.loads(row["blueprint_json"])
        genre = bp.get("genre", "isekai")

    loop = asyncio.get_running_loop()
    start_continue_pipeline(novel_id, req.num_chapters, genre, loop)
    return {"ok": True}


# ── POST /novels/{id}/approve-characters ───────────────────────────────────

@app.post("/novels/{novel_id}/approve-characters")
async def approve_characters(novel_id: str, req: ApproveCharactersRequest):
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")
    checkpoint_gate.resolve(f"{novel_id}:characters", "approve", data=req.characters)
    return {"ok": True}


# ── POST /novels ───────────────────────────────────────────────────────────

@app.post("/novels", status_code=201)
async def create_novel(req: CreateNovelRequest):
    if not GEMINI_API_KEY:
        raise HTTPException(400, "GEMINI_API_KEY not set. Set env var and restart.")
    # Ensure Gemini is initialized (idempotent if already done at startup)
    init_gemini(GEMINI_API_KEY)

    novel_id = str(uuid.uuid4())
    style_json = req.style_config.model_dump_json() if req.style_config else None
    db.create_novel(novel_id, req.prompt, style_json)

    loop = asyncio.get_running_loop()
    style_dict = req.style_config.model_dump() if req.style_config else None
    start_novel_pipeline(
        novel_id, req.prompt,
        req.num_chapters, req.words_per_chapter,
        req.genre, loop, style_dict,
    )
    return {"id": novel_id}


# ── GET /novels/{id} ──────────────────────────────────────────────────────

@app.get("/novels/{novel_id}", response_model=NovelStatusResponse)
async def get_novel(novel_id: str):
    row = db.get_novel(novel_id)
    if not row:
        raise HTTPException(404, "Novel not found")

    title = None
    premise = None
    if row["blueprint_json"]:
        bp = json.loads(row["blueprint_json"])
        title = bp.get("title")
        premise = bp.get("premise")

    return NovelStatusResponse(
        id=novel_id,
        status=row["status"],
        current_chapter=row["current_chapter"],
        title=title,
        premise=premise,
    )


# ── POST /novels/{id}/approve-plot ────────────────────────────────────────

@app.post("/novels/{novel_id}/approve-plot")
async def approve_plot(novel_id: str, body: dict = None):
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")
    decision = (body or {}).get("decision", "approve")  # "approve" | "reject"
    checkpoint_gate.resolve(f"{novel_id}:plot", decision)
    return {"ok": True}


# ── POST /novels/{id}/approve-chapter-1 ──────────────────────────────────

@app.post("/novels/{novel_id}/approve-chapter-1")
async def approve_chapter1(novel_id: str, req: ApproveChapter1Request):
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")
    # action: "approve" | "skip" | "regen"
    decision = req.action if req.action in ("approve", "skip", "regen") else "approve"
    checkpoint_gate.resolve(f"{novel_id}:chapter1", decision)
    return {"ok": True}


# ── POST /novels/{id}/chapters/{n}/regen ─────────────────────────────────

@app.post("/novels/{novel_id}/chapters/{chapter_number}/regen")
async def regen_chapter(novel_id: str, chapter_number: int):
    row = db.get_novel(novel_id)
    if not row:
        raise HTTPException(404, "Novel not found")
    if not row["blueprint_json"]:
        raise HTTPException(400, "Blueprint not available — pipeline may still be running")
    if not db.get_chapter(novel_id, chapter_number):
        raise HTTPException(404, f"Chapter {chapter_number} not found")

    loop = asyncio.get_running_loop()
    start_regen_chapter(novel_id, chapter_number, loop)
    return {"ok": True, "queued": chapter_number}


# ── PATCH /novels/{id}/chapters/{n} ───────────────────────────────────────

@app.patch("/novels/{novel_id}/chapters/{chapter_number}")
async def update_chapter(novel_id: str, chapter_number: int, req: UpdateChapterRequest):
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")
    if not db.get_chapter(novel_id, chapter_number):
        raise HTTPException(404, "Chapter not found")
    db.update_chapter_content(novel_id, chapter_number, req.content)
    return {"ok": True}


# ── GET /novels/{id}/chapters ─────────────────────────────────────────────

@app.get("/novels/{novel_id}/chapters")
async def get_chapters(novel_id: str):
    rows = db.get_chapters(novel_id)
    return [
        ChapterResponse(
            number=r["number"],
            title=r["title"],
            content=r["content"],
            audit_passed=bool(r["audit_passed"]),
            audit_notes=r["audit_notes"],
            word_count=len(r["content"].split()),
        )
        for r in rows
    ]


# ── GET /novels/{id}/chapters/{n} ─────────────────────────────────────────

@app.get("/novels/{novel_id}/chapters/{chapter_number}")
async def get_chapter(novel_id: str, chapter_number: int):
    row = db.get_chapter(novel_id, chapter_number)
    if not row:
        raise HTTPException(404, "Chapter not found")
    return ChapterResponse(
        number=row["number"],
        title=row["title"],
        content=row["content"],
        audit_passed=bool(row["audit_passed"]),
        audit_notes=row["audit_notes"],
        word_count=len(row["content"].split()),
    )


# ── GET /novels/{id}/download ─────────────────────────────────────────────

@app.get("/novels/{novel_id}/download")
async def download_novel(novel_id: str):
    row = db.get_novel(novel_id)
    if not row:
        raise HTTPException(404, "Novel not found")
    if row["status"] != "completed":
        raise HTTPException(400, "Novel not yet completed")
    path = Path(row["output_path"])
    if not path.exists():
        raise HTTPException(404, "Output file not found")
    return FileResponse(
        str(path),
        media_type="text/markdown",
        filename=path.name,
    )


# ── GET /novels/{id}/download/txt ─────────────────────────────────────────

@app.get("/novels/{novel_id}/download/txt")
async def download_txt(novel_id: str):
    from fastapi.responses import Response
    row = db.get_novel(novel_id)
    if not row:
        raise HTTPException(404, "Novel not found")
    if row["status"] != "completed":
        raise HTTPException(400, "Novel not yet completed")

    chapters = db.get_chapters(novel_id)
    title, premise = "", ""
    if row["blueprint_json"]:
        bp = json.loads(row["blueprint_json"])
        title = bp.get("title", "")
        premise = bp.get("premise", "")

    sep = "═" * 60
    thin = "─" * 40
    lines = [f"{title}\n\n{premise}\n\n{sep}\n\n"]
    for ch in chapters:
        lines.append(f"CHƯƠNG {ch['number']}: {ch['title'].upper()}\n\n")
        lines.append(ch["content"].strip())
        lines.append(f"\n\n{thin}\n\n")

    safe_title = (title[:40] or novel_id[:8]).replace("/", "-").replace("\\", "-")
    return Response(
        content="".join(lines).encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.txt"'},
    )


# ── GET /novels/{id}/download/epub ────────────────────────────────────────

@app.get("/novels/{novel_id}/download/epub")
async def download_epub(novel_id: str):
    try:
        from ebooklib import epub as _epub
    except ImportError:
        raise HTTPException(500, "epub export requires: pip install ebooklib")

    import tempfile, re

    row = db.get_novel(novel_id)
    if not row:
        raise HTTPException(404, "Novel not found")
    if row["status"] != "completed":
        raise HTTPException(400, "Novel not yet completed")

    chapters = db.get_chapters(novel_id)
    title, premise = "Light Novel", ""
    if row["blueprint_json"]:
        bp = json.loads(row["blueprint_json"])
        title = bp.get("title", title)
        premise = bp.get("premise", "")

    book = _epub.EpubBook()
    book.set_title(title)
    book.set_language("vi")
    if premise:
        book.add_metadata("DC", "description", premise)

    epub_chapters = []
    for ch in chapters:
        paras = "".join(
            f"<p>{line}</p>"
            for line in ch["content"].split("\n")
            if line.strip()
        )
        item = _epub.EpubHtml(
            title=ch["title"],
            file_name=f"ch{ch['number']:03d}.xhtml",
            lang="vi",
        )
        item.content = (
            f'<h2>Chương {ch["number"]}: {ch["title"]}</h2>{paras}'
        ).encode("utf-8")
        book.add_item(item)
        epub_chapters.append(item)

    book.toc = epub_chapters
    book.add_item(_epub.EpubNcx())
    book.add_item(_epub.EpubNav())
    book.spine = ["nav"] + epub_chapters

    safe_title = (title[:40] or novel_id[:8]).replace("/", "-").replace("\\", "-")
    tmp = tempfile.NamedTemporaryFile(suffix=".epub", delete=False)
    tmp.close()
    _epub.write_epub(tmp.name, book)
    return FileResponse(
        tmp.name,
        media_type="application/epub+zip",
        filename=f"{safe_title}.epub",
    )


# ── POST /novels/{id}/rollback ─────────────────────────────────────────────

@app.post("/novels/{novel_id}/rollback")
async def rollback_novel(novel_id: str, req: RollbackRequest):
    from datetime import datetime

    row = db.get_novel(novel_id)
    if not row or not row["blueprint_json"]:
        raise HTTPException(404, "Novel not found")
    if row["status"] != "completed":
        raise HTTPException(400, "Novel must be completed to rollback")

    chapters = db.get_chapters(novel_id)
    keep = req.keep_chapters
    if keep < 1:
        raise HTTPException(400, "keep_chapters must be >= 1")
    if keep >= len(chapters):
        raise HTTPException(400, f"Novel only has {len(chapters)} chapter(s) — nothing to remove")

    # Delete chapters + summaries from DB
    db.delete_chapters_from(novel_id, keep + 1)

    # Trim blueprint chapters list
    bp_data = json.loads(row["blueprint_json"])
    bp_data["chapters"] = [c for c in bp_data["chapters"] if c["number"] <= keep]
    bp_data["target_chapters"] = keep
    new_bp_json = json.dumps(bp_data, ensure_ascii=False)
    db.update_novel_blueprint(novel_id, new_bp_json)

    # Rebuild markdown from remaining chapters
    remaining = db.get_chapters(novel_id)
    title = bp_data.get("title", "")
    premise = bp_data.get("premise", "")
    safe_title = (title[:40] or novel_id[:8]).replace("/", "-").replace("\\", "-")
    out_dir = Path(__file__).parent.parent / "output"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = out_dir / f"{ts}_{safe_title}.md"
    lines = [f"# {title}\n", f"*{premise}*\n\n"]
    for ch in remaining:
        lines.append(f"## Chương {ch['number']}: {ch['title']}\n\n")
        lines.append(ch["content"])
        lines.append("\n\n---\n\n")
    md_path.write_text("".join(lines), encoding="utf-8")
    db.update_novel_output_path(novel_id, str(md_path))
    db.update_novel_status(novel_id, "completed", keep)

    return {"ok": True, "chapters_kept": keep}


# ── GET /novels/{id}/timeline ──────────────────────────────────────────────

@app.get("/novels/{novel_id}/timeline")
async def character_timeline(novel_id: str):
    row = db.get_novel(novel_id)
    if not row or not row["blueprint_json"]:
        raise HTTPException(404, "Novel not found")

    bp = json.loads(row["blueprint_json"])
    characters = bp.get("characters", [])
    chapters = db.get_chapters(novel_id)

    result = []
    for char in characters:
        name = char.get("name", "")
        role = char.get("role", "")
        appears_in = [
            ch["number"]
            for ch in chapters
            if name and name.lower() in ch["content"].lower()
        ]
        result.append({"name": name, "role": role, "chapters": appears_in})

    return result


# ── WS /novels/{id}/ws ────────────────────────────────────────────────────

@app.websocket("/novels/{novel_id}/ws")
async def novel_ws(websocket: WebSocket, novel_id: str):
    await websocket.accept()
    q = broadcaster.subscribe(novel_id)

    # Send current novel state immediately on connect
    row = db.get_novel(novel_id)
    if row:
        await websocket.send_json({
            "type": "status",
            "status": row["status"],
            "current_chapter": row["current_chapter"],
        })
        chapters = db.get_chapters(novel_id)
        for ch in chapters:
            await websocket.send_json({
                "type": "chapter_done",
                "number": ch["number"],
                "title": ch["title"],
                "word_count": len(ch["content"].split()),
                "audit_passed": bool(ch["audit_passed"]),
                "audit_notes": ch["audit_notes"],
            })

    try:
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=30)
                await websocket.send_json(event)
            except asyncio.TimeoutError:
                # Ping to keep connection alive
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    finally:
        broadcaster.unsubscribe(novel_id, q)
