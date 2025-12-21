"""Stats tab for CampusStudyHub."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from collections import Counter
from datetime import date, timedelta
from typing import Callable, List

from .models import Task


class StatsFrame(ttk.Frame):
    """Display simple statistics about tasks."""

    def __init__(self, master: tk.Widget, tasks_provider: Callable[[], List[Task]]) -> None:
        super().__init__(master, padding=10)
        self.tasks_provider = tasks_provider

        self.course_label = ttk.Label(self, text="Tasks per course: -")
        self.course_label.pack(anchor=tk.W, pady=5)
        self.status_label = ttk.Label(self, text="Tasks by status: -")
        self.status_label.pack(anchor=tk.W, pady=5)
        self.completion_label = ttk.Label(self, text="Completed in last 7 days: -")
        self.completion_label.pack(anchor=tk.W, pady=5)

        self.progress = ttk.Progressbar(self, orient=tk.HORIZONTAL, length=300, mode="determinate")
        self.progress.pack(anchor=tk.W, pady=10)

        self.refresh()

    def refresh(self) -> None:
        tasks = self.tasks_provider()
        by_course = Counter(t.course for t in tasks)
        by_status = Counter(t.status for t in tasks)

        self.course_label.config(
            text="Tasks per course: " + ", ".join(f"{course} ({count})" for course, count in by_course.items() or [("None", 0)])
        )
        self.status_label.config(
            text="Tasks by status: " + ", ".join(f"{status} ({count})" for status, count in by_status.items() or [("None", 0)])
        )

        last_week = date.today() - timedelta(days=7)
        completed_recent = [t for t in tasks if t.status == "done" and self._completed_within(t, last_week)]
        self.completion_label.config(text=f"Completed in last 7 days: {len(completed_recent)}")

        total = len(tasks)
        done = by_status.get("done", 0)
        self.progress.config(maximum=total or 1, value=done)

    def _completed_within(self, task: Task, since: date) -> bool:
        try:
            due = date.fromisoformat(task.due_date)
        except ValueError:
            return False
        return task.status == "done" and due >= since
