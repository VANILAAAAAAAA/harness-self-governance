from __future__ import annotations

from pathlib import Path
from typing import Any

from .schemas import PROFILE_IDS, default_profile, deterministic_write_json, read_json


def profile_dir(memory_root: Path, profile_id: str) -> Path:
    return memory_root / 'profiles' / profile_id


def profile_path(memory_root: Path, profile_id: str) -> Path:
    return profile_dir(memory_root, profile_id) / 'profile.json'


def ensure_profile(memory_root: Path, profile_id: str) -> Path:
    target = profile_path(memory_root, profile_id)
    if not target.exists():
        deterministic_write_json(target, default_profile(profile_id))
    return target


def load_profile(memory_root: Path, profile_id: str) -> dict[str, Any]:
    ensure_profile(memory_root, profile_id)
    return read_json(profile_path(memory_root, profile_id))


def build_profile_index(memory_root: Path) -> dict[str, Any]:
    profiles = []
    for profile_id in PROFILE_IDS:
        profile = load_profile(memory_root, profile_id)
        profiles.append(
            {
                'profile_id': profile['profile_id'],
                'label': profile['label'],
                'role': profile['role'],
                'description': profile['description'],
                'projects': profile.get('projects', []),
            }
        )
    return {
        'schema_version': '2.0',
        'active_profile': 'general',
        'profiles': profiles,
        'warnings': [],
        'blockers': [],
    }
