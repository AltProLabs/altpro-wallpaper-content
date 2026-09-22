from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT / "content"
WALLPAPER_DIR = CONTENT_DIR / "wallpapers"
THUMBNAIL_DIR = CONTENT_DIR / "thumbnails"
MANIFEST_PATH = CONTENT_DIR / "manifest.json"

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".webp"}
MAX_WALLPAPER_SIZE_BYTES = 15 * 1024 * 1024
MAX_THUMBNAIL_SIZE_BYTES = 2 * 1024 * 1024

MIN_WIDTH = 720
MIN_HEIGHT = 1280

errors: list[str] = []


def error(message: str) -> None:
    errors.append(message)


def load_manifest() -> dict:
    if not MANIFEST_PATH.is_file():
        error(f"Missing manifest: {MANIFEST_PATH}")
        return {}

    try:
        with MANIFEST_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        error(f"Invalid JSON in manifest: {exc}")
        return {}

    if not isinstance(data, dict):
        error("Manifest root must be a JSON object.")
        return {}

    return data


def validate_manifest_structure(manifest: dict) -> None:
    required_fields = {
        "schemaVersion",
        "contentVersion",
        "catalogName",
        "categories",
    }

    missing = required_fields - manifest.keys()

    for field in sorted(missing):
        error(f"Manifest is missing required field: {field}")

    categories = manifest.get("categories")

    if not isinstance(categories, list):
        error("Manifest field 'categories' must be an array.")
        return

    category_ids: set[str] = set()
    wallpaper_ids: set[str] = set()

    for category in categories:
        if not isinstance(category, dict):
            error("Every category must be a JSON object.")
            continue

        category_id = category.get("id")
        category_name = category.get("name")
        wallpapers = category.get("wallpapers")

        if not isinstance(category_id, str) or not category_id:
            error("Every category must have a non-empty string 'id'.")
        elif category_id in category_ids:
            error(f"Duplicate category id: {category_id}")
        else:
            category_ids.add(category_id)

        if not isinstance(category_name, str) or not category_name:
            error(f"Category '{category_id}' has an invalid name.")

        if not isinstance(wallpapers, list):
            error(f"Category '{category_id}' must contain a 'wallpapers' array.")
            continue

        for wallpaper in wallpapers:
            if not isinstance(wallpaper, dict):
                error(f"Category '{category_id}' contains an invalid wallpaper entry.")
                continue

            wallpaper_id = wallpaper.get("id")
            image = wallpaper.get("image")
            thumbnail = wallpaper.get("thumbnail")

            if not isinstance(wallpaper_id, str) or not wallpaper_id:
                error(f"Category '{category_id}' contains a wallpaper with an invalid id.")
                continue

            if wallpaper_id in wallpaper_ids:
                error(f"Duplicate wallpaper id: {wallpaper_id}")
            else:
                wallpaper_ids.add(wallpaper_id)

            if not isinstance(image, str) or not image:
                error(f"Wallpaper '{wallpaper_id}' has an invalid image path.")

            if not isinstance(thumbnail, str) or not thumbnail:
                error(f"Wallpaper '{wallpaper_id}' has an invalid thumbnail path.")

    validate_referenced_files(manifest)


def validate_referenced_files(manifest: dict) -> None:
    categories = manifest.get("categories", [])

    if not isinstance(categories, list):
        return

    for category in categories:
        if not isinstance(category, dict):
            continue

        wallpapers = category.get("wallpapers", [])

        if not isinstance(wallpapers, list):
            continue

        for wallpaper in wallpapers:
            if not isinstance(wallpaper, dict):
                continue

            wallpaper_id = wallpaper.get("id", "<unknown>")
            image_path = wallpaper.get("image")
            thumbnail_path = wallpaper.get("thumbnail")

            if isinstance(image_path, str):
                validate_referenced_file(
                    wallpaper_id,
                    image_path,
                    CONTENT_DIR,
                    MAX_WALLPAPER_SIZE_BYTES,
                    "wallpaper",
                )

            if isinstance(thumbnail_path, str):
                validate_referenced_file(
                    wallpaper_id,
                    thumbnail_path,
                    CONTENT_DIR,
                    MAX_THUMBNAIL_SIZE_BYTES,
                    "thumbnail",
                )


def validate_referenced_file(
    wallpaper_id: str,
    relative_path: str,
    root: Path,
    max_size: int,
    file_type: str,
) -> None:
    path = root / relative_path

    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        error(
            f"{file_type.capitalize()} '{wallpaper_id}' points outside the content directory: "
            f"{relative_path}"
        )
        return

    if not path.is_file():
        error(
            f"Missing {file_type} for wallpaper '{wallpaper_id}': {relative_path}"
        )
        return

    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        error(
            f"Unsupported {file_type} format for '{wallpaper_id}': {path.suffix}"
        )
        return

    size = path.stat().st_size

    if size > max_size:
        error(
            f"{file_type.capitalize()} '{relative_path}' is too large: "
            f"{size} bytes; maximum is {max_size} bytes."
        )


