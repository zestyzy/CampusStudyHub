"""CustomTkinter 番茄钟，提供沉浸模式、可配置时长与精确倒计时。"""
from __future__ import annotations

import time
from datetime import datetime
from zoneinfo import ZoneInfo

import customtkinter as ctk


class PomodoroFrame(ctk.CTkFrame):
    """包含进度条、沉浸模式、番茄计数与可配置的倒计时。"""

    DEFAULT_FOCUS = 25 * 60
    DEFAULT_BREAK = 5 * 60

    def __init__(self, master: ctk.CTkBaseClass) -> None:
        super().__init__(master)
        self.total = float(self.DEFAULT_FOCUS)
        self.remaining = float(self.DEFAULT_FOCUS)
        self.mode_focus = True
        self.running = False
        self.session_count = 0
        self.after_id: str | None = None
        self.last_tick = time.monotonic()

        self._build_ui()
        self._update_labels()
        self._update_clock()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        title_row = ctk.CTkFrame(self, fg_color="transparent")
        title_row.grid(row=0, column=0, pady=(12, 6), sticky="ew")
        title_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(title_row, text="番茄钟", font=("PingFang SC", 28, "bold")).grid(row=0, column=0, padx=4)
        self.mode_badge = ctk.CTkLabel(
            title_row, text="模式：专注", fg_color="#1f6aa5", text_color="white", corner_radius=12, padx=12
        )
        self.mode_badge.grid(row=0, column=1, sticky="e", padx=6)

        self.timer_label = ctk.CTkLabel(self, text="25:00", font=("Menlo", 52, "bold"))
        self.timer_label.grid(row=1, column=0, pady=6)

        self.progress = ctk.CTkProgressBar(self, width=520)
        self.progress.set(0)
        self.progress.grid(row=2, column=0, pady=4, padx=20)

        self.session_counter = ctk.CTkLabel(self, text="今日专注：0 个番茄", font=("PingFang SC", 14))
        self.session_counter.grid(row=3, column=0, pady=2)

        self.beijing_label = ctk.CTkLabel(self, text="北京时间：--:--:--", font=("Menlo", 14))
        self.beijing_label.grid(row=4, column=0, pady=2)

        control_row = ctk.CTkFrame(self, fg_color="transparent")
        control_row.grid(row=5, column=0, pady=8)
        ctk.CTkButton(control_row, text="开始", command=self.start, width=100).grid(row=0, column=0, padx=6)
        ctk.CTkButton(control_row, text="暂停", command=self.pause, width=100).grid(row=0, column=1, padx=6)
        ctk.CTkButton(control_row, text="重置", command=self.reset, width=100).grid(row=0, column=2, padx=6)

        config_row = ctk.CTkFrame(self, corner_radius=12)
        config_row.grid(row=6, column=0, pady=8, padx=10, sticky="ew")
        config_row.grid_columnconfigure(3, weight=1)
        ctk.CTkLabel(config_row, text="专注(分钟)").grid(row=0, column=0, padx=4, pady=6)
        self.focus_entry = ctk.CTkEntry(config_row, width=70)
        self.focus_entry.insert(0, "25")
        self.focus_entry.grid(row=0, column=1, padx=4)
        ctk.CTkLabel(config_row, text="休息(分钟)").grid(row=0, column=2, padx=4)
        self.break_entry = ctk.CTkEntry(config_row, width=70)
        self.break_entry.insert(0, "5")
        self.break_entry.grid(row=0, column=3, padx=4, sticky="w")
        ctk.CTkLabel(config_row, text="自定义秒数").grid(row=1, column=0, padx=4, pady=6)
        self.custom_seconds = ctk.CTkEntry(config_row, width=120)
        self.custom_seconds.insert(0, "0")
        self.custom_seconds.grid(row=1, column=1, padx=4)
        ctk.CTkButton(config_row, text="应用时长", command=self._apply_durations, width=120).grid(row=1, column=2, padx=6)

        focus_row = ctk.CTkFrame(self, fg_color="transparent")
        focus_row.grid(row=7, column=0, pady=8)
        self.focus_switch = ctk.CTkSwitch(focus_row, text="沉浸模式（静音/禁通知）", command=self._toggle_focus_mode)
        self.focus_switch.grid(row=0, column=0, padx=6)
        self.dnd_label = ctk.CTkLabel(
            focus_row, text="已开启请勿打扰", fg_color="#1f6aa5", text_color="white", corner_radius=10, padx=10
        )
        self.dnd_label.grid(row=0, column=1, padx=8)
        self.dnd_label.grid_remove()

        detail_row = ctk.CTkFrame(self, fg_color="transparent")
        detail_row.grid(row=8, column=0, pady=(4, 10))
        self.detail_label = ctk.CTkLabel(detail_row, text="剩余：0 秒", font=("PingFang SC", 12))
        self.detail_label.grid(row=0, column=0, padx=6)

    def _toggle_focus_mode(self) -> None:
        if self.focus_switch.get():
            self.dnd_label.grid()
        else:
            self.dnd_label.grid_remove()

    def _apply_durations(self) -> None:
        try:
            focus_minutes = float(self.focus_entry.get() or 25)
            break_minutes = float(self.break_entry.get() or 5)
            custom_secs = float(self.custom_seconds.get() or 0)
        except ValueError:
            return
        self.DEFAULT_FOCUS = max(int(focus_minutes * 60), 1)
        self.DEFAULT_BREAK = max(int(break_minutes * 60), 1)
        if custom_secs > 0:
            self.total = custom_secs
            self.remaining = custom_secs
        else:
            self.total = float(self.DEFAULT_FOCUS if self.mode_focus else self.DEFAULT_BREAK)
            self.remaining = self.total
        self._update_labels()

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.last_tick = time.monotonic()
        self._tick()

    def pause(self) -> None:
        self.running = False
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None

    def reset(self) -> None:
        self.pause()
        self.mode_focus = True
        self.total = float(self.DEFAULT_FOCUS)
        self.remaining = float(self.DEFAULT_FOCUS)
        self._update_labels()
        self.progress.set(0)

    def _tick(self) -> None:
        if not self.running:
            return
        now = time.monotonic()
        delta = now - self.last_tick
        self.last_tick = now
        self.remaining -= delta
        if self.remaining <= 0:
            if not self.focus_switch.get():
                print("Ding!")
                self.bell()
            if self.mode_focus:
                self.session_count += 1
            self._switch_mode()
        self._update_labels()
        self.after_id = self.after(200, self._tick)

    def _switch_mode(self) -> None:
        self.mode_focus = not self.mode_focus
        self.total = float(self.DEFAULT_FOCUS if self.mode_focus else self.DEFAULT_BREAK)
        self.remaining = self.total
        self.running = False
        self._update_labels()

    def _update_clock(self) -> None:
        beijing = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%H:%M:%S")
        self.beijing_label.configure(text=f"北京时间：{beijing}")
        self.after(1000, self._update_clock)

    def _update_labels(self) -> None:
        remaining = max(self.remaining, 0)
        hours, rem = divmod(int(remaining), 3600)
        mins, secs = divmod(rem, 60)
        self.timer_label.configure(text=f"{hours:02d}:{mins:02d}:{secs:02d}")
        self.mode_badge.configure(text="模式：专注" if self.mode_focus else "模式：休息")
        progress = 1 - (remaining / self.total) if self.total else 0
        self.progress.set(max(0.0, min(1.0, progress)))
        self.session_counter.configure(text=f"今日专注：{self.session_count} 个番茄")
        self.detail_label.configure(text=f"剩余：{remaining:.1f} 秒 | 总时长：{self.total:.1f} 秒")

