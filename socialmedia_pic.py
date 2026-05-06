"""Pick images from ``socialmedia-pic`` for multimodal tweet posts."""

from __future__ import annotations

import base64
import json
import os
import random
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from env_utils import env_bool, env_list

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def list_social_images(directory: str | None = None) -> list[Path]:
    root = Path(
        directory or os.getenv("SOCIALMEDIA_PIC_DIR") or "socialmedia-pic"
    ).resolve()
    if not root.is_dir():
        return []
    paths = sorted(
        p
        for p in root.iterdir()
        if p.is_file() and p.suffix.lower() in _IMAGE_SUFFIXES
    )
    return paths


def image_file_to_data_url(path: str | Path) -> str:
    p = Path(path)
    suffix = p.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    mime = mime_map.get(suffix, "image/jpeg")
    raw = p.read_bytes()
    b64 = base64.standard_b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def infer_post_slot(post_times: list[str]) -> int:
    """Map current local time to the index of the nearest scheduled POST_TIME."""
    if not post_times:
        return 0
    scheduled = sorted(post_times)
    now = datetime.now()
    current = now.hour * 60 + now.minute
    best_index = 0
    best_dist = 10**9
    for i, raw in enumerate(scheduled):
        hour_s, minute_s = raw.split(":", 1)
        target = int(hour_s) * 60 + int(minute_s)
        dist = abs(current - target)
        if dist < best_dist:
            best_dist = dist
            best_index = i
    return best_index


def resolve_image_slot(post_times: list[str]) -> int:
    """
    Which of the three daily runs this invocation represents.
    On GitHub Actions, the scheduled workflow uses UTC hours 16, 0, 13
    (see ``post-tweet.yml``), so we map those hours to slots 0–2. Else we
    use ``SOCIALMEDIA_PIC_SLOT`` or the nearest ``POST_TIMES`` bucket.
    """
    slot_raw = os.getenv("SOCIALMEDIA_PIC_SLOT")
    if slot_raw is not None and slot_raw.strip() != "":
        return int(slot_raw) % 3

    if os.getenv("GITHUB_ACTIONS"):
        hour_utc = datetime.now(timezone.utc).hour
        if hour_utc == 16:
            return 0
        if hour_utc == 0:
            return 1
        if hour_utc == 13:
            return 2

    return infer_post_slot(post_times) % 3


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _pick_index_deterministic(paths: list[Path], slot: int) -> int:
    """Legacy: up to three different images per day (one per schedule slot)."""
    if not paths:
        return 0
    day_ord = date.today().toordinal()
    return (day_ord * 3 + (slot % 3)) % len(paths)


def _pick_index_once_per_day(paths: list[Path]) -> int:
    """One featured image per calendar day, cycle through the folder."""
    if not paths:
        return 0
    return date.today().toordinal() % len(paths)


def _pick_with_state_file(
    paths: list[Path],
    state_path: str | Path | None,
) -> Path:
    default_name = "socialmedia-pic-state.json"
    path = Path(state_path or os.getenv("SOCIALMEDIA_PIC_STATE_PATH", default_name))
    data = _load_json(path)
    order: list[str] = data.get("order") or []
    next_index = int(data.get("next_index", 0))

    if len(order) != len(paths) or set(order) != {str(p.resolve()) for p in paths}:
        order = [str(p.resolve()) for p in paths]
        random.shuffle(order)
        next_index = 0

    if next_index >= len(order):
        order = [str(p.resolve()) for p in paths]
        random.shuffle(order)
        next_index = 0

    chosen = Path(order[next_index])
    data = {"order": order, "next_index": next_index + 1}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as error:
        print(f"Could not persist social image state: {error}")

    return chosen


def pick_social_image(
    directory: str | None = None,
    state_path: str | Path | None = None,
) -> Path | None:
    """
    Returns an image path for this run, or None.

    - If ``SOCIALMEDIA_PIC_ONCE_PER_DAY`` (default true): only the run matching
      ``SOCIALMEDIA_PIC_IMAGE_SLOT`` (0–2, default 0) uses an image; other
      daily runs return None so those tweets stay text-only.
    - Deterministic (default): image of the day = stable index by date
      ``day_ordinal % N``.
    - ``SOCIALMEDIA_PIC_STATE_MODE=file``: shuffle queue; still only advances
      on the allowed daily slot when once-per-day is on.

    Slots: GitHub Actions maps UTC hours 16/0/13 to 0/1/2; else nearest
    ``POST_TIMES``. Override with ``SOCIALMEDIA_PIC_SLOT`` for testing.
    """
    paths = list_social_images(directory)
    if not paths:
        return None

    post_times = env_list(
        "POST_TIMES",
        ["00:30", "08:30", "21:30"],
    )
    current_slot = resolve_image_slot(post_times)
    once_per_day = env_bool("SOCIALMEDIA_PIC_ONCE_PER_DAY", True)

    if once_per_day:
        image_slot = int(os.getenv("SOCIALMEDIA_PIC_IMAGE_SLOT", "0")) % 3
        if current_slot != image_slot:
            return None

    mode = os.getenv("SOCIALMEDIA_PIC_STATE_MODE", "deterministic").lower()
    if mode == "file":
        return _pick_with_state_file(paths, state_path)

    if once_per_day:
        index = _pick_index_once_per_day(paths)
    else:
        index = _pick_index_deterministic(paths, current_slot)
    return paths[index]


def social_image_posts_enabled() -> bool:
    return env_bool("ENABLE_SOCIALMEDIA_PIC", False)
