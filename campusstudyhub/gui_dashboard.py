from __future__ import annotations

import os
import platform
import shutil
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import List

import customtkinter as ctk

from .models import ConferenceEvent, ExperimentEntry, GradeEntry, Task
from .storage import (
    load_conferences,
    load_experiments,
    load_grades,
    load_papers,
    load_tasks,
)


class DashboardFrame(ctk.CTkFrame):
    """仪表盘式总览，将任务、会议、实验与 GPA 摘要集中在一屏显示。"""

    def __init__(self, master: ctk.CTkBaseClass) -> None:
        super().__init__(master)
        self.tasks: List[Task] = []
        self.confs: List[ConferenceEvent] = []
        self.experiments: List[ExperimentEntry] = []
        self.grades: List[GradeEntry] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        self.grid_columnconfigure((0, 1, 2), weight=1, uniform="col")
        self.grid_rowconfigure((0, 1), weight=1)

        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="研究与学习总览", font=("PingFang SC", 24, "bold")).grid(
            row=0, column=0, sticky="w", padx=4, pady=6
        )
        ctk.CTkButton(header, text="刷新", width=80, command=self.refresh).grid(row=0, column=1, padx=4)

        self.card_tasks = self._card("任务概览", 0, 0)
        self.card_gpa = self._card("GPA 摘要", 0, 1)
        self.card_research = self._card("科研记录", 0, 2)
        self.card_confs = self._card("近期会议", 1, 0)
        self.card_resources = self._card("资源监控", 1, 1)
        self.card_clock = self._card("时间信息", 1, 2)

        self.card_tasks.grid_rowconfigure(1, weight=1)
        self.tasks_box = ctk.CTkTextbox(self.card_tasks, height=180)
        self.tasks_box.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        self.tasks_box.configure(state="disabled")

        self.card_gpa.grid_rowconfigure(2, weight=1)
        self.gpa_label = ctk.CTkLabel(
            self.card_gpa, text="加载中…", font=("PingFang SC", 16, "bold")
        )
        self.gpa_label.grid(row=1, column=0, sticky="w", padx=6, pady=(2, 0))
        self.gpa_table = ctk.CTkTextbox(self.card_gpa, height=160)
        self.gpa_table.grid(row=2, column=0, sticky="nsew", padx=6, pady=6)
        self.gpa_table.configure(state="disabled")

        self.card_research.grid_rowconfigure(1, weight=1)
        self.research_box = ctk.CTkTextbox(self.card_research, height=200)
        self.research_box.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        self.research_box.configure(state="disabled")

        self.card_confs.grid_rowconfigure(1, weight=1)
        self.conf_box = ctk.CTkTextbox(self.card_confs, height=200)
        self.conf_box.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        self.conf_box.configure(state="disabled")

        self.card_resources.grid_rowconfigure(1, weight=1)
        self.resource_box = ctk.CTkTextbox(self.card_resources, height=200)
        self.resource_box.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        self.resource_box.configure(state="disabled")

        self.card_clock.grid_rowconfigure((1, 2), weight=1)
        self.clock_label = ctk.CTkLabel(
            self.card_clock, text="", font=("Consolas", 32, "bold")
        )
        self.clock_label.grid(row=1, column=0, pady=(12, 4), sticky="n")
        self.clock_detail = ctk.CTkLabel(
            self.card_clock, text="", font=("PingFang SC", 14)
        )
        self.clock_detail.grid(row=2, column=0, sticky="n")
        self.after(1000, self._update_clock)

    def _card(self, title: str, row: int, column: int) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self, corner_radius=12)
        frame.grid(row=row + 1, column=column, padx=8, pady=8, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text=title, font=("PingFang SC", 18, "bold")).grid(
            row=0, column=0, sticky="w", padx=6, pady=6
        )
        return frame

    def refresh(self) -> None:
        self.tasks = load_tasks()
        self.confs = load_conferences()
        self.experiments = load_experiments()
        self.grades = load_grades()
        self._render_tasks()
        self._render_gpa()
        self._render_research()
        self._render_confs()
        self._render_resources()

    def _render_tasks(self) -> None:
        now = date.today()
        upcoming = []
        overdue = []
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
        self._fill_box(self.tasks_box, "【逾期】\n" + "\n".join(overdue) + "\n\n【一周内】\n" + "\n".join(upcoming))

    def _render_gpa(self) -> None:
        entries = self.grades
        if not entries:
            self.gpa_label.configure(text="暂无成绩数据")
            self._fill_box(self.gpa_table, "请在 GPA 工具中录入课程成绩")
            return
        total_credits = sum(e.credit for e in entries)
        weighted = sum(e.credit * e.score for e in entries) / total_credits if total_credits else 0
        gpa_overall = sum(e.credit * self._score_to_gpa(e.score) for e in entries) / total_credits if total_credits else 0
        major = [e for e in entries if getattr(e, "type", "必修") == "必修"]
        if major:
            major_credit = sum(e.credit for e in major)
            gpa_major = sum(e.credit * self._score_to_gpa(e.score) for e in major) / major_credit
        else:
            gpa_major = 0
        self.gpa_label.configure(
            text=f"总学分: {total_credits:.1f}  平均分: {weighted:.2f}  GPA: {gpa_overall:.2f}  专业GPA: {gpa_major:.2f}"
        )
        lines = ["课程\t学分\t成绩"]
        for e in entries[:10]:
            lines.append(f"{e.course}\t{e.credit}\t{e.score}")
        if len(entries) > 10:
            lines.append(f"... 共 {len(entries)} 条")
        self._fill_box(self.gpa_table, "\n".join(lines))

    def _render_research(self) -> None:
        lines: List[str] = []
        if self.experiments:
            lines.append("【实验】")
            for exp in self.experiments[:5]:
                lines.append(f"- {exp.title} ({exp.project}) — {exp.status} | {exp.metric or '指标未知'}")
            if len(self.experiments) > 5:
                lines.append(f"... 共 {len(self.experiments)} 条实验")
        papers = load_papers()
        if papers:
            lines.append("\n【阅读】")
            for paper in papers[:5]:
                lines.append(f"- {paper.title} [{paper.status}] {paper.doi or ''}")
            if len(papers) > 5:
                lines.append(f"... 共 {len(papers)} 篇文献")
        if not lines:
            lines = ["暂无科研记录，可在科研模块添加实验或阅读清单"]
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

    def _render_resources(self) -> None:
        texts: List[str] = []
        # CPU load (basic近似)
        if hasattr(os, "getloadavg"):
            try:
                load1, load5, load15 = os.getloadavg()
                texts.append(f"CPU 负载: {load1:.2f} / {load5:.2f} / {load15:.2f}")
            except OSError:
                pass
        # Disk usage
        usage = shutil.disk_usage(Path.home())
        disk_percent = usage.used / usage.total * 100
        texts.append(f"磁盘占用: {disk_percent:.1f}% ({usage.used // (1024**3)}G / {usage.total // (1024**3)}G)")
        # GPU info
        gpu_text = self._gpu_info()
        texts.append(gpu_text)
        self._fill_box(self.resource_box, "\n".join(texts))

    def _gpu_info(self) -> str:
        system = platform.system().lower()
        if system == "darwin":
            return "GPU: 未检测到 NVIDIA，尝试使用 system_profiler/powermetrics 观测"
        cmds = [["gpustat", "-i"]]
        for cmd in cmds:
            try:
                out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=3)
                return out.strip()
            except Exception:
                continue
        return "GPU: 未检测到可用的 gpustat/nvidia-smi"

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
