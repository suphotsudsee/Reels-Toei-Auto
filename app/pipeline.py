import json
import os
import re
import subprocess
import unicodedata
from pathlib import Path
import numpy as np
from minio import Minio
from moviepy import AudioFileClip, CompositeVideoClip, ImageClip, VideoFileClip
from PIL import Image, ImageDraw, ImageFont
from pythainlp.tokenize import word_tokenize
from .config import settings
from .providers import download_pexels_video, generate_json, text_to_speech


def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout


def write_json(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def research(job, root: Path) -> Path:
    data = generate_json(
        "You are a careful short-video researcher. Return JSON only and avoid unsupported medical claims.",
        f"Research topic: {job.topic}. Language: {job.language}. Return title, audience, 5 key_facts, 3 angles, safety_notes, and source_queries.",
    )
    if not data:
        data = {"title": job.topic, "audience": "general", "key_facts": [], "angles": [job.topic], "safety_notes": ["ตรวจสอบข้อเท็จจริงก่อนเผยแพร่"], "source_queries": [job.topic], "mode": "offline-fallback"}
    return write_json(root / "01_research.json", data)


def script(job, root: Path) -> Path:
    notes = (root / "01_research.json").read_text(encoding="utf-8")
    data = generate_json(
        "You write punchy vertical-video scripts. Return JSON only. Narration must fit the requested duration.",
        f"Create a {job.target_seconds}-second script in {job.language} from research {notes}. Return hook, scenes (narration, broll_query, seconds), cta and disclaimer.",
    )
    if not data or not data.get("scenes"):
        scene_seconds = max(5, job.target_seconds // 4)
        data = {"hook": job.topic, "scenes": [
            {"narration": f"วันนี้เรามารู้จัก {job.topic}", "broll_query": "hospital technology", "seconds": scene_seconds},
            {"narration": "เทคโนโลยีช่วยลดงานซ้ำซ้อนและทำให้ข้อมูลพร้อมใช้", "broll_query": "doctor using tablet", "seconds": scene_seconds},
            {"narration": "หัวใจสำคัญคือความปลอดภัย ความถูกต้อง และคนไข้", "broll_query": "healthcare team", "seconds": scene_seconds},
            {"narration": "ติดตามเพื่อดูตัวอย่างการใช้งานจริง", "broll_query": "modern hospital", "seconds": scene_seconds},
        ], "cta": "ติดตามตอนต่อไป", "disclaimer": "ข้อมูลเพื่อการสื่อสารทั่วไป", "mode": "offline-fallback"}
    return write_json(root / "02_script.json", data)


def broll(job, root: Path) -> Path:
    data = json.loads((root / "02_script.json").read_text(encoding="utf-8"))
    clips = root / "broll"
    clips.mkdir(exist_ok=True)
    manifest = []
    for i, scene in enumerate(data["scenes"], 1):
        out = clips / f"scene_{i:02d}.mp4"
        downloaded = download_pexels_video(scene.get("broll_query", job.topic), out)
        if not downloaded:
            duration = max(2, int(scene.get("seconds", 5)))
            colors = ["0x123047", "0x183B50", "0x20495B", "0x285766"]
            run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={colors[(i - 1) % len(colors)]}:s=1080x1920:r=30:d={duration}", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)])
        manifest.append({"scene": i, "file": str(out.relative_to(root)), "source": "pexels" if downloaded else "generated-fallback", "seconds": scene.get("seconds", 5)})
    return write_json(root / "03_broll.json", {"clips": manifest})


def voice(job, root: Path) -> Path:
    data = json.loads((root / "02_script.json").read_text(encoding="utf-8"))
    narration = " ".join(s["narration"] for s in data["scenes"])
    out = root / "04_voice.mp3"
    generated = text_to_speech(narration, out)
    if not generated:
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", str(job.target_seconds), "-q:a", "9", "-acodec", "libmp3lame", str(out)])
    (root / "04_narration.txt").write_text(narration, encoding="utf-8")
    return out


def _srt_time(seconds: float) -> str:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3_600_000); m, ms = divmod(ms, 60_000); s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def _display_width(text: str) -> float:
    """Estimate rendered width without treating combining marks as characters."""
    width = 0.0
    for char in text:
        if char.isspace():
            width += 0.5
        elif unicodedata.combining(char) or unicodedata.category(char) in {"Mn", "Me"}:
            continue
        elif unicodedata.east_asian_width(char) in {"W", "F"}:
            width += 2.0
        else:
            width += 1.0
    return width


def _caption_tokens(text: str) -> list[str]:
    """Tokenize Thai and Latin text while preserving spaces between Latin words."""
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []

    tokens: list[str] = []
    pattern = r"[A-Za-z0-9]+(?:[-'’][A-Za-z0-9]+)*|[\u0E00-\u0E7F]+|\s+|[^\s]"
    for part in re.findall(pattern, normalized):
        if re.fullmatch(r"[\u0E00-\u0E7F]+", part):
            tokens.extend(word_tokenize(part, engine="newmm", keep_whitespace=False))
        else:
            tokens.append(part)
    return tokens


def _caption_chunks(text: str, max_line_width: float = 20.0, max_lines: int = 2) -> list[str]:
    """Create explicit subtitle lines; a token is never split across lines."""
    chunks: list[str] = []
    lines: list[str] = []
    line = ""

    def flush_line() -> None:
        nonlocal line, lines, chunks
        clean = line.rstrip()
        if clean:
            lines.append(clean)
        line = ""
        if len(lines) == max_lines:
            chunks.append("\n".join(lines))
            lines = []

    for token in _caption_tokens(text):
        if not token:
            continue
        if token.isspace():
            if line and not line.endswith(" "):
                line += " "
            continue

        candidate = f"{line}{token}"
        if line.strip() and _display_width(candidate) > max_line_width:
            flush_line()
            token = token.lstrip()
        line += token

    flush_line()
    if lines:
        chunks.append("\n".join(lines))
    return chunks


def captions(job, root: Path) -> Path:
    data = json.loads((root / "02_script.json").read_text(encoding="utf-8"))
    lines, start, caption_index = [], 0.0, 1
    for scene in data["scenes"]:
        duration = float(scene.get("seconds", job.target_seconds / len(data["scenes"])))
        chunks = _caption_chunks(scene["narration"])
        weights = [max(_display_width(chunk), 1.0) for chunk in chunks]
        total_weight = sum(weights)
        cue_start = start
        for chunk, weight in zip(chunks, weights):
            cue_duration = duration * weight / total_weight
            cue_end = min(start + duration, cue_start + cue_duration)
            lines += [
                str(caption_index),
                f"{_srt_time(cue_start)} --> {_srt_time(cue_end)}",
                chunk,
                "",
            ]
            caption_index += 1
            cue_start = cue_end
        start += duration
    out = root / "05_captions.srt"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _parse_srt(path: Path) -> list[tuple[float, float, str]]:
    """Read the simple UTF-8 SRT generated by this pipeline."""
    cues: list[tuple[float, float, str]] = []
    blocks = re.split(r"\r?\n\s*\r?\n", path.read_text(encoding="utf-8-sig").strip())

    def seconds(value: str) -> float:
        hours, minutes, rest = value.strip().split(":")
        secs, millis = rest.split(",")
        return int(hours) * 3600 + int(minutes) * 60 + int(secs) + int(millis) / 1000

    for block in blocks:
        rows = block.splitlines()
        if len(rows) < 3 or " --> " not in rows[1]:
            continue
        start, end = rows[1].split(" --> ", 1)
        cues.append((seconds(start), seconds(end), "\n".join(rows[2:])))
    return cues


def _thai_font(size: int) -> ImageFont.FreeTypeFont:
    font_path = Path(os.environ.get("SUBTITLE_FONT_PATH", "/srv/app/assets/fonts/Prompt-Bold.ttf"))
    if not font_path.is_file() or font_path.stat().st_size == 0:
        raise FileNotFoundError(
            f"Thai subtitle font is missing: {font_path}. Rebuild the Docker image."
        )
    return ImageFont.truetype(
        str(font_path), size=size, layout_engine=ImageFont.Layout.RAQM
    )


def _subtitle_card(text: str, canvas_width: int = 1080) -> np.ndarray:
    """Create a sharp, transparent subtitle card safe for a 9:16 frame."""
    max_width = canvas_width - 240
    padding_x, padding_y = 38, 28
    probe = Image.new("RGBA", (max_width, 400), (0, 0, 0, 0))
    draw = ImageDraw.Draw(probe)
    font_size = 56
    while True:
        font = _thai_font(font_size)
        bbox = draw.multiline_textbbox(
            (0, 0), text, font=font, spacing=12, align="center", stroke_width=2
        )
        text_width = bbox[2] - bbox[0]
        if text_width <= max_width - padding_x * 2 or font_size <= 38:
            break
        font_size -= 2
    text_height = bbox[3] - bbox[1]
    width = int(min(max_width, text_width + padding_x * 2))
    height = int(text_height + padding_y * 2)
    card = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=30, fill=(5, 12, 20, 205))
    draw.multiline_text(
        (width / 2, height / 2),
        text,
        font=font,
        fill=(255, 255, 255, 255),
        anchor="mm",
        align="center",
        spacing=12,
        stroke_width=2,
        stroke_fill=(0, 0, 0, 220),
    )
    return np.asarray(card)


