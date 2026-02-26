#!/usr/bin/env python3
"""
LN Writer MVP
Usage: python run.py "Your story idea here"
       python run.py "Một học sinh cấp 3 bị isekai vào thế giới game"
"""
import sys
import os
import uuid
from datetime import datetime

# Fix Windows console encoding for Vietnamese
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.ai_adapter import init_gemini
from core.models import NovelProject
from core.pipeline import LightNovelPipeline
from config import OUTPUT_DIR


def save_output(project: NovelProject) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c for c in project.blueprint.title if c.isalnum() or c in " _-")[:40]
    filename = f"{OUTPUT_DIR}/{timestamp}_{safe_title}.md"

    with open(filename, "w", encoding="utf-8") as f:
        bp = project.blueprint
        f.write(f"# {bp.title}\n\n")
        f.write(f"*{bp.premise}*\n\n")
        f.write(f"---\n\n")

        for chapter in bp.chapters:
            f.write(f"## Chương {chapter.number}: {chapter.title}\n\n")
            f.write(chapter.content)
            f.write("\n\n---\n\n")

    return filename


def main():
    if len(sys.argv) < 2:
        print("Usage: python run.py \"Your story idea here\"")
        sys.exit(1)

    user_prompt = " ".join(sys.argv[1:])
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        print("Set it with: set GEMINI_API_KEY=your_key_here  (Windows)")
        sys.exit(1)

    print(f"\n LN Writer MVP")
    print(f" Prompt: {user_prompt}")
    print(f" Output: {OUTPUT_DIR}/\n")

    init_gemini(api_key)

    project = NovelProject(
        id=str(uuid.uuid4())[:8],
        user_prompt=user_prompt,
    )

    pipeline = LightNovelPipeline()
    project = pipeline.run(project)

    if project.status.value == "completed":
        output_file = save_output(project)
        print(f"\n Done! Output saved to: {output_file}")
        chapters = project.blueprint.chapters
        total_words = sum(len(ch.content.split()) for ch in chapters)
        print(f" {len(chapters)} chapters | {total_words:,} words total")
    else:
        print(f"\n Pipeline ended with status: {project.status.value}")


if __name__ == "__main__":
    main()
