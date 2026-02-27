# LN-Writer — Fix Checklist

**Cập nhật:** 2026-02-27 | **Personal tool**

---

## ✅ Phase 1 — Emergency Fixes (DONE)

- [x] `_BridgeEvent.wait()` thêm timeout 30 phút → tránh executor deadlock
- [x] `config.py` summarizer dùng đúng env var `SUMMARIZER_PROVIDER/MODEL`
- [x] `parse_json_response()` wrap `json.loads` trong try/except → raise `ValueError` rõ
- [x] `database._conn()` thêm `PRAGMA foreign_keys = ON`
- [x] `write/[id]/page.tsx` — WS JSON.parse + cancelNovel/approvePlot/approveChapter1 có try/catch

---

## ✅ Quan trọng — ảnh hưởng trực tiếp khi dùng (DONE)

### Frontend: `novels/page.tsx`

- [x] `ws.onmessage` — wrap `JSON.parse(ev.data)` trong try/catch
- [x] `ws.onerror` — thêm `console.error`
- [x] `handleStartContinue` — try/catch + reset loading + `modalError` display
- [x] `handleApproveCharacters` — try/catch + reset loading + `modalError` display
- [x] `handleApprovePlot` — try/catch + reset loading + `modalError` display
- [x] `handleDelete` — try/catch + `console.error`

### Backend: Stream Retry (`core/agents/draft_master.py`)

- [x] `DraftMaster._write()` — vòng for stream bọc trong retry loop 2 lần, reset `chunks` mỗi attempt

---

## ✅ Nên làm (DONE)

### AI Quality

- [x] `_generate_summary` lấy `content[:2000] + "…" + content[-2000:]` thay vì chỉ `[-4000:]`
- [x] Token count warning trong `DraftMaster._write()` — log warning nếu prompt ước tính >30k tokens

### Database (`api/database.py`)

- [x] Indexes `idx_chapters_novel_id` + `idx_summaries_novel_id` thêm vào `init_db()`
- [x] Migration `try/except` chỉ catch `sqlite3.OperationalError` với "duplicate column name", re-raise lỗi thật

### Logging

- [x] `logging.basicConfig(...)` setup ở `api/main.py` (timestamp + level + module name)
- [x] Tất cả `print(...)` trong agents, ai_adapter, service, config → `logger.info/warning/error(...)`
- [x] `traceback.print_exc()` → `logger.error(..., exc_info=True)` ở 3 exception handlers trong service.py

---

## ✅ Tùy thích (DONE)

- [x] `frontend/app/lib/constants.ts` — export `API` + `WS_BASE`, 5 pages import từ đây
- [x] `novels/page.tsx` `ws.onerror` → `console.error`

---

## Bỏ khỏi scope (personal tool)

- ~~Security / auth / rate limiting~~ — chạy localhost
- ~~Accessibility (ARIA)~~ — chỉ mình dùng
- ~~Testing infrastructure~~ — overkill cho side project
- ~~Frontend component refactor~~ — functional là đủ
- ~~Input validation Pydantic~~ — UI đã giới hạn, không cần validate backend
- ~~Repository pattern, DTOs~~ — over-engineer
