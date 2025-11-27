"""Storage utilities for CampusStudyHub."""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import List, Optional

from .config import DATA_DIR, ensure_data_dir
from .models import FileIndexEntry, Task

TASKS_PATH = DATA_DIR / "tasks.json"
FILES_INDEX_PATH = DATA_DIR / "files_index.csv"


def load_tasks() -> List[Task]:
    """Load tasks from disk and return as Task objects."""
    ensure_data_dir()
    if not TASKS_PATH.exists():
        return []
    try:
        with TASKS_PATH.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return [Task.from_dict(item) for item in raw]
    except Exception:
        return []


def save_tasks(tasks: List[Task]) -> None:
    """Persist tasks to disk in JSON format."""
    ensure_data_dir()
    serializable = [task.to_dict() for task in tasks]
    with TASKS_PATH.open("w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)


def add_task(tasks: List[Task], task: Task) -> List[Task]:
    """Add a new task to the list and save it."""
    tasks.append(task)
    save_tasks(tasks)
    return tasks


def update_task(tasks: List[Task], updated: Task) -> List[Task]:
    """Update an existing task by id and save."""
    for idx, task in enumerate(tasks):
        if task.id == updated.id:
            tasks[idx] = updated
            break
    save_tasks(tasks)
    return tasks


def delete_task(tasks: List[Task], task_id: str) -> List[Task]:
    """Remove a task by id and save."""
    tasks = [t for t in tasks if t.id != task_id]
    save_tasks(tasks)
    return tasks


def scan_files(base_dir: Path) -> List[Path]:
    """Recursively scan for files under the given base directory."""
    files: List[Path] = []
    if not base_dir.exists():
        return files
    for path in base_dir.rglob("*"):
        if path.is_file():
            files.append(path)
    return files


def move_file_safe(source: Path, dest: Path) -> None:
    """Move a file to destination while creating parent directories."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(dest))


def export_file_index(entries: List[FileIndexEntry]) -> None:
    """Export a list of file index entries to CSV."""
    ensure_data_dir()
    with FILES_INDEX_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["course", "type", "filename", "full_path", "modified"])
        for entry in entries:
            writer.writerow(entry.to_csv_row())
