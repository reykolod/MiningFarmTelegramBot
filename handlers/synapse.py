import asyncio
import json
import html
import re
import urllib.parse
import urllib.request
from typing import Optional, Tuple

from aiogram import Router, F
from aiogram.types import Message, URLInputFile

from config import SOUNDCLOUD_CLIENT_ID, JAMENDO_CLIENT_ID
from utils import save_chat_from_message

try:
    import requests
except Exception:
    requests = None


router = Router()


def _safe_filename(text: str) -> str:
    v = (text or "").strip()
    v = re.sub(r"[\\/:*?\"<>|]+", "_", v)
    v = re.sub(r"\s+", " ", v).strip()
    if not v:
        return "track"
    if len(v) > 120:
        v = v[:120].strip()
    return v


def _http_get_json_sync(url: str, params: Optional[dict] = None, timeout: float = 7.0) -> Optional[object]:
    if params:
        query = urllib.parse.urlencode(params)
        url = f"{url}?{query}"

    if requests is not None:
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MiningFarmBot/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


async def _http_get_json(url: str, params: Optional[dict] = None, timeout: float = 7.0) -> Optional[object]:
    return await asyncio.to_thread(_http_get_json_sync, url, params, timeout)


async def _search_soundcloud(query: str) -> Optional[Tuple[str, str, str, str, bool, Optional[str]]]:
    client_id = (SOUNDCLOUD_CLIENT_ID or "").strip()
    if not client_id:
        return None

    data = await _http_get_json(
        "https://api-v2.soundcloud.com/search/tracks",
        params={
            "q": query,
            "client_id": client_id,
            "limit": 1,
            "offset": 0,
        },
    )
    if not isinstance(data, dict):
        return None

    collection = data.get("collection")
    if not isinstance(collection, list) or not collection:
        return None

    track = collection[0]
    if not isinstance(track, dict):
        return None

    title = str(track.get("title") or "")
    user = track.get("user") if isinstance(track.get("user"), dict) else {}
    artist = str((user or {}).get("username") or "SoundCloud")
    page_url = track.get("permalink_url")

    media = track.get("media") if isinstance(track.get("media"), dict) else None
    transcodings = None
    if isinstance(media, dict):
        transcodings = media.get("transcodings")

    if not isinstance(transcodings, list):
        return None

    progressive_url = None
    for t in transcodings:
        if not isinstance(t, dict):
            continue
        fmt = t.get("format") if isinstance(t.get("format"), dict) else {}
        if (fmt or {}).get("protocol") == "progressive":
            progressive_url = t.get("url")
            break

    if not progressive_url:
        return None

    resolved = await _http_get_json(
        str(progressive_url),
        params={"client_id": client_id},
    )
    if not isinstance(resolved, dict):
        return None

    stream_url = resolved.get("url")
    if not stream_url:
        return None

    return str(stream_url), title, artist, "SoundCloud", False, (str(page_url) if page_url else None)


async def _search_jamendo(query: str) -> Optional[Tuple[str, str, str, str, bool, Optional[str]]]:
    client_id = (JAMENDO_CLIENT_ID or "").strip()
    if not client_id:
        return None

    data = await _http_get_json(
        "https://api.jamendo.com/v3.0/tracks",
        params={
            "client_id": client_id,
            "format": "json",
            "limit": 1,
            "search": query,
            "audioformat": "mp32",
        },
    )
    if not isinstance(data, dict):
        return None

    results = data.get("results")
    if not isinstance(results, list) or not results:
        return None

    track = results[0]
    if not isinstance(track, dict):
        return None

    audio_url = track.get("audio")
    if not audio_url:
        return None

    title = str(track.get("name") or "")
    artist = str(track.get("artist_name") or "Jamendo")
    page_url = track.get("shareurl")
    return str(audio_url), title, artist, "Jamendo", False, (str(page_url) if page_url else None)


