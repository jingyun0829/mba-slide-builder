"""Generate a 1-2 minute course intro video (course trailer).

Pipeline:
  1. Claude writes the script: full narration text + scene-by-scene storyboard.
  2. ElevenLabs synthesizes the narration → mp3 (Alice voice by default).
  3. Tavily searches a real image per scene (parallel).
  4. PIL resizes/letterboxes images to 1920x1080.
  5. ffmpeg stitches images + audio → mp4.

Output: a self-contained .mp4 file ready to upload anywhere.
Cost: ~$0.05 per video (Claude script + ElevenLabs TTS + Tavily lookups).
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from anthropic import Anthropic

_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
_MODEL = os.getenv("ANTHROPIC_VIDEO_MODEL", "claude-sonnet-4-6")
_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"

# Default voice: Alice — "Clear, Engaging Educator" (free tier)
DEFAULT_VOICE_ID = "Xb7hH8MSUJpSbSDYk0k2"
ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

# Output video resolution (16:9)
TARGET_W, TARGET_H = 1920, 1080


# ---------------- 1. Script generation ----------------

def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip("` \n")
    return text


def _summarize_outline(outline: dict) -> str:
    """Extract a compact text summary of the session's outline for video script context."""
    parts = []
    parts.append(f"Session title: {outline.get('session_title', '')}")
    parts.append(f"Duration: {outline.get('duration_minutes', 90)} minutes")
    if outline.get("learning_objectives"):
        parts.append("Learning objectives:")
        for o in outline["learning_objectives"]:
            parts.append(f"  - {o}")

    parts.append("\nWhat the session covers (slide-by-slide):")
    slides = outline.get("slides") or []
    for s in slides[:30]:  # cap to keep prompt manageable
        title = s.get("title", "")
        stype = (s.get("type") or "concept").lower()
        parts.append(f"  • [{stype}] {title}")
        # Add a few key lines for substance
        lines = s.get("lines") or []
        line_texts = []
        for line in lines[:3]:
            if isinstance(line, str):
                line_texts.append(line)
            elif isinstance(line, dict):
                line_texts.append(line.get("text", ""))
        if line_texts:
            parts.append(f"    └ {' / '.join(line_texts)[:150]}")
        kt = s.get("key_takeaway")
        if kt:
            parts.append(f"    ★ {kt}")

    if outline.get("homework"):
        hw = outline["homework"]
        parts.append(f"\nHomework: {hw.get('title','')} — {hw.get('problem_statement','')[:200]}")

    return "\n".join(parts)


