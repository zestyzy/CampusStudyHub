from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import customtkinter as ctk

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
    CARD_PAD_X,
    CARD_PAD_Y,
)

# ============================================================
# Small local style helpers (safe fallbacks, no external deps)
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

BANNER_BG = "#0b121b"


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
    "A+": 4.0,
    "A": 4.0,
    "A-": 3.7,
    "B+": 3.3,
    "B": 3.0,
    "B-": 2.7,
    "C+": 2.3,
    "C": 2.0,
    "C-": 1.7,
    "D": 1.0,
    "F": 0.0,
}


@dataclass
class _CourseRow:
    name: str = ""
    credits: float = 3.0
    grade: str = "A"


# ============================================================
# DashboardFrame (complete replacement)
# ============================================================
class DashboardFrame(ctk.CTkFrame):
    """
    Polished console-style dashboard that matches the provided UI reference.

    Layout (matches screenshot):
    - Top: navigation bar (Tasks / Files / School / Research / Monitor / Tools / Pomodoro)
    - Main row:
        Left:   Task List (with overdue highlight + list + action buttons)
        Center: GPA Calculator (Required/Elective tabs + summary + course table)
        Right:  Research Logs (Upcoming Conferences + Experiment Logs + console pane)
    - Bottom row:
        GPU pill | CPU pill | Disk pill | BibTeX Generator | Pomodoro Timer
    - Bottom banner (left side): signature / class / date fields (optional decorative)
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

        # gpa state (local, UI-only)
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
        self.after(1000, self._tick_clock)
        self.after(1500, self._tick_resources)
        self.after(250, self._tick_pomodoro)

    # ============================================================
    # Build UI
    # ============================================================
    def _build_ui(self) -> None:
        self.grid_columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="rootcol")
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)  # main content
        self.grid_rowconfigure(2, weight=0)  # bottom tools
        self.grid_rowconfigure(3, weight=0)  # banner

        # Top navigation bar
        self._nav = ctk.CTkFrame(self, fg_color=NAV_BG, corner_radius=0)
        self._nav.grid(row=0, column=0, columnspan=5, sticky="ew")
        self._nav.grid_columnconfigure(0, weight=1)

        self._build_navbar(self._nav)

        # Main area: 3 columns (Task / GPA / Research Logs)
        self._main = ctk.CTkFrame(self, fg_color=BG_DARK)
        self._main.grid(row=1, column=0, columnspan=5, sticky="nsew", padx=12, pady=(10, 8))
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

        # Bottom row: GPU/CPU/Disk pills + BibTeX + Pomodoro
        self._bottom = ctk.CTkFrame(self, fg_color=BG_DARK)
        self._bottom.grid(row=2, column=0, columnspan=5, sticky="ew", padx=12, pady=(0, 10))
        self._bottom.grid_columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="bottom")

        self.gpu_pill = _MetricPill(self._bottom, "GPU", 0, "45%")
        self.cpu_pill = _MetricPill(self._bottom, "CPU", 1, "23%")
        self.disk_pill = _MetricPill(self._bottom, "Disk", 2, "120GB Free")

        self.card_bib = self._make_card(self._bottom, "BiBTeX Generator", 0, 3, nav_key="tools", compact=True)
        self.card_pomo = self._make_card(self._bottom, "Pomodoro Timer", 0, 4, nav_key="pomodoro", compact=True)

        self._build_bibtex_panel(self.card_bib)
        self._build_pomodoro_panel(self.card_pomo)

        # Bottom banner (left side like screenshot)
        self._banner = ctk.CTkFrame(self, fg_color=BANNER_BG, corner_radius=14)
        self._banner.grid(row=3, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 12))
        self._banner.grid_columnconfigure(0, weight=1)
        self._build_banner(self._banner)

    def _build_navbar(self, master: ctk.CTkFrame) -> None:
        bar = ctk.CTkFrame(master, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        bar.grid_columnconfigure(0, weight=1)

        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")
        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e")

        tabs = [
            ("Tasks", "tasks"),
            ("Files", "files"),
            ("School", "school"),
            ("Research", "research"),
            ("Monitor", "monitor"),
            ("Tools", "tools"),
            ("Pomodoro", "pomodoro"),
        ]

        # Active tab in your screenshot is "Research"
        active_key = "research"

        for i, (label, key) in enumerate(tabs):
            is_active = key == active_key
            btn = ctk.CTkButton(
                left,
                text=label,
                height=34,
                width=118 if label != "Pomodoro" else 130,
                fg_color=NAV_ACTIVE_BG if is_active else NAV_BTN_BG,
                hover_color=NAV_BTN_HOVER,
                font=BADGE_FONT,
                corner_radius=10,
                command=lambda k=key: self._navigate(k),
            )
            btn.grid(row=0, column=i, padx=(0 if i == 0 else 8, 0))

        # right side: "⋯" menu
        ctk.CTkButton(
            right,
            text="⋯",
            width=44,
            height=34,
            fg_color=NAV_BTN_BG,
            hover_color=NAV_BTN_HOVER,
            font=BADGE_FONT,
            corner_radius=10,
            command=lambda: None,
        ).grid(row=0, column=0, padx=(8, 0))

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
        frame.grid(row=row, column=col, sticky="nsew", padx=10, pady=8)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        # header
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 6 if compact else 8))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text=title, font=LABEL_BOLD, text_color=TEXT_PRIMARY).grid(
            row=0, column=0, sticky="w"
        )

        # right: open + menu dots (like screenshot)
        right = ctk.CTkFrame(header, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e")

        ctk.CTkButton(
            right,
            text="Open" if not compact else "",
            width=76 if not compact else 38,
            height=28,
            fg_color=BTN_DARK,
            hover_color=BTN_DARK_HOVER,
            font=BADGE_FONT,
            corner_radius=10,
            command=lambda k=nav_key: self._navigate(k),
        ).grid(row=0, column=0, padx=(0, 8))

        ctk.CTkButton(
            right,
            text="⋯",
            width=38,
            height=28,
            fg_color=BTN_DARK,
            hover_color=BTN_DARK_HOVER,
            font=BADGE_FONT,
            corner_radius=10,
            command=lambda: None,
        ).grid(row=0, column=1)

        # divider line
        div = ctk.CTkFrame(frame, fg_color=DIVIDER, height=1, corner_radius=0)
        div.grid(row=0, column=0, sticky="ew", padx=12, pady=(44, 0))
        div.lift()

        return frame

    # ============================================================
    # Task panel
    # ============================================================
    def _build_task_panel(self, card: ctk.CTkFrame) -> None:
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(10, 10))
        body.grid_rowconfigure(1, weight=1)
        body.grid_columnconfigure(0, weight=1)

        # Overdue highlight bar (top row)
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

        # List (scroll)
        self.task_list = ctk.CTkScrollableFrame(body, fg_color=BG_CARD, corner_radius=12)
        self.task_list.grid(row=1, column=0, sticky="nsew")
        self.task_list.grid_columnconfigure(0, weight=1)

        # Bottom action buttons (Add/Edit/Delete)
        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        actions.grid_columnconfigure((0, 1, 2), weight=1)

        self.btn_task_add = ctk.CTkButton(
            actions,
            text="Add Task",
            height=34,
            fg_color=BTN_DARK,
            hover_color=BTN_DARK_HOVER,
            font=BADGE_FONT,
            corner_radius=10,
            command=lambda: self._navigate("tasks"),
        )
        self.btn_task_edit = ctk.CTkButton(
            actions,
            text="Edit",
            height=34,
            fg_color=BTN_DARK,
            hover_color=BTN_DARK_HOVER,
            font=BADGE_FONT,
            corner_radius=10,
            command=lambda: self._navigate("tasks"),
        )
        self.btn_task_del = ctk.CTkButton(
            actions,
            text="Delete",
            height=34,
            fg_color=BTN_DARK,
            hover_color=BTN_DARK_HOVER,
            font=BADGE_FONT,
            corner_radius=10,
            command=lambda: self._navigate("tasks"),
        )
        self.btn_task_add.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.btn_task_edit.grid(row=0, column=1, sticky="ew", padx=8)
        self.btn_task_del.grid(row=0, column=2, sticky="ew", padx=(8, 0))

    # ============================================================
    # GPA panel
    # ============================================================
    def _build_gpa_panel(self, card: ctk.CTkFrame) -> None:
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(10, 10))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(2, weight=1)

        # tabs (Required / Elective)
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

        # GPA summary
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

        # Course table
        table = ctk.CTkFrame(body, fg_color=BG_CARD, corner_radius=12)
        table.grid(row=2, column=0, sticky="nsew")
        table.grid_columnconfigure(0, weight=1)
        table.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(table, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))
        header.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(header, text="Course", font=LABEL_BOLD, text_color=TEXT_MUTED).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header, text="Credits", font=LABEL_BOLD, text_color=TEXT_MUTED).grid(row=0, column=1)
        ctk.CTkLabel(header, text="Grade", font=LABEL_BOLD, text_color=TEXT_MUTED).grid(row=0, column=2)
        ctk.CTkLabel(header, text="", font=LABEL_BOLD, text_color=TEXT_MUTED).grid(row=0, column=3, sticky="e")

        self.course_list = ctk.CTkScrollableFrame(table, fg_color="transparent")
        self.course_list.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.course_list.grid_columnconfigure(0, weight=1)

        # bottom small actions
        actions = ctk.CTkFrame(table, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))
        actions.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            actions,
            text="Add Course",
            height=32,
            fg_color=BTN_DARK,
            hover_color=BTN_DARK_HOVER,
            font=BADGE_FONT,
            corner_radius=10,
            command=self._add_course_row,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            actions,
            text="Recalculate",
            height=32,
            fg_color=ACCENT,
            hover_color=ACCENT_ALT,
            font=BADGE_FONT,
            corner_radius=10,
            command=self._recalc_gpa,
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0))

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

    # ============================================================
    # Logs panel (right)
    # ============================================================
    def _build_logs_panel(self, card: ctk.CTkFrame) -> None:
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(10, 10))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(2, weight=1)

        # Upcoming Conferences (sub-card)
        self.sub_confs = ctk.CTkFrame(body, fg_color=BG_CARD, corner_radius=12)
        self.sub_confs.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.sub_confs.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.sub_confs, text="Upcoming Conferences", font=LABEL_BOLD, text_color=TEXT_PRIMARY).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 6)
        )
        self.conf_list = ctk.CTkFrame(self.sub_confs, fg_color="transparent")
        self.conf_list.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.conf_list.grid_columnconfigure(0, weight=1)

        # Experiment Logs (sub-card)
        self.sub_exps = ctk.CTkFrame(body, fg_color=BG_CARD, corner_radius=12)
        self.sub_exps.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.sub_exps.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.sub_exps, text="Experiment Logs", font=LABEL_BOLD, text_color=TEXT_PRIMARY).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 6)
        )
        self.exp_list = ctk.CTkFrame(self.sub_exps, fg_color="transparent")
        self.exp_list.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.exp_list.grid_columnconfigure(0, weight=1)

        # Console pane
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

    # ============================================================
    # BibTeX panel
    # ============================================================
    def _build_bibtex_panel(self, card: ctk.CTkFrame) -> None:
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(10, 10))
        body.grid_columnconfigure(0, weight=1)

        self.doi_entry = ctk.CTkEntry(
            body,
            placeholder_text="Enter DOI (e.g., 10.1145/xxxxxx)",
            height=34,
            fg_color=BG_CARD,
            border_color=DIVIDER,
            border_width=1,
            font=LABEL_FONT,
        )
        self.doi_entry.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        btns.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btns,
            text="Fetch DOI",
            height=32,
            fg_color=BTN_DARK,
            hover_color=BTN_DARK_HOVER,
            font=BADGE_FONT,
            corner_radius=10,
            command=self._bib_fetch,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            btns,
            text="Generate",
            height=32,
            fg_color=ACCENT,
            hover_color=ACCENT_ALT,
            font=BADGE_FONT,
            corner_radius=10,
            command=self._bib_generate,
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0))

        self.bib_box = ctk.CTkTextbox(
            body,
            fg_color=BG_CARD,
            border_width=0,
            corner_radius=12,
            font=MONO_FONT,
            text_color=TEXT_PRIMARY,
            height=120,
        )
        self.bib_box.grid(row=2, column=0, sticky="nsew")
        self.bib_box.insert("end", "% Paste DOI then Generate.\n")
        self.bib_box.configure(state="disabled")

    # ============================================================
    # Pomodoro panel
    # ============================================================
    def _build_pomodoro_panel(self, card: ctk.CTkFrame) -> None:
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(10, 10))
        body.grid_columnconfigure(0, weight=1)

        self.pomo_time = ctk.CTkLabel(
            body,
            text=self._fmt_time(self._pomo_left_sec),
            font=("Inter", 42, "bold") if isinstance(CLOCK_FONT, tuple) else CLOCK_FONT,
            text_color=TEXT_PRIMARY,
        )
        self.pomo_time.grid(row=0, column=0, pady=(6, 10))

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.grid(row=1, column=0, sticky="ew")
        btns.grid_columnconfigure((0, 1), weight=1)

        self.btn_pomo_start = ctk.CTkButton(
            btns,
            text="Start",
            height=36,
            fg_color="#d57a1f",
            hover_color="#e08a34",
            font=BADGE_FONT,
            corner_radius=10,
            command=self._pomo_toggle,
        )
        self.btn_pomo_reset = ctk.CTkButton(
            btns,
            text="Reset",
            height=36,
            fg_color="#b33636",
            hover_color="#c74747",
            font=BADGE_FONT,
            corner_radius=10,
            command=self._pomo_reset,
        )
        self.btn_pomo_start.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.btn_pomo_reset.grid(row=0, column=1, sticky="ew", padx=(8, 0))

    # ============================================================
    # Banner (bottom-left decorative, like screenshot)
    # ============================================================
    def _build_banner(self, banner: ctk.CTkFrame) -> None:
        banner.grid_rowconfigure(0, weight=1)
        banner.grid_columnconfigure(0, weight=1)

        # top “image-like” area (no external image dependency)
        top = ctk.CTkFrame(banner, fg_color="#0a1824", corner_radius=14)
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        top.grid_columnconfigure(0, weight=1)

        # subtle text overlay placeholders
        info = ctk.CTkFrame(top, fg_color="transparent")
        info.grid(row=0, column=0, sticky="ew", padx=12, pady=18)
        info.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(info, text="分享人：__________", font=LABEL_FONT, text_color=TEXT_MUTED).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkLabel(info, text="班级/学号：__________", font=LABEL_FONT, text_color=TEXT_MUTED).grid(
            row=0, column=1, sticky="w"
        )
        ctk.CTkLabel(info, text="日期：__________", font=LABEL_FONT, text_color=TEXT_MUTED).grid(
            row=0, column=2, sticky="w"
        )

    # ============================================================
    # Navigation
    # ============================================================
    def _navigate(self, key: str) -> None:
        cb = self.navigator.get(key)
        if cb:
            cb()

    # ============================================================
    # Refresh & render
    # ============================================================
    def refresh(self) -> None:
        # Keep your existing data flow (same as old code) :contentReference[oaicite:1]{index=1}
        self.tasks = load_tasks()
        self.confs = load_conferences()
        self.exps = load_experiments()
        self.monitors = load_log_monitors()

        self._render_tasks()
        self._render_logs()
        self._render_gpa_table()
        self._recalc_gpa()
        self._render_console()

        # resources updated by timer loop, but do one initial tick
        self._tick_resources()

    # ------------------------------
    # Render Tasks
    # ------------------------------
    def _render_tasks(self) -> None:
        # clear list
        for w in self.task_list.winfo_children():
            w.destroy()

        today = date.today()
        # classify
        overdue = []
        upcoming = []
        normal = []

        for t in sorted(self.tasks, key=lambda x: getattr(x, "due_date", "9999-12-31")):
            due = _safe_date(getattr(t, "due_date", ""))
            if not due:
                normal.append((t, None, 999999))
                continue
            delta = (due - today).days
            if delta < 0:
                overdue.append((t, due, delta))
            elif delta <= 7:
                upcoming.append((t, due, delta))
            else:
                normal.append((t, due, delta))

        # Overdue bar text (like screenshot)
        if overdue:
            top_task, due, delta = overdue[0]
            self.task_overdue_label.configure(
                text=f"⚠ {top_task.title} — {_days_to_text(delta)}",
                text_color=OVERDUE_FG,
            )
            self.task_overdue_bar.configure(fg_color=OVERDUE_BG)
        else:
            self.task_overdue_label.configure(text="✓ No overdue tasks", text_color=OK_FG)
            self.task_overdue_bar.configure(fg_color="#0f2a1a")

        # show only a few rows (like screenshot)
        display_rows = overdue[:1] + upcoming[:3]
        if not display_rows and normal:
            display_rows = normal[:4]

        for idx, (t, due, delta) in enumerate(display_rows):
            status = getattr(t, "status", "todo")
            title = getattr(t, "title", "Untitled")
            course = getattr(t, "course", "")

            # row background
            row_bg = OVERDUE_BG if (delta is not None and delta < 0) else "transparent"

            row = ctk.CTkFrame(self.task_list, fg_color=row_bg, corner_radius=10)
            row.grid(row=idx, column=0, sticky="ew", padx=8, pady=6)
            row.grid_columnconfigure(1, weight=1)

            # checkbox-like icon
            icon = "☑" if status == "done" else "☐"
            ctk.CTkLabel(row, text=icon, font=LABEL_BOLD, text_color=TEXT_PRIMARY).grid(
                row=0, column=0, rowspan=2, padx=(10, 8), pady=8, sticky="n"
            )

            ctk.CTkLabel(row, text=title, font=LABEL_BOLD, text_color=TEXT_PRIMARY).grid(
                row=0, column=1, sticky="w", pady=(8, 0)
            )

            subtitle = ""
            if course:
                subtitle += course
            if due:
                subtitle += (" — " if subtitle else "") + _days_to_text(delta if delta is not None else 0)

            ctk.CTkLabel(row, text=subtitle, font=LABEL_FONT, text_color=TEXT_MUTED).grid(
                row=1, column=1, sticky="w", pady=(0, 8)
            )

    # ------------------------------
    # Render Logs (right column)
    # ------------------------------
    def _render_logs(self) -> None:
        for w in self.conf_list.winfo_children():
            w.destroy()
        for w in self.exp_list.winfo_children():
            w.destroy()

        # conferences
        today = date.today()
        confs = sorted(self.confs, key=lambda c: getattr(c, "submission_deadline", "9999-12-31"))[:2]
        if not confs:
            _mini_row(self.conf_list, "📁 No upcoming conferences", "", TEXT_MUTED)
        else:
            for i, c in enumerate(confs):
                due = _safe_date(getattr(c, "submission_deadline", ""))
                delta = (due - today).days if due else 999
                color = WARN_FG if 0 <= delta <= 14 else (BAD_FG if delta < 0 else TEXT_PRIMARY)
                _mini_row(
                    self.conf_list,
                    f"📁 {c.name}",
                    f"Deadline: {getattr(c, 'submission_deadline', 'Unknown')}",
                    color,
                )

        # experiments
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

        # monitors summary (like your old code used load_log_monitors) :contentReference[oaicite:2]{index=2}
        if self.monitors:
            lines.append(f"[Monitor] watching {len(self.monitors)} logs")

        # append some experiment tail info
        if self.exps:
            top = self.exps[0]
            tail = getattr(top, "last_message", "") or getattr(top, "metric", "") or ""
            if tail:
                lines.append(f"[Latest] {top.title} | {tail}")

        # a few “console-like” demo lines if empty
        if not lines:
            lines = [
                "[Epoch 10] Loss: 0.123  Accuracy: 91.4%",
                "Warning: ...",
                "Error: Out of Memory!",
            ]

        self._fill_box(self.console, "\n".join(lines))

    # ============================================================
    # GPA render & compute
    # ============================================================
    def _render_gpa_table(self) -> None:
        for w in self.course_list.winfo_children():
            w.destroy()

        courses = self._required_courses if self._gpa_tab.get() == "Required Courses" else self._elective_courses

        for idx, c in enumerate(courses):
            row = ctk.CTkFrame(self.course_list, fg_color="transparent")
            row.grid(row=idx, column=0, sticky="ew", padx=6, pady=6)
            row.grid_columnconfigure(0, weight=1)
            row.grid_columnconfigure(1, weight=0)
            row.grid_columnconfigure(2, weight=0)
            row.grid_columnconfigure(3, weight=0)

            name = ctk.CTkEntry(
                row,
                height=30,
                fg_color=PILL_BG,
                border_color=DIVIDER,
                border_width=1,
                font=LABEL_FONT,
            )
            name.insert(0, c.name)
            name.grid(row=0, column=0, sticky="ew", padx=(0, 10))

            credits = ctk.CTkEntry(
                row,
                width=70,
                height=30,
                fg_color=PILL_BG,
                border_color=DIVIDER,
                border_width=1,
                font=LABEL_FONT,
                justify="center",
            )
            credits.insert(0, f"{c.credits:g}")
            credits.grid(row=0, column=1, padx=(0, 10))

            grade = ctk.CTkOptionMenu(
                row,
                values=list(_GRADE_POINTS.keys()),
                fg_color=PILL_BG,
                button_color=BTN_DARK,
                button_hover_color=BTN_DARK_HOVER,
                font=LABEL_FONT,
                dropdown_font=LABEL_FONT,
                width=90,
                height=30,
            )
            grade.set(c.grade)
            grade.grid(row=0, column=2, padx=(0, 10))

            # status dot at far right
            dot_color = OK_FG if _GRADE_POINTS.get(grade.get(), 0.0) >= 3.0 else (WARN_FG if _GRADE_POINTS.get(grade.get(), 0.0) >= 2.0 else BAD_FG)
            dot = ctk.CTkLabel(row, text="●", font=LABEL_BOLD, text_color=dot_color)
            dot.grid(row=0, column=3, sticky="e")

            # bind updates
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
            grade.configure(command=lambda _v, _i=idx: self._on_grade_change(_i))

    def _on_grade_change(self, idx: int) -> None:
        # called after menu selection; just recalc
        self._recalc_gpa()

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
        self.gpu_pill.set_value(gpu_ratio, f"{int(gpu_ratio * 100)}%")
        self.disk_pill.set_value(disk_ratio, disk_text)

        self.after(1500, self._tick_resources)

    def _cpu_usage_ratio(self) -> float:
        # lightweight approx: loadavg / cpu_count
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
            used = usage.used / (1024**3)
            total = usage.total / (1024**3)
            free = total - used
            ratio = usage.used / usage.total if usage.total else 0.0
            text = f"{int(free)}GB Free"
            return _clamp(ratio), text
        except Exception:
            return 0.0, "--"

    def _gpu_usage_ratio(self) -> Tuple[float, str]:
        system = platform.system().lower()
        if system == "darwin":
            return 0.0, "N/A"
        # try gpustat
        for cmd in (["gpustat", "-i"], ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"]):
            try:
                out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=2)
                # parse percentage
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
    # Clock
    # ============================================================
    def _tick_clock(self) -> None:
        # (We keep clock inside Pomodoro; if you want a separate clock card, add here.)
        self.after(1000, self._tick_clock)

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
        """
        Try to fetch BibTeX using system tools if available.
        - If `doi2bib` exists: use it.
        - Else fallback to template.
        """
        doi = self.doi_entry.get().strip()
        if not doi:
            self._bib_set("% Please input DOI.\n")
            return

        # attempt doi2bib
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
    # Small textbox helper
    # ============================================================
    @staticmethod
    def _fill_box(box: ctk.CTkTextbox, text: str) -> None:
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("end", text)
        box.configure(state="disabled")


# ============================================================
# UI Widgets
# ============================================================
class _MetricPill:
    """Bottom resource pill like screenshot (GPU/CPU/Disk)."""

    def __init__(self, parent: ctk.CTkFrame, title: str, col: int, right_text: str) -> None:
        self.frame = ctk.CTkFrame(parent, fg_color=PILL_BG, corner_radius=12)
        self.frame.grid(row=0, column=col, sticky="ew", padx=10, pady=8)
        self.frame.grid_columnconfigure(1, weight=1)

        self.lbl = ctk.CTkLabel(self.frame, text=f"{title}:", font=LABEL_BOLD, text_color=TEXT_PRIMARY)
        self.lbl.grid(row=0, column=0, padx=(12, 8), pady=10, sticky="w")

        self.value = ctk.CTkLabel(self.frame, text=right_text, font=LABEL_BOLD, text_color=OK_FG)
        self.value.grid(row=0, column=2, padx=(8, 12), pady=10, sticky="e")

        self.bar = ctk.CTkProgressBar(self.frame, fg_color=PILL_BAR_BG, progress_color=OK_FG, height=10)
        self.bar.grid(row=0, column=1, padx=8, pady=10, sticky="ew")
        self.bar.set(0.3)

    def set_value(self, ratio: float, text: str) -> None:
        ratio = _clamp(ratio)
        self.bar.set(ratio)

        # color by severity
        if ratio < 0.6:
            col = OK_FG
        elif ratio < 0.85:
            col = WARN_FG
        else:
            col = BAD_FG
        self.value.configure(text=text, text_color=col)
        self.bar.configure(progress_color=col)


def _mini_row(parent: ctk.CTkFrame, title: str, subtitle: str, color: str) -> None:
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.grid(sticky="ew", pady=4)
    row.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(row, text=title, font=LABEL_BOLD, text_color=TEXT_PRIMARY).grid(
        row=0, column=0, sticky="w"
    )
    if subtitle:
        ctk.CTkLabel(row, text=subtitle, font=LABEL_FONT, text_color=TEXT_MUTED).grid(
            row=1, column=0, sticky="w"
        )

    ctk.CTkLabel(row, text="●", font=LABEL_BOLD, text_color=color).grid(row=0, column=1, rowspan=2, sticky="e")
