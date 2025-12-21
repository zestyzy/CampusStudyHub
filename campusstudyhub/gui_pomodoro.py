"""Pomodoro timer widget using Tkinter after loop."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

FOCUS_SECONDS = 25 * 60
BREAK_SECONDS = 5 * 60


class PomodoroTimer(tk.Frame):
    """A simple Pomodoro timer with focus/break cycles."""

    def __init__(self, master: tk.Misc):
        super().__init__(master)
        self.remaining = FOCUS_SECONDS
        self.mode = "focus"  # "focus" or "break"
        self._after_id: str | None = None
        self._build_ui()
        self._update_labels()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.timer_var = tk.StringVar()
        self.status_var = tk.StringVar()

        tk.Label(self, textvariable=self.timer_var, font=("Helvetica", 48)).grid(
            row=0, column=0, pady=(20, 10), padx=20
        )
        tk.Label(self, textvariable=self.status_var, font=("Helvetica", 16)).grid(
            row=1, column=0, pady=5
        )

        btn_frame = tk.Frame(self)
        btn_frame.grid(row=2, column=0, pady=10)
        tk.Button(btn_frame, text="开始", command=self.start).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="暂停", command=self.pause).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="重置", command=self.reset).pack(side=tk.LEFT, padx=5)

    def start(self) -> None:
        """Start or resume the timer."""
        if self._after_id:
            return
        self._tick()

    def pause(self) -> None:
        """Pause the countdown."""
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

    def reset(self) -> None:
        """Reset to focus period."""
        self.pause()
        self.mode = "focus"
        self.remaining = FOCUS_SECONDS
        self._update_labels()

    def _tick(self) -> None:
        self._update_labels()
        if self.remaining <= 0:
            self._finish_cycle()
            return
        self.remaining -= 1
        self._after_id = self.after(1000, self._tick)

    def _finish_cycle(self) -> None:
        self._after_id = None
        self.bell()  # system beep
        if self.mode == "focus":
            if messagebox.askyesno("时间到", "专注结束，开始休息？"):
                self.mode = "break"
                self.remaining = BREAK_SECONDS
                self.start()
        else:
            messagebox.showinfo("时间到", "休息结束，重新开始专注！")
            self.mode = "focus"
            self.remaining = FOCUS_SECONDS
            self.start()
        self._update_labels()

    def _update_labels(self) -> None:
        minutes, seconds = divmod(self.remaining, 60)
        self.timer_var.set(f"{int(minutes):02d}:{int(seconds):02d}")
        self.status_var.set("专注时间" if self.mode == "focus" else "休息时间")
