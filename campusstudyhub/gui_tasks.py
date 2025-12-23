"""任务管理页（已本地化为简体中文）。"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from datetime import date
from typing import Callable, List, Optional

from .config import AppConfig
from .models import PRIORITY_LEVELS, TASK_STATUSES, Task
from .storage import add_task, delete_task, save_tasks, update_task


class TasksFrame(ttk.Frame):
    """任务增删改查与提醒列表。"""

    def __init__(
        self,
        master: tk.Widget,
        tasks: List[Task],
        config: AppConfig,
        on_tasks_updated: Callable[[List[Task]], None],
        on_config_update: Callable[[AppConfig], None],
    ) -> None:
        super().__init__(master, padding=10)
        self.tasks = tasks
        self.config = config
        self.on_tasks_updated = on_tasks_updated
        self.on_config_update = on_config_update
        self.selected_task_id: Optional[str] = None

        self._build_widgets()
        self.refresh_tasks()

    def _build_widgets(self) -> None:
        filter_frame = ttk.LabelFrame(self, text="筛选", padding=10)
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(filter_frame, text="课程：").grid(row=0, column=0, sticky=tk.W)
        self.course_filter = ttk.Combobox(filter_frame, values=self._course_options(), state="readonly")
        self.course_filter.set("全部")
        self.course_filter.grid(row=0, column=1, padx=5)

        ttk.Label(filter_frame, text="状态：").grid(row=0, column=2, sticky=tk.W)
        self.status_filter = ttk.Combobox(filter_frame, values=["全部"] + TASK_STATUSES, state="readonly")
        self.status_filter.set("全部")
        self.status_filter.grid(row=0, column=3, padx=5)

        self.overdue_only = tk.BooleanVar()
        ttk.Checkbutton(filter_frame, text="仅查看逾期", variable=self.overdue_only).grid(row=0, column=4, padx=5)

        ttk.Button(filter_frame, text="应用筛选", command=self.refresh_tasks).grid(row=0, column=5, padx=5)

        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        form_frame = ttk.LabelFrame(main_pane, text="任务详情", padding=10)
        self._build_form(form_frame)

        list_frame = ttk.Frame(main_pane)
        self._build_task_list(list_frame)

        main_pane.add(form_frame, weight=1)
        main_pane.add(list_frame, weight=2)

        reminder_frame = ttk.LabelFrame(self, text="提醒", padding=10)
        reminder_frame.pack(fill=tk.X, pady=(10, 0))
        self.upcoming_label = ttk.Label(reminder_frame, text="即将到期：-")
        self.upcoming_label.pack(anchor=tk.W)
        self.overdue_label = ttk.Label(reminder_frame, text="已逾期：-")
        self.overdue_label.pack(anchor=tk.W)
        ttk.Button(reminder_frame, text="刷新提醒", command=self.refresh_tasks).pack(anchor=tk.E, pady=5)

        settings_frame = ttk.LabelFrame(self, text="课程设置", padding=10)
        settings_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(settings_frame, text="课程列表（逗号分隔）：").grid(row=0, column=0, sticky=tk.W)
        self.course_settings = tk.Text(settings_frame, height=2, width=60)
        self.course_settings.grid(row=0, column=1, padx=5)
        self.course_settings.insert("1.0", ", ".join(self.config.courses))
        ttk.Button(settings_frame, text="保存课程", command=self._save_courses).grid(row=0, column=2)

    def _build_form(self, container: ttk.LabelFrame) -> None:
        labels = ["标题", "课程", "类型", "截止日期 (YYYY-MM-DD)", "优先级", "状态", "备注"]
        for idx, text in enumerate(labels):
            ttk.Label(container, text=text).grid(row=idx, column=0, sticky=tk.W, pady=2)

        self.title_entry = ttk.Entry(container, width=40)
        self.course_entry = ttk.Combobox(container, values=self.config.courses, width=37)
        self.type_entry = ttk.Entry(container, width=40)
        self.due_entry = ttk.Entry(container, width=40)
        self.priority_combo = ttk.Combobox(container, values=PRIORITY_LEVELS, state="readonly", width=37)
        self.priority_combo.set("medium")
        self.status_combo = ttk.Combobox(container, values=TASK_STATUSES, state="readonly", width=37)
        self.status_combo.set("todo")
        self.notes_text = tk.Text(container, width=30, height=5)

        widgets = [
            self.title_entry,
            self.course_entry,
            self.type_entry,
            self.due_entry,
            self.priority_combo,
            self.status_combo,
            self.notes_text,
        ]
        for idx, widget in enumerate(widgets):
            if isinstance(widget, tk.Text):
                widget.grid(row=idx, column=1, pady=2, sticky=tk.W)
            else:
                widget.grid(row=idx, column=1, pady=2, sticky=tk.W)

        btn_frame = ttk.Frame(container)
        btn_frame.grid(row=len(labels), column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="新建", command=self._clear_form).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="保存", command=self._save_task).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="删除", command=self._delete_task).pack(side=tk.LEFT, padx=5)

    def _build_task_list(self, container: ttk.Frame) -> None:
        columns = ("title", "course", "due", "priority", "status")
        self.tree = ttk.Treeview(container, columns=columns, show="headings", selectmode="browse")
        for col, heading in zip(columns, ["标题", "课程", "截止", "优先级", "状态"]):
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=120, anchor=tk.W)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.tag_configure("overdue", background="#ffe0e0")

        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _course_options(self) -> List[str]:
        return ["全部"] + self.config.courses

    def refresh_config(self, config: AppConfig) -> None:
        """Update UI when config changes."""
        self.config = config
        self.course_entry.configure(values=config.courses)
        self.course_filter.configure(values=self._course_options())
        self.course_settings.delete("1.0", tk.END)
        self.course_settings.insert("1.0", ", ".join(config.courses))

    def refresh_tasks(self) -> None:
        """Refresh the task list and reminders according to filters."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        course_filter = self.course_filter.get()
        status_filter = self.status_filter.get()

        filtered = []
        for task in self.tasks:
            if course_filter not in ("", "全部") and task.course != course_filter:
                continue
            if status_filter not in ("", "全部") and task.status != status_filter:
                continue
            if self.overdue_only.get() and not task.is_overdue():
                continue
            filtered.append(task)

        for task in filtered:
            tags = ("overdue",) if task.is_overdue() else ()
            self.tree.insert(
                "",
                tk.END,
                iid=task.id,
                values=(task.title, task.course, task.due_date, task.priority, task.status),
                tags=tags,
            )

        self._update_reminders()

    def _update_reminders(self) -> None:
        upcoming = [t for t in self.tasks if t.is_due_within(self.config.upcoming_window_days)]
        overdue = [t for t in self.tasks if t.is_overdue()]
        upcoming_text = ", ".join(f"{t.title} ({t.due_date})" for t in upcoming) or "无"
        overdue_text = ", ".join(f"{t.title} ({t.due_date})" for t in overdue) or "无"
        self.upcoming_label.config(text=f"即将到期（未来 {self.config.upcoming_window_days} 天）：{upcoming_text}")
        self.overdue_label.config(text=f"已逾期：{overdue_text}")

    def _on_select(self, event: tk.Event) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        task_id = selection[0]
        task = next((t for t in self.tasks if t.id == task_id), None)
        if not task:
            return
        self.selected_task_id = task.id
        self.title_entry.delete(0, tk.END)
        self.title_entry.insert(0, task.title)
        self.course_entry.set(task.course)
        self.type_entry.delete(0, tk.END)
        self.type_entry.insert(0, task.task_type)
        self.due_entry.delete(0, tk.END)
        self.due_entry.insert(0, task.due_date)
        self.priority_combo.set(task.priority)
        self.status_combo.set(task.status)
        self.notes_text.delete("1.0", tk.END)
        self.notes_text.insert("1.0", task.notes)

    def _clear_form(self) -> None:
        self.selected_task_id = None
        self.title_entry.delete(0, tk.END)
        self.course_entry.set("")
        self.type_entry.delete(0, tk.END)
        self.due_entry.delete(0, tk.END)
        self.priority_combo.set("medium")
        self.status_combo.set("todo")
        self.notes_text.delete("1.0", tk.END)

    def _save_task(self) -> None:
        title = self.title_entry.get().strip()
        course = self.course_entry.get().strip()
        task_type = self.type_entry.get().strip()
        due_date_str = self.due_entry.get().strip()
        priority = self.priority_combo.get()
        status = self.status_combo.get()
        notes = self.notes_text.get("1.0", tk.END).strip()

        if not title or not course or not task_type or not due_date_str:
            messagebox.showerror("信息不完整", "请填写标题、课程、类型和截止日期。")
            return

        try:
            # Validate date format
            date.fromisoformat(due_date_str)
        except ValueError:
            messagebox.showerror("日期格式错误", "请使用 YYYY-MM-DD 格式。")
            return

        if self.selected_task_id:
            existing = next((t for t in self.tasks if t.id == self.selected_task_id), None)
            if not existing:
                return
            updated = Task(
                id=existing.id,
                title=title,
                course=course,
                task_type=task_type,
                due_date=due_date_str,
                priority=priority,
                status=status,
                notes=notes,
            )
            self.tasks = update_task(self.tasks, updated)
        else:
            new_task = Task(
                title=title,
                course=course,
                task_type=task_type,
                due_date=due_date_str,
                priority=priority,
                status=status,
                notes=notes,
            )
            self.tasks = add_task(self.tasks, new_task)
            self.selected_task_id = new_task.id

        self.on_tasks_updated(self.tasks)
        self.refresh_tasks()

    def _delete_task(self) -> None:
        if not self.selected_task_id:
            messagebox.showinfo("请选择任务", "请先在列表中选择要删除的任务。")
            return
        if not messagebox.askyesno("确认", "确定删除选中的任务吗？"):
            return
        self.tasks = delete_task(self.tasks, self.selected_task_id)
        self.selected_task_id = None
        self.on_tasks_updated(self.tasks)
        self.refresh_tasks()
        self._clear_form()

    def _save_courses(self) -> None:
        raw = self.course_settings.get("1.0", tk.END).strip()
        courses = [c.strip() for c in raw.split(",") if c.strip()]
        if not courses:
            messagebox.showerror("课程列表", "请至少填写一个课程名称。")
            return
        self.config.courses = courses
        self.on_config_update(self.config)
        messagebox.showinfo("课程列表", "课程列表已更新。")
        self.refresh_config(self.config)