def render(job, root: Path) -> Path:
    manifest = json.loads((root / "03_broll.json").read_text(encoding="utf-8"))["clips"]
    normalized = root / "normalized"
    normalized.mkdir(exist_ok=True)
    concat_lines = []
    for item in manifest:
        source = root / item["file"]
        target = normalized / source.name
        run(["ffmpeg", "-y", "-i", str(source), "-t", str(item["seconds"]), "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(target)])
        concat_lines.append(f"file '{target.as_posix()}'")
    concat_file = root / "concat.txt"
    concat_file.write_text("\n".join(concat_lines), encoding="utf-8")
    base = root / "base.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(base)])
    out = root / "06_final.mp4"

    # Pillow shapes Thai glyphs with RAQM/HarfBuzz, then MoviePy overlays each
    # transparent card. This avoids libass line wrapping and floating marks.
    with VideoFileClip(str(base)) as video, AudioFileClip(str(root / "04_voice.mp3")) as audio:
        duration = min(float(job.target_seconds), video.duration)
        layers = [video.subclipped(0, duration)]
        for start, end, text in _parse_srt(root / "05_captions.srt"):
            if start >= duration:
                continue
            card = (
                ImageClip(_subtitle_card(text))
                .with_start(start)
                .with_duration(max(0.05, min(end, duration) - start))
                .with_position(("center", 1500))
            )
            layers.append(card)
        final = CompositeVideoClip(layers, size=(1080, 1920)).with_duration(duration)
        final = final.with_audio(audio.subclipped(0, min(audio.duration, duration)))
        final.write_videofile(
            str(out), fps=30, codec="libx264", audio_codec="aac", bitrate="8M",
            preset="medium", ffmpeg_params=["-movflags", "+faststart", "-pix_fmt", "yuv420p"],
            logger=None,
        )
        final.close()
    return out


def qc(job, root: Path) -> Path:
    video = root / "06_final.mp4"
    probe = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)]))
    streams = probe.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    a = next((s for s in streams if s.get("codec_type") == "audio"), {})
    duration = float(probe.get("format", {}).get("duration", 0))
    checks = {
        "has_video": bool(v), "has_audio": bool(a),
        "vertical_1080x1920": v.get("width") == 1080 and v.get("height") == 1920,
        "duration_in_range": 10 <= duration <= 95,
        "required_artifacts": all((root / x).exists() for x in ["01_research.json", "02_script.json", "03_broll.json", "04_voice.mp3", "05_captions.srt", "06_final.mp4"]),
    }
    report = {"passed": all(checks.values()), "checks": checks, "duration_seconds": duration, "probe": {"video_codec": v.get("codec_name"), "audio_codec": a.get("codec_name")}}
    write_json(root / "07_qc.json", report)
    if not report["passed"]:
        raise RuntimeError(f"QC failed: {checks}")
    return root / "07_qc.json"


def archive(job, root: Path) -> Path:
    client = Minio(settings.minio_endpoint, access_key=settings.minio_access_key, secret_key=settings.minio_secret_key, secure=False)
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)
    files = [p for p in root.rglob("*") if p.is_file() and "normalized" not in p.parts and p.name not in {"base.mp4", "concat.txt"}]
    uploaded = []
    for file in files:
        key = f"{job.id}/{file.relative_to(root).as_posix()}"
        client.fput_object(settings.minio_bucket, key, str(file))
        uploaded.append(key)
    manifest = write_json(root / "08_archive.json", {"bucket": settings.minio_bucket, "objects": uploaded})
    client.fput_object(settings.minio_bucket, f"{job.id}/08_archive.json", str(manifest))
    return manifest


STAGES = [("research", research), ("script", script), ("broll", broll), ("voice", voice), ("caption", captions), ("render", render), ("qc", qc), ("archive", archive)]
