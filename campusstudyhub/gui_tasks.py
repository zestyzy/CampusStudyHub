"""任务管理页（CustomTkinter 深色主题版 - 布局完美修复版）。"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from datetime import date
from typing import Callable, List, Optional

import customtkinter as ctk

from .config import AppConfig
from .models import Task
from .storage import add_task, delete_task, update_task
from .ui_style import (
    BG_CARD,
    HEADER_FONT,
    LABEL_BOLD,
    TEXT_PRIMARY,
    TEXT_MUTED,
    card_kwargs,
)

# 映射常量
PRIORITY_MAP = {"低": "low", "中": "medium", "高": "high"}
PRIORITY_INV = {v: k for k, v in PRIORITY_MAP.items()}
STATUS_MAP = {"待办": "todo", "进行中": "in_progress", "已完成": "done"}
STATUS_INV = {v: k for k, v in STATUS_MAP.items()}

# 深色 Treeview 样式补丁
def setup_treeview_style():
    style = ttk.Style()
    style.theme_use("clam")
    
    style.configure(
        "Treeview",
        background="#2b2b2b",
        foreground="#dce4ee",
        fieldbackground="#2b2b2b",
        borderwidth=0,
        font=("Arial", 11),
        rowheight=28
    )
    style.map("Treeview", background=[("selected", "#1f538d")])
    style.configure(
        "Treeview.Heading",
        background="#3a3a3a",
        foreground="#ffffff",
        relief="flat",
        font=("Arial", 11, "bold")
    )
    style.map("Treeview.Heading", background=[("active", "#4a4a4a")])


class TasksFrame(ctk.CTkFrame):
    """任务增删改查与提醒列表。"""

    def __init__(
        self,
        master: tk.Widget,
        tasks: List[Task],
        config: AppConfig,
        on_tasks_updated: Callable[[List[Task]], None],
        on_config_update: Callable[[AppConfig], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.tasks = tasks
        self.config = config
        self.on_tasks_updated = on_tasks_updated
        self.on_config_update = on_config_update
        self.selected_task_id: Optional[str] = None

        setup_treeview_style()
        self._build_ui()
        self.refresh_tasks()

    def _build_ui(self) -> None:
        # 左右分栏：左侧列表(4)，右侧详情(3) -> 增加左侧权重，防止列表过窄
        self.columnconfigure(0, weight=4)
        self.columnconfigure(1, weight=3)
        self.rowconfigure(0, weight=1)

        # ================= 左侧面板 (列表区) =================
        left_panel = ctk.CTkFrame(self, **card_kwargs())
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)
        
        left_panel.rowconfigure(2, weight=1) # 列表区域自动伸缩
        left_panel.columnconfigure(0, weight=1)

        # 1. 提醒横幅 (顶部)
        self.reminder_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        self.reminder_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        self.upcoming_label = ctk.CTkLabel(self.reminder_frame, text="即将到期：-", text_color="#FFB74D", font=LABEL_BOLD)
        self.upcoming_label.pack(anchor="w")
        self.overdue_label = ctk.CTkLabel(self.reminder_frame, text="已逾期：-", text_color="#EF5350", font=LABEL_BOLD)
        self.overdue_label.pack(anchor="w")

        # 2. 筛选栏
        filter_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        filter_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        ctk.CTkLabel(filter_frame, text="筛选:").pack(side="left", padx=(0, 5))
        
        self.course_filter = ctk.CTkComboBox(filter_frame, width=110, state="readonly", values=self._course_options())
        self.course_filter.pack(side="left", padx=5)
        self.course_filter.set("全部")
        
        self.status_filter = ctk.CTkComboBox(filter_frame, width=100, state="readonly", values=["全部"] + list(STATUS_MAP.keys()))
        self.status_filter.pack(side="left", padx=5)
        self.status_filter.set("全部")

        self.overdue_only = ctk.CTkCheckBox(filter_frame, text="仅逾期", width=60)
        self.overdue_only.pack(side="left", padx=10)

        ctk.CTkButton(filter_frame, text="查询", width=60, command=self.refresh_tasks).pack(side="left", padx=5)

        # 3. 任务列表 (Treeview)
        tree_container = ctk.CTkFrame(left_panel, fg_color="transparent")
        tree_container.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        tree_container.rowconfigure(0, weight=1)
        tree_container.columnconfigure(0, weight=1)
        
        cols = ("title", "course", "due", "prio", "status")
        self.tree = ttk.Treeview(tree_container, columns=cols, show="headings", selectmode="browse")
        
        self.tree.heading("title", text="标题")
        self.tree.heading("course", text="课程")
        self.tree.heading("due", text="截止日期")
        self.tree.heading("prio", text="优先级")
        self.tree.heading("status", text="状态")

        self.tree.column("title", width=180)
        self.tree.column("course", width=100)
        self.tree.column("due", width=90)
        self.tree.column("prio", width=60, anchor="center")
        self.tree.column("status", width=70, anchor="center")

        ysb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=ysb.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.tag_configure("overdue", foreground="#ff6b6b") 

        # ================= 右侧面板 (详情编辑) =================
        right_panel = ctk.CTkFrame(self, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew", pady=0)
        right_panel.columnconfigure(0, weight=1)

        # 1. 编辑表单卡片 (使用 Grid 布局解决阶梯问题)
        form_card = ctk.CTkFrame(right_panel, **card_kwargs())
        form_card.pack(fill="x", pady=(0, 15))
        
        # 配置表单 Grid：Col 0 是标签，Col 1 是输入框
        form_card.columnconfigure(0, weight=0, minsize=80)
        form_card.columnconfigure(1, weight=1)
        
        ctk.CTkLabel(form_card, text="任务详情", font=HEADER_FONT).grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(15, 10))
        
        # 行 1：标题
        ctk.CTkLabel(form_card, text="标题").grid(row=1, column=0, sticky="e", padx=(15, 10), pady=6)
        self.title_entry = ctk.CTkEntry(form_card)
        self.title_entry.grid(row=1, column=1, sticky="ew", padx=(0, 15), pady=6)

        # 行 2：课程
        ctk.CTkLabel(form_card, text="课程").grid(row=2, column=0, sticky="e", padx=(15, 10), pady=6)
        self.course_entry = ctk.CTkComboBox(form_card, values=self.config.courses)
        self.course_entry.grid(row=2, column=1, sticky="ew", padx=(0, 15), pady=6)

        # 行 3：类型
        ctk.CTkLabel(form_card, text="类型").grid(row=3, column=0, sticky="e", padx=(15, 10), pady=6)
        self.type_entry = ctk.CTkEntry(form_card, placeholder_text="作业/考试/阅读")
        self.type_entry.grid(row=3, column=1, sticky="ew", padx=(0, 15), pady=6)

        # 行 4：截止日期
        ctk.CTkLabel(form_card, text="截止").grid(row=4, column=0, sticky="e", padx=(15, 10), pady=6)
        self.due_entry = ctk.CTkEntry(form_card, placeholder_text="YYYY-MM-DD")
        self.due_entry.grid(row=4, column=1, sticky="ew", padx=(0, 15), pady=6)

        # 行 5：优先级
        ctk.CTkLabel(form_card, text="优先级").grid(row=5, column=0, sticky="e", padx=(15, 10), pady=6)
        self.prio_combo = ctk.CTkComboBox(form_card, values=list(PRIORITY_MAP.keys()), state="readonly")
        self.prio_combo.grid(row=5, column=1, sticky="ew", padx=(0, 15), pady=6)

        # 行 6：状态
        ctk.CTkLabel(form_card, text="状态").grid(row=6, column=0, sticky="e", padx=(15, 10), pady=6)
        self.status_combo = ctk.CTkComboBox(form_card, values=list(STATUS_MAP.keys()), state="readonly")
        self.status_combo.grid(row=6, column=1, sticky="ew", padx=(0, 15), pady=6)

        # 行 7：备注
        ctk.CTkLabel(form_card, text="备注").grid(row=7, column=0, sticky="ne", padx=(15, 10), pady=6)
        self.notes_text = ctk.CTkTextbox(form_card, height=100)
        self.notes_text.grid(row=7, column=1, sticky="ew", padx=(0, 15), pady=6)

        # 行 8：按钮组
        btn_row = ctk.CTkFrame(form_card, fg_color="transparent")
        btn_row.grid(row=8, column=0, columnspan=2, sticky="ew", padx=15, pady=15)
        
        ctk.CTkButton(btn_row, text="清空/新建", fg_color="transparent", border_width=1, width=80, command=self._clear_form).pack(side="left", padx=(0, 5), fill="x", expand=True)
        ctk.CTkButton(btn_row, text="保存任务", command=self._save_task).pack(side="left", padx=5, fill="x", expand=True)
        ctk.CTkButton(btn_row, text="删除", fg_color="#b33636", hover_color="#8f2a2a", width=60, command=self._delete_task).pack(side="right", padx=(5, 0), fill="x", expand=True)

        # 2. 课程设置卡片
        course_card = ctk.CTkFrame(right_panel, **card_kwargs())
        course_card.pack(fill="x")
        
        ctk.CTkLabel(course_card, text="课程管理 (逗号分隔)", font=LABEL_BOLD).pack(anchor="w", padx=15, pady=(15, 5))
        self.course_settings = ctk.CTkTextbox(course_card, height=60)
        self.course_settings.insert("1.0", ", ".join(self.config.courses))
        self.course_settings.pack(fill="x", padx=15, pady=5)
        ctk.CTkButton(course_card, text="更新课程列表", height=32, command=self._save_courses).pack(fill="x", padx=15, pady=(5, 15))

        # Init defaults
        self.prio_combo.set("中")
        self.status_combo.set("待办")

    def _course_options(self) -> List[str]:
        return ["全部"] + self.config.courses

    def refresh_tasks(self) -> None:
        # 清空列表
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 获取筛选条件
        c_filter = self.course_filter.get()
        s_filter = self.status_filter.get()
        s_val = STATUS_MAP.get(s_filter, s_filter)
        only_overdue = self.overdue_only.get()

        filtered = []
        for t in self.tasks:
            if c_filter not in ("", "全部") and t.course != c_filter: continue
            if s_filter not in ("", "全部") and t.status != s_val: continue
            if only_overdue and not t.is_overdue(): continue
            filtered.append(t)

        # 排序：未完成的在前，日期近的在前
        filtered.sort(key=lambda x: (x.status == "done", x.due_date))

        for t in filtered:
            tags = ("overdue",) if t.is_overdue() and t.status != "done" else ()
            self.tree.insert("", "end", iid=t.id, values=(
                t.title,
                t.course,
                t.due_date,
                PRIORITY_INV.get(t.priority, t.priority),
                STATUS_INV.get(t.status, t.status)
            ), tags=tags)

        self._update_reminders()

    def _update_reminders(self) -> None:
        upcoming = [t for t in self.tasks if t.is_due_within(self.config.upcoming_window_days) and t.status != 'done']
        overdue = [t for t in self.tasks if t.is_overdue() and t.status != 'done']
        
        up_txt = f"{len(upcoming)} 个 (未来 {self.config.upcoming_window_days} 天)"
        od_txt = f"{len(overdue)} 个"
        
        self.upcoming_label.configure(text=f"即将到期：{up_txt}")
        self.overdue_label.configure(text=f"已逾期：{od_txt}")

    def _on_select(self, event):
        sel = self.tree.selection()
        if not sel: return
        t_id = sel[0]
        task = next((t for t in self.tasks if t.id == t_id), None)
        if not task: return
        
        self.selected_task_id = task.id
        
        # 填充表单
        self.title_entry.delete(0, "end"); self.title_entry.insert(0, task.title)
        self.course_entry.set(task.course)
        self.type_entry.delete(0, "end"); self.type_entry.insert(0, task.task_type)
        self.due_entry.delete(0, "end"); self.due_entry.insert(0, task.due_date)
        
        self.prio_combo.set(PRIORITY_INV.get(task.priority, "中"))
        self.status_combo.set(STATUS_INV.get(task.status, "待办"))
        
        self.notes_text.delete("1.0", "end")
        self.notes_text.insert("1.0", task.notes)

    def _clear_form(self):
        self.selected_task_id = None
        self.title_entry.delete(0, "end")
        self.course_entry.set("")
        self.type_entry.delete(0, "end")
        self.due_entry.delete(0, "end")
        self.prio_combo.set("中")
        self.status_combo.set("待办")
        self.notes_text.delete("1.0", "end")

    def _save_task(self):
        title = self.title_entry.get().strip()
        course = self.course_entry.get().strip()
        ttype = self.type_entry.get().strip()
        due = self.due_entry.get().strip()
        prio = PRIORITY_MAP.get(self.prio_combo.get(), "medium")
        status = STATUS_MAP.get(self.status_combo.get(), "todo")
        notes = self.notes_text.get("1.0", "end").strip()

        if not (title and course and ttype and due):
            messagebox.showerror("错误", "标题、课程、类型、截止日期为必填项")
            return
        
        try: date.fromisoformat(due)
        except ValueError:
            messagebox.showerror("错误", "日期格式需为 YYYY-MM-DD")
            return

        if self.selected_task_id:
            # Update existing
            t = next((t for t in self.tasks if t.id == self.selected_task_id), None)
            if t:
                new_t = Task(id=t.id, title=title, course=course, task_type=ttype, due_date=due, priority=prio, status=status, notes=notes)
                self.tasks = update_task(self.tasks, new_t)
        else:
            # Create new
            new_t = Task(title=title, course=course, task_type=ttype, due_date=due, priority=prio, status=status, notes=notes)
            self.tasks = add_task(self.tasks, new_t)
            self.selected_task_id = new_t.id

        self.on_tasks_updated(self.tasks)
        self.refresh_tasks()

    def _delete_task(self):
        if not self.selected_task_id: return
        if not messagebox.askyesno("确认", "确定删除该任务吗？"): return
        self.tasks = delete_task(self.tasks, self.selected_task_id)
        self.selected_task_id = None
        self.on_tasks_updated(self.tasks)
        self._clear_form()
        self.refresh_tasks()

    def _save_courses(self):
        raw = self.course_settings.get("1.0", "end").strip()
        courses = [c.strip() for c in raw.split(",") if c.strip()]
        if not courses:
            messagebox.showerror("错误", "至少需要一个课程")
            return
        self.config.courses = courses
        self.on_config_update(self.config)
        self.course_entry.configure(values=courses)
        self.course_filter.configure(values=["全部"] + courses)
        messagebox.showinfo("成功", "课程列表已更新")