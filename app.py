import csv
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
VIDEO_EXTS = {".mp4", ".m4v", ".mov"}
MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS

DEFAULT_DESCRIPTIONS_FILE = "/opt/camnow_gallery/descriptions.csv"
CSV_FIELDS = ["group", "description", "enabled", "sort_order", "live_url", "notes"]
EXCLUDED_NAME_SUBSTRINGS = {"conflict"}


def natural_key(value: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", value)]


def safe_child(root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def media_group(filename: str) -> str:
    return Path(filename).stem.strip()


def is_excluded_filename(filename: str) -> bool:
    """Return True for generated/conflict files that should never be displayed or onboarded."""
    lowered = filename.lower()
    return any(token in lowered for token in EXCLUDED_NAME_SUBSTRINGS)


def is_good_media_file(path: Path) -> bool:
    if path.name.startswith("."):
        return False
    if path.name.endswith(".tmp"):
        return False
    if is_excluded_filename(path.name):
        return False
    if path.suffix.lower() not in MEDIA_EXTS:
        return False
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def load_descriptions(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    if not path.exists():
        return rows

    try:
        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                group = (row.get("group") or "").strip()
                if not group:
                    continue

                clean = {field: (row.get(field) or "").strip() for field in CSV_FIELDS}
                clean["group"] = group
                if not clean["enabled"]:
                    clean["enabled"] = "yes"
                rows[group] = clean
    except Exception:
        return {}

    return rows


def write_descriptions(path: Path, rows: dict[str, dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")

    def sort_value(row: dict[str, str]):
        raw = row.get("sort_order", "")
        order = int(raw) if raw.isdigit() else 999999
        return order, natural_key(row.get("group", ""))

    ordered = sorted(rows.values(), key=sort_value)

    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in ordered:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})

    tmp.replace(path)


def discover_media(root: Path, recursive: bool = False) -> dict:
    files: list[Path] = []
    unreadable: list[dict[str, str]] = []
    iterator = root.rglob("*") if recursive else root.iterdir()

    for p in iterator:
        try:
            if not safe_child(root, p):
                continue
            if is_good_media_file(p):
                files.append(p)
        except Exception as e:
            unreadable.append({"path": str(p), "error": str(e)})

    groups = sorted({media_group(p.name) for p in files if media_group(p.name)}, key=natural_key)
    return {"files": files, "groups": groups, "unreadable": unreadable}


def sync_description_file(root: Path, descriptions_file: Path) -> dict:
    discovered = discover_media(root, recursive=False)
    rows = load_descriptions(descriptions_file)

    added: list[str] = []
    for group in discovered["groups"]:
        if group not in rows:
            rows[group] = {
                "group": group,
                "description": "",
                "enabled": "yes",
                "sort_order": "",
                "live_url": "",
                "notes": "auto-discovered",
            }
            added.append(group)

    write_descriptions(descriptions_file, rows)

    return {
        "added": added,
        "known": sorted(rows.keys(), key=natural_key),
        "groups_found": discovered["groups"],
        "unreadable": discovered["unreadable"],
    }


def list_media(root: Path, rel: Path, q: str = "", sort: str = "mtime", desc: bool = True):
    target = (root / rel).resolve()

    if not safe_child(root, target):
        return [], [], "Invalid path"
    if not target.exists() or not target.is_dir():
        return [], [], "Folder not found"

    dirs: list[Path] = []
    files: list[Path] = []
    q_lower = q.lower().strip()

    try:
        for p in target.iterdir():
            if p.name.startswith("."):
                continue
            if is_excluded_filename(p.name):
                continue
            if q_lower and q_lower not in p.name.lower():
                continue
            if p.is_dir():
                dirs.append(p)
            elif is_good_media_file(p):
                files.append(p)
    except PermissionError:
        return [], [], "PermissionError reading directory"

    def mtime(path: Path):
        try:
            return path.stat().st_mtime
        except OSError:
            return 0

    if sort == "mtime":
        dirs.sort(key=mtime, reverse=desc)
        files.sort(key=mtime, reverse=desc)
    else:
        dirs.sort(key=lambda p: natural_key(p.name))
        files.sort(key=lambda p: natural_key(p.name))
        if desc:
            files.reverse()

    return dirs, files, None


def create_app():
    app = Flask(__name__)

    media_root = os.environ.get("MEDIA_ROOT")
    if not media_root:
        raise RuntimeError("MEDIA_ROOT env var not set")

    root = Path(media_root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise RuntimeError(f"MEDIA_ROOT is not a directory: {root}")

    descriptions_file = Path(os.environ.get("DESCRIPTIONS_FILE", DEFAULT_DESCRIPTIONS_FILE)).expanduser().resolve()

    @app.route("/")
    def index():
        sync_description_file(root, descriptions_file)
        description_rows = load_descriptions(descriptions_file)

        descriptions = {
            group: row.get("description", "")
            for group, row in description_rows.items()
            if row.get("enabled", "yes").lower() != "no"
        }
        live_urls = {
            group: row.get("live_url", "")
            for group, row in description_rows.items()
            if row.get("enabled", "yes").lower() != "no"
        }

        rel = request.args.get("path", "").strip("/")
        q = request.args.get("q", "")
        sort = request.args.get("sort", "mtime")
        desc = request.args.get("desc", "1") == "1"
        refresh = int(request.args.get("refresh", "0") or "0")

        rel_path = Path(rel) if rel else Path(".")
        _dirs, files, err = list_media(root, rel_path, q=q, sort=sort, desc=desc)

        file_items = []
        for f in files:
            try:
                group = media_group(f.name)
                row = description_rows.get(group, {})
                if row.get("enabled", "yes").lower() == "no":
                    continue
                file_items.append({
                    "name": f.name,
                    "group": group,
                    "ext": f.suffix.lower(),
                    "path": quote(str((rel_path / f.name).as_posix()).strip("./")),
                    "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(f.stat().st_mtime)),
                    "size": f.stat().st_size,
                })
            except OSError:
                continue

        return render_template(
            "index.html",
            page_mode="browse",
            refresh=refresh,
            rel=str(rel_path).replace("\\", "/").strip(".").strip("/"),
            files=file_items,
            descriptions=descriptions,
            live_urls=live_urls,
            err=err,
        )

    @app.route("/discover")
    def discover():
        result = sync_description_file(root, descriptions_file)
        return jsonify({
            "media_root": str(root),
            "descriptions_file": str(descriptions_file),
            "added_new_groups": result["added"],
            "groups_found_in_media_folder": result["groups_found"],
            "known_groups_in_csv": result["known"],
            "unreadable": result["unreadable"],
            "excluded_name_substrings": sorted(EXCLUDED_NAME_SUBSTRINGS),
        })

    @app.route("/health")
    def health():
        return jsonify({
            "ok": True,
            "media_root": str(root),
            "media_root_exists": root.exists(),
            "descriptions_file": str(descriptions_file),
            "descriptions_file_exists": descriptions_file.exists(),
            "excluded_name_substrings": sorted(EXCLUDED_NAME_SUBSTRINGS),
        })

    @app.route("/media/<path:subpath>")
    def media(subpath):
        full = (root / subpath.strip("/")).resolve()
        if not safe_child(root, full):
            abort(403)
        if not full.exists() or not full.is_file():
            abort(404)
        if is_excluded_filename(full.name):
            abort(404)
        return send_from_directory(root, subpath)

    return app


app = create_app()

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    app.run(host=host, port=port, threaded=True)
