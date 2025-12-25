from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import customtkinter as ctk

# 请确保这些模块在你的项目中存在
from .models import ConferenceEvent, ExperimentEntry, Task
from .storage import (
    load_conferences,
    load_experiments,
    load_log_monitors,
    load_papers,
    load_tasks,
)
from .ui_style import (
    ACCENT,
    ACCENT_ALT,
    BADGE_FONT,
    BG_CARD,
    BG_DARK,
    CLOCK_FONT,
    DATE_FONT,
    HEADER_FONT,
    LABEL_FONT,
    LABEL_BOLD,
    MONO_FONT,
    TEXT_ERROR,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_WARN,
    card_kwargs,
)

# ============================================================
# Visual style constants
# ============================================================

NAV_BG = "#0b121b"
NAV_BTN_BG = "#101a26"
NAV_BTN_HOVER = "#162233"
NAV_ACTIVE_BG = "#0f253a"
DIVIDER = "#1a2a3d"

PILL_BG = "#0e1a28"
PILL_BAR_BG = "#0b1522"

OVERDUE_BG = "#4a0f14"
OVERDUE_FG = "#ff6b6b"

OK_FG = "#3ddc84"
WARN_FG = "#ffb020"
BAD_FG = "#ff4d4d"

BTN_DARK = "#152133"
BTN_DARK_HOVER = "#1a2a40"

WEATHER_BG = "#0b121b"
WEATHER_INNER = "#0a1824"


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _safe_date(s: str) -> Optional[date]:
    try:
        return date.fromisoformat(s)
    except Exception:
        return None


def _days_to_text(delta: int) -> str:
    if delta < 0:
        return f"Overdue {abs(delta)}d"
    if delta == 0:
        return "Due Today"
    if delta == 1:
        return "Due Tomorrow"
    return f"Due in {delta}d"


# =========================
# GPA helper
# =========================
_GRADE_POINTS = {
    "A+": 4.0, "A": 4.0, "A-": 3.7, "B+": 3.3, "B": 3.0, "B-": 2.7,
    "C+": 2.3, "C": 2.0, "C-": 1.7, "D": 1.0, "F": 0.0,
}


@dataclass
class _CourseRow:
    name: str = ""
    credits: float = 3.0
    grade: str = "A"


