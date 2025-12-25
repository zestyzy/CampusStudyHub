"""Stats tab for CampusStudyHub (CustomTkinter Version)."""
from __future__ import annotations

import customtkinter as ctk
from collections import Counter
from datetime import date, timedelta
from typing import Callable, List, Dict

# 复用你项目中的样式配置
from .ui_style import (
    BG_CARD, 
    HEADER_FONT, 
    LABEL_BOLD, 
    TEXT_PRIMARY, 
    TEXT_MUTED, 
    card_kwargs
)
from .models import Task

class StatsFrame(ctk.CTkFrame):
    """Display statistics about tasks with modern UI."""

    def __init__(self, master: ctk.CTkBaseClass, tasks_provider: Callable[[], List[Task]]) -> None:
        super().__init__(master, fg_color="transparent") # 透明背景，融入主界面
        self.tasks_provider = tasks_provider

        # 1. 顶部：核心指标卡片 (Total / Done / Rate)
        self.kpi_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.kpi_frame.pack(fill="x", pady=(0, 15))
        
        self.card_total = self._create_kpi_card(self.kpi_frame, "总任务", "0", 0)
        self.card_done = self._create_kpi_card(self.kpi_frame, "已完成", "0", 1)
        self.card_rate = self._create_kpi_card(self.kpi_frame, "完成率", "0%", 2)

        # 2. 进度条区域
        self.progress_frame = ctk.CTkFrame(self, **card_kwargs())
        self.progress_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(self.progress_frame, text="总体进度", font=LABEL_BOLD, text_color=TEXT_PRIMARY).pack(anchor="w", padx=15, pady=(10, 5))
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, height=12, corner_radius=6)
        self.progress_bar.pack(fill="x", padx=15, pady=(0, 15))
        self.progress_bar.set(0)

        # 3. 详细统计区域 (改为左右分栏或上下排列)
        self.details_frame = ctk.CTkFrame(self, **card_kwargs())
        self.details_frame.pack(fill="both", expand=True)
        
        # 3a. 状态分布
        ctk.CTkLabel(self.details_frame, text="状态分布", font=LABEL_BOLD, text_color=TEXT_PRIMARY).pack(anchor="w", padx=15, pady=(10, 5))
        self.status_box = ctk.CTkTextbox(self.details_frame, height=80, fg_color="transparent", text_color=TEXT_MUTED)
        self.status_box.pack(fill="x", padx=10)
        
        # 3b. 课程分布
        ctk.CTkLabel(self.details_frame, text="课程分布", font=LABEL_BOLD, text_color=TEXT_PRIMARY).pack(anchor="w", padx=15, pady=(10, 5))
        self.course_box = ctk.CTkTextbox(self.details_frame, height=120, fg_color="transparent", text_color=TEXT_MUTED)
        self.course_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # 4. 近期完成 (底部小字)
        self.recent_label = ctk.CTkLabel(self.details_frame, text="近7天完成: -", text_color=TEXT_MUTED, font=("Arial", 11))
        self.recent_label.pack(anchor="e", padx=15, pady=10)

        self.refresh()

    def _create_kpi_card(self, parent, title, value, col):
        """创建顶部的小指标卡片"""
        parent.columnconfigure(col, weight=1)
        card = ctk.CTkFrame(parent, **card_kwargs())
        card.grid(row=0, column=col, sticky="ew", padx=(0 if col==0 else 5, 0 if col==2 else 5))
        
        lbl_title = ctk.CTkLabel(card, text=title, font=("Arial", 12), text_color=TEXT_MUTED)
        lbl_title.pack(pady=(10, 0))
        
        lbl_val = ctk.CTkLabel(card, text=value, font=("Arial", 20, "bold"), text_color=TEXT_PRIMARY)
        lbl_val.pack(pady=(0, 10))
        return lbl_val

    def refresh(self) -> None:
        tasks = self.tasks_provider()
        total = len(tasks)
        
        # 1. 基础计数
        by_course = Counter(getattr(t, 'course', '未分类') for t in tasks)
        by_status = Counter(getattr(t, 'status', 'todo') for t in tasks)
        
        done_count = by_status.get("done", 0) + by_status.get("completed", 0)
        rate = (done_count / total * 100) if total > 0 else 0.0

        # 2. 更新 KPI 卡片
        self.card_total.configure(text=str(total))
        self.card_done.configure(text=str(done_count))
        self.card_rate.configure(text=f"{rate:.1f}%")

        # 3. 更新进度条
        self.progress_bar.set(rate / 100)

        # 4. 更新文本框 (Text Box 自动换行，优于 Label 拼接)
        self._update_textbox(self.status_box, by_status)
        self._update_textbox(self.course_box, by_course)

        # 5. 近期完成 (保留你原有的逻辑，尽量做容错)
        last_week = date.today() - timedelta(days=7)
        recent_count = 0
        for t in tasks:
            if getattr(t, 'status', '') == 'done':
                if self._completed_within(t, last_week):
                    recent_count += 1
        
        self.recent_label.configure(text=f"最近 7 天内截止并完成的任务: {recent_count}")

    def _update_textbox(self, textbox: ctk.CTkTextbox, counter: Counter):
        textbox.configure(state="normal")
        textbox.delete("1.0", "end")
        
        if not counter:
            textbox.insert("end", "暂无数据")
        else:
            # 排序：数量多的在前
            items = sorted(counter.items(), key=lambda x: x[1], reverse=True)
            text_content = ""
            for name, count in items:
                # 使用点号列表格式，更清晰
                text_content += f"• {name}: {count}\n"
            textbox.insert("end", text_content)
            
        textbox.configure(state="disabled")

    def _completed_within(self, task: Task, since: date) -> bool:
        # 注意：这里依然依赖 due_date，因为 Task 模型可能没有 finished_at
        try:
            d_str = getattr(task, 'due_date', '')
            if not d_str: return False
            due = date.fromisoformat(d_str)
            return due >= since
        except ValueError:
            return False