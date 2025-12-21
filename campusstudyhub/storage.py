"""Storage utilities for CampusStudyHub."""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import List, Optional

from .config import DATA_DIR, ensure_data_dir
from .models import (
    ConferenceEvent,
    ExperimentEntry,
    FileIndexEntry,
    GradeEntry,
    PaperEntry,
    Task,
)

TASKS_PATH = DATA_DIR / "tasks.json"
FILES_INDEX_PATH = DATA_DIR / "files_index.csv"
CONFERENCES_PATH = DATA_DIR / "conferences.json"
GRADES_PATH = DATA_DIR / "grades.json"
EXPERIMENTS_PATH = DATA_DIR / "experiments.json"
PAPERS_PATH = DATA_DIR / "papers.json"
RESEARCH_MD_PATH = DATA_DIR / "research_summary.md"


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


def default_conferences() -> List[ConferenceEvent]:
    """Provide a short built-in list of CCF-related conferences."""

    defaults = [
        {
            "name": "AAAI",
            "category": "CCF-A",
            "submission_deadline": "2025-08-15",
            "location": "North America",
            "url": "https://aaai.org",
            "note": "AI flagship",
        },
        {
            "name": "CVPR",
            "category": "CCF-A",
            "submission_deadline": "2025-11-15",
            "location": "International",
            "url": "https://cvpr.thecvf.com",
            "note": "Computer vision",
        },
        {
            "name": "ICML",
            "category": "CCF-A",
            "submission_deadline": "2025-01-20",
            "location": "International",
            "url": "https://icml.cc",
            "note": "Machine learning",
        },
        {
            "name": "SIGIR",
            "category": "CCF-A",
            "submission_deadline": "2025-02-01",
            "location": "International",
            "url": "https://sigir.org",
            "note": "Information retrieval",
        },
        {
            "name": "IJCAI",
            "category": "CCF-A",
            "submission_deadline": "2025-01-10",
            "location": "International",
            "url": "https://ijcai.org",
            "note": "AI conference",
        },
    ]
    return [ConferenceEvent.from_dict(item) for item in defaults]


def load_conferences() -> List[ConferenceEvent]:
    """Load conference deadlines from disk, seeding defaults if missing."""

    ensure_data_dir()
    if not CONFERENCES_PATH.exists():
        defaults = default_conferences()
        save_conferences(defaults)
        return defaults

    try:
        with CONFERENCES_PATH.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return [ConferenceEvent.from_dict(item) for item in raw]
    except Exception:
        return default_conferences()


def save_conferences(conferences: List[ConferenceEvent]) -> None:
    """Persist conferences to disk."""

    ensure_data_dir()
    serializable = [c.to_dict() for c in conferences]
    with CONFERENCES_PATH.open("w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)


def load_grades() -> List[GradeEntry]:
    """Load GPA entries from disk."""

    ensure_data_dir()
    if not GRADES_PATH.exists():
        return []
    try:
        with GRADES_PATH.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return [GradeEntry.from_dict(item) for item in raw]
    except Exception:
        return []


def save_grades(entries: List[GradeEntry]) -> None:
    """Persist GPA rows to disk."""

    ensure_data_dir()
    serializable = [e.to_dict() for e in entries]
    with GRADES_PATH.open("w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)


def load_experiments() -> List[ExperimentEntry]:
    """Load experiment tracker entries from disk."""

    ensure_data_dir()
    if not EXPERIMENTS_PATH.exists():
        return []
    try:
        with EXPERIMENTS_PATH.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return [ExperimentEntry.from_dict(item) for item in raw]
    except Exception:
        return []


def save_experiments(entries: List[ExperimentEntry]) -> None:
    """Persist experiments to disk."""

    ensure_data_dir()
    serializable = [e.to_dict() for e in entries]
    with EXPERIMENTS_PATH.open("w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)


def load_papers() -> List[PaperEntry]:
    """Load reading list papers from disk."""

    ensure_data_dir()
    if not PAPERS_PATH.exists():
        return []
    try:
        with PAPERS_PATH.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return [PaperEntry.from_dict(item) for item in raw]
    except Exception:
        return []


def save_papers(entries: List[PaperEntry]) -> None:
    """Persist papers to disk."""

    ensure_data_dir()
    serializable = [e.to_dict() for e in entries]
    with PAPERS_PATH.open("w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)


def export_research_summary(experiments: List[ExperimentEntry], papers: List[PaperEntry]) -> None:
    """Export a markdown summary for experiments and reading list."""

    ensure_data_dir()
    lines = ["# Research Summary", ""]
    if experiments:
        lines.append("## Experiments")
        for exp in experiments:
            lines.append(
                f"- **{exp.title}** ({exp.project}) — {exp.status} | metric: {exp.metric or 'n/a'} | updated: {exp.updated_at or 'unknown'}"
            )
        lines.append("")
    if papers:
        lines.append("## Reading List")
        for paper in papers:
            doi_part = f" DOI: {paper.doi}" if paper.doi else ""
            lines.append(f"- **{paper.title}** [{paper.status}] {doi_part}")
    RESEARCH_MD_PATH.write_text("\n".join(lines), encoding="utf-8")
