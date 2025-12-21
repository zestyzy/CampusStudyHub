"""番茄钟（CustomTkinter 版本）。"""
from __future__ import annotations

import customtkinter as ctk


class PomodoroFrame(ctk.CTkFrame):
    """包含进度条、专注/休息状态机以及沉浸模式的番茄钟。"""

    FOCUS_SECONDS = 25 * 60
    BREAK_SECONDS = 5 * 60

    def __init__(self, master: ctk.CTkBaseClass) -> None:
        super().__init__(master)
        self.remaining = self.FOCUS_SECONDS
        self.total = self.FOCUS_SECONDS
        self.mode_focus = True
        self.running = False
        self.session_count = 0
        self.after_id: str | None = None

        self._build_ui()
        self._update_labels()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(self, text="番茄钟", font=("PingFang SC", 28, "bold"))
        self.title_label.grid(row=0, column=0, pady=(10, 6))

        self.status_label = ctk.CTkLabel(self, text="模式：专注", font=("PingFang SC", 16))
        self.status_label.grid(row=1, column=0, pady=4)

        self.timer_label = ctk.CTkLabel(
            self,
            text="25:00",
            font=("Menlo", 48, "bold"),
        )
        self.timer_label.grid(row=2, column=0, pady=10)

        self.progress = ctk.CTkProgressBar(self, width=400)
        self.progress.set(0)
        self.progress.grid(row=3, column=0, pady=6, padx=20)

        self.session_counter = ctk.CTkLabel(self, text="今日专注：0 个番茄", font=("PingFang SC", 14))
        self.session_counter.grid(row=4, column=0, pady=4)

        button_row = ctk.CTkFrame(self)
        button_row.grid(row=5, column=0, pady=8)
        start_btn = ctk.CTkButton(button_row, text="开始", command=self.start)
        pause_btn = ctk.CTkButton(button_row, text="暂停", command=self.pause)
        reset_btn = ctk.CTkButton(button_row, text="重置", command=self.reset)
        start_btn.grid(row=0, column=0, padx=6)
        pause_btn.grid(row=0, column=1, padx=6)
        reset_btn.grid(row=0, column=2, padx=6)

        focus_row = ctk.CTkFrame(self)
        focus_row.grid(row=6, column=0, pady=(4, 12))
        self.focus_switch = ctk.CTkSwitch(focus_row, text="沉浸模式", command=self._toggle_focus_mode)
        self.focus_switch.grid(row=0, column=0, padx=6)
        self.dnd_label = ctk.CTkLabel(focus_row, text="请勿打扰", fg_color="#1f6aa5", text_color="white", corner_radius=8)
        self.dnd_label.grid(row=0, column=1, padx=6)
        self.dnd_label.grid_remove()

    def _toggle_focus_mode(self) -> None:
        if self.focus_switch.get():
            self.dnd_label.grid()
        else:
            self.dnd_label.grid_remove()

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._tick()

    def pause(self) -> None:
        self.running = False
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None

    def reset(self) -> None:
        self.pause()
        self.mode_focus = True
        self.remaining = self.FOCUS_SECONDS
        self.total = self.FOCUS_SECONDS
        self._update_labels()
        self.progress.set(0)

    def _tick(self) -> None:
        if not self.running:
            return
        self.remaining -= 1
        if self.remaining <= 0:
            print("Ding!")
            if self.mode_focus:
                self.session_count += 1
            self._switch_mode()
        self._update_labels()
        self.after_id = self.after(1000, self._tick)

    def _switch_mode(self) -> None:
        self.mode_focus = not self.mode_focus
        self.total = self.FOCUS_SECONDS if self.mode_focus else self.BREAK_SECONDS
        self.remaining = self.total
        self.running = False
        self._update_labels()

    def _update_labels(self) -> None:
        mins, secs = divmod(max(self.remaining, 0), 60)
        self.timer_label.configure(text=f"{mins:02d}:{secs:02d}")
        self.status_label.configure(text="模式：专注" if self.mode_focus else "模式：休息")
        progress = 1 - (self.remaining / self.total)
        self.progress.set(progress)
        self.session_counter.configure(text=f"今日专注：{self.session_count} 个番茄")

