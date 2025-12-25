"""Conference tab UI for CCF deadline tracking and LAN notifications.

在你当前版本基础上合并增强：
- 修复 Treeview 滚动条绑定（yscrollcommand）
- 发送提醒：先自动匹配（默认勾选），再弹窗手动确认/调整后发送；即使自动匹配为空也会弹窗
- 发送提醒候选池：遵循“等级筛选”，不被 show_all 的展示逻辑卡死
- 表单回填对 None 更健壮
- LAN 联系人新增解析更健壮 + 显示格式统一
- 更专业的布局：grid 自适应、统一间距、Text/Listbox 增加滚动条
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Callable, List, Optional, Set

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

    # ---------------------------------------------------------------------
    # UI
    # ---------------------------------------------------------------------
    def _build_widgets(self) -> None:
        # root grid
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        controls = ttk.LabelFrame(self, text="会议筛选", padding=10)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self._build_controls(controls)

        main = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main.grid(row=1, column=0, sticky="nsew")

        list_frame = ttk.Frame(main, padding=(0, 0, 8, 0))
        form_frame = ttk.LabelFrame(main, text="新增 / 编辑", padding=12)

        self._build_table(list_frame)
        self._build_form(form_frame)

        main.add(list_frame, weight=3)
        main.add(form_frame, weight=2)

    def _build_controls(self, controls: ttk.LabelFrame) -> None:
        # columns layout:
        # 0 label, 1 combo(stretch), 2 label, 3 entry, 4 check, 5 spacer, 6 apply, 7 send, 8 pick
        for c in range(9):
            controls.columnconfigure(c, weight=0)
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(5, weight=1)

        ttk.Label(controls, text="等级：").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        self.category_filter = ttk.Combobox(
            controls, values=["全部", "CCF-A", "CCF-B", "CCF-C"], state="readonly", width=12
        )
        self.category_filter.set("全部")
        self.category_filter.grid(row=0, column=1, sticky="ew", pady=2)
        self.category_filter.bind("<<ComboboxSelected>>", lambda _e: self.refresh_list())

        ttk.Label(controls, text="截止天数：").grid(row=0, column=2, sticky="w", padx=(14, 6), pady=2)
        self.window_entry = ttk.Entry(controls, width=10)
        self.window_entry.insert(0, str(self.config.conference_window_days))
        self.window_entry.grid(row=0, column=3, sticky="w", pady=2)
        self.window_entry.bind("<Return>", lambda _e: self.refresh_list())
        self.window_entry.bind("<FocusOut>", lambda _e: self._normalize_window_days())

        self.show_all_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            controls, text="显示全部", variable=self.show_all_var, command=self.refresh_list
        ).grid(row=0, column=4, sticky="w", padx=(14, 0), pady=2)

        ttk.Button(controls, text="应用筛选", command=self.refresh_list, width=10).grid(
            row=0, column=6, sticky="e", padx=(0, 6), pady=2
        )
        ttk.Button(controls, text="发送提醒", command=self._send_lan, width=10).grid(
            row=0, column=7, sticky="e", padx=(0, 6), pady=2
        )
        ttk.Button(controls, text="选择会议发送", command=self._pick_and_send, width=14).grid(
            row=0, column=8, sticky="e", pady=2
        )

    def _build_table(self, container: ttk.Frame) -> None:
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        columns = ("name", "category", "deadline", "location")
        self.tree = ttk.Treeview(container, columns=columns, show="headings", selectmode="extended")
        headings = ["名称", "等级", "截稿", "地点"]

        for col, head in zip(columns, headings):
            self.tree.heading(col, text=head)
            if col == "name":
                self.tree.column(col, anchor=tk.W, width=240, stretch=True)
            elif col == "location":
                self.tree.column(col, anchor=tk.W, width=200, stretch=True)
            else:
                self.tree.column(col, anchor=tk.W, width=120, stretch=False)

        # Scrollbars (FIX: yscrollcommand)
        ysb = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.tree.yview)
        xsb = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.tag_configure("overdue", background="#ffe6e6")

        tip = ttk.Label(
            container,
            text="提示：点击「发送提醒」会先自动匹配并默认勾选，再弹窗让你手动确认后发送（无匹配也会弹窗）。",
        )
        tip.grid(row=2, column=0, sticky="w", pady=(8, 0))

    def _build_form(self, container: ttk.LabelFrame) -> None:
        container.columnconfigure(0, weight=0)
        container.columnconfigure(1, weight=1)

        labels = ["名称", "等级", "截稿日期 (YYYY-MM-DD)", "地点", "链接", "备注"]
        for idx, label in enumerate(labels):
            ttk.Label(container, text=label).grid(row=idx, column=0, sticky="w", pady=4, padx=(0, 10))

        self.name_entry = ttk.Entry(container)
        self.category_entry = ttk.Combobox(container, values=["CCF-A", "CCF-B", "CCF-C"], state="readonly")
        self.deadline_entry = ttk.Entry(container)
        self.location_entry = ttk.Entry(container)
        self.url_entry = ttk.Entry(container)

        self.name_entry.grid(row=0, column=1, sticky="ew", pady=4)
        self.category_entry.grid(row=1, column=1, sticky="ew", pady=4)
        self.deadline_entry.grid(row=2, column=1, sticky="ew", pady=4)
        self.location_entry.grid(row=3, column=1, sticky="ew", pady=4)
        self.url_entry.grid(row=4, column=1, sticky="ew", pady=4)

        # Note: Text + scrollbar
        note_wrap = ttk.Frame(container)
        note_wrap.grid(row=5, column=1, sticky="nsew", pady=4)
        note_wrap.columnconfigure(0, weight=1)
        note_wrap.rowconfigure(0, weight=1)

        self.note_text = tk.Text(note_wrap, height=5, wrap="word")
        note_ysb = ttk.Scrollbar(note_wrap, orient=tk.VERTICAL, command=self.note_text.yview)
        self.note_text.configure(yscrollcommand=note_ysb.set)
        self.note_text.grid(row=0, column=0, sticky="nsew")
        note_ysb.grid(row=0, column=1, sticky="ns")

        btns = ttk.Frame(container)
        btns.grid(row=len(labels), column=0, columnspan=2, sticky="ew", pady=(10, 4))
        left = ttk.Frame(btns)
        left.pack(side=tk.LEFT)

        ttk.Button(left, text="新建", command=self._clear_form).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(left, text="保存", command=self._save_conference).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(left, text="删除", command=self._delete_conference).pack(side=tk.LEFT)

        # LAN targets
        targets = ttk.LabelFrame(container, text="局域网联系人", padding=8)
        targets.grid(row=len(labels) + 1, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        targets.columnconfigure(0, weight=1)
        targets.rowconfigure(0, weight=1)

        list_wrap = ttk.Frame(targets)
        list_wrap.grid(row=0, column=0, sticky="nsew")
        list_wrap.columnconfigure(0, weight=1)
        list_wrap.rowconfigure(0, weight=1)

        self.lan_list = tk.Listbox(list_wrap, height=6)
        lan_ysb = ttk.Scrollbar(list_wrap, orient=tk.VERTICAL, command=self.lan_list.yview)
        self.lan_list.configure(yscrollcommand=lan_ysb.set)
        self.lan_list.grid(row=0, column=0, sticky="nsew")
        lan_ysb.grid(row=0, column=1, sticky="ns")

        self._refresh_lan_listbox()
        ttk.Button(targets, text="管理联系人", command=self._edit_lan_targets).grid(
            row=1, column=0, sticky="e", pady=(6, 0)
        )

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------
    def _normalize_window_days(self) -> int:
        try:
            window_days = int(self.window_entry.get())
            if window_days < 0:
                raise ValueError
        except ValueError:
            window_days = self.config.conference_window_days
            self.window_entry.delete(0, tk.END)
            self.window_entry.insert(0, str(window_days))
        return window_days

    def _get_display_filtered_confs(self) -> List[ConferenceEvent]:
        """List display filter: respects category + show_all + window_days."""
        category = self.category_filter.get()
        window_days = self._normalize_window_days()

        filtered: List[ConferenceEvent] = []
        for conf in self.conferences:
            if category not in ("", "全部") and conf.category != category:
                continue
            if not self.show_all_var.get() and not (conf.is_due_within(window_days) or conf.is_overdue()):
                continue
            filtered.append(conf)
        return filtered

    def _get_category_candidates(self) -> List[ConferenceEvent]:
        """Sending candidate pool: respects category ONLY (not blocked by show_all)."""
        category = self.category_filter.get()
        candidates: List[ConferenceEvent] = []
        for conf in self.conferences:
            if category not in ("", "全部") and conf.category != category:
                continue
            candidates.append(conf)
        return candidates

    def _format_lan_target(self, target) -> str:
        suffix = f"{target.host}:{target.port}" if getattr(target, "port", None) else target.host
        email = getattr(target, "email", "") or ""
        if email:
            suffix += f" | {email}"
        return f"{target.label} ({suffix})"

    def _refresh_lan_listbox(self) -> None:
        self.lan_list.delete(0, tk.END)
        for target in self.config.lan_targets:
            self.lan_list.insert(tk.END, self._format_lan_target(target))

    # ---------------------------------------------------------------------
    # List / config refresh
    # ---------------------------------------------------------------------
    def refresh_list(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        filtered = self._get_display_filtered_confs()
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
        self.config = config
        self.window_entry.delete(0, tk.END)
        self.window_entry.insert(0, str(config.conference_window_days))
        self._refresh_lan_listbox()

    # ---------------------------------------------------------------------
    # Selection -> form fill (None-safe)
    # ---------------------------------------------------------------------
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
        self.name_entry.insert(0, conf.name or "")

        self.category_entry.set(conf.category or "CCF-A")

        self.deadline_entry.delete(0, tk.END)
        self.deadline_entry.insert(0, conf.submission_deadline or "")

        self.location_entry.delete(0, tk.END)
        self.location_entry.insert(0, conf.location or "")

        self.url_entry.delete(0, tk.END)
        self.url_entry.insert(0, conf.url or "")

        self.note_text.delete("1.0", tk.END)
        self.note_text.insert("1.0", conf.note or "")

    def _clear_form(self) -> None:
        self.selected_id = None
        for entry in [self.name_entry, self.deadline_entry, self.location_entry, self.url_entry]:
            entry.delete(0, tk.END)
        self.category_entry.set("")
        self.note_text.delete("1.0", tk.END)

    # ---------------------------------------------------------------------
    # CRUD
    # ---------------------------------------------------------------------
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

    # ---------------------------------------------------------------------
    # Notifications
    # ---------------------------------------------------------------------
    def _send_lan(self) -> None:
        """
        发送提醒：
        - 先自动匹配（window_days 内到期或已过期）作为默认勾选
        - 弹窗让用户手动确认/调整后发送
        - 即使自动匹配为空，也会弹窗（让用户手动选择）
        - 候选池仅遵循“等级筛选”，不被 show_all 限制
        """
        if not self.config.lan_targets:
            messagebox.showinfo("尚无联系人", "请先添加局域网联系人。")
            return

        window_days = self._normalize_window_days()

        candidates = self._get_category_candidates()
        if not candidates:
            messagebox.showinfo("暂无会议", "当前等级筛选下没有会议记录。")
            return

        auto_ids: Set[str] = {c.id for c in candidates if (c.is_due_within(window_days) or c.is_overdue())}

        # 如果用户在表格里已有选择，则优先作为默认勾选（更符合直觉）
        selection = self.tree.selection()
        preselect_ids = set(selection) if selection else auto_ids  # 允许为空

        dialog = ConferencePickDialog(self, candidates, preselect_ids=preselect_ids)
        self.wait_window(dialog)
        if not dialog.result:
            return

        self._dispatch_notifications(dialog.result)

    def _pick_and_send(self) -> None:
        """完全手动选择发送（仍遵循等级筛选；若表格有选中则作为默认勾选）。"""
        candidates = self._get_category_candidates()
        if not candidates:
            messagebox.showinfo("暂无会议", "当前等级筛选下没有会议记录。")
            return

        selection = self.tree.selection()
        preselect_ids = set(selection) if selection else set()

        dialog = ConferencePickDialog(self, candidates, preselect_ids=preselect_ids)
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
        self.transient(master)
        self.grab_set()

    def _build_ui(self) -> None:
        self.resizable(False, False)
        frame = ttk.Frame(self, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        list_wrap = ttk.Frame(frame)
        list_wrap.grid(row=0, column=0, sticky="nsew")
        list_wrap.columnconfigure(0, weight=1)
        list_wrap.rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(list_wrap, width=55, height=8)
        ysb = ttk.Scrollbar(list_wrap, orient=tk.VERTICAL, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=ysb.set)
        self.listbox.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")

        for tgt in self.targets:
            suffix = f"{tgt.host}:{tgt.port}" if getattr(tgt, "port", None) else tgt.host
            email = getattr(tgt, "email", "") or ""
            if email:
                suffix += f" | {email}"
            self.listbox.insert(tk.END, f"{tgt.label} ({suffix})")

        ttk.Label(frame, text="新增格式：标签,主机,端口,邮箱（端口/邮箱可留空）").grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )

        btns = ttk.Frame(frame)
        btns.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(btns, text="新增", command=self._add_target, width=10).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btns, text="移除", command=self._remove_target, width=10).pack(side=tk.LEFT)
        ttk.Button(btns, text="取消", command=self._cancel, width=10).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(btns, text="保存", command=self._save, width=10).pack(side=tk.RIGHT)

    def _add_target(self) -> None:
        row = simpledialog.askstring(
            "新增联系人",
            "标签,主机,端口,邮箱（逗号分隔，端口或邮箱可留空）",
            parent=self,
        )
        if not row:
            return

        try:
            parts = [part.strip() for part in row.split(",")]
            if len(parts) < 2 or not parts[0] or not parts[1]:
                raise ValueError("missing label/host")
            label, host = parts[0], parts[1]
            port_int = int(parts[2]) if len(parts) > 2 and parts[2] else None
            email = parts[3] if len(parts) > 3 else ""
        except (ValueError, IndexError):
            messagebox.showerror("格式错误", "请输入：标签,主机,端口,邮箱（端口/邮箱可留空）")
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

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


class ConferencePickDialog(tk.Toplevel):
    """选择会议以发送提醒的对话框（支持默认勾选）。"""

    def __init__(
        self,
        master: tk.Widget,
        conferences: List[ConferenceEvent],
        preselect_ids: Optional[Set[str]] = None,
    ) -> None:
        super().__init__(master)
        self.title("选择会议")
        self.result: Optional[List[ConferenceEvent]] = None
        self.conferences = conferences
        self.preselect_ids = preselect_ids or set()
        self._build_ui()
        self.transient(master)
        self.grab_set()

    def _build_ui(self) -> None:
        self.resizable(False, False)
        frame = ttk.Frame(self, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        ttk.Label(
            frame,
            text="请确认要发送提醒的会议（已自动勾选到期/过期项；若未匹配到，也可手动选择）：",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        list_wrap = ttk.Frame(frame)
        list_wrap.grid(row=1, column=0, sticky="nsew")
        list_wrap.columnconfigure(0, weight=1)
        list_wrap.rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(list_wrap, selectmode=tk.MULTIPLE, width=70, height=12)
        ysb = ttk.Scrollbar(list_wrap, orient=tk.VERTICAL, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=ysb.set)

        first_selected_idx: Optional[int] = None
        for i, conf in enumerate(self.conferences):
            text = f"{conf.name} | {conf.category} | 截止 {conf.submission_deadline}"
            self.listbox.insert(tk.END, text)
            if conf.id in self.preselect_ids:
                self.listbox.select_set(i)
                if first_selected_idx is None:
                    first_selected_idx = i

        self.listbox.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")

        if first_selected_idx is not None:
            self.listbox.see(first_selected_idx)

        tools = ttk.Frame(frame)
        tools.grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Button(tools, text="全选", command=self._select_all, width=8).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(tools, text="清空", command=self._clear_all, width=8).pack(side=tk.LEFT)

        btns = ttk.Frame(frame)
        btns.grid(row=3, column=0, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="取消", command=self.destroy, width=10).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(btns, text="发送", command=self._confirm, width=10).pack(side=tk.RIGHT)

    def _select_all(self) -> None:
        self.listbox.select_set(0, tk.END)

    def _clear_all(self) -> None:
        self.listbox.selection_clear(0, tk.END)

    def _confirm(self) -> None:
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showinfo("未选择", "请先选择需要提醒的会议。")
            return
        self.result = [self.conferences[i] for i in selection]
        self.destroy()
