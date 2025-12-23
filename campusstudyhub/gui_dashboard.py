from __future__ import annotations

import os
import platform
import shutil
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

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


class DashboardFrame(ctk.CTkFrame):
    """仪表盘式总览，将任务、会议、实验与资源概览集中展示（不含 GPA）。"""

    def __init__(self, master: ctk.CTkBaseClass, navigator: Optional[Dict[str, Callable[[], None]]] = None) -> None:
        super().__init__(master, fg_color=BG_DARK)
        self.navigator = navigator or {}
        self.tasks: List[Task] = []
        self.confs: List[ConferenceEvent] = []
        self.experiments: List[ExperimentEntry] = []
        self.monitors = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        self.grid_columnconfigure((0, 1, 2), weight=1, uniform="col")
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure((1, 2), weight=1)

        header = ctk.CTkFrame(self, fg_color=BG_DARK)
        header.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0, minsize=190)
        ctk.CTkLabel(header, text="研究与学习总览", font=HEADER_FONT, text_color=TEXT_PRIMARY).grid(
            row=0, column=0, sticky="w", padx=6, pady=6
        )
        ctk.CTkButton(
            header,
            text="刷新",
            width=170,
            height=38,
            fg_color=ACCENT,
            hover_color=ACCENT_ALT,
            font=BADGE_FONT,
            command=self.refresh,
        ).grid(row=0, column=1, padx=8, pady=6, sticky="e")

        # 第一行：任务、科研记录、会议
        self.card_tasks = self._card("任务清单", 1, 0, "tasks")
        self.card_research = self._card("科研记录", 1, 1, "research")
        self.card_confs = self._card("近期会议", 1, 2, "conferences")

        # 第二行：实验日志、资源与时钟
        self.card_exps = self._card("实验日志", 2, 0, "experiments")
        self.card_resources = self._card("资源监控", 2, 1, "monitor")
        self.card_clock = self._card("时间信息", 2, 2, "clock")

        # 任务卡片
        self.card_tasks.grid_rowconfigure(2, weight=1)
        self.tasks_badge = ctk.CTkLabel(
            self.card_tasks, text="加载中…", font=LABEL_BOLD, text_color=ACCENT_ALT
        )
        self.tasks_badge.grid(row=1, column=0, sticky="w", padx=CARD_PAD_X, pady=(0, 4))
        self.tasks_box = ctk.CTkTextbox(
            self.card_tasks,
            height=200,
            fg_color=BG_CARD,
            border_width=0,
            font=MONO_FONT,
            text_color=TEXT_PRIMARY,
        )
        self.tasks_box.grid(row=2, column=0, sticky="nsew", padx=CARD_PAD_X, pady=(0, CARD_PAD_Y))
        self.tasks_box.configure(state="disabled")

        # 科研记录
        self.card_research.grid_rowconfigure(1, weight=1)
        self.research_box = ctk.CTkTextbox(
            self.card_research,
            height=220,
            fg_color=BG_CARD,
            border_width=0,
            font=LABEL_FONT,
            text_color=TEXT_PRIMARY,
        )
        self.research_box.grid(row=1, column=0, sticky="nsew", padx=CARD_PAD_X, pady=(0, CARD_PAD_Y))
        self.research_box.configure(state="disabled")

        # 会议卡片
        self.card_confs.grid_rowconfigure(1, weight=1)
        self.conf_box = ctk.CTkTextbox(
            self.card_confs,
            height=220,
            fg_color=BG_CARD,
            border_width=0,
            font=LABEL_FONT,
            text_color=TEXT_PRIMARY,
        )
        self.conf_box.grid(row=1, column=0, sticky="nsew", padx=CARD_PAD_X, pady=(0, CARD_PAD_Y))
        self.conf_box.configure(state="disabled")

        # 实验日志卡片
        self.card_exps.grid_rowconfigure(1, weight=1)
        self.exp_box = ctk.CTkTextbox(
            self.card_exps,
            height=220,
            fg_color=BG_CARD,
            border_width=0,
            font=MONO_FONT,
            text_color=TEXT_PRIMARY,
        )
        self.exp_box.grid(row=1, column=0, sticky="nsew", padx=CARD_PAD_X, pady=(0, CARD_PAD_Y))
        self.exp_box.configure(state="disabled")

        # 资源卡片
        for r in range(3):
            self.card_resources.grid_rowconfigure(r + 1, weight=1)
        self.card_resources.grid_columnconfigure(1, weight=1)
        self.cpu_label = ctk.CTkLabel(self.card_resources, text="CPU", font=LABEL_BOLD, text_color=TEXT_PRIMARY)
        self.cpu_value = ctk.CTkLabel(self.card_resources, text="--", font=LABEL_FONT, text_color=TEXT_MUTED)
        self.cpu_bar = ctk.CTkProgressBar(self.card_resources, fg_color="#0d1826", progress_color=ACCENT)
        self.gpu_label = ctk.CTkLabel(self.card_resources, text="GPU", font=LABEL_BOLD, text_color=TEXT_PRIMARY)
        self.gpu_value = ctk.CTkLabel(self.card_resources, text="--", font=LABEL_FONT, text_color=TEXT_MUTED)
        self.gpu_bar = ctk.CTkProgressBar(self.card_resources, fg_color="#0d1826", progress_color=ACCENT)
        self.disk_label = ctk.CTkLabel(self.card_resources, text="磁盘", font=LABEL_BOLD, text_color=TEXT_PRIMARY)
        self.disk_value = ctk.CTkLabel(self.card_resources, text="--", font=LABEL_FONT, text_color=TEXT_MUTED)
        self.disk_bar = ctk.CTkProgressBar(self.card_resources, fg_color="#0d1826", progress_color=ACCENT)

        self.cpu_label.grid(row=1, column=0, sticky="w", padx=CARD_PAD_X, pady=4)
        self.cpu_bar.grid(row=1, column=1, sticky="ew", padx=6, pady=4)
        self.cpu_value.grid(row=1, column=2, sticky="e", padx=CARD_PAD_X, pady=4)

        self.gpu_label.grid(row=2, column=0, sticky="w", padx=CARD_PAD_X, pady=4)
        self.gpu_bar.grid(row=2, column=1, sticky="ew", padx=6, pady=4)
        self.gpu_value.grid(row=2, column=2, sticky="e", padx=CARD_PAD_X, pady=4)

        self.disk_label.grid(row=3, column=0, sticky="w", padx=CARD_PAD_X, pady=4)
        self.disk_bar.grid(row=3, column=1, sticky="ew", padx=6, pady=4)
        self.disk_value.grid(row=3, column=2, sticky="e", padx=CARD_PAD_X, pady=4)

        # 时钟卡片
        self.card_clock.grid_rowconfigure((1, 2), weight=1)
        self.clock_label = ctk.CTkLabel(
            self.card_clock, text="", font=CLOCK_FONT, text_color=TEXT_PRIMARY
        )
        self.clock_label.grid(row=1, column=0, pady=(18, 6), sticky="n")
        self.clock_detail = ctk.CTkLabel(self.card_clock, text="", font=DATE_FONT, text_color=TEXT_MUTED)
        self.clock_detail.grid(row=2, column=0, sticky="n")
        self.after(1000, self._update_clock)

    def _card(self, title: str, row: int, column: int, nav_key: str) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self, **card_kwargs())
        frame.grid(row=row, column=column, padx=12, pady=8, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1, minsize=220)

        title_row = ctk.CTkFrame(frame, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="ew", padx=CARD_PAD_X, pady=(CARD_PAD_Y, 6))
        title_row.grid_columnconfigure(0, weight=1)
        title_row.grid_columnconfigure(1, weight=0, minsize=180)
        ctk.CTkLabel(title_row, text=title, font=LABEL_BOLD, text_color=TEXT_PRIMARY).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkButton(
            title_row,
            text="打开",
            width=160,
            height=36,
            command=lambda key=nav_key: self._navigate(key),
            fg_color=ACCENT,
            hover_color=ACCENT_ALT,
            font=BADGE_FONT,
            corner_radius=12,
        ).grid(row=0, column=1, sticky="e", padx=4)

        # Placeholder content row will be added by caller
        return frame

    def _navigate(self, key: str) -> None:
        cb = self.navigator.get(key)
        if cb:
            cb()

    def refresh(self) -> None:
        self.tasks = load_tasks()
        self.confs = load_conferences()
        self.experiments = load_experiments()
        self.monitors = load_log_monitors()
        self._render_tasks()
        self._render_research()
        self._render_confs()
        self._render_exps()
        self._render_resources()

    def _render_tasks(self) -> None:
        now = date.today()
        upcoming: List[str] = []
        overdue: List[str] = []
        in_week = 0
        status_map = {"todo": "待办", "in_progress": "进行中", "done": "已完成"}
        priority_map = {"low": "低", "medium": "中", "high": "高"}
        for task in sorted(self.tasks, key=lambda t: t.due_date):
            try:
                due = date.fromisoformat(task.due_date)
            except ValueError:
                continue
            days = (due - now).days
            status_text = status_map.get(task.status, task.status)
            priority_text = priority_map.get(task.priority, task.priority)
            line = (
                f"[{status_text}|优先级:{priority_text}] {task.title} / {task.course}  "
                f"截止: {task.due_date} ({days:+d} 天)"
            )
            if days < 0:
                overdue.append(line)
            elif days <= 7:
                upcoming.append(line)
                in_week += 1
        badge_text = f"逾期 {len(overdue)} | 7天内 {in_week}"
        self.tasks_badge.configure(text=badge_text, text_color=ACCENT_ALT if overdue or in_week else TEXT_MUTED)
        content = "【逾期】\n" + ("\n".join(overdue) or "暂无逾期任务")
        content += "\n\n【一周内】\n" + ("\n".join(upcoming) or "暂无即将到期任务")
        self._fill_box(self.tasks_box, content)

    def _render_research(self) -> None:
        lines: List[str] = []
        papers = load_papers()
        if papers:
            lines.append("【阅读】")
            for paper in papers[:6]:
                tag_map = {
                    "to_read": "待阅读",
                    "reading": "阅读中",
                    "done": "已完成",
                }
                tag = f"[{tag_map.get(paper.status, paper.status)}]" if paper.status else ""
                lines.append(f"- {paper.title} {tag} {paper.doi or ''}")
            if len(papers) > 6:
                lines.append(f"... 共 {len(papers)} 篇文献")
        else:
            lines.append("暂无阅读记录，可在科研模块添加文献")
        self._fill_box(self.research_box, "\n".join(lines))

    def _render_confs(self) -> None:
        now = date.today()
        sorted_confs = sorted(self.confs, key=lambda c: c.submission_deadline)
        lines = []
        for conf in sorted_confs[:6]:
            try:
                due = date.fromisoformat(conf.submission_deadline)
                delta = (due - now).days
                days_text = f"{delta} 天后" if delta >= 0 else "已过期"
                color = TEXT_WARN if 0 <= delta <= 14 else (TEXT_ERROR if delta < 0 else TEXT_PRIMARY)
            except ValueError:
                days_text = "日期未知"
                color = TEXT_MUTED
            line = f"{conf.name} ({conf.category}) 截止: {conf.submission_deadline} | {days_text}"
            lines.append((line, color))
        if not lines:
            lines = [("暂无会议数据，可在会议模块导入或刷新", TEXT_MUTED)]
        self._fill_box_with_colors(self.conf_box, lines)

    def _render_exps(self) -> None:
        lines: List[str] = []
        monitors = self.monitors or []
        if monitors:
            lines.append(f"正在监控: {len(monitors)} 个日志")
        if self.experiments:
            status_map = {
                "planned": "计划中",
                "running": "运行中",
                "done": "完成",
                "failed": "失败",
            }
            for exp in self.experiments[:4]:
                tail = exp.last_message or exp.metric or ""
                lines.append(
                    f"[{status_map.get(exp.status, exp.status)}] {exp.title} - {exp.project}  {tail}"
                )
            if len(self.experiments) > 4:
                lines.append(f"... 共 {len(self.experiments)} 条实验")
        elif not monitors:
            lines.append("暂无实验监控，可在科研模块添加日志")
        self._fill_box(self.exp_box, "\n".join(lines))

    def _render_resources(self) -> None:
        cpu_ratio = 0.0
        cpu_count = os.cpu_count() or 1
        if hasattr(os, "getloadavg"):
            try:
                load1, *_ = os.getloadavg()
                cpu_ratio = min(max(load1 / cpu_count, 0.0), 1.5)
            except OSError:
                cpu_ratio = 0.0
        self.cpu_bar.set(min(cpu_ratio, 1.0))
        self.cpu_value.configure(text=f"{cpu_ratio*100:.0f}% (≈)", text_color=TEXT_PRIMARY)

        usage = shutil.disk_usage(Path.home())
        disk_percent = usage.used / usage.total if usage.total else 0
        self.disk_bar.set(min(disk_percent, 1.0))
        self.disk_value.configure(
            text=f"{disk_percent*100:.1f}% ({usage.used // (1024**3)}G / {usage.total // (1024**3)}G)",
            text_color=TEXT_PRIMARY,
        )

        gpu_text, gpu_ratio, gpu_color = self._gpu_info()
        self.gpu_bar.set(min(gpu_ratio, 1.0))
        self.gpu_value.configure(text=gpu_text, text_color=gpu_color)

    def _gpu_info(self) -> tuple[str, float, str]:
        system = platform.system().lower()
        if system == "darwin":
            return "无 NVIDIA (macOS 兼容降级)", 0.0, TEXT_MUTED
        cmds = [["gpustat", "-i"]]
        for cmd in cmds:
            try:
                out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=3)
                percent = 0.0
                for line in out.splitlines():
                    if "%" in line:
                        try:
                            percent = float(line.split("%", 1)[0].split()[-1]) / 100
                            break
                        except Exception:
                            continue
                return f"{percent*100:.0f}% (gpustat)", min(max(percent, 0.0), 1.0), TEXT_PRIMARY
            except Exception:
                continue
        return "未检测到 GPU (gpustat/nvidia-smi)", 0.0, TEXT_MUTED

    def _fill_box(self, box: ctk.CTkTextbox, text: str) -> None:
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("end", text)
        box.configure(state="disabled")

    def _fill_box_with_colors(self, box: ctk.CTkTextbox, lines: List[tuple[str, str]]) -> None:
        box.configure(state="normal")
        box.delete("1.0", "end")
        for idx, (text, color) in enumerate(lines):
            box.insert("end", text + "\n")
            tag = f"line_color_{idx}"
            box.tag_add(tag, "end-1l linestart", "end-1l lineend")
            box.tag_config(tag, foreground=color)
        box.configure(state="disabled")

    def _update_clock(self) -> None:
        now = datetime.now()
        weekday_map = {
            0: "星期一",
            1: "星期二",
            2: "星期三",
            3: "星期四",
            4: "星期五",
            5: "星期六",
            6: "星期日",
        }
        self.clock_label.configure(text=now.strftime("%H:%M:%S"))
        self.clock_detail.configure(
            text=f"{now.strftime('%Y-%m-%d')} {weekday_map.get(now.weekday(), '')}"
        )
        self.after(1000, self._update_clock)
