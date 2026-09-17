from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

SEARCH_URL = "https://shazam.p.rapidapi.com/search"
API_HOST = "shazam.p.rapidapi.com"
REQUEST_TIMEOUT_SECONDS = 10
RESULT_LIMIT = 20


@dataclass(frozen=True)
class Track:
    key: str
    title: str
    artist: str
    image_url: str | None
    shazam_url: str | None
    listen_url: str | None


class ShazamClientError(Exception):
    def __init__(self, user_message: str, status_code: int = 502):
        super().__init__(user_message)
        self.user_message = user_message
        self.status_code = status_code


def normalize_query(value: Any) -> str:
    return str(value or "").strip()


def safe_external_url(value: Any) -> str | None:
    if not value:
        return None

    try:
        parsed = urlparse(str(value))
    except (TypeError, ValueError):
        return None

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    return parsed.geturl()


def _first_text(*values: Any, fallback: str) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _listen_url(track: dict[str, Any]) -> str | None:
    actions = track.get("hub", {}).get("actions", [])
    if not isinstance(actions, list):
        return None

    for action in actions:
        if not isinstance(action, dict):
            continue
        url = safe_external_url(action.get("uri"))
        if url:
            return url

    return None


def normalize_hit(hit: Any) -> Track | None:
    if not isinstance(hit, dict):
        return None

    raw_track = hit.get("track")
    if not isinstance(raw_track, dict):
        return None

    title = _first_text(raw_track.get("title"), fallback="Untitled track")
    artist = _first_text(raw_track.get("subtitle"), fallback="Unknown artist")
    key = _first_text(raw_track.get("key"), f"{title}:{artist}", fallback=f"{title}:{artist}")

    images = raw_track.get("images") if isinstance(raw_track.get("images"), dict) else {}
    image_url = safe_external_url(images.get("coverart") or images.get("background"))

    return Track(
        key=key,
        title=title,
        artist=artist,
        image_url=image_url,
        shazam_url=safe_external_url(raw_track.get("url")),
        listen_url=_listen_url(raw_track),
    )


def parse_tracks(payload: Any) -> list[Track]:
    if not isinstance(payload, dict):
        return []

    tracks = payload.get("tracks")
    if not isinstance(tracks, dict):
        return []

    hits = tracks.get("hits")
    if not isinstance(hits, list):
        return []

    normalized: list[Track] = []
    seen: set[str] = set()

    for hit in hits:
        track = normalize_hit(hit)
        if track is None or track.key in seen:
            continue
        seen.add(track.key)
        normalized.append(track)

    return normalized


def search_tracks(
    query: str,
    *,
    api_key: str,
    session: requests.Session | None = None,
    timeout: int = REQUEST_TIMEOUT_SECONDS,
) -> list[Track]:
    normalized_query = normalize_query(query)
    if not normalized_query:
        return []

    client = session or requests.Session()

    try:
        response = client.get(
            SEARCH_URL,
            headers={
                "X-RapidAPI-Host": API_HOST,
                "X-RapidAPI-Key": api_key,
                "Accept": "application/json",
            },
            params={
                "term": normalized_query,
                "locale": "en-US",
                "offset": "0",
                "limit": str(RESULT_LIMIT),
            },
            timeout=timeout,
        )
    except requests.Timeout as error:
        raise ShazamClientError(
            "The Shazam search service took too long to respond. Try again in a moment.",
            504,
        ) from error
    except requests.RequestException as error:
        raise ShazamClientError(
            "Could not reach the Shazam search service. Check your connection and try again.",
            502,
        ) from error

    if response.status_code == 429:
        raise ShazamClientError(
            "The Shazam API is rate-limiting requests right now. Give it a moment and try again.",
            429,
        )

    if response.status_code in {401, 403}:
        raise ShazamClientError(
            "RapidAPI rejected the configured key. Check RAPIDAPI_KEY and the Shazam API subscription.",
            503,
        )

    try:
        response.raise_for_status()
        payload = response.json()
    except requests.HTTPError as error:
        raise ShazamClientError(
            "The Shazam search service returned an unexpected error.",
            502,
        ) from error
    except ValueError as error:
        raise ShazamClientError(
            "The Shazam search service returned data this app could not read.",
            502,
        ) from error

    return parse_tracks(payload)
