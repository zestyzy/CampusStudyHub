from __future__ import annotations

import os
import platform
import shutil
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import List

import customtkinter as ctk

from .models import ConferenceEvent, ExperimentEntry, Task
from .storage import load_conferences, load_experiments, load_papers, load_tasks


class DashboardFrame(ctk.CTkFrame):
    """仪表盘式总览，将任务、会议、实验与资源概览集中展示（不含 GPA）。"""

    def __init__(self, master: ctk.CTkBaseClass) -> None:
        super().__init__(master)
        self.tasks: List[Task] = []
        self.confs: List[ConferenceEvent] = []
        self.experiments: List[ExperimentEntry] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        # 三列两行卡片布局，模仿截图的“仪表盘”分区
        self.grid_columnconfigure((0, 1, 2), weight=1, uniform="col")
        self.grid_rowconfigure((0, 1), weight=1)

        header = ctk.CTkFrame(self, fg_color=("#1e1e1e", "#1e1e1e"))
        header.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="研究与学习总览", font=("PingFang SC", 24, "bold")).grid(
            row=0, column=0, sticky="w", padx=8, pady=8
        )
        ctk.CTkButton(header, text="刷新", width=96, command=self.refresh).grid(
            row=0, column=1, padx=8, pady=8
        )

        # 第一行：任务、科研记录、会议
        self.card_tasks = self._card("任务清单", 0, 0)
        self.card_research = self._card("科研记录", 0, 1)
        self.card_confs = self._card("近期会议", 0, 2)

        # 第二行：实验日志、资源与时钟
        self.card_exps = self._card("实验日志", 1, 0)
        self.card_resources = self._card("资源监控", 1, 1)
        self.card_clock = self._card("时间信息", 1, 2)

        # 任务卡片
        self.card_tasks.grid_rowconfigure(2, weight=1)
        self.tasks_badge = ctk.CTkLabel(
            self.card_tasks, text="加载中…", font=("PingFang SC", 14, "bold"), text_color="#3ea6ff"
        )
        self.tasks_badge.grid(row=1, column=0, sticky="w", padx=8)
        self.tasks_box = ctk.CTkTextbox(self.card_tasks, height=200)
        self.tasks_box.grid(row=2, column=0, sticky="nsew", padx=8, pady=(4, 8))
        self.tasks_box.configure(state="disabled")

        # 科研记录（阅读/实验概览）
        self.card_research.grid_rowconfigure(1, weight=1)
        self.research_box = ctk.CTkTextbox(self.card_research, height=220)
        self.research_box.grid(row=1, column=0, sticky="nsew", padx=8, pady=(4, 8))
        self.research_box.configure(state="disabled")

        # 会议卡片
        self.card_confs.grid_rowconfigure(1, weight=1)
        self.conf_box = ctk.CTkTextbox(self.card_confs, height=220)
        self.conf_box.grid(row=1, column=0, sticky="nsew", padx=8, pady=(4, 8))
        self.conf_box.configure(state="disabled")

        # 实验日志卡片
        self.card_exps.grid_rowconfigure(1, weight=1)
        self.exp_box = ctk.CTkTextbox(self.card_exps, height=220)
        self.exp_box.grid(row=1, column=0, sticky="nsew", padx=8, pady=(4, 8))
        self.exp_box.configure(state="disabled")

        # 资源卡片，改为条形视图
        self.card_resources.grid_rowconfigure((1, 2, 3), weight=1)
        self.cpu_label = ctk.CTkLabel(self.card_resources, text="CPU", font=("PingFang SC", 13, "bold"))
        self.cpu_label.grid(row=1, column=0, sticky="w", padx=8)
        self.cpu_bar = ctk.CTkProgressBar(self.card_resources)
        self.cpu_bar.grid(row=1, column=1, sticky="ew", padx=8)
        self.cpu_value = ctk.CTkLabel(self.card_resources, text="--")
        self.cpu_value.grid(row=1, column=2, padx=6)

        self.gpu_label = ctk.CTkLabel(self.card_resources, text="GPU", font=("PingFang SC", 13, "bold"))
        self.gpu_label.grid(row=2, column=0, sticky="w", padx=8)
        self.gpu_bar = ctk.CTkProgressBar(self.card_resources)
        self.gpu_bar.grid(row=2, column=1, sticky="ew", padx=8)
        self.gpu_value = ctk.CTkLabel(self.card_resources, text="--")
        self.gpu_value.grid(row=2, column=2, padx=6)

        self.disk_label = ctk.CTkLabel(self.card_resources, text="磁盘", font=("PingFang SC", 13, "bold"))
        self.disk_label.grid(row=3, column=0, sticky="w", padx=8)
        self.disk_bar = ctk.CTkProgressBar(self.card_resources)
        self.disk_bar.grid(row=3, column=1, sticky="ew", padx=8)
        self.disk_value = ctk.CTkLabel(self.card_resources, text="--")
        self.disk_value.grid(row=3, column=2, padx=6)
        self.card_resources.grid_columnconfigure(1, weight=1)

        # 时钟卡片
        self.card_clock.grid_rowconfigure((1, 2), weight=1)
        self.clock_label = ctk.CTkLabel(self.card_clock, text="", font=("Consolas", 34, "bold"))
        self.clock_label.grid(row=1, column=0, pady=(18, 6), sticky="n")
        self.clock_detail = ctk.CTkLabel(self.card_clock, text="", font=("PingFang SC", 14))
        self.clock_detail.grid(row=2, column=0, sticky="n")
        self.after(1000, self._update_clock)

    def _card(self, title: str, row: int, column: int) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self, corner_radius=12)
        frame.grid(row=row + 1, column=column, padx=10, pady=8, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        title_row = ctk.CTkFrame(frame, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        title_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(title_row, text=title, font=("PingFang SC", 18, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        badge = ctk.CTkLabel(
            title_row,
            text="概览",
            font=("PingFang SC", 12, "bold"),
            fg_color="#283c53",
            corner_radius=10,
            padx=8,
            pady=4,
        )
        badge.grid(row=0, column=1, sticky="e")
        return frame

    def refresh(self) -> None:
        self.tasks = load_tasks()
        self.confs = load_conferences()
        self.experiments = load_experiments()
        self._render_tasks()
        self._render_research()
        self._render_confs()
        self._render_exps()
        self._render_resources()

    def _render_tasks(self) -> None:
        now = date.today()
        upcoming = []
        overdue = []
        in_week = 0
        for task in sorted(self.tasks, key=lambda t: t.due_date):
            try:
                due = date.fromisoformat(task.due_date)
            except ValueError:
                continue
            days = (due - now).days
            line = f"[{task.status}] {task.title} / {task.course}  截止: {task.due_date} ({days:+d} 天)"
            if days < 0:
                overdue.append(line)
            elif days <= 7:
                upcoming.append(line)
                in_week += 1
        badge_text = f"逾期 {len(overdue)} | 7天内 {in_week}"
        self.tasks_badge.configure(text=badge_text)
        content = "【逾期】\n" + ("\n".join(overdue) or "暂无")
        content += "\n\n【一周内】\n" + ("\n".join(upcoming) or "暂无")
        self._fill_box(self.tasks_box, content)

    def _render_research(self) -> None:
        lines: List[str] = []
        papers = load_papers()
        if papers:
            lines.append("【阅读】")
            for paper in papers[:4]:
                lines.append(f"- {paper.title} [{paper.status}] {paper.doi or ''}")
            if len(papers) > 4:
                lines.append(f"... 共 {len(papers)} 篇文献")
        if not lines:
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
            except ValueError:
                days_text = "日期未知"
            lines.append(f"{conf.name} ({conf.category}) 截止: {conf.submission_deadline} | {days_text}")
        if not lines:
            lines = ["暂无会议数据，可在会议模块导入或刷新"]
        self._fill_box(self.conf_box, "\n".join(lines))

    def _render_exps(self) -> None:
        lines: List[str] = []
        if self.experiments:
            for exp in self.experiments[:6]:
                tail = exp.last_message or exp.metric or ""
                lines.append(f"[{exp.status}] {exp.title} - {exp.project}  {tail}")
            if len(self.experiments) > 6:
                lines.append(f"... 共 {len(self.experiments)} 条实验")
        if not lines:
            lines = ["暂无实验监控，可在科研模块添加日志"]
        self._fill_box(self.exp_box, "\n".join(lines))

    def _render_resources(self) -> None:
        # CPU 近似利用率（用 loadavg 归一化到 CPU 数）
        cpu_count = os.cpu_count() or 1
        if hasattr(os, "getloadavg"):
            try:
                load1, *_ = os.getloadavg()
                cpu_ratio = min(load1 / cpu_count, 1.5)
            except OSError:
                cpu_ratio = 0
        else:
            cpu_ratio = 0
        self.cpu_bar.set(min(cpu_ratio / 1.0, 1.0))
        self.cpu_value.configure(text=f"{cpu_ratio*100:.0f}% (≈)")

        # 磁盘占用
        usage = shutil.disk_usage(Path.home())
        disk_percent = usage.used / usage.total if usage.total else 0
        self.disk_bar.set(disk_percent)
        self.disk_value.configure(
            text=f"{disk_percent*100:.1f}% ({usage.used // (1024**3)}G / {usage.total // (1024**3)}G)"
        )

        # GPU 信息
        gpu_text, gpu_ratio = self._gpu_info()
        self.gpu_bar.set(gpu_ratio)
        self.gpu_value.configure(text=gpu_text)

    def _gpu_info(self) -> tuple[str, float]:
        system = platform.system().lower()
        if system == "darwin":
            # macOS 无 NVIDIA，提示降级
            return "无 NVIDIA (macOS 兼容降级)", 0
        cmds = [["gpustat", "-i"]]
        for cmd in cmds:
            try:
                out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=3)
                # 简单检测利用率字段
                percent = 0.0
                for line in out.splitlines():
                    if "%" in line:
                        try:
                            percent = float(line.split("%", 1)[0].split()[-1]) / 100
                            break
                        except Exception:
                            continue
                return f"{percent*100:.0f}% (gpustat)", min(max(percent, 0.0), 1.0)
            except Exception:
                continue
        return "未检测到 GPU (gpustat/nvidia-smi)", 0

    def _fill_box(self, box: ctk.CTkTextbox, text: str) -> None:
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("end", text)
        box.configure(state="disabled")

    def _score_to_gpa(self, score: float) -> float:
        if score >= 90:
            return 4.0
        if score >= 85:
            return 3.7
        if score >= 80:
            return 3.3
        if score >= 75:
            return 3.0
        if score >= 70:
            return 2.7
        if score >= 67:
            return 2.3
        if score >= 65:
            return 2.0
        if score >= 62:
            return 1.7
        if score >= 60:
            return 1.0
        return 0.0

    def _update_clock(self) -> None:
        now = datetime.now()
        self.clock_label.configure(text=now.strftime("%H:%M:%S"))
        self.clock_detail.configure(text=now.strftime("%Y-%m-%d %A"))
        self.after(1000, self._update_clock)
