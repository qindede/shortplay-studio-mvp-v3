from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db_store, storage
from app.config import UPLOAD_DIR

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "db.json"


def replace_value(value, mapping: dict[str, str]):
    if isinstance(value, dict):
        return {key: replace_value(item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_value(item, mapping) for item in value]
    if isinstance(value, str):
        return mapping.get(value, value)
    return value


def load_current_data() -> dict:
    if db_store.enabled():
        return db_store.load_data()
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def save_current_data(data: dict) -> None:
    if db_store.enabled():
        db_store.save_data(data)
        return
    backup = DATA_PATH.with_suffix(".r2-backup.json")
    if not backup.exists():
        backup.write_text(DATA_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    if not storage.configured():
        raise RuntimeError("R2 is not configured")
    if not UPLOAD_DIR.exists():
        print("No local uploads directory found")
        return

    data = load_current_data()
    mapping: dict[str, str] = {}
    for path in UPLOAD_DIR.iterdir():
        if not path.is_file():
            continue
        old_url = f"/uploads/{path.name}"
        key = storage.make_object_key("migrated", path.name)
        new_url = storage.put_bytes(path.read_bytes(), key, storage.guess_content_type(path.name))
        mapping[old_url] = new_url
        print(f"{old_url} -> {new_url}")

    if not mapping:
        print("No files to migrate")
        return

    updated = replace_value(deepcopy(data), mapping)
    save_current_data(updated)
    print(f"Migrated {len(mapping)} files")


if __name__ == "__main__":
    main()
