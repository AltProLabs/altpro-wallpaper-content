#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
CONTENT_DIR = ROOT_DIR / "content"
WALLPAPERS_DIR = CONTENT_DIR / "wallpapers"
THUMBNAILS_DIR = CONTENT_DIR / "thumbnails"
MANIFEST_PATH = CONTENT_DIR / "manifest.json"

SUPPORTED_WALLPAPER_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".webp",
}

SUPPORTED_THUMBNAIL_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".webp",
}

IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def category_display_name(category_id: str) -> str:
    words = re.split(r"[-_]+", category_id)
    return " ".join(word.capitalize() for word in words if word)


def validate_identifier(identifier: str, description: str) -> None:
    if not IDENTIFIER_PATTERN.fullmatch(identifier):
        fail(
            f"Invalid {description} '{identifier}'. "
            "Use lowercase letters, numbers, underscores, and hyphens."
        )


def find_thumbnail(category_id: str, wallpaper_stem: str) -> Path:
    category_dir = THUMBNAILS_DIR / category_id

    if not category_dir.is_dir():
        fail(
            f"Missing thumbnail category directory for "
            f"'{category_id}'. Expected: {category_dir}"
        )

    candidates = [
        category_dir / f"{wallpaper_stem}{extension}"
        for extension in sorted(SUPPORTED_THUMBNAIL_EXTENSIONS)
    ]

    existing = [path for path in candidates if path.is_file()]

    if len(existing) == 0:
        fail(
            f"Missing thumbnail for wallpaper "
            f"'{category_id}/{wallpaper_stem}'."
        )

    if len(existing) > 1:
        paths = ", ".join(str(path.relative_to(ROOT_DIR)) for path in existing)
        fail(
            f"Multiple thumbnails found for "
            f"'{category_id}/{wallpaper_stem}': {paths}"
        )

    return existing[0]


def build_manifest() -> dict:
    if not WALLPAPERS_DIR.is_dir():
        fail(f"Wallpaper directory does not exist: {WALLPAPERS_DIR}")

    if not THUMBNAILS_DIR.is_dir():
        fail(f"Thumbnail directory does not exist: {THUMBNAILS_DIR}")

    categories = []

    category_directories = sorted(
        path for path in WALLPAPERS_DIR.iterdir() if path.is_dir()
    )

    for category_dir in category_directories:
        category_id = category_dir.name

        validate_identifier(category_id, "category identifier")

        wallpapers = []

        wallpaper_files = sorted(
            path
            for path in category_dir.iterdir()
            if path.is_file()
        )

        seen_ids = set()

        for wallpaper_path in wallpaper_files:
            if wallpaper_path.name.startswith("."):
                continue

            if wallpaper_path.suffix.lower() not in SUPPORTED_WALLPAPER_EXTENSIONS:
                fail(
                    f"Unsupported wallpaper file: "
                    f"{wallpaper_path.relative_to(ROOT_DIR)}"
                )

            wallpaper_id = wallpaper_path.stem.lower()

            validate_identifier(wallpaper_id, "wallpaper identifier")

            if wallpaper_id in seen_ids:
                fail(
                    f"Duplicate wallpaper identifier "
                    f"'{wallpaper_id}' in category '{category_id}'."
                )

            seen_ids.add(wallpaper_id)

            thumbnail_path = find_thumbnail(
                category_id,
                wallpaper_path.stem,
            )

            wallpaper_relative_path = wallpaper_path.relative_to(CONTENT_DIR)
            thumbnail_relative_path = thumbnail_path.relative_to(CONTENT_DIR)

            wallpapers.append(
                {
                    "id": wallpaper_id,
                    "image": wallpaper_relative_path.as_posix(),
                    "thumbnail": thumbnail_relative_path.as_posix(),
                }
            )

        categories.append(
            {
                "id": category_id,
                "name": category_display_name(category_id),
                "wallpapers": wallpapers,
            }
        )

    content_version = int(time.time())

    return {
        "schemaVersion": 1,
        "contentVersion": content_version,
        "catalogName": "ALTPro-Labs Wallpaper Collection",
        "categories": categories,
    }


def write_manifest(manifest: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = MANIFEST_PATH.with_suffix(".json.tmp")

    serialized = json.dumps(
        manifest,
        indent=2,
        ensure_ascii=False,
    )

    temporary_path.write_text(
        serialized + "\n",
        encoding="utf-8",
    )

    temporary_path.replace(MANIFEST_PATH)


def main() -> None:
    manifest = build_manifest()
    write_manifest(manifest)

    category_count = len(manifest["categories"])

    wallpaper_count = sum(
        len(category["wallpapers"])
        for category in manifest["categories"]
    )

    print("Manifest generated successfully.")
    print(f"Categories: {category_count}")
    print(f"Wallpapers: {wallpaper_count}")
    print(f"Content version: {manifest['contentVersion']}")
    print(f"Manifest: {MANIFEST_PATH.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
