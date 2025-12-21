"""Tkinter main window for CampusStudyHub."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import List

from .config import AppConfig, load_config, save_config
from .models import Task
from .storage import load_tasks
from .gui_tasks import TasksFrame
from .gui_files import FilesFrame
from .gui_stats import StatsFrame
from .gui_conferences import ConferencesFrame
from .gui_plot import FigureComposer
from .gui_pomodoro import PomodoroTimer
from .gui_gpa import GPACalculator
from .gui_bibtex import BibtexGenerator


class App(tk.Tk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title("CampusStudyHub")
        self.geometry("1000x700")

        self.config_data: AppConfig = load_config()
        self.tasks: List[Task] = load_tasks()

        self._build_ui()

    def _build_ui(self) -> None:
        """Create tabs and widgets."""
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True)

        self.tasks_frame = TasksFrame(
            notebook,
            tasks=self.tasks,
            config=self.config_data,
            on_tasks_updated=self._update_tasks,
            on_config_update=self._update_config,
        )
        notebook.add(self.tasks_frame, text="Tasks")

        self.files_frame = FilesFrame(
            notebook,
            config=self.config_data,
            on_config_update=self._update_config,
        )
        notebook.add(self.files_frame, text="Files")

        self.stats_frame = StatsFrame(notebook, tasks_provider=self._get_tasks)
        notebook.add(self.stats_frame, text="Stats")

        self.conf_frame = ConferencesFrame(
            notebook,
            config=self.config_data,
            on_config_update=self._update_config,
        )
        notebook.add(self.conf_frame, text="CCF Conferences")

        self.figure_frame = FigureComposer(notebook)
        notebook.add(self.figure_frame, text="Figure Tool")

        self.pomodoro_frame = PomodoroTimer(notebook)
        notebook.add(self.pomodoro_frame, text="Pomodoro")

        self.gpa_frame = GPACalculator(notebook)
        notebook.add(self.gpa_frame, text="GPA Calc")

        self.bib_frame = BibtexGenerator(notebook)
        notebook.add(self.bib_frame, text="BibTeX")

    def _update_tasks(self, tasks: List[Task]) -> None:
        """Callback when tasks change."""
        self.tasks = tasks
        self.stats_frame.refresh()

    def _update_config(self, config: AppConfig) -> None:
        """Persist updated config and notify frames."""
        self.config_data = config
        save_config(config)
        self.tasks_frame.refresh_config(config)
        self.files_frame.refresh_config(config)
        self.conf_frame.refresh_config(config)

    def _get_tasks(self) -> List[Task]:
        return self.tasks


def launch_app() -> None:
    """Launch the Tkinter application."""
    app = App()
    app.mainloop()