def _generate_script(outline_json: str, duration_seconds: int) -> dict:
    system = (_PROMPT_DIR / "intro_video.md").read_text()
    target_words = int(duration_seconds * 2.4)  # ~140 wpm

    outline = json.loads(outline_json)
    summary = _summarize_outline(outline)

    user_msg = f"""You are previewing this UPCOMING session for prospective students.
Use the session's actual content below to make the script concrete — name the real
companies, concepts, and frameworks that will be covered. The goal is to make students
excited to attend.

{summary}

Target video duration: {duration_seconds} seconds (~{target_words} words narration).

Generate the script JSON."""

    resp = _client.messages.create(
        model=_MODEL,
        max_tokens=4000,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = _strip_fences(resp.content[0].text)
    return json.loads(text)


# ---------------- 2. ElevenLabs TTS ----------------

def _generate_tts(text: str, voice_id: str, output_path: Path) -> None:
    import requests
    key = os.getenv("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY not set in .env")
    url = ELEVENLABS_TTS_URL.format(voice_id=voice_id)
    r = requests.post(
        url,
        headers={"xi-api-key": key, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs TTS failed [{r.status_code}]: {r.text[:300]}")
    output_path.write_bytes(r.content)


def _audio_duration_seconds(audio_path: Path) -> float:
    """Use ffprobe to get audio duration."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


# ---------------- 3. Scene image fetching (parallel) ----------------

def _download_image(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
        if len(data) < 200:
            return False
        dest.write_bytes(data)
        return True
    except Exception:
        return False


def _fetch_scene_images(scenes: list[dict], workdir: Path) -> list[Path | None]:
    """Search and download an image per scene in parallel."""
    try:
        from pipeline.image_search import search_image
    except Exception:
        return [None] * len(scenes)

    def _one(idx_scene):
        idx, scene = idx_scene
        query = (scene.get("image_query") or "").strip()
        if not query:
            return idx, None
        info = search_image(query)
        if not info or not info.get("url"):
            return idx, None
        url = info["url"]
        ext = url.split(".")[-1].split("?")[0].lower()
        if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
            ext = "jpg"
        dest = workdir / f"scene_raw_{idx:02d}.{ext}"
        ok = _download_image(url, dest)
        return idx, (dest if ok else None)

    out = [None] * len(scenes)
    with ThreadPoolExecutor(max_workers=8) as ex:
        for idx, path in ex.map(_one, list(enumerate(scenes))):
            out[idx] = path
    return out


# ---------------- 4. Image normalization (1920x1080 letterbox) ----------------

def _make_placeholder(workdir: Path, idx: int, caption: str = "") -> Path:
    """When image search fails, render a teal card with the scene caption as fallback."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (TARGET_W, TARGET_H), color=(13, 148, 136))  # teal #0d9488
    if caption:
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 60)
        except Exception:
            font = ImageFont.load_default()
        # Wrap text manually
        max_chars_per_line = 32
        words = caption.split()
        lines, line = [], ""
        for w in words:
            if len(line) + len(w) + 1 <= max_chars_per_line:
                line = (line + " " + w).strip()
            else:
                lines.append(line); line = w
        if line: lines.append(line)
        # Center vertically
        line_height = 80
        total_h = line_height * len(lines)
        y = (TARGET_H - total_h) // 2
        for ln in lines:
            bbox = draw.textbbox((0, 0), ln, font=font)
            w = bbox[2] - bbox[0]
            x = (TARGET_W - w) // 2
            draw.text((x, y), ln, fill=(255, 255, 255), font=font)
            y += line_height
    dest = workdir / f"placeholder_{idx:02d}.jpg"
    img.save(dest, "JPEG", quality=88)
    return dest


def _normalize_images(image_paths: list[Path | None], scenes: list[dict],
                      workdir: Path) -> list[Path]:
    """Resize each image to 1920x1080 letterboxed; placeholder if missing."""
    from PIL import Image
    normalized = []
    for i, src in enumerate(image_paths):
        scene = scenes[i] if i < len(scenes) else {}
        if src is None or not src.exists():
            normalized.append(_make_placeholder(workdir, i, scene.get("on_screen_caption") or scene.get("image_query", "")))
            continue
        try:
            img = Image.open(src).convert("RGB")
            img.thumbnail((TARGET_W, TARGET_H), Image.LANCZOS)
            canvas = Image.new("RGB", (TARGET_W, TARGET_H), color=(8, 28, 28))
            x = (TARGET_W - img.width) // 2
            y = (TARGET_H - img.height) // 2
            canvas.paste(img, (x, y))
            dest = workdir / f"scene_norm_{i:02d}.jpg"
            canvas.save(dest, "JPEG", quality=88)
            normalized.append(dest)
        except Exception:
            normalized.append(_make_placeholder(workdir, i, scene.get("image_query", "")))
    return normalized


# ---------------- 5. ffmpeg stitching ----------------

def _build_concat_file(image_paths: list[Path], scenes: list[dict],
                       audio_duration: float, workdir: Path) -> Path:
    """Calibrate scene durations to match the actual audio length, then write concat.txt."""
    raw_durs = [float(s.get("duration_seconds") or 0) for s in scenes]
    total = sum(raw_durs)
    if total <= 0:
        durs = [audio_duration / max(1, len(scenes))] * len(scenes)
    else:
        scale = audio_duration / total
        durs = [d * scale for d in raw_durs]

    concat_path = workdir / "scenes_concat.txt"
    lines = []
    for path, dur in zip(image_paths, durs):
        lines.append(f"file '{path.absolute()}'")
        lines.append(f"duration {dur:.3f}")
    # ffmpeg concat demuxer quirk: last image must be repeated once without duration
    lines.append(f"file '{image_paths[-1].absolute()}'")
    concat_path.write_text("\n".join(lines))
    return concat_path


def _run_ffmpeg(concat_path: Path, audio_path: Path, output_path: Path) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_path),
        "-i", str(audio_path),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-vf", "fps=24,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-500:]}")


# ---------------- Public API ----------------

def generate_intro_video(
    outline_json: str,
    output_path: str,
    duration_seconds: int = 90,
    voice_id: str = DEFAULT_VOICE_ID,
) -> dict:
    """Generate a 1-2 min preview video for the upcoming session. Returns metadata dict.

    Uses the session's actual outline (Stage 3/4) so the video references the real
    companies, concepts, and homework that will be covered — not generic course-level pitch.
    """
    workdir = Path(tempfile.mkdtemp(prefix="previewvideo_"))

    # 1. Script
    script = _generate_script(outline_json, duration_seconds)
    narration = script.get("narration", "")
    scenes = script.get("scenes") or []
    if not narration or not scenes:
        raise RuntimeError("Script missing narration or scenes.")

    # 2. TTS
    audio_path = workdir / "narration.mp3"
    _generate_tts(narration, voice_id, audio_path)
    audio_dur = _audio_duration_seconds(audio_path)

    # 3. Images (parallel)
    raw_imgs = _fetch_scene_images(scenes, workdir)

    # 4. Normalize to 1920x1080
    norm_imgs = _normalize_images(raw_imgs, scenes, workdir)

    # 5. Stitch with ffmpeg
    concat_path = _build_concat_file(norm_imgs, scenes, audio_dur, workdir)
    _run_ffmpeg(concat_path, audio_path, Path(output_path))

    # Pull the session title from the outline as a fallback for video title
    try:
        _session_title = json.loads(outline_json).get("session_title", "Session preview")
    except Exception:
        _session_title = "Session preview"

    return {
        "path": str(output_path),
        "title": script.get("title", _session_title),
        "duration_seconds": round(audio_dur, 1),
        "scene_count": len(scenes),
        "image_hits": sum(1 for p in raw_imgs if p is not None),
        "narration_preview": narration[:160] + ("..." if len(narration) > 160 else ""),
    }
