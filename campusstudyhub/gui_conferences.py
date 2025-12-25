"""Conference tab UI for CCF deadline tracking and LAN notifications."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Callable, List, Optional

from .config import AppConfig
from .lan import send_lan_notifications
from .models import ConferenceEvent
from .storage import load_conferences, save_conferences


class ConferencesFrame(ttk.Frame):
    """Frame to show CCF conferences and send LAN notifications."""

    def __init__(
        self,
        master: tk.Widget,
        config: AppConfig,
        on_config_update: Callable[[AppConfig], None],
    ) -> None:
        super().__init__(master, padding=10)
        self.config = config
        self.on_config_update = on_config_update
        self.conferences: List[ConferenceEvent] = load_conferences()
        self.selected_id: Optional[str] = None

        self._build_widgets()
        self.refresh_list()

    def _build_widgets(self) -> None:
        controls = ttk.LabelFrame(self, text="会议筛选", padding=8)
        controls.pack(fill=tk.X, pady=(0, 8))
        for idx in range(8):
            controls.columnconfigure(idx, weight=1)

        ttk.Label(controls, text="等级：").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.category_filter = ttk.Combobox(
            controls, values=["全部", "CCF-A", "CCF-B", "CCF-C"], state="readonly", width=10
        )
        self.category_filter.set("全部")
        self.category_filter.grid(row=0, column=1, sticky=tk.W, padx=4, pady=2)

        ttk.Label(controls, text="截止天数：").grid(row=0, column=2, sticky=tk.W, pady=2)
        self.window_entry = ttk.Entry(controls, width=8)
        self.window_entry.insert(0, str(self.config.conference_window_days))
        self.window_entry.grid(row=0, column=3, sticky=tk.W, pady=2)

        self.show_all_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(controls, text="显示全部", variable=self.show_all_var, command=self.refresh_list).grid(
            row=0, column=4, sticky=tk.W, padx=4, pady=2
        )

        ttk.Button(controls, text="应用筛选", command=self.refresh_list, width=10).grid(
            row=0, column=5, sticky=tk.E, padx=4, pady=2
        )
        ttk.Button(controls, text="发送提醒", command=self._send_lan, width=10).grid(
            row=0, column=6, sticky=tk.E, padx=4, pady=2
        )
        ttk.Button(controls, text="选择会议发送", command=self._pick_and_send, width=14).grid(
            row=0, column=7, sticky=tk.E, padx=4, pady=2
        )

        main = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True)

        list_frame = ttk.Frame(main)
        self._build_table(list_frame)
        form_frame = ttk.LabelFrame(main, text="新增 / 编辑", padding=10)
        self._build_form(form_frame)

        main.add(list_frame, weight=2)
        main.add(form_frame, weight=1)

    def _build_table(self, container: ttk.Frame) -> None:
        columns = ("name", "category", "deadline", "location")
        self.tree = ttk.Treeview(container, columns=columns, show="headings", selectmode="extended")
        headings = ["名称", "等级", "截稿", "地点"]
        for col, head in zip(columns, headings):
            self.tree.heading(col, text=head)
            self.tree.column(col, anchor=tk.W, width=140)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.tag_configure("overdue", background="#ffe6e6")

        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_form(self, container: ttk.LabelFrame) -> None:
        labels = ["名称", "等级", "截稿日期 (YYYY-MM-DD)", "地点", "链接", "备注"]
        for idx, label in enumerate(labels):
            ttk.Label(container, text=label).grid(row=idx, column=0, sticky=tk.W, pady=2)

        self.name_entry = ttk.Entry(container, width=28)
        self.category_entry = ttk.Combobox(container, values=["CCF-A", "CCF-B", "CCF-C"], width=25)
        self.deadline_entry = ttk.Entry(container, width=28)
        self.location_entry = ttk.Entry(container, width=28)
        self.url_entry = ttk.Entry(container, width=28)
        self.note_text = tk.Text(container, height=4, width=21)

        widgets = [
            self.name_entry,
            self.category_entry,
            self.deadline_entry,
            self.location_entry,
            self.url_entry,
            self.note_text,
        ]
        for idx, widget in enumerate(widgets):
            if isinstance(widget, tk.Text):
                widget.grid(row=idx, column=1, pady=2, sticky=tk.W)
            else:
                widget.grid(row=idx, column=1, pady=2, sticky=tk.W)

        btns = ttk.Frame(container)
        btns.grid(row=len(labels), column=0, columnspan=2, pady=8)
        ttk.Button(btns, text="新建", command=self._clear_form).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="保存", command=self._save_conference).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="删除", command=self._delete_conference).pack(side=tk.LEFT, padx=4)

        targets = ttk.LabelFrame(container, text="局域网联系人", padding=6)
        targets.grid(row=len(labels) + 1, column=0, columnspan=2, sticky=tk.EW, pady=(10, 0))
        self.lan_list = tk.Listbox(targets, height=4)
        self.lan_list.pack(fill=tk.X)
        self._refresh_lan_listbox()
        ttk.Button(targets, text="管理联系人", command=self._edit_lan_targets).pack(anchor=tk.E, pady=4)

    def _refresh_lan_listbox(self) -> None:
        self.lan_list.delete(0, tk.END)
        for target in self.config.lan_targets:
            suffix = f"{target.host}:{target.port}" if target.port else target.host
            if target.email:
                suffix += f" | {target.email}"
            self.lan_list.insert(tk.END, f"{target.label} ({suffix})")

    def refresh_list(self) -> None:
        """Refresh displayed conferences according to filters."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        category = self.category_filter.get()
        try:
            window_days = int(self.window_entry.get())
        except ValueError:
            window_days = self.config.conference_window_days
            self.window_entry.delete(0, tk.END)
            self.window_entry.insert(0, str(window_days))

        filtered: List[ConferenceEvent] = []
        for conf in self.conferences:
            if category not in ("", "全部") and conf.category != category:
                continue
            if not self.show_all_var.get() and not (conf.is_due_within(window_days) or conf.is_overdue()):
                continue
            filtered.append(conf)

        for conf in filtered:
            tags = ("overdue",) if conf.is_overdue() else ()
            self.tree.insert(
                "",
                tk.END,
                iid=conf.id,
                values=(conf.name, conf.category, conf.submission_deadline, conf.location or "-"),
                tags=tags,
            )

    def refresh_config(self, config: AppConfig) -> None:
        """Refresh local config and LAN list when settings change."""

        self.config = config
        self.window_entry.delete(0, tk.END)
        self.window_entry.insert(0, str(config.conference_window_days))
        self._refresh_lan_listbox()

    def _on_select(self, event: tk.Event) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        conf_id = selection[0]
        conf = next((c for c in self.conferences if c.id == conf_id), None)
        if not conf:
            return
        self.selected_id = conf.id
        self.name_entry.delete(0, tk.END)
        self.name_entry.insert(0, conf.name)
        self.category_entry.set(conf.category)
        self.deadline_entry.delete(0, tk.END)
        self.deadline_entry.insert(0, conf.submission_deadline)
        self.location_entry.delete(0, tk.END)
        self.location_entry.insert(0, conf.location)
        self.url_entry.delete(0, tk.END)
        self.url_entry.insert(0, conf.url)
        self.note_text.delete("1.0", tk.END)
        self.note_text.insert("1.0", conf.note)

    def _clear_form(self) -> None:
        self.selected_id = None
        for entry in [self.name_entry, self.category_entry, self.deadline_entry, self.location_entry, self.url_entry]:
            entry.delete(0, tk.END)
        self.note_text.delete("1.0", tk.END)

    def _save_conference(self) -> None:
        name = self.name_entry.get().strip()
        category = self.category_entry.get().strip() or "CCF-A"
        deadline = self.deadline_entry.get().strip()
        location = self.location_entry.get().strip()
        url = self.url_entry.get().strip()
        note = self.note_text.get("1.0", tk.END).strip()

        if not name or not deadline:
            messagebox.showerror("缺少必填项", "请填写会议名称和截稿日期。")
            return

        if self.selected_id:
            for idx, conf in enumerate(self.conferences):
                if conf.id == self.selected_id:
                    self.conferences[idx] = ConferenceEvent(
                        name=name,
                        category=category,
                        submission_deadline=deadline,
                        location=location,
                        url=url,
                        note=note,
                        id=self.selected_id,
                    )
                    break
        else:
            self.conferences.append(
                ConferenceEvent(
                    name=name,
                    category=category,
                    submission_deadline=deadline,
                    location=location,
                    url=url,
                    note=note,
                )
            )

        save_conferences(self.conferences)
        self.refresh_list()
        self._clear_form()

    def _delete_conference(self) -> None:
        if not self.selected_id:
            return
        if not messagebox.askyesno("确认", "确定要删除这条会议记录吗？"):
            return
        self.conferences = [c for c in self.conferences if c.id != self.selected_id]
        save_conferences(self.conferences)
        self.refresh_list()
        self._clear_form()

    def _send_lan(self) -> None:
        if not self.config.lan_targets:
            messagebox.showinfo("尚无联系人", "请先添加局域网联系人。")
            return

        try:
            window_days = int(self.window_entry.get())
        except ValueError:
            window_days = self.config.conference_window_days

        selection = self.tree.selection()
        selected_map = {c.id: c for c in self.conferences}
        picked = [selected_map[iid] for iid in selection if iid in selected_map]

        if not picked:
            due_items = [
                c
                for c in self.conferences
                if c.is_due_within(window_days) or c.is_overdue()
            ]
        else:
            due_items = picked

        if not due_items:
            # 当前筛选无匹配时，直接引导用户手动勾选要发送的会议
            dialog = ConferencePickDialog(self, self.conferences)
            self.wait_window(dialog)
            if dialog.result:
                self._dispatch_notifications(dialog.result)
            else:
                messagebox.showinfo("暂无可发送的会议", "请选择会议或调整筛选条件后再试。")
            return

        self._dispatch_notifications(due_items)

    def _pick_and_send(self) -> None:
        dialog = ConferencePickDialog(self, self.conferences)
        self.wait_window(dialog)
        if not dialog.result:
            return
        self._dispatch_notifications(dialog.result)

    def _dispatch_notifications(self, conferences: List[ConferenceEvent]) -> None:
        if not conferences:
            messagebox.showinfo("暂无可发送的会议", "请至少选择一条会议记录。")
            return

        lines = [f"{c.name} ({c.category}) 截止 {c.submission_deadline}" for c in conferences]
        message = "CampusStudyHub 会议提醒\n" + "\n".join(lines)
        results = send_lan_notifications(
            message,
            self.config.lan_targets,
            smtp_host=self.config.smtp_host,
            smtp_port=self.config.smtp_port,
            smtp_sender=self.config.smtp_sender,
        )

        success = [r for r in results if r[1]]
        failed = [r for r in results if not r[1]]
        detail = f"成功发送: {len(success)} 条；失败: {len(failed)} 条"
        if failed:
            detail += "\n" + "\n".join(f"{t.label}: {msg}" for t, _, msg in failed)
        messagebox.showinfo("提醒结果", detail)

    def _edit_lan_targets(self) -> None:
        dialog = LanTargetsDialog(self, self.config.lan_targets)
        self.wait_window(dialog)
        if dialog.result is not None:
            self.config.lan_targets = dialog.result
            self.on_config_update(self.config)
            self._refresh_lan_listbox()


