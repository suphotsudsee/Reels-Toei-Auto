import json
from pathlib import Path
import httpx
from openai import OpenAI
from .config import settings


def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)


def generate_json(system: str, prompt: str) -> dict:
    if not settings.openai_api_key:
        return {}
    response = _client().chat.completions.create(
        model=settings.openai_text_model,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0.5,
    )
    return json.loads(response.choices[0].message.content or "{}")


def text_to_speech(text: str, output: Path) -> bool:
    if not settings.openai_api_key:
        return False
    with _client().audio.speech.with_streaming_response.create(
        model=settings.openai_tts_model,
        voice=settings.openai_tts_voice,
        input=text,
        instructions="Speak naturally, clearly, and energetically for a short social video.",
    ) as response:
        response.stream_to_file(output)
    return True


def download_pexels_video(query: str, output: Path) -> bool:
    if not settings.pexels_api_key:
        return False
    with httpx.Client(timeout=45, follow_redirects=True) as client:
        data = client.get("https://api.pexels.com/videos/search", params={"query": query, "per_page": 5, "orientation": "portrait"}, headers={"Authorization": settings.pexels_api_key}).json()
        videos = data.get("videos", [])
        if not videos:
            return False
        files = sorted(videos[0].get("video_files", []), key=lambda x: abs((x.get("width") or 0) - 1080))
        if not files:
            return False
        with client.stream("GET", files[0]["link"]) as response:
            response.raise_for_status()
            with output.open("wb") as fh:
                for chunk in response.iter_bytes():
                    fh.write(chunk)
    return True