async def _search_deezer(query: str) -> Optional[Tuple[str, str, str, str, bool, Optional[str]]]:
    data = await _http_get_json(
        "https://api.deezer.com/search",
        params={
            "q": query,
            "limit": 1,
        },
    )
    if not isinstance(data, dict):
        return None

    results = data.get("data")
    if not isinstance(results, list) or not results:
        return None

    track = results[0]
    if not isinstance(track, dict):
        return None

    preview_url = track.get("preview")
    if not preview_url:
        return None

    title = str(track.get("title") or "")
    artist_obj = track.get("artist") if isinstance(track.get("artist"), dict) else {}
    artist = str((artist_obj or {}).get("name") or "Deezer")
    page_url = track.get("link")
    return str(preview_url), title, artist, "Deezer", True, (str(page_url) if page_url else None)


async def _search_itunes(query: str) -> Optional[Tuple[str, str, str, str, bool, Optional[str]]]:
    data = await _http_get_json(
        "https://itunes.apple.com/search",
        params={
            "term": query,
            "media": "music",
            "entity": "song",
            "limit": 1,
        },
    )
    if not isinstance(data, dict):
        return None

    results = data.get("results")
    if not isinstance(results, list) or not results:
        return None

    track = results[0]
    if not isinstance(track, dict):
        return None

    preview_url = track.get("previewUrl")
    if not preview_url:
        return None

    title = str(track.get("trackName") or "")
    artist = str(track.get("artistName") or "iTunes")
    page_url = track.get("trackViewUrl")
    return str(preview_url), title, artist, "iTunes", True, (str(page_url) if page_url else None)


async def _find_track(query: str) -> Optional[Tuple[str, str, str, str, bool, Optional[str]]]:
                                                                       
    for fn in (_search_soundcloud, _search_jamendo):
        try:
            res = await fn(query)
            if res:
                return res
        except Exception:
            continue

    for fn in (_search_deezer, _search_itunes):
        try:
            res = await fn(query)
            if res:
                return res
        except Exception:
            continue

    return None


@router.message(F.text.startswith("Синапс"))
@router.message(F.text.startswith("синапс"))
@router.message(F.text.startswith("СИНАПС"))
async def synapse_message_handler(message: Message):
    save_chat_from_message(message)

    text = (message.text or "").strip()
    lower = text.lower()
    if not lower.startswith("синапс"):
        return

    query = ""
    parts = text.split(maxsplit=1)
    if len(parts) >= 2:
        query = parts[1].strip()
    if not query:
        await message.reply("❌ Укажите запрос.")
        return

    found = await _find_track(query)
    if not found:
        await message.reply("❌ Ничего не найдено.")
        return

    audio_url, title, artist, source, is_preview, page_url = found

    title_s = (title or "").strip() or "Трек"
    artist_s = (artist or "").strip() or "Unknown"

    filename = _safe_filename(f"{artist_s} — {title_s}") + ".mp3"
    audio = URLInputFile(audio_url, filename=filename)

    title_html = html.escape(title_s)
    artist_html = html.escape(artist_s)
    source_html = html.escape(source or "")
    query_html = html.escape(query)

    caption_lines = [
        f"🎧 <b>{title_html}</b>",
        f"👤 <b>Исполнитель:</b> {artist_html}",
        f"🌐 <b>Источник:</b> {source_html}" + (" <i>(превью ~30с)</i>" if is_preview else ""),
        f"🔎 <b>Запрос:</b> <code>{query_html}</code>",
    ]
    if page_url:
        caption_lines.append(f"🔗 <a href=\"{html.escape(page_url)}\">Открыть источник</a>")

    caption = "\n".join([l for l in caption_lines if l])

    await message.answer_audio(
        audio=audio,
        title=title_s,
        performer=artist_s,
        caption=caption,
        parse_mode="HTML",
        reply_to_message_id=message.message_id,
    )