class LanTargetsDialog(tk.Toplevel):
    """局域网联系人编辑对话框。"""

    def __init__(self, master: tk.Widget, targets: List) -> None:
        super().__init__(master)
        self.title("编辑联系人")
        self.result: Optional[List] = None
        self.targets = list(targets)
        self._build_ui()

    def _build_ui(self) -> None:
        self.resizable(False, False)
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        self.listbox = tk.Listbox(frame, width=45, height=6)
        self.listbox.pack(fill=tk.X)
        for tgt in self.targets:
            self.listbox.insert(tk.END, f"{tgt.label} ({tgt.host}:{tgt.port})")

        btns = ttk.Frame(frame)
        btns.pack(fill=tk.X, pady=6)
        ttk.Button(btns, text="新增", command=self._add_target).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="移除", command=self._remove_target).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="保存", command=self._save).pack(side=tk.RIGHT, padx=4)

    def _add_target(self) -> None:
        row = simpledialog.askstring("新增联系人", "标签,主机,端口,邮箱（逗号分隔，端口或邮箱可留空）", parent=self)
        if not row:
            return
        try:
            parts = [part.strip() for part in row.split(",")]
            label, host = parts[0], parts[1]
            port_int = int(parts[2]) if len(parts) > 2 and parts[2] else None
            email = parts[3] if len(parts) > 3 else ""
        except ValueError:
            messagebox.showerror("格式错误", "请输入：标签,主机,端口,邮箱")
            return
        from .models import LanTarget  # local import to avoid cycle

        self.targets.append(LanTarget(label=label, host=host, port=port_int, email=email))
        suffix = f"{host}:{port_int}" if port_int else host
        if email:
            suffix += f" | {email}"
        self.listbox.insert(tk.END, f"{label} ({suffix})")

    def _remove_target(self) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        self.listbox.delete(idx)
        self.targets.pop(idx)

    def _save(self) -> None:
        self.result = self.targets
        self.destroy()


