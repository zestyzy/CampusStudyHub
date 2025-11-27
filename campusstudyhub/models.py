"""Data models for CampusStudyHub."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import List, Optional
import uuid


PRIORITY_LEVELS = ["low", "medium", "high"]
TASK_STATUSES = ["todo", "in_progress", "done"]


@dataclass
class Task:
    """Represents a study task or assignment."""

    title: str
    course: str
    task_type: str
    due_date: str
    priority: str = "medium"
    status: str = "todo"
    notes: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        """Serialize task to a dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Create a Task instance from dictionary data."""
        return cls(**data)

    def is_overdue(self) -> bool:
        """Return True if the task is overdue based on today's date."""
        try:
            due = date.fromisoformat(self.due_date)
        except ValueError:
            return False
        return due < date.today() and self.status != "done"

    def is_due_within(self, days: int) -> bool:
        """Return True if the task is due within the next given number of days."""
        try:
            due = date.fromisoformat(self.due_date)
        except ValueError:
            return False
        return 0 <= (due - date.today()).days <= days


@dataclass
class FileIndexEntry:
    """Represents an indexed study material file."""

    course: str
    file_type: str
    filename: str
    full_path: str
    modified: str

    def to_csv_row(self) -> List[str]:
        return [self.course, self.file_type, self.filename, self.full_path, self.modified]


def format_datetime(ts: float) -> str:
    """Format a timestamp to a readable string."""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