# ============================================================
# DashboardFrame (Aligned Layout + Live Data)
# ============================================================
class DashboardFrame(ctk.CTkFrame):
    """
    Console-style dashboard with strict alignment AND live data refresh.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        navigator: Optional[Dict[str, Callable[[], None]]] = None,
    ) -> None:
        super().__init__(master, fg_color=BG_DARK)
        self.navigator = navigator or {}

        # data
        self.tasks: List[Task] = []
        self.confs: List[ConferenceEvent] = []
        self.exps: List[ExperimentEntry] = []
        self.monitors = []

        # gpa state
        self._required_courses: List[_CourseRow] = [
            _CourseRow("Algorithms", 4.0, "A-"),
            _CourseRow("Systems", 3.0, "A"),
            _CourseRow("ML", 3.0, "B+"),
            _CourseRow("Math", 4.0, "A-"),
        ]
        self._elective_courses: List[_CourseRow] = [
            _CourseRow("Seminar", 2.0, "A"),
            _CourseRow("Reading", 1.0, "A"),
        ]
        self._gpa_tab = ctk.StringVar(value="Required Courses")

        # pomodoro
        self._pomo_running = False
        self._pomo_total_sec = 25 * 60
        self._pomo_left_sec = self._pomo_total_sec
        self._pomo_last_tick: Optional[datetime] = None

        self._build_ui()
        self.refresh()

        # loops
        self.after(1500, self._tick_resources)
        self.after(250, self._tick_pomodoro)
        self.after(10_000, self._tick_weather)
        
        # [NEW] Heartbeat for data refresh (Every 5 seconds)
        self.after(5000, self._tick_data_refresh)

    # ============================================================
    # Build UI (Layout Preserved)
    # ============================================================
    def _build_ui(self) -> None:
        # Root layout: 5 equal columns
        self.grid_columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="rootcol")
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        # --- 1. Main Content Area (Row 0) ---
        self._main = ctk.CTkFrame(self, fg_color=BG_DARK)
        self._main.grid(row=0, column=0, columnspan=5, sticky="nsew", padx=12, pady=(12, 6))
        self._main.grid_columnconfigure(0, weight=1, uniform="main")
        self._main.grid_columnconfigure(1, weight=1, uniform="main")
        self._main.grid_columnconfigure(2, weight=1, uniform="main")
        self._main.grid_rowconfigure(0, weight=1)

        self.card_tasks = self._make_card(self._main, "Task List", 0, 0, nav_key="tasks")
        self.card_gpa = self._make_card(self._main, "GPA Calculator", 0, 1, nav_key="school")
        self.card_logs = self._make_card(self._main, "Research Logs", 0, 2, nav_key="research")

        self._build_task_panel(self.card_tasks)
        self._build_gpa_panel(self.card_gpa)
        self._build_logs_panel(self.card_logs)

        # --- 2. Bottom Container (Row 1) ---
        self._bottom = ctk.CTkFrame(self, fg_color="transparent")
        self._bottom.grid(row=1, column=0, columnspan=5, sticky="ew", padx=12, pady=(6, 12))
        
        self._bottom.grid_columnconfigure(0, weight=3, uniform="bot_group_l") 
        self._bottom.grid_columnconfigure(1, weight=2, uniform="bot_group_r") 
        self._bottom.grid_rowconfigure(0, weight=1)

        # === LEFT GROUP ===
        self._bot_left = ctk.CTkFrame(self._bottom, fg_color="transparent")
        self._bot_left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self._bot_left.grid_columnconfigure(0, weight=1)
        self._bot_left.grid_rowconfigure(0, weight=0)
        self._bot_left.grid_rowconfigure(1, weight=1)

        # A. Resources
        self._res_row = ctk.CTkFrame(self._bot_left, fg_color="transparent")
        self._res_row.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self._res_row.grid_columnconfigure((0, 1, 2), weight=1, uniform="res_pill")
        
        self.gpu_pill = _MetricPill(self._res_row, "GPU", 0, "—")
        self.cpu_pill = _MetricPill(self._res_row, "CPU", 1, "—")
        self.disk_pill = _MetricPill(self._res_row, "Disk", 2, "—")

        # B. Weather
        self.weather_bar = _WeatherBar(self._bot_left, row=1, col=0)
        self.weather_bar.refresh()

        # === RIGHT GROUP ===
        self._bot_right = ctk.CTkFrame(self._bottom, fg_color="transparent")
        self._bot_right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self._bot_right.grid_columnconfigure((0, 1), weight=1, uniform="bot_tool")
        self._bot_right.grid_rowconfigure(0, weight=1)

        self.card_bib = self._make_card(self._bot_right, "BiBTeX", 0, 0, nav_key="tools", compact=True)
        self.card_pomo = self._make_card(self._bot_right, "Pomodoro", 0, 1, nav_key="pomodoro", compact=True)
        
        self._build_bibtex_panel(self.card_bib)
        self._build_pomodoro_panel(self.card_pomo)

    def _make_card(
        self,
        parent: ctk.CTkFrame,
        title: str,
        row: int,
        col: int,
        nav_key: str,
        compact: bool = False,
    ) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent, **card_kwargs())
        frame.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 6 if compact else 8))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text=title, font=LABEL_BOLD, text_color=TEXT_PRIMARY).grid(
            row=0, column=0, sticky="w"
        )

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e")

        ctk.CTkButton(
            right,
            text="Open" if not compact else "",
            width=76 if not compact else 24,
            height=28,
            fg_color=BTN_DARK,
            hover_color=BTN_DARK_HOVER,
            font=BADGE_FONT,
            corner_radius=10,
            command=lambda k=nav_key: self._navigate(k),
        ).grid(row=0, column=0, padx=(0, 6))

        ctk.CTkButton(
            right,
            text="⋯",
            width=30 if compact else 38,
            height=28,
            fg_color=BTN_DARK,
            hover_color=BTN_DARK_HOVER,
            font=BADGE_FONT,
            corner_radius=10,
            command=lambda: None,
        ).grid(row=0, column=1)

        div = ctk.CTkFrame(frame, fg_color=DIVIDER, height=1, corner_radius=0)
        div.grid(row=0, column=0, sticky="ew", padx=12, pady=(44, 0))
        div.lift()
        return frame

    # ============================================================
    # Panels (Task logic updated)
    # ============================================================
    def _build_task_panel(self, card: ctk.CTkFrame) -> None:
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(10, 10))
        body.grid_rowconfigure(1, weight=1)
        body.grid_columnconfigure(0, weight=1)

        self.task_overdue_bar = ctk.CTkFrame(body, fg_color=OVERDUE_BG, corner_radius=10)
        self.task_overdue_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.task_overdue_bar.grid_columnconfigure(0, weight=1)

        self.task_overdue_label = ctk.CTkLabel(
            self.task_overdue_bar,
            text="No overdue tasks",
            font=LABEL_BOLD,
            text_color=OVERDUE_FG,
        )
        self.task_overdue_label.grid(row=0, column=0, sticky="w", padx=10, pady=8)

        # We keep the ScrollableFrame because it fits the UI better than a Textbox
        self.task_list = ctk.CTkScrollableFrame(body, fg_color=BG_CARD, corner_radius=12)
        self.task_list.grid(row=1, column=0, sticky="nsew")
        self.task_list.grid_columnconfigure(0, weight=1)

        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        actions.grid_columnconfigure((0, 1, 2), weight=1)

        for i, (txt, cmd) in enumerate([
            ("Add Task", lambda: self._navigate("tasks")),
            ("Edit", lambda: self._navigate("tasks")),
            ("Delete", lambda: self._navigate("tasks")),
        ]):
            ctk.CTkButton(
                actions,
                text=txt,
                height=34,
                fg_color=BTN_DARK,
                hover_color=BTN_DARK_HOVER,
                font=BADGE_FONT,
                corner_radius=10,
                command=cmd,
            ).grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 4, 0 if i == 2 else 4))

    def _build_gpa_panel(self, card: ctk.CTkFrame) -> None:
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(10, 10))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(2, weight=1)

        tabs = ctk.CTkFrame(body, fg_color=BG_CARD, corner_radius=12)
        tabs.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        tabs.grid_columnconfigure((0, 1), weight=1)

        self.btn_required = ctk.CTkButton(
            tabs,
            text="Required Courses",
            height=34,
            fg_color=NAV_ACTIVE_BG,
            hover_color=NAV_BTN_HOVER,
            font=BADGE_FONT,
            corner_radius=10,
            command=lambda: self._switch_gpa_tab("Required Courses"),
        )
        self.btn_elective = ctk.CTkButton(
            tabs,
            text="Elective Courses",
            height=34,
            fg_color=NAV_BTN_BG,
            hover_color=NAV_BTN_HOVER,
            font=BADGE_FONT,
            corner_radius=10,
            command=lambda: self._switch_gpa_tab("Elective Courses"),
        )
        self.btn_required.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        self.btn_elective.grid(row=0, column=1, sticky="ew", padx=8, pady=8)

        summary = ctk.CTkFrame(body, fg_color=BG_CARD, corner_radius=12)
        summary.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        summary.grid_columnconfigure((0, 1), weight=1)

        self.lbl_major = ctk.CTkLabel(summary, text="Major GPA:", font=LABEL_BOLD, text_color=TEXT_MUTED)
        self.val_major = ctk.CTkLabel(summary, text="0.00", font=HEADER_FONT, text_color=OK_FG)
        self.lbl_overall = ctk.CTkLabel(summary, text="Overall GPA:", font=LABEL_BOLD, text_color=TEXT_MUTED)
        self.val_overall = ctk.CTkLabel(summary, text="0.00", font=HEADER_FONT, text_color=WARN_FG)

        self.lbl_major.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 0))
        self.val_major.grid(row=0, column=1, sticky="e", padx=12, pady=(10, 0))
        self.lbl_overall.grid(row=1, column=0, sticky="w", padx=12, pady=(6, 12))
        self.val_overall.grid(row=1, column=1, sticky="e", padx=12, pady=(6, 12))

        table = ctk.CTkFrame(body, fg_color=BG_CARD, corner_radius=12)
        table.grid(row=2, column=0, sticky="nsew")
        table.grid_columnconfigure(0, weight=1)
        table.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(table, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))
        header.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(header, text="Course", font=LABEL_BOLD, text_color=TEXT_MUTED).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header, text="Cr.", font=LABEL_BOLD, text_color=TEXT_MUTED).grid(row=0, column=1)
        ctk.CTkLabel(header, text="Gr.", font=LABEL_BOLD, text_color=TEXT_MUTED).grid(row=0, column=2)

        self.course_list = ctk.CTkScrollableFrame(table, fg_color="transparent")
        self.course_list.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.course_list.grid_columnconfigure(0, weight=1)

        actions = ctk.CTkFrame(table, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))
        actions.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            actions,
            text="+ Add",
            height=32,
            fg_color=BTN_DARK,
            hover_color=BTN_DARK_HOVER,
            font=BADGE_FONT,
            corner_radius=10,
            command=self._add_course_row,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            actions,
            text="Recalc",
            height=32,
            fg_color=ACCENT,
            hover_color=ACCENT_ALT,
            font=BADGE_FONT,
            corner_radius=10,
            command=self._recalc_gpa,
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0))

    def _build_logs_panel(self, card: ctk.CTkFrame) -> None:
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(10, 10))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(2, weight=1)

        self.sub_confs = ctk.CTkFrame(body, fg_color=BG_CARD, corner_radius=12)
        self.sub_confs.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.sub_confs.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.sub_confs, text="Upcoming Conferences", font=LABEL_BOLD, text_color=TEXT_PRIMARY).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 6)
        )
        self.conf_list = ctk.CTkFrame(self.sub_confs, fg_color="transparent")
        self.conf_list.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.conf_list.grid_columnconfigure(0, weight=1)

        self.sub_exps = ctk.CTkFrame(body, fg_color=BG_CARD, corner_radius=12)
        self.sub_exps.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.sub_exps.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.sub_exps, text="Experiment Logs", font=LABEL_BOLD, text_color=TEXT_PRIMARY).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 6)
        )
        self.exp_list = ctk.CTkFrame(self.sub_exps, fg_color="transparent")
        self.exp_list.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.exp_list.grid_columnconfigure(0, weight=1)

        self.console = ctk.CTkTextbox(
            body,
            fg_color=BG_CARD,
            border_width=0,
            corner_radius=12,
            font=MONO_FONT,
            text_color=TEXT_PRIMARY,
            height=180,
        )
        self.console.grid(row=2, column=0, sticky="nsew")
        self.console.configure(state="disabled")

    def _build_bibtex_panel(self, card: ctk.CTkFrame) -> None:
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(10, 10))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(2, weight=1)

        self.doi_entry = ctk.CTkEntry(
            body,
            placeholder_text="DOI (10.1145/...)",
            height=30,
            fg_color=BG_CARD,
            border_color=DIVIDER,
            border_width=1,
            font=LABEL_FONT,
        )
        self.doi_entry.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        btns.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btns,
            text="Fetch",
            height=28,
            fg_color=BTN_DARK,
            hover_color=BTN_DARK_HOVER,
            font=BADGE_FONT,
            corner_radius=10,
            command=self._bib_fetch,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))

        ctk.CTkButton(
            btns,
            text="Gen",
            height=28,
            fg_color=ACCENT,
            hover_color=ACCENT_ALT,
            font=BADGE_FONT,
            corner_radius=10,
            command=self._bib_generate,
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self.bib_box = ctk.CTkTextbox(
            body,
            fg_color=BG_CARD,
            border_width=0,
            corner_radius=12,
            font=MONO_FONT,
            text_color=TEXT_PRIMARY,
            height=60,
        )
        self.bib_box.grid(row=2, column=0, sticky="nsew")
        self.bib_box.insert("end", "% DOI -> BibTeX\n")
        self.bib_box.configure(state="disabled")

    def _build_pomodoro_panel(self, card: ctk.CTkFrame) -> None:
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(10, 10))
        body.grid_columnconfigure(0, weight=1)

        self.pomo_time = ctk.CTkLabel(
            body,
            text=self._fmt_time(self._pomo_left_sec),
            font=("Inter", 38, "bold"),
            text_color=TEXT_PRIMARY,
        )
        self.pomo_time.grid(row=0, column=0, pady=(10, 10))

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.grid(row=1, column=0, sticky="ew")
        btns.grid_columnconfigure((0, 1), weight=1)

        self.btn_pomo_start = ctk.CTkButton(
            btns,
            text="Start",
            height=32,
            fg_color="#d57a1f",
            hover_color="#e08a34",
            font=BADGE_FONT,
            corner_radius=10,
            command=self._pomo_toggle,
        )
        self.btn_pomo_reset = ctk.CTkButton(
            btns,
            text="↺",
            width=32,
            height=32,
            fg_color=BTN_DARK,
            hover_color=BTN_DARK_HOVER,
            font=BADGE_FONT,
            corner_radius=10,
            command=self._pomo_reset,
        )
        self.btn_pomo_start.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.btn_pomo_reset.grid(row=0, column=1, sticky="ew")

    # ============================================================
    # Navigation
    # ============================================================
    def _navigate(self, key: str) -> None:
        cb = self.navigator.get(key)
        if cb:
            cb()

    # ============================================================
    # Refresh & Data Logic [UPDATED]
    # ============================================================
    def _tick_data_refresh(self) -> None:
        """Background loop to auto-refresh data every 5s."""
        try:
            self.refresh()
        except Exception:
            pass
        finally:
            self.after(5000, self._tick_data_refresh)

    def refresh(self) -> None:
        self.tasks = load_tasks()
        self.confs = load_conferences()
        self.exps = load_experiments()
        self.monitors = load_log_monitors()

        self._render_tasks()
        self._render_logs()
        self._render_gpa_table()
        self._recalc_gpa()
        self._render_console()
        self._tick_resources()

    def _render_tasks(self) -> None:
        """
        Render ALL tasks to the ScrollableFrame.
        Sort order: Overdue -> Upcoming -> Later -> No Date
        """
        for w in self.task_list.winfo_children():
            w.destroy()

        today = date.today()
        
        # 1. Sort logic:
        # Group 0: Has Date (sort by date)
        # Group 1: No Date (sort by creation id/title usually, here just title)
        def _sort_key(t):
            ds = getattr(t, "due_date", "") or ""
            d = _safe_date(ds)
            if d:
                return (0, d)
            return (1, date.max) 

        sorted_tasks = sorted(self.tasks, key=_sort_key)
        
        # Determine status for Badge only (Overdue count)
        overdue_count = 0
        for t in self.tasks:
            d = _safe_date(getattr(t, "due_date", "") or "")
            if d and (d - today).days < 0:
                overdue_count += 1

        # Update Badge
        if overdue_count > 0:
            self.task_overdue_label.configure(text=f"⚠ {overdue_count} Overdue Tasks", text_color=OVERDUE_FG)
            self.task_overdue_bar.configure(fg_color=OVERDUE_BG)
        else:
            self.task_overdue_label.configure(text="✓ All caught up", text_color=OK_FG)
            self.task_overdue_bar.configure(fg_color="#0f2a1a")

        if not sorted_tasks:
            ctk.CTkLabel(self.task_list, text="No tasks found", text_color=TEXT_MUTED).pack(pady=20)
            return

        # Render rows
        for idx, t in enumerate(sorted_tasks):
            title = getattr(t, "title", "Untitled")
            status = getattr(t, "status", "todo")
            course = getattr(t, "course", "") or getattr(t, "category", "")
            
            due_s = getattr(t, "due_date", "") or ""
            due = _safe_date(due_s)
            
            delta = None
            if due:
                delta = (due - today).days

            # Determine row style
            # Overdue: Red BG
            # Normal: Transparent
            row_bg = "transparent"
            if delta is not None and delta < 0:
                row_bg = OVERDUE_BG

            row = ctk.CTkFrame(self.task_list, fg_color=row_bg, corner_radius=10)
            row.grid(row=idx, column=0, sticky="ew", padx=8, pady=6)
            row.grid_columnconfigure(1, weight=1)

            # Icon
            icon = "☑" if status == "done" else "☐"
            ctk.CTkLabel(row, text=icon, font=LABEL_BOLD, text_color=TEXT_PRIMARY).grid(
                row=0, column=0, rowspan=2, padx=(10, 8), pady=8, sticky="n"
            )

            # Title
            ctk.CTkLabel(row, text=title, font=LABEL_BOLD, text_color=TEXT_PRIMARY).grid(
                row=0, column=1, sticky="w", pady=(8, 0)
            )

            # Subtitle (Course + Date)
            subtitle_parts = []
            if course:
                subtitle_parts.append(course)
            
            if delta is not None:
                subtitle_parts.append(_days_to_text(delta))
                subtitle_parts.append(f"({due_s})")
            else:
                subtitle_parts.append("No Due Date")

            subtitle = "  ·  ".join(subtitle_parts)
            ctk.CTkLabel(row, text=subtitle, font=LABEL_FONT, text_color=TEXT_MUTED).grid(
                row=1, column=1, sticky="w", pady=(0, 8)
            )

    def _render_logs(self) -> None:
        for w in self.conf_list.winfo_children():
            w.destroy()
        for w in self.exp_list.winfo_children():
            w.destroy()

        today = date.today()
        confs = sorted(self.confs, key=lambda c: getattr(c, "submission_deadline", "9999-12-31"))[:2]
        if not confs:
            _mini_row(self.conf_list, "📁 No upcoming conferences", "", TEXT_MUTED)
        else:
            for c in confs:
                due = _safe_date(getattr(c, "submission_deadline", ""))
                delta = (due - today).days if due else 999
                color = WARN_FG if 0 <= delta <= 14 else (BAD_FG if delta < 0 else TEXT_PRIMARY)
                _mini_row(
                    self.conf_list,
                    f"📁 {c.name}",
                    f"Deadline: {getattr(c, 'submission_deadline', 'Unknown')}",
                    color,
                )

        exps = self.exps[:2]
        if not exps:
            _mini_row(self.exp_list, "🧪 No experiments", "", TEXT_MUTED)
        else:
            for e in exps:
                status = getattr(e, "status", "planned")
                if status == "running":
                    color = OK_FG
                    tag = "Running"
                elif status in ("failed", "error"):
                    color = BAD_FG
                    tag = "Failed"
                elif status in ("done", "completed"):
                    color = WARN_FG
                    tag = "Completed"
                else:
                    color = TEXT_MUTED
                    tag = status

                _mini_row(
                    self.exp_list,
                    f"🧪 {e.title}",
                    f"{tag}  ·  {getattr(e, 'project', '')}",
                    color,
                )

    def _render_console(self) -> None:
        lines: List[str] = []
        if self.monitors:
            lines.append(f"[Monitor] watching {len(self.monitors)} logs")
        if self.exps:
            top = self.exps[0]
            tail = getattr(top, "last_message", "") or getattr(top, "metric", "") or ""
            if tail:
                lines.append(f"[Latest] {top.title} | {tail}")
        if not lines:
            lines = [
                "[Epoch 10] Loss: 0.123  Accuracy: 91.4%",
                "Warning: ...",
                "Error: Out of Memory!",
            ]
        self._fill_box(self.console, "\n".join(lines))

    @staticmethod
    def _fill_box(box: ctk.CTkTextbox, text: str) -> None:
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("end", text)
        box.configure(state="disabled")

    # ============================================================
    # GPA
    # ============================================================
    def _switch_gpa_tab(self, tab: str) -> None:
        self._gpa_tab.set(tab)
        if tab == "Required Courses":
            self.btn_required.configure(fg_color=NAV_ACTIVE_BG)
            self.btn_elective.configure(fg_color=NAV_BTN_BG)
        else:
            self.btn_required.configure(fg_color=NAV_BTN_BG)
            self.btn_elective.configure(fg_color=NAV_ACTIVE_BG)
        self._render_gpa_table()
        self._recalc_gpa()

    def _render_gpa_table(self) -> None:
        for w in self.course_list.winfo_children():
            w.destroy()

        courses = self._required_courses if self._gpa_tab.get() == "Required Courses" else self._elective_courses

        for idx, c in enumerate(courses):
            row = ctk.CTkFrame(self.course_list, fg_color="transparent")
            row.grid(row=idx, column=0, sticky="ew", padx=6, pady=6)
            row.grid_columnconfigure(0, weight=1)

            name = ctk.CTkEntry(
                row,
                height=30,
                fg_color=PILL_BG,
                border_color=DIVIDER,
                border_width=1,
                font=LABEL_FONT,
            )
            name.insert(0, c.name)
            name.grid(row=0, column=0, sticky="ew", padx=(0, 6))

            credits = ctk.CTkEntry(
                row,
                width=40,
                height=30,
                fg_color=PILL_BG,
                border_color=DIVIDER,
                border_width=1,
                font=LABEL_FONT,
                justify="center",
            )
            credits.insert(0, f"{c.credits:g}")
            credits.grid(row=0, column=1, padx=(0, 6))

            grade = ctk.CTkOptionMenu(
                row,
                values=list(_GRADE_POINTS.keys()),
                fg_color=PILL_BG,
                button_color=BTN_DARK,
                button_hover_color=BTN_DARK_HOVER,
                font=LABEL_FONT,
                dropdown_font=LABEL_FONT,
                width=60,
                height=30,
            )
            grade.set(c.grade)
            grade.grid(row=0, column=2, padx=(0, 6))

            gp = _GRADE_POINTS.get(grade.get(), 0.0)
            dot_color = OK_FG if gp >= 3.0 else (WARN_FG if gp >= 2.0 else BAD_FG)
            ctk.CTkLabel(row, text="●", font=LABEL_BOLD, text_color=dot_color).grid(
                row=0, column=3, sticky="e"
            )

            def _sync(_evt=None, _i=idx, _name=name, _credits=credits, _grade=grade):
                try:
                    courses[_i].name = _name.get().strip()
                    courses[_i].credits = float(_credits.get().strip() or "0")
                    courses[_i].grade = _grade.get()
                except Exception:
                    pass
                self._recalc_gpa()

            name.bind("<KeyRelease>", _sync)
            credits.bind("<KeyRelease>", _sync)
            grade.configure(command=lambda _v: self._recalc_gpa())

    def _add_course_row(self) -> None:
        courses = self._required_courses if self._gpa_tab.get() == "Required Courses" else self._elective_courses
        courses.append(_CourseRow("New Course", 3.0, "A"))
        self._render_gpa_table()
        self._recalc_gpa()

    def _recalc_gpa(self) -> None:
        major = self._calc_gpa(self._required_courses)
        overall = self._calc_gpa(self._required_courses + self._elective_courses)
        self.val_major.configure(text=f"{major:.2f}")
        self.val_overall.configure(text=f"{overall:.2f}")

    def _calc_gpa(self, courses: List[_CourseRow]) -> float:
        total_credits = 0.0
        total_points = 0.0
        for c in courses:
            cr = float(c.credits or 0.0)
            gp = _GRADE_POINTS.get(c.grade, 0.0)
            if cr <= 0:
                continue
            total_credits += cr
            total_points += cr * gp
        return (total_points / total_credits) if total_credits > 0 else 0.0

    # ============================================================
    # Resources (GPU/CPU/Disk)
    # ============================================================
    def _tick_resources(self) -> None:
        cpu_ratio = self._cpu_usage_ratio()
        gpu_ratio, gpu_text = self._gpu_usage_ratio()
        disk_ratio, disk_text = self._disk_usage_ratio()

        self.cpu_pill.set_value(cpu_ratio, f"{int(cpu_ratio * 100)}%")
        self.gpu_pill.set_value(gpu_ratio, gpu_text if gpu_text != "--" else f"{int(gpu_ratio * 100)}%")
        self.disk_pill.set_value(disk_ratio, disk_text)

        self.after(1500, self._tick_resources)

    def _cpu_usage_ratio(self) -> float:
        cpu_count = os.cpu_count() or 1
        if hasattr(os, "getloadavg"):
            try:
                load1, *_ = os.getloadavg()
                return _clamp(load1 / cpu_count, 0.0, 1.0)
            except Exception:
                return 0.0
        return 0.0

    def _disk_usage_ratio(self) -> Tuple[float, str]:
        try:
            usage = shutil.disk_usage(Path.home())
            total = usage.total / (1024**3)
            free = usage.free / (1024**3)
            ratio = usage.used / usage.total if usage.total else 0.0
            return _clamp(ratio), f"{int(free)}GB Free"
        except Exception:
            return 0.0, "--"

    def _gpu_usage_ratio(self) -> Tuple[float, str]:
        system = platform.system().lower()
        if system == "darwin":
            return 0.0, "N/A"
        for cmd in (
            ["gpustat", "-i"],
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
        ):
            try:
                out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=2)
                m = re.search(r"(\d+)\s*%", out)
                if not m:
                    m = re.search(r"^\s*(\d+)\s*$", out.strip())
                if m:
                    pct = float(m.group(1))
                    return _clamp(pct / 100.0), f"{int(pct)}%"
            except Exception:
                continue
        return 0.0, "--"

    # ============================================================
    # Weather periodic
    # ============================================================
    def _tick_weather(self) -> None:
        try:
            self.weather_bar.refresh()
        except Exception:
            pass
        self.after(600_000, self._tick_weather)  # 10 minutes

    # ============================================================
    # Pomodoro
    # ============================================================
    def _pomo_toggle(self) -> None:
        self._pomo_running = not self._pomo_running
        if self._pomo_running:
            self._pomo_last_tick = datetime.now()
            self.btn_pomo_start.configure(text="Pause")
        else:
            self._pomo_last_tick = None
            self.btn_pomo_start.configure(text="Start")

    def _pomo_reset(self) -> None:
        self._pomo_running = False
        self._pomo_left_sec = self._pomo_total_sec
        self._pomo_last_tick = None
        self.btn_pomo_start.configure(text="Start")
        self.pomo_time.configure(text=self._fmt_time(self._pomo_left_sec))

    def _tick_pomodoro(self) -> None:
        if self._pomo_running and self._pomo_last_tick is not None:
            now = datetime.now()
            dt = (now - self._pomo_last_tick).total_seconds()
            if dt >= 0.2:
                self._pomo_left_sec = max(0, self._pomo_left_sec - int(dt))
                self._pomo_last_tick = now
                self.pomo_time.configure(text=self._fmt_time(self._pomo_left_sec))
                if self._pomo_left_sec <= 0:
                    self._pomo_running = False
                    self.btn_pomo_start.configure(text="Start")
        self.after(250, self._tick_pomodoro)

    @staticmethod
    def _fmt_time(sec: int) -> str:
        m = sec // 60
        s = sec % 60
        return f"{m:02d}:{s:02d}"

    # ============================================================
    # BibTeX
    # ============================================================
    def _bib_fetch(self) -> None:
        doi = self.doi_entry.get().strip()
        if not doi:
            self._bib_set("% Please input DOI.\n")
            return

        if shutil.which("doi2bib"):
            try:
                out = subprocess.check_output(["doi2bib", doi], text=True, timeout=5)
                self._bib_set(out.strip() + "\n")
                return
            except Exception as e:
                self._bib_set(f"% doi2bib failed: {e}\n% fallback to template.\n" + self._bib_template(doi))
                return

        self._bib_set("% Offline mode: cannot fetch DOI metadata.\n" + self._bib_template(doi))

    def _bib_generate(self) -> None:
        doi = self.doi_entry.get().strip()
        if not doi:
            self._bib_set("% Please input DOI.\n")
            return
        self._bib_set(self._bib_template(doi))

    def _bib_template(self, doi: str) -> str:
        key = re.sub(r"[^a-zA-Z0-9]+", "", doi.split("/", 1)[-1])[:12] or "paper"
        return (
            f"@article{{{key},\n"
            f"  title={{TODO}},\n"
            f"  author={{TODO}},\n"
            f"  journal={{TODO}},\n"
            f"  year={{TODO}},\n"
            f"  doi={{ {doi} }},\n"
            f"}}\n"
        )

    def _bib_set(self, text: str) -> None:
        self._fill_box(self.bib_box, text)


# ============================================================
# UI Widgets (Grid-Aware)
# ============================================================
class _MetricPill:
    """Bottom resource pill (GPU/CPU/Disk)."""

    def __init__(self, parent: ctk.CTkFrame, title: str, col: int, right_text: str) -> None:
        self.frame = ctk.CTkFrame(parent, fg_color=PILL_BG, corner_radius=12)
        # Using nsew to fill the grid cell perfectly
        self.frame.grid(row=0, column=col, sticky="nsew", padx=6, pady=6)
        self.frame.grid_columnconfigure(1, weight=1)

        self.lbl = ctk.CTkLabel(self.frame, text=f"{title}:", font=LABEL_BOLD, text_color=TEXT_PRIMARY)
        self.lbl.grid(row=0, column=0, padx=(12, 6), pady=10, sticky="w")

        self.bar = ctk.CTkProgressBar(self.frame, fg_color=PILL_BAR_BG, progress_color=OK_FG, height=8)
        self.bar.grid(row=0, column=1, padx=6, pady=10, sticky="ew")
        self.bar.set(0.0)

        self.value = ctk.CTkLabel(self.frame, text=right_text, font=LABEL_BOLD, text_color=OK_FG)
        self.value.grid(row=0, column=2, padx=(6, 12), pady=10, sticky="e")

    def set_value(self, ratio: float, text: str) -> None:
        ratio = _clamp(ratio)
        self.bar.set(ratio)
        if ratio < 0.6:
            col = OK_FG
        elif ratio < 0.85:
            col = WARN_FG
        else:
            col = BAD_FG
        self.value.configure(text=text, text_color=col)
        self.bar.configure(progress_color=col)


class _WeatherBar:
    """
    Bottom weather bar (Expands to fill height).
    """

    def __init__(self, parent: ctk.CTkFrame, row: int, col: int) -> None:
        # Outer frame expands (sticky="nsew") to match the BibTeX/Pomo height
        self.outer = ctk.CTkFrame(parent, fg_color=WEATHER_BG, corner_radius=18)
        self.outer.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)
        self.outer.grid_columnconfigure(0, weight=1)
        self.outer.grid_rowconfigure(0, weight=1) # Center vertically

        self.inner = ctk.CTkFrame(self.outer, fg_color=WEATHER_INNER, corner_radius=16)
        self.inner.grid(row=0, column=0, sticky="ew", padx=8, pady=8)

        # layout: left fixed, mid stretch, right fixed
        self.inner.grid_columnconfigure(0, weight=0)
        self.inner.grid_columnconfigure(1, weight=1)
        self.inner.grid_columnconfigure(2, weight=0)

        # LEFT
        left = ctk.CTkFrame(self.inner, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=(6, 10), pady=4)

        ctk.CTkLabel(left, text="Weather", font=LABEL_BOLD, text_color=TEXT_PRIMARY).grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )

        self.city = ctk.CTkEntry(
            left,
            width=140,
            height=28,
            fg_color=PILL_BG,
            border_color=DIVIDER,
            border_width=1,
            font=LABEL_FONT,
            placeholder_text="City",
        )
        self.city.grid(row=0, column=1, sticky="w")
        self.city.insert(0, "Singapore")

        # MID
        mid = ctk.CTkFrame(self.inner, fg_color="transparent")
        mid.grid(row=0, column=1, sticky="ew", padx=10, pady=4)
        mid.grid_columnconfigure(0, weight=1)

        self.line1 = ctk.CTkLabel(mid, text="—", font=LABEL_BOLD, text_color=TEXT_PRIMARY)
        self.line1.grid(row=0, column=0, sticky="w")

        # RIGHT
        right = ctk.CTkFrame(self.inner, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e", padx=(10, 6), pady=4)
        
        self.btn = ctk.CTkButton(
            right,
            text="⟳",
            width=32,
            height=28,
            fg_color=BTN_DARK,
            hover_color=BTN_DARK_HOVER,
            font=BADGE_FONT,
            corner_radius=10,
            command=self.refresh,
        )
        self.btn.grid(row=0, column=0, sticky="e")

        self.time = ctk.CTkLabel(right, text="", font=DATE_FONT, text_color=TEXT_MUTED)
        self.time.grid(row=0, column=1, sticky="e", padx=(8, 0))

    def refresh(self) -> None:
        city = (self.city.get() or "").strip() or "Singapore"
        try:
            data = self._fetch_wttr(city)
            if not data:
                raise RuntimeError("empty data")

            current = data.get("current_condition", [{}])[0]
            area = data.get("nearest_area", [{}])[0].get("areaName", [{}])[0].get("value", city)

            temp_c = current.get("temp_C", "?")
            desc = current.get("weatherDesc", [{}])[0].get("value", "—")

            self.line1.configure(text=f"{area}: {temp_c}°C ({desc})", text_color=TEXT_PRIMARY)
            self.time.configure(text=datetime.now().strftime("%H:%M"))
        except Exception:
            self.line1.configure(text=f"{city}: Offline", text_color=TEXT_PRIMARY)
            self.time.configure(text=datetime.now().strftime("%H:%M"))

    @staticmethod
    def _fetch_wttr(city: str) -> Optional[dict]:
        q = urllib.parse.quote(city)
        url = f"https://wttr.in/{q}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        return json.loads(raw) if raw else None


def _mini_row(parent: ctk.CTkFrame, title: str, subtitle: str, color: str) -> None:
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.grid(sticky="ew", pady=4)
    row.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(row, text=title, font=LABEL_BOLD, text_color=TEXT_PRIMARY).grid(row=0, column=0, sticky="w")
    if subtitle:
        ctk.CTkLabel(row, text=subtitle, font=LABEL_FONT, text_color=TEXT_MUTED).grid(row=1, column=0, sticky="w")
    ctk.CTkLabel(row, text="●", font=LABEL_BOLD, text_color=color).grid(row=0, column=1, rowspan=2, sticky="e")