class ConferencePickDialog(tk.Toplevel):
    """选择会议以发送提醒的对话框。"""

    def __init__(self, master: tk.Widget, conferences: List[ConferenceEvent]) -> None:
        super().__init__(master)
        self.title("选择会议")
        self.result: Optional[List[ConferenceEvent]] = None
        self.conferences = conferences
        self._build_ui()

    def _build_ui(self) -> None:
        self.resizable(False, False)
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="请选择要发送提醒的会议（可多选）：").pack(anchor=tk.W, pady=(0, 6))
        self.listbox = tk.Listbox(frame, selectmode=tk.MULTIPLE, width=48, height=10)
        for conf in self.conferences:
            text = f"{conf.name} | {conf.category} | 截止 {conf.submission_deadline}"
            self.listbox.insert(tk.END, text)
        self.listbox.pack(fill=tk.BOTH, expand=True)

        btns = ttk.Frame(frame)
        btns.pack(fill=tk.X, pady=8)
        ttk.Button(btns, text="取消", command=self.destroy).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btns, text="发送", command=self._confirm).pack(side=tk.RIGHT, padx=4)

    def _confirm(self) -> None:
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showinfo("未选择", "请先选择需要提醒的会议。")
            return
        self.result = [self.conferences[i] for i in selection]
        self.destroy()
