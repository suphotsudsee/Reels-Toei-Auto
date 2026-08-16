import json
import math
import re
import subprocess
import unicodedata
from pathlib import Path

from minio import Minio
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
        "You write clear Thai vertical-video scripts. Return JSON only. Every scene narration must use short, natural spoken sentences. Avoid unexplained English abbreviations. The first scene must contain the hook and the final scene must finish the thought and CTA; never end mid-sentence.",
        f"Create a complete {job.target_seconds}-second script in {job.language} from research {notes}. Aim for narration that can be spoken in {max(15, job.target_seconds - 4)} seconds, leaving a short ending hold. Return hook, scenes (narration, broll_query, seconds), cta and disclaimer. Use 5-7 scenes and keep each narration concise.",
    )
    if not data or not data.get("scenes"):
        scene_seconds = max(5, job.target_seconds // 4)
        data = {"hook": job.topic, "scenes": [
            {"narration": f"วันนี้ มารู้จัก {job.topic} กันครับ", "broll_query": "hospital technology", "seconds": scene_seconds},
            {"narration": "เทคโนโลยี ช่วยลดงานซ้ำซ้อน และทำให้ข้อมูลพร้อมใช้", "broll_query": "doctor using tablet", "seconds": scene_seconds},
            {"narration": "หัวใจสำคัญ คือความปลอดภัย ความถูกต้อง และประโยชน์ของผู้ป่วย", "broll_query": "healthcare team", "seconds": scene_seconds},
            {"narration": "ติดตามตอนต่อไป เพื่อดูตัวอย่างการใช้งานจริงครับ", "broll_query": "modern hospital", "seconds": scene_seconds},
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


def _spoken_text(text: str) -> str:
    replacements = {"AI": "เอไอ", "A.I.": "เอไอ", "OPD": "โอพีดี", "IPD": "ไอพีดี"}
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def voice(job, root: Path) -> Path:
    data = json.loads((root / "02_script.json").read_text(encoding="utf-8"))
    narration = "\n".join(_spoken_text(s["narration"]) for s in data["scenes"])
    out = root / "04_voice.mp3"
    if not text_to_speech(narration, out, language=job.language):
        raise RuntimeError("สร้างเสียงพากย์ไม่ได้: กรุณาตั้งค่า OPENAI_API_KEY แล้วเริ่มงานใหม่ (ระบบจะไม่สร้างคลิปเสียงเงียบ)")
    duration = _media_duration(out)
    (root / "04_narration.txt").write_text(narration, encoding="utf-8")
    write_json(root / "04_voice.json", {"duration_seconds": duration, "narration": narration})
    return out


def _media_duration(path: Path) -> float:
    value = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]).strip()
    return float(value)


def _srt_time(seconds: float) -> str:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def _clusters(text: str) -> list[str]:
    clusters: list[str] = []
    for char in text:
        if clusters and (unicodedata.combining(char) or unicodedata.category(char) in {"Mn", "Mc", "Me"}):
            clusters[-1] += char
        else:
            clusters.append(char)
    return clusters


def _wrap_caption(text: str, max_chars: int = 18, max_lines: int = 2) -> list[str]:
    """Split Thai/Latin narration into word-safe, two-line caption cards."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    tokens = word_tokenize(text, engine="newmm", keep_whitespace=True)
    lines: list[str] = []
    current = ""
    for token in tokens:
        token = token.replace("\n", " ")
        candidate = current + token
        if current and len(_clusters(candidate.strip())) > max_chars:
            lines.append(current.strip())
            current = token.lstrip()
        else:
            current = candidate
    if current.strip():
        lines.append(current.strip())

    cards = []
    for index in range(0, len(lines), max_lines):
        cards.append("\n".join(lines[index:index + max_lines]))
    return cards


def _scene_durations(data: dict, total_seconds: float) -> list[float]:
    weights = [max(1, len(_clusters(_spoken_text(scene["narration"])))) for scene in data["scenes"]]
    total_weight = sum(weights)
    return [total_seconds * weight / total_weight for weight in weights]


def captions(job, root: Path) -> Path:
    data = json.loads((root / "02_script.json").read_text(encoding="utf-8"))
    audio_duration = _media_duration(root / "04_voice.mp3")
    scene_durations = _scene_durations(data, audio_duration)
    lines: list[str] = []
    cue_number = 1
    start = 0.0
    for scene, scene_duration in zip(data["scenes"], scene_durations):
        cards = _wrap_caption(_spoken_text(scene["narration"])) or [""]
        weights = [max(1, len(_clusters(card.replace("\n", "")))) for card in cards]
        unit = scene_duration / sum(weights)
        for card, weight in zip(cards, weights):
            duration = unit * weight
            end = min(audio_duration, start + duration)
            lines += [str(cue_number), f"{_srt_time(start)} --> {_srt_time(end)}", card, ""]
            cue_number += 1
            start = end
    out = root / "05_captions.srt"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def render(job, root: Path) -> Path:
    data = json.loads((root / "02_script.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "03_broll.json").read_text(encoding="utf-8"))["clips"]
    audio_duration = _media_duration(root / "04_voice.mp3")
    ending_hold = 0.8
    visual_duration = audio_duration + ending_hold
    scene_durations = _scene_durations(data, visual_duration)
    normalized = root / "normalized"
    normalized.mkdir(exist_ok=True)
    concat_lines = []
    for item, duration in zip(manifest, scene_durations):
        source = root / item["file"]
        target = normalized / source.name
        run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(source), "-t", f"{duration:.3f}", "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(target)])
        concat_lines.append(f"file '{target.as_posix()}'")
    concat_file = root / "concat.txt"
    concat_file.write_text("\n".join(concat_lines), encoding="utf-8")
    base = root / "base.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(base)])
    out = root / "06_final.mp4"
    subtitle = (root / "05_captions.srt").as_posix().replace(":", "\\:").replace("'", "\\'")
    style = "FontName=Noto Sans Thai,FontSize=52,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=4,Shadow=1,Alignment=2,MarginL=110,MarginR=110,MarginV=260,WrapStyle=0"
    audio_filter = f"highpass=f=80,lowpass=f=12000,acompressor=threshold=-18dB:ratio=2.5:attack=20:release=200,loudnorm=I=-16:TP=-1.5:LRA=8,apad=pad_dur={ending_hold}"
    run(["ffmpeg", "-y", "-i", str(base), "-i", str(root / "04_voice.mp3"), "-vf", f"subtitles='{subtitle}':fontsdir=/usr/share/fonts/truetype/noto:force_style='{style}'", "-af", audio_filter, "-t", f"{visual_duration:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)])
    return out


def qc(job, root: Path) -> Path:
    video = root / "06_final.mp4"
    probe = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)]))
    streams = probe.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    a = next((s for s in streams if s.get("codec_type") == "audio"), {})
    duration = float(probe.get("format", {}).get("duration", 0))
    voice_duration = _media_duration(root / "04_voice.mp3")
    checks = {
        "has_video": bool(v),
        "has_audio": bool(a),
        "vertical_1080x1920": v.get("width") == 1080 and v.get("height") == 1920,
        "speech_not_cut": duration >= voice_duration,
        "duration_in_range": 10 <= duration <= max(95, job.target_seconds + 20),
        "required_artifacts": all((root / x).exists() for x in ["01_research.json", "02_script.json", "03_broll.json", "04_voice.mp3", "04_voice.json", "05_captions.srt", "06_final.mp4"]),
    }
    report = {"passed": all(checks.values()), "checks": checks, "duration_seconds": duration, "voice_duration_seconds": voice_duration, "target_seconds": job.target_seconds, "probe": {"video_codec": v.get("codec_name"), "audio_codec": a.get("codec_name")}}
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