def validate_wallpaper_dimensions(manifest: dict) -> None:
    categories = manifest.get("categories", [])

    if not isinstance(categories, list):
        return

    checked_paths: set[Path] = set()

    for category in categories:
        if not isinstance(category, dict):
            continue

        wallpapers = category.get("wallpapers", [])

        if not isinstance(wallpapers, list):
            continue

        for wallpaper in wallpapers:
            if not isinstance(wallpaper, dict):
                continue

            image_path = wallpaper.get("image")
            wallpaper_id = wallpaper.get("id", "<unknown>")

            if not isinstance(image_path, str):
                continue

            path = CONTENT_DIR / image_path

            if path in checked_paths or not path.is_file():
                continue

            checked_paths.add(path)

            try:
                with Image.open(path) as image:
                    width, height = image.size

                    if width < MIN_WIDTH or height < MIN_HEIGHT:
                        error(
                            f"Wallpaper '{wallpaper_id}' is too small: "
                            f"{width}x{height}. Minimum is "
                            f"{MIN_WIDTH}x{MIN_HEIGHT}."
                        )

                    if width <= 0 or height <= 0:
                        error(
                            f"Wallpaper '{wallpaper_id}' has invalid dimensions: "
                            f"{width}x{height}."
                        )

                    image.verify()

            except Exception as exc:
                error(
                    f"Wallpaper '{wallpaper_id}' could not be validated: {exc}"
                )


def validate_thumbnail_dimensions(manifest: dict) -> None:
    categories = manifest.get("categories", [])

    if not isinstance(categories, list):
        return

    checked_paths: set[Path] = set()

    for category in categories:
        if not isinstance(category, dict):
            continue

        wallpapers = category.get("wallpapers", [])

        if not isinstance(wallpapers, list):
            continue

        for wallpaper in wallpapers:
            if not isinstance(wallpaper, dict):
                continue

            thumbnail_path = wallpaper.get("thumbnail")
            wallpaper_id = wallpaper.get("id", "<unknown>")

            if not isinstance(thumbnail_path, str):
                continue

            path = CONTENT_DIR / thumbnail_path

            if path in checked_paths or not path.is_file():
                continue

            checked_paths.add(path)

            try:
                with Image.open(path) as image:
                    width, height = image.size

                    if width <= 0 or height <= 0:
                        error(
                            f"Thumbnail '{wallpaper_id}' has invalid dimensions: "
                            f"{width}x{height}."
                        )

                    image.verify()

            except Exception as exc:
                error(
                    f"Thumbnail '{wallpaper_id}' could not be validated: {exc}"
                )


def validate_unreferenced_content() -> None:
    referenced_wallpapers: set[Path] = set()
    referenced_thumbnails: set[Path] = set()

    if MANIFEST_PATH.is_file():
        try:
            with MANIFEST_PATH.open("r", encoding="utf-8") as file:
                manifest = json.load(file)
        except Exception:
            return

        categories = manifest.get("categories", [])

        if isinstance(categories, list):
            for category in categories:
                if not isinstance(category, dict):
                    continue

                wallpapers = category.get("wallpapers", [])

                if not isinstance(wallpapers, list):
                    continue

                for wallpaper in wallpapers:
                    if not isinstance(wallpaper, dict):
                        continue

                    image_path = wallpaper.get("image")
                    thumbnail_path = wallpaper.get("thumbnail")

                    if isinstance(image_path, str):
                        referenced_wallpapers.add(
                            (CONTENT_DIR / image_path).resolve()
                        )

                    if isinstance(thumbnail_path, str):
                        referenced_thumbnails.add(
                            (CONTENT_DIR / thumbnail_path).resolve()
                        )

    for directory, referenced, label in (
        (WALLPAPER_DIR, referenced_wallpapers, "wallpaper"),
        (THUMBNAIL_DIR, referenced_thumbnails, "thumbnail"),
    ):
        if not directory.exists():
            continue

        for path in directory.rglob("*"):
            if not path.is_file():
                continue

            if path.resolve() not in referenced:
                error(
                    f"Unreferenced {label} file: "
                    f"{path.relative_to(CONTENT_DIR).as_posix()}"
                )


def main() -> int:
    manifest = load_manifest()

    if manifest:
        validate_manifest_structure(manifest)
        validate_wallpaper_dimensions(manifest)
        validate_thumbnail_dimensions(manifest)
        validate_unreferenced_content()

    if errors:
        print("CONTENT VALIDATION FAILED")
        print()

        for item in errors:
            print(f"- {item}")

        print()
        print(f"{len(errors)} validation error(s) found.")
        return 1

    print("CONTENT VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
