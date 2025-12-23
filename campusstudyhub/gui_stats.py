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

        self.course_label = ttk.Label(self, text="各课程任务数：-")
        self.course_label.pack(anchor=tk.W, pady=5)
        self.status_label = ttk.Label(self, text="按状态统计：-")
        self.status_label.pack(anchor=tk.W, pady=5)
        self.completion_label = ttk.Label(self, text="近7天完成：-")
        self.completion_label.pack(anchor=tk.W, pady=5)

        self.progress = ttk.Progressbar(self, orient=tk.HORIZONTAL, length=300, mode="determinate")
        self.progress.pack(anchor=tk.W, pady=10)

        self.refresh()

    def refresh(self) -> None:
        tasks = self.tasks_provider()
        by_course = Counter(t.course for t in tasks)
        by_status = Counter(t.status for t in tasks)

        self.course_label.config(
            text="各课程任务数：" + ", ".join(f"{course} ({count})" for course, count in by_course.items() or [("无", 0)])
        )
        self.status_label.config(
            text="按状态统计：" + ", ".join(f"{status} ({count})" for status, count in by_status.items() or [("无", 0)])
        )

        last_week = date.today() - timedelta(days=7)
        completed_recent = [t for t in tasks if t.status == "done" and self._completed_within(t, last_week)]
        self.completion_label.config(text=f"近7天完成：{len(completed_recent)}")

        total = len(tasks)
        done = by_status.get("done", 0)
        self.progress.config(maximum=total or 1, value=done)

    def _completed_within(self, task: Task, since: date) -> bool:
        try:
            due = date.fromisoformat(task.due_date)
        except ValueError:
            return False
        return task.status == "done" and due >= since
