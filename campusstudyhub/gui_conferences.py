# -*- coding: utf-8 -*-
"""
gui_conferences.py (Dark UI, polished + stable version)

Features
- Left: recipients (add/edit/delete, checkbox select)
- Right: conference list (filter, favorite, batch actions)
- Reminder: manual select / auto match preview -> confirm dialog -> async send
- Treeview dark styling (scoped style name, does not override global Treeview)
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, List, Optional, Sequence, Set, Tuple, Any

import customtkinter as ctk

from .config import AppConfig
from .lan import send_lan_notifications
from .models import ConferenceEvent
from .storage import load_conferences, save_conferences


# =============================================================================
# Helpers & Constants
# =============================================================================
CHECK_ON = "☑"
CHECK_OFF = "☐"

TREEVIEW_BG = "#2b2b2b"
TREEVIEW_FG = "#dce4ee"
TREEVIEW_SEL_BG = "#1f538d"
HEADER_BG = "#3a3a3a"
HEADER_FG = "#ffffff"


def _safe_str(x: object) -> str:
    return "" if x is None else str(x)


def _try_int(s: str, default: int) -> int:
    try:
        v = int(str(s).strip())
        if v < 0:
            return default
        return v
    except Exception:
        return default


def _clamp_int(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _parse_date_yyyy_mm_dd(date_str: str) -> str:
    """
    Validate and normalize YYYY-MM-DD.
    Returns normalized string if ok; raises ValueError otherwise.
    """
    d = datetime.strptime(date_str.strip(), "%Y-%m-%d")
    return d.strftime("%Y-%m-%d")


_STYLE_DONE = False


def setup_treeview_style_scoped() -> None:
    """
    Define a scoped ttk style for Treeview under dark theme.
    Won't override the default 'Treeview' style globally.
    """
    global _STYLE_DONE
    if _STYLE_DONE:
        return

    style = ttk.Style()
    try:
        # clam is more customizable; may affect global theme in ttk,
        # but styling name is still scoped and won't override "Treeview".
        style.theme_use("clam")
    except Exception:
        pass

    style.configure(
        "Conf.Treeview",
        background=TREEVIEW_BG,
        foreground=TREEVIEW_FG,
        fieldbackground=TREEVIEW_BG,
        borderwidth=0,
        font=("Arial", 11),
        rowheight=26,
    )
    style.map("Conf.Treeview", background=[("selected", TREEVIEW_SEL_BG)])

    style.configure(
        "Conf.Treeview.Heading",
        background=HEADER_BG,
        foreground=HEADER_FG,
        relief="flat",
        font=("Arial", 11, "bold"),
    )
    style.map("Conf.Treeview.Heading", background=[("active", "#4a4a4a")])

    _STYLE_DONE = True


@dataclass
class LanTargetLite:
    """
    A stable recipient record.
    Keep attribute names compatible with your existing code (label/email/host/port).
    """
    label: str
    email: str
    host: str = "-"
    port: int = 0


def _ensure_target_obj(name: str, email: str) -> Any:
    """
    Create a target object compatible with existing config storage.

    - Prefer LanTargetLite (stable, picklable).
    - If your config persistence is JSON-only and fails on dataclass,
      you can easily swap this to a dict-like object + adapter later.
    """
    return LanTargetLite(label=name, email=email, host="-", port=0)


# =============================================================================
# Main Frame
# =============================================================================
class ConferencesFrame(ctk.CTkFrame):
    def __init__(
        self,
        master: tk.Widget,
        config: AppConfig,
        on_config_update: Callable[[AppConfig], None],
    ) -> None:
        super().__init__(master)
        self.config = config
        self.on_config_update = on_config_update

        # Data
        self.conferences: List[ConferenceEvent] = load_conferences()
        self._fav_ids: Set[str] = set()

        # Variables
        self.keyword_var = tk.StringVar(value="")
        self.category_var = tk.StringVar(value="全部")
        self.refresh_min_var = tk.StringVar(value="60")
        self.show_tab_var = tk.StringVar(value="all")  # "all" or "fav"

        # Auto-remind settings
        self.window_days_var = tk.StringVar(value=str(getattr(self.config, "conference_window_days", 7)))
        self.include_overdue_var = tk.BooleanVar(value=True)

        self._after_id: Optional[str] = None
        self._sending = False

        setup_treeview_style_scoped()

        self._build_ui()
        self._rebuild_fav_set()
        self.refresh_targets()
        self.refresh_conference_list()
        self._schedule_auto_refresh()

    # -------------------------------------------------------------------------
    # UI
    # -------------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=5)
        self.rowconfigure(1, weight=1)

        title = ctk.CTkLabel(self, text="会议通知中心", font=("Arial", 20, "bold"))
        title.grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 6))

        left_panel = ctk.CTkFrame(self)
        left_panel.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=(6, 12))
        self._build_left(left_panel)

        right_panel = ctk.CTkFrame(self)
        right_panel.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=(6, 12))
        self._build_right(right_panel)

    # -------------------------------------------------------------------------
    # Left Panel (Targets)
    # -------------------------------------------------------------------------
    def _build_left(self, parent: ctk.CTkFrame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        ctk.CTkLabel(header, text="通知对象", font=("Arial", 14, "bold")).pack(side="left")

        # Buttons row
        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 8))

        ctk.CTkButton(btn_row, text="全选", width=60, height=26, command=self.select_all_targets).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row, text="反选", width=60, height=26, command=self.invert_targets).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row, text="编辑", width=60, height=26, fg_color="transparent", border_width=1, command=self.edit_selected_target).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row, text="删除", width=60, height=26, fg_color="transparent", border_width=1, command=self.delete_selected_target).pack(side="left")

        ctk.CTkButton(btn_row, text="邮件设置", width=84, height=26, fg_color="transparent", border_width=1, command=self._open_email_settings).pack(side="right")

        # Treeview container
        tree_frame = ctk.CTkFrame(parent, fg_color="transparent")
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(6, 4))
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        cols = ("check", "label", "info")
        self.targets_tree = ttk.Treeview(
            tree_frame,
            columns=cols,
            show="headings",
            selectmode="browse",
            style="Conf.Treeview",
        )
        self.targets_tree.heading("check", text="选")
        self.targets_tree.heading("label", text="姓名")
        self.targets_tree.heading("info", text="邮箱/信息")

        self.targets_tree.column("check", width=40, anchor="center", stretch=False)
        self.targets_tree.column("label", width=110, anchor="w", stretch=False)
        self.targets_tree.column("info", width=220, anchor="w")

        ysb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.targets_tree.yview)
        self.targets_tree.configure(yscrollcommand=ysb.set)

        self.targets_tree.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")

        self.targets_tree.bind("<Button-1>", self._on_targets_click)
        self.targets_tree.bind("<Double-1>", lambda e: self.edit_selected_target())

        # Add target row
        add_frame = ctk.CTkFrame(parent)
        add_frame.grid(row=3, column=0, sticky="ew", padx=12, pady=(4, 10))

        self.t_name_var = tk.StringVar()
        self.t_email_var = tk.StringVar()

        ctk.CTkEntry(add_frame, textvariable=self.t_name_var, placeholder_text="姓名", width=90).pack(side="left", padx=8, pady=8)
        ctk.CTkEntry(add_frame, textvariable=self.t_email_var, placeholder_text="邮箱地址", width=220).pack(
            side="left", padx=(0, 8), pady=8, fill="x", expand=True
        )
        ctk.CTkButton(add_frame, text="+ 添加", width=72, command=self.add_target_inline).pack(side="left", padx=(0, 8), pady=8)

        # Send section
        send_frame = ctk.CTkFrame(parent, fg_color="transparent")
        send_frame.grid(row=4, column=0, sticky="ew", padx=12, pady=(2, 12))

        auto_row = ctk.CTkFrame(send_frame, fg_color="transparent")
        auto_row.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(auto_row, text="自动匹配: 提前").pack(side="left")
        ctk.CTkEntry(auto_row, textvariable=self.window_days_var, width=52).pack(side="left", padx=6)
        ctk.CTkLabel(auto_row, text="天").pack(side="left")
        ctk.CTkCheckBox(auto_row, text="含过期", variable=self.include_overdue_var, width=80).pack(side="left", padx=10)

        self.btn_auto_send = ctk.CTkButton(
            send_frame,
            text="自动预览发送",
            fg_color="#E08e00",
            hover_color="#B06e00",
            command=self.auto_remind_preview,
        )
        self.btn_auto_send.pack(fill="x", pady=3)

        self.btn_manual_send = ctk.CTkButton(
            send_frame,
            text="手动发送（先选会议再选人）",
            command=self.send_reminder_manual,
        )
        self.btn_manual_send.pack(fill="x", pady=(3, 0))

    # -------------------------------------------------------------------------
    # Right Panel (Conferences)
    # -------------------------------------------------------------------------
    def _build_right(self, parent: ctk.CTkFrame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)

        # Toolbar
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))

        ctk.CTkEntry(toolbar, textvariable=self.keyword_var, placeholder_text="搜索会议...", width=180).pack(side="left", padx=(0, 10))
        ctk.CTkComboBox(toolbar, variable=self.category_var, values=["全部", "CCF-A", "CCF-B", "CCF-C"], width=110).pack(
            side="left", padx=(0, 10)
        )
        ctk.CTkButton(toolbar, text="过滤", width=60, command=self.refresh_conference_list).pack(side="left")

        # Auto refresh control (minutes)
        right_box = ctk.CTkFrame(toolbar, fg_color="transparent")
        right_box.pack(side="right")

        ctk.CTkButton(right_box, text="↻ 刷新", width=80, fg_color="transparent", border_width=1, command=self.manual_refresh).pack(
            side="right", padx=(10, 0)
        )
        ctk.CTkButton(right_box, text="+ 新增会议", width=110, command=self.open_add_conf_dialog).pack(side="right", padx=(10, 0))

        ctk.CTkLabel(right_box, text="自动刷新(分钟)").pack(side="right", padx=(10, 6))
        ctk.CTkEntry(right_box, textvariable=self.refresh_min_var, width=60).pack(side="right")
        ctk.CTkButton(right_box, text="应用", width=60, fg_color="transparent", border_width=1, command=self._apply_refresh_minutes).pack(
            side="right", padx=(6, 0)
        )

        # Tabs
        tab_frame = ctk.CTkFrame(parent, fg_color="transparent")
        tab_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))

        self.seg_tab = ctk.CTkSegmentedButton(tab_frame, values=["全部会议", "我的关注"], command=self._on_tab_change)
        self.seg_tab.set("全部会议")
        self.seg_tab.pack(side="left")

        # Treeview list
        tree_box = ctk.CTkFrame(parent, fg_color="transparent")
        tree_box.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 6))
        tree_box.rowconfigure(0, weight=1)
        tree_box.columnconfigure(0, weight=1)

        cols = ("check", "fav", "name", "cat", "deadline", "remind")
        self.conf_tree = ttk.Treeview(
            tree_box,
            columns=cols,
            show="headings",
            selectmode="extended",
            style="Conf.Treeview",
        )

        self.conf_tree.heading("check", text="选")
        self.conf_tree.heading("fav", text="★")
        self.conf_tree.heading("name", text="会议名称")
        self.conf_tree.heading("cat", text="等级")
        self.conf_tree.heading("deadline", text="截止日期")
        self.conf_tree.heading("remind", text="提醒")

        self.conf_tree.column("check", width=40, anchor="center", stretch=False)
        self.conf_tree.column("fav", width=40, anchor="center", stretch=False)
        self.conf_tree.column("name", width=360, anchor="w")
        self.conf_tree.column("cat", width=70, anchor="center", stretch=False)
        self.conf_tree.column("deadline", width=110, anchor="w", stretch=False)
        self.conf_tree.column("remind", width=90, anchor="w", stretch=False)

        ysb = ttk.Scrollbar(tree_box, orient="vertical", command=self.conf_tree.yview)
        self.conf_tree.configure(yscrollcommand=ysb.set)

        self.conf_tree.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")

        self.conf_tree.bind("<Button-1>", self._on_conf_click)
        self.conf_tree.tag_configure("overdue", foreground="#ff6b6b")

        # Action bar
        action_bar = ctk.CTkFrame(parent, fg_color="transparent")
        action_bar.grid(row=3, column=0, sticky="ew", padx=12, pady=(6, 12))

        ctk.CTkButton(action_bar, text="全选", width=60, height=30, fg_color="transparent", border_width=1, command=self.select_all_confs).pack(
            side="left", padx=(0, 6)
        )
        ctk.CTkButton(action_bar, text="清空", width=60, height=30, fg_color="transparent", border_width=1, command=self.clear_conf_selection).pack(
            side="left", padx=(0, 10)
        )
        ctk.CTkLabel(action_bar, text="|", text_color="gray").pack(side="left", padx=(0, 10))

        ctk.CTkButton(action_bar, text="编辑", width=70, height=30, command=self.edit_selected_conf).pack(side="left", padx=(0, 6))
        ctk.CTkButton(action_bar, text="关注/取关", width=90, height=30, command=self.toggle_favorite_selected).pack(side="left", padx=(0, 6))

        ctk.CTkButton(action_bar, text="删除", width=70, height=30, fg_color="#b33636", hover_color="#8f2a2a", command=self.delete_selected_conf).pack(
            side="right"
        )

    # -------------------------------------------------------------------------
    # Targets logic
    # -------------------------------------------------------------------------
    def refresh_targets(self) -> None:
        for i in self.targets_tree.get_children():
            self.targets_tree.delete(i)

        targets = list(getattr(self.config, "lan_targets", []) or [])
        for idx, t in enumerate(targets):
            label = getattr(t, "label", f"User {idx}")
            email = getattr(t, "email", "")
            self.targets_tree.insert("", tk.END, iid=str(idx), values=(CHECK_OFF, label, email))

    def _on_targets_click(self, event: tk.Event) -> None:
        region = self.targets_tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self.targets_tree.identify_column(event.x)
        if col != "#1":
            return
        item = self.targets_tree.identify_row(event.y)
        if not item:
            return
        vals = list(self.targets_tree.item(item, "values"))
        vals[0] = CHECK_OFF if vals[0] == CHECK_ON else CHECK_ON
        self.targets_tree.item(item, values=vals)

    def select_all_targets(self) -> None:
        for item in self.targets_tree.get_children():
            vals = list(self.targets_tree.item(item, "values"))
            vals[0] = CHECK_ON
            self.targets_tree.item(item, values=vals)

    def invert_targets(self) -> None:
        for item in self.targets_tree.get_children():
            vals = list(self.targets_tree.item(item, "values"))
            vals[0] = CHECK_OFF if vals[0] == CHECK_ON else CHECK_ON
            self.targets_tree.item(item, values=vals)

    def get_checked_targets(self) -> List[Any]:
        targets = list(getattr(self.config, "lan_targets", []) or [])
        out: List[Any] = []
        for item in self.targets_tree.get_children():
            vals = self.targets_tree.item(item, "values")
            if vals and vals[0] == CHECK_ON:
                try:
                    idx = int(item)
                    if 0 <= idx < len(targets):
                        out.append(targets[idx])
                except Exception:
                    pass
        return out

    def _get_selected_target_index(self) -> Optional[int]:
        sel = self.targets_tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except Exception:
            return None

    def add_target_inline(self) -> None:
        name = self.t_name_var.get().strip()
        email = self.t_email_var.get().strip()
        if not name or not email:
            messagebox.showwarning("提示", "请填写姓名和邮箱")
            return

        new_t = _ensure_target_obj(name, email)

        current = list(getattr(self.config, "lan_targets", []) or [])
        current.append(new_t)
        self.config.lan_targets = current
        self.on_config_update(self.config)

        self.refresh_targets()
        self.t_name_var.set("")
        self.t_email_var.set("")

    def edit_selected_target(self) -> None:
        idx = self._get_selected_target_index()
        targets = list(getattr(self.config, "lan_targets", []) or [])
        if idx is None or not (0 <= idx < len(targets)):
            messagebox.showinfo("提示", "请先在联系人列表中选择一个联系人（可双击编辑）")
            return

        t = targets[idx]
        EditTargetDialog(self, t, on_save=lambda: self._on_target_modified())

    def delete_selected_target(self) -> None:
        idx = self._get_selected_target_index()
        targets = list(getattr(self.config, "lan_targets", []) or [])
        if idx is None or not (0 <= idx < len(targets)):
            messagebox.showinfo("提示", "请先选择一个联系人")
            return

        t = targets[idx]
        label = getattr(t, "label", "该联系人")
        if not messagebox.askyesno("确认删除", f"确定删除联系人：{label} ?"):
            return

        targets.pop(idx)
        self.config.lan_targets = targets
        self.on_config_update(self.config)
        self.refresh_targets()

    def _on_target_modified(self) -> None:
        self.on_config_update(self.config)
        self.refresh_targets()

    # -------------------------------------------------------------------------
    # Conference logic
    # -------------------------------------------------------------------------
    def _rebuild_fav_set(self) -> None:
        self._fav_ids = {c.id for c in self.conferences if getattr(c, "favorite", False)}

    def _on_tab_change(self, value: str) -> None:
        self.show_tab_var.set("fav" if value == "我的关注" else "all")
        self.refresh_conference_list()

    def refresh_conference_list(self) -> None:
        self._rebuild_fav_set()

        for i in self.conf_tree.get_children():
            self.conf_tree.delete(i)

        cat_filter = self.category_var.get()
        kw_filter = self.keyword_var.get().lower().strip()
        tab_filter = self.show_tab_var.get()

        for c in self.conferences:
            if cat_filter != "全部" and c.category != cat_filter:
                continue
            if tab_filter == "fav" and not getattr(c, "favorite", False):
                continue
            if kw_filter and kw_filter not in c.name.lower():
                continue

            fav_mark = "★" if getattr(c, "favorite", False) else "☆"
            remind_days = getattr(c, "remind_before_days", None)
            remind_txt = f"提前{remind_days}天" if isinstance(remind_days, int) else "默认"

            tags = ()
            try:
                if c.is_overdue():
                    tags = ("overdue",)
            except Exception:
                # 不吞掉：只是不影响渲染
                tags = ()

            self.conf_tree.insert(
                "",
                tk.END,
                iid=c.id,
                values=(CHECK_OFF, fav_mark, c.name, c.category, c.submission_deadline, remind_txt),
                tags=tags,
            )

    def _on_conf_click(self, event: tk.Event) -> None:
        region = self.conf_tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        col = self.conf_tree.identify_column(event.x)
        item = self.conf_tree.identify_row(event.y)
        if not item:
            return

        if col == "#1":
            vals = list(self.conf_tree.item(item, "values"))
            vals[0] = CHECK_OFF if vals[0] == CHECK_ON else CHECK_ON
            self.conf_tree.item(item, values=vals)
        elif col == "#2":
            self._toggle_fav_single(item)

    def _toggle_fav_single(self, conf_id: str) -> None:
        conf = next((c for c in self.conferences if c.id == conf_id), None)
        if not conf:
            return
        cur = bool(getattr(conf, "favorite", False))
        setattr(conf, "favorite", not cur)
        save_conferences(self.conferences)
        self.refresh_conference_list()

    def get_checked_confs(self) -> List[ConferenceEvent]:
        checked: List[ConferenceEvent] = []
        highlighted: List[ConferenceEvent] = []
        map_confs = {c.id: c for c in self.conferences}

        for item in self.conf_tree.get_children():
            vals = self.conf_tree.item(item, "values")
            if vals and vals[0] == CHECK_ON and item in map_confs:
                checked.append(map_confs[item])

        for item in self.conf_tree.selection():
            if item in map_confs:
                highlighted.append(map_confs[item])

        return checked if checked else highlighted

    def select_all_confs(self) -> None:
        for item in self.conf_tree.get_children():
            vals = list(self.conf_tree.item(item, "values"))
            vals[0] = CHECK_ON
            self.conf_tree.item(item, values=vals)

    def clear_conf_selection(self) -> None:
        for item in self.conf_tree.get_children():
            vals = list(self.conf_tree.item(item, "values"))
            vals[0] = CHECK_OFF
            self.conf_tree.item(item, values=vals)
        # ✅ 修复：selection_remove 需要 *items
        self.conf_tree.selection_remove(*self.conf_tree.selection())

    # -------------------------------------------------------------------------
    # Operations
    # -------------------------------------------------------------------------
    def open_add_conf_dialog(self) -> None:
        AddConferenceDialog(self, self._on_add_conf_save)

    def _on_add_conf_save(self, new_conf: ConferenceEvent) -> None:
        self.conferences.append(new_conf)
        save_conferences(self.conferences)
        self.refresh_conference_list()

    def edit_selected_conf(self) -> None:
        targets = self.get_checked_confs()
        if len(targets) != 1:
            messagebox.showwarning("提示", "请选择且仅选择一个会议进行编辑（勾选或高亮均可）")
            return
        EditConferenceDialog(self, targets[0], self._on_edit_save)

    def _on_edit_save(self) -> None:
        save_conferences(self.conferences)
        self.refresh_conference_list()

    def delete_selected_conf(self) -> None:
        targets = self.get_checked_confs()
        if not targets:
            return
        if not messagebox.askyesno("确认", f"确定删除选中的 {len(targets)} 个会议吗?"):
            return

        ids = {c.id for c in targets}
        self.conferences = [c for c in self.conferences if c.id not in ids]
        save_conferences(self.conferences)
        self.refresh_conference_list()

    def toggle_favorite_selected(self) -> None:
        targets = self.get_checked_confs()
        if not targets:
            return

        # 如果选中里有人未关注 -> 全部关注；否则全部取关
        any_not_fav = any(not bool(getattr(c, "favorite", False)) for c in targets)
        for c in targets:
            setattr(c, "favorite", True if any_not_fav else False)

        save_conferences(self.conferences)
        self.refresh_conference_list()

    def manual_refresh(self) -> None:
        self.conferences = load_conferences()
        self.refresh_conference_list()

    # -------------------------------------------------------------------------
    # Auto refresh
    # -------------------------------------------------------------------------
    def _apply_refresh_minutes(self) -> None:
        mins = _try_int(self.refresh_min_var.get(), 60)
        mins = _clamp_int(mins, 1, 12 * 60)  # 1min ~ 12h
        self.refresh_min_var.set(str(mins))
        self._schedule_auto_refresh()
        messagebox.showinfo("已应用", f"自动刷新间隔已设置为 {mins} 分钟")

    def _schedule_auto_refresh(self) -> None:
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

        mins = _try_int(self.refresh_min_var.get(), 60)
        mins = _clamp_int(mins, 1, 12 * 60)
        ms = mins * 60 * 1000
        self._after_id = self.after(ms, self._auto_tick)

    def _auto_tick(self) -> None:
        self.manual_refresh()
        self._schedule_auto_refresh()

    # -------------------------------------------------------------------------
    # Reminder System
    # -------------------------------------------------------------------------
    def _persist_auto_remind_settings(self) -> None:
        days = _try_int(self.window_days_var.get(), 7)
        days = _clamp_int(days, 1, 365)
        self.window_days_var.set(str(days))

        # 写回 config（你原本就从 config 读了 conference_window_days）
        try:
            setattr(self.config, "conference_window_days", days)
            self.on_config_update(self.config)
        except Exception:
            pass

    def send_reminder_manual(self) -> None:
        targets = self.get_checked_targets()
        confs = self.get_checked_confs()
        self._open_send_dialog(confs, targets, "发送提醒（确认）")

    def auto_remind_preview(self) -> None:
        self._persist_auto_remind_settings()

        days = _try_int(self.window_days_var.get(), 7)
        include_overdue = bool(self.include_overdue_var.get())

        matches: List[ConferenceEvent] = []
        for c in self.conferences:
            try:
                if c.is_due_within(days) or (include_overdue and c.is_overdue()):
                    matches.append(c)
            except Exception:
                # 如果日期不可解析，不参与自动匹配
                continue

        targets = self.get_checked_targets()
        self._open_send_dialog(matches, targets, "自动提醒预览")

    def _open_send_dialog(self, confs: Sequence[ConferenceEvent], targets: Sequence[Any], title: str) -> None:
        all_t = list(getattr(self.config, "lan_targets", []) or [])
        sel_t_idxs = {i for i, t in enumerate(all_t) if t in targets}
        sel_c_ids = {c.id for c in confs}

        dlg = SendConfirmDialog(self, self.conferences, all_t, sel_c_ids, sel_t_idxs, title)
        self.wait_window(dlg)

        if dlg.result:
            final_confs, final_targets = dlg.result
            self._do_send_async(final_confs, final_targets)

    def _set_sending_state(self, sending: bool) -> None:
        self._sending = sending
        state = "disabled" if sending else "normal"
        try:
            self.btn_auto_send.configure(state=state)
            self.btn_manual_send.configure(state=state)
        except Exception:
            pass

    def _do_send_async(self, confs: Sequence[ConferenceEvent], targets: Sequence[Any]) -> None:
        if not confs:
            messagebox.showinfo("提示", "没有选择任何会议。")
            return
        if not targets:
            messagebox.showinfo("提示", "没有选择任何接收人。")
            return
        if self._sending:
            messagebox.showinfo("提示", "正在发送中，请稍后再试。")
            return

        msg = "会议提醒:\n" + "\n".join([f"- {c.name} (截止: {c.submission_deadline})" for c in confs])

        self._set_sending_state(True)

        def worker():
            try:
                res = send_lan_notifications(
                    msg,
                    list(targets),
                    smtp_host=getattr(self.config, "smtp_host", ""),
                    smtp_port=getattr(self.config, "smtp_port", 465),
                    smtp_sender=getattr(self.config, "smtp_sender", ""),
                    smtp_username=getattr(self.config, "smtp_username", ""),
                    smtp_password=getattr(self.config, "smtp_password", ""),
                    smtp_use_tls=getattr(self.config, "smtp_use_tls", True),
                )
            except Exception as e:
                res = None
                err = str(e)

                def ui_fail():
                    self._set_sending_state(False)
                    messagebox.showerror("发送失败", f"发送过程中发生异常：\n{err}")

                self.after(0, ui_fail)
                return

            def ui_done():
                self._set_sending_state(False)
                if not res:
                    messagebox.showerror("发送失败", "未获得发送结果（可能发送模块返回空）。")
                    return

                ok = sum(1 for r in res if r[1])
                fail_msg = "\n".join([f"{getattr(r[0], 'label', 'Unknown')}: {r[2]}" for r in res if not r[1]])

                if ok == len(list(targets)):
                    messagebox.showinfo("发送成功", f"全部 {ok} 条发送成功！")
                else:
                    messagebox.showerror(
                        "部分失败",
                        f"成功: {ok}\n失败: {len(list(targets)) - ok}\n\n错误详情:\n{fail_msg}",
                    )

            self.after(0, ui_done)

        threading.Thread(target=worker, daemon=True).start()

    def _open_email_settings(self) -> None:
        EmailSettingsDialog(self, self.config, lambda c: self.on_config_update(c))


# =============================================================================
# Dialogs
# =============================================================================
class AddConferenceDialog(ctk.CTkToplevel):
    def __init__(self, master, on_save: Callable[[ConferenceEvent], None]):
        super().__init__(master)
        self.title("新增会议")
        self.on_save = on_save
        self.geometry("420x450")

        self.name_var = tk.StringVar()
        self.cat_var = tk.StringVar(value="CCF-A")
        self.date_var = tk.StringVar()
        self.loc_var = tk.StringVar()
        self.url_var = tk.StringVar()
        self.remind_var = tk.StringVar(value="7")

        self._build()
        self.transient(master)
        self.grab_set()

    def _build(self):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=20, pady=20)

        grid_opts = {"sticky": "ew", "pady": 8}
        f.columnconfigure(1, weight=1)

        ctk.CTkLabel(f, text="会议名称 *").grid(row=0, column=0, sticky="w")
        ctk.CTkEntry(f, textvariable=self.name_var).grid(row=0, column=1, **grid_opts)

        ctk.CTkLabel(f, text="等级").grid(row=1, column=0, sticky="w")
        ctk.CTkComboBox(f, variable=self.cat_var, values=["CCF-A", "CCF-B", "CCF-C"]).grid(row=1, column=1, **grid_opts)

        ctk.CTkLabel(f, text="截止日期 * (YYYY-MM-DD)").grid(row=2, column=0, sticky="w")
        ctk.CTkEntry(f, textvariable=self.date_var).grid(row=2, column=1, **grid_opts)

        ctk.CTkLabel(f, text="地点/备注").grid(row=3, column=0, sticky="w")
        ctk.CTkEntry(f, textvariable=self.loc_var).grid(row=3, column=1, **grid_opts)

        ctk.CTkLabel(f, text="URL").grid(row=4, column=0, sticky="w")
        ctk.CTkEntry(f, textvariable=self.url_var).grid(row=4, column=1, **grid_opts)

        ctk.CTkLabel(f, text="提前提醒(天)").grid(row=5, column=0, sticky="w")
        ctk.CTkEntry(f, textvariable=self.remind_var).grid(row=5, column=1, **grid_opts)

        btn_row = ctk.CTkFrame(f, fg_color="transparent")
        btn_row.grid(row=6, column=0, columnspan=2, pady=(20, 0), sticky="e")

        ctk.CTkButton(btn_row, text="取消", width=80, fg_color="transparent", border_width=1, command=self.destroy).pack(side="right", padx=8)
        ctk.CTkButton(btn_row, text="保存", width=80, command=self._save).pack(side="right")

    def _save(self):
        name = self.name_var.get().strip()
        date_str = self.date_var.get().strip()

        if not name or not date_str:
            messagebox.showerror("错误", "名称和截止日期必填")
            return

        try:
            date_norm = _parse_date_yyyy_mm_dd(date_str)
        except Exception:
            messagebox.showerror("错误", "截止日期格式必须为 YYYY-MM-DD（例如 2026-01-15）")
            return

        c = ConferenceEvent(name=name, category=self.cat_var.get(), submission_deadline=date_norm)
        c.location = self.loc_var.get()
        c.url = self.url_var.get()
        try:
            c.remind_before_days = int(self.remind_var.get())
        except Exception:
            c.remind_before_days = 7

        self.on_save(c)
        self.destroy()


class EditConferenceDialog(AddConferenceDialog):
    def __init__(self, master, conf: ConferenceEvent, on_save: Callable[[], None]):
        ctk.CTkToplevel.__init__(self, master)
        self.title("编辑会议")
        self.conf = conf
        self.final_cb = on_save
        self.geometry("420x450")

        self.name_var = tk.StringVar(value=conf.name)
        self.cat_var = tk.StringVar(value=conf.category)
        self.date_var = tk.StringVar(value=conf.submission_deadline)
        self.loc_var = tk.StringVar(value=getattr(conf, "location", ""))
        self.url_var = tk.StringVar(value=getattr(conf, "url", ""))
        self.remind_var = tk.StringVar(value=str(getattr(conf, "remind_before_days", 7)))

        self._build()
        self.transient(master)
        self.grab_set()

    def _save(self):
        name = self.name_var.get().strip()
        date_str = self.date_var.get().strip()
        if not name or not date_str:
            messagebox.showerror("错误", "名称和截止日期必填")
            return

        try:
            date_norm = _parse_date_yyyy_mm_dd(date_str)
        except Exception:
            messagebox.showerror("错误", "截止日期格式必须为 YYYY-MM-DD（例如 2026-01-15）")
            return

        self.conf.name = name
        self.conf.category = self.cat_var.get()
        self.conf.submission_deadline = date_norm
        self.conf.location = self.loc_var.get()
        self.conf.url = self.url_var.get()
        try:
            self.conf.remind_before_days = int(self.remind_var.get())
        except Exception:
            pass

        self.final_cb()
        self.destroy()


class SendConfirmDialog(ctk.CTkToplevel):
    def __init__(self, master, all_confs, all_targets, sel_c_ids, sel_t_idxs, title):
        super().__init__(master)
        self.title(title)
        self.result = None
        self.all_confs = list(all_confs)
        self.all_targets = list(all_targets)

        self.geometry("920x580")
        self.minsize(880, 540)

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)

        # Left: targets
        left = ctk.CTkFrame(self)
        left.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="发送给谁？", font=("Arial", 14, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        self.tree_t = self._create_check_tree(left, headers=["姓名", "邮箱"], widths=[130, 260], stretch_cols=[1])
        self.tree_t.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))

        for i, t in enumerate(self.all_targets):
            ck = CHECK_ON if i in sel_t_idxs else CHECK_OFF
            self.tree_t.insert("", tk.END, iid=str(i), values=(ck, getattr(t, "label", ""), getattr(t, "email", "")))

        t_btn = ctk.CTkFrame(left, fg_color="transparent")
        t_btn.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        ctk.CTkButton(t_btn, text="全选", width=70, fg_color="transparent", border_width=1, command=lambda: self._set_all(self.tree_t, True)).pack(side="left", padx=(0, 8))
        ctk.CTkButton(t_btn, text="清空", width=70, fg_color="transparent", border_width=1, command=lambda: self._set_all(self.tree_t, False)).pack(side="left")

        # Right: conferences
        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="发送哪些会议？", font=("Arial", 14, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        self.tree_c = self._create_check_tree(right, headers=["会议", "截止"], widths=[520, 110], stretch_cols=[0])
        self.tree_c.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))

        for c in self.all_confs:
            ck = CHECK_ON if c.id in sel_c_ids else CHECK_OFF
            self.tree_c.insert("", tk.END, iid=c.id, values=(ck, c.name, c.submission_deadline))

        c_btn = ctk.CTkFrame(right, fg_color="transparent")
        c_btn.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        ctk.CTkButton(c_btn, text="全选", width=70, fg_color="transparent", border_width=1, command=lambda: self._set_all(self.tree_c, True)).pack(side="left", padx=(0, 8))
        ctk.CTkButton(c_btn, text="清空", width=70, fg_color="transparent", border_width=1, command=lambda: self._set_all(self.tree_c, False)).pack(side="left")

        # Bottom buttons
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=1, column=0, columnspan=2, sticky="e", padx=12, pady=(0, 12))
        ctk.CTkButton(bottom, text="取消", width=90, fg_color="transparent", border_width=1, command=self.destroy).pack(side="right", padx=(0, 10))
        ctk.CTkButton(bottom, text="确认发送", width=110, command=self._confirm).pack(side="right")

    def _create_check_tree(self, parent: ctk.CTkFrame, headers: List[str], widths: List[int], stretch_cols: List[int]):
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        cols = ["check"] + [f"col{i}" for i in range(len(headers))]
        tree = ttk.Treeview(container, columns=cols, show="headings", style="Conf.Treeview")

        tree.heading("check", text="选")
        tree.column("check", width=40, anchor="center", stretch=False)

        for i, h in enumerate(headers):
            tree.heading(f"col{i}", text=h)
            tree.column(
                f"col{i}",
                width=widths[i],
                anchor="w",
                stretch=(i in stretch_cols),
            )

        ysb = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=ysb.set)

        tree.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")

        tree.bind("<Button-1>", lambda e: self._on_toggle(e, tree))
        return container if isinstance(container, ttk.Widget) else container  # keep linter quiet

    def _tree_from_container(self, container: ctk.CTkFrame) -> ttk.Treeview:
        # container holds [Treeview, Scrollbar] as children; find the Treeview
        for ch in container.winfo_children():
            if isinstance(ch, ttk.Treeview):
                return ch
        raise RuntimeError("Treeview not found")

    def _on_toggle(self, event: tk.Event, tree: ttk.Treeview):
        region = tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        if tree.identify_column(event.x) != "#1":
            return
        item = tree.identify_row(event.y)
        if not item:
            return
        vals = list(tree.item(item, "values"))
        vals[0] = CHECK_OFF if vals[0] == CHECK_ON else CHECK_ON
        tree.item(item, values=vals)

    def _set_all(self, container_or_tree, on: bool) -> None:
        tree = container_or_tree if isinstance(container_or_tree, ttk.Treeview) else self._tree_from_container(container_or_tree)
        flag = CHECK_ON if on else CHECK_OFF
        for item in tree.get_children():
            vals = list(tree.item(item, "values"))
            vals[0] = flag
            tree.item(item, values=vals)

    def _confirm(self):
        tree_t = self._tree_from_container(self.tree_t) if not isinstance(self.tree_t, ttk.Treeview) else self.tree_t
        tree_c = self._tree_from_container(self.tree_c) if not isinstance(self.tree_c, ttk.Treeview) else self.tree_c

        fin_t = []
        for item in tree_t.get_children():
            vals = tree_t.item(item, "values")
            if vals and vals[0] == CHECK_ON:
                try:
                    fin_t.append(self.all_targets[int(item)])
                except Exception:
                    pass

        fin_c = []
        map_c = {c.id: c for c in self.all_confs}
        for item in tree_c.get_children():
            vals = tree_c.item(item, "values")
            if vals and vals[0] == CHECK_ON and item in map_c:
                fin_c.append(map_c[item])

        self.result = (fin_c, fin_t)
        self.destroy()


class EmailSettingsDialog(ctk.CTkToplevel):
    def __init__(self, master, config: AppConfig, on_save: Callable[[AppConfig], None]):
        super().__init__(master)
        self.title("邮件配置")
        self.geometry("420x360")

        self.host = tk.StringVar(value=getattr(config, "smtp_host", "smtp.qq.com"))
        self.port = tk.StringVar(value=str(getattr(config, "smtp_port", "465")))
        self.sender = tk.StringVar(value=getattr(config, "smtp_sender", ""))
        self.password = tk.StringVar(value=getattr(config, "smtp_password", ""))
        self.use_tls = tk.BooleanVar(value=getattr(config, "smtp_use_tls", True))

        self._build(on_save, config)
        self.transient(master)
        self.grab_set()

    def _build(self, on_save: Callable[[AppConfig], None], config: AppConfig):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=20, pady=20)

        opts = {"sticky": "ew", "pady": 6}
        f.columnconfigure(1, weight=1)

        ctk.CTkLabel(f, text="SMTP 服务器 (如 smtp.qq.com):").grid(row=0, column=0, sticky="w")
        ctk.CTkEntry(f, textvariable=self.host).grid(row=0, column=1, **opts)

        ctk.CTkLabel(f, text="端口 (SSL一般465):").grid(row=1, column=0, sticky="w")
        ctk.CTkEntry(f, textvariable=self.port).grid(row=1, column=1, **opts)

        ctk.CTkLabel(f, text="发件邮箱:").grid(row=2, column=0, sticky="w")
        ctk.CTkEntry(f, textvariable=self.sender).grid(row=2, column=1, **opts)

        ctk.CTkLabel(f, text="授权码/密码:").grid(row=3, column=0, sticky="w")
        ctk.CTkEntry(f, textvariable=self.password, show="*").grid(row=3, column=1, **opts)

        ctk.CTkCheckBox(f, text="使用 TLS/SSL", variable=self.use_tls).grid(row=4, column=1, sticky="w", pady=10)

        btn = ctk.CTkFrame(f, fg_color="transparent")
        btn.grid(row=5, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ctk.CTkButton(btn, text="取消", width=90, fg_color="transparent", border_width=1, command=self.destroy).pack(side="right", padx=(0, 10))
        ctk.CTkButton(btn, text="保存配置", width=110, command=lambda: self._save(on_save, config)).pack(side="right")

    def _save(self, on_save: Callable[[AppConfig], None], config: AppConfig):
        try:
            port_val = int(self.port.get())
        except Exception:
            port_val = 465

        setattr(config, "smtp_host", self.host.get().strip())
        setattr(config, "smtp_port", port_val)
        setattr(config, "smtp_sender", self.sender.get().strip())
        setattr(config, "smtp_password", self.password.get().strip())
        setattr(config, "smtp_username", self.sender.get().strip())  # 常见：用户名=邮箱
        setattr(config, "smtp_use_tls", bool(self.use_tls.get()))

        on_save(config)
        self.destroy()


class EditTargetDialog(ctk.CTkToplevel):
    def __init__(self, master, target_obj: Any, on_save: Callable[[], None]):
        super().__init__(master)
        self.title("编辑联系人")
        self.geometry("420x240")
        self.target = target_obj
        self.on_save = on_save

        self.name_var = tk.StringVar(value=getattr(target_obj, "label", ""))
        self.email_var = tk.StringVar(value=getattr(target_obj, "email", ""))

        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=20, pady=20)
        f.columnconfigure(1, weight=1)

        ctk.CTkLabel(f, text="姓名 *").grid(row=0, column=0, sticky="w", pady=8)
        ctk.CTkEntry(f, textvariable=self.name_var).grid(row=0, column=1, sticky="ew", pady=8)

        ctk.CTkLabel(f, text="邮箱 *").grid(row=1, column=0, sticky="w", pady=8)
        ctk.CTkEntry(f, textvariable=self.email_var).grid(row=1, column=1, sticky="ew", pady=8)

        btn = ctk.CTkFrame(f, fg_color="transparent")
        btn.grid(row=2, column=0, columnspan=2, sticky="e", pady=(14, 0))

        ctk.CTkButton(btn, text="取消", width=90, fg_color="transparent", border_width=1, command=self.destroy).pack(side="right", padx=(0, 10))
        ctk.CTkButton(btn, text="保存", width=110, command=self._save).pack(side="right")

        self.transient(master)
        self.grab_set()

    def _save(self):
        name = self.name_var.get().strip()
        email = self.email_var.get().strip()
        if not name or not email:
            messagebox.showerror("错误", "姓名和邮箱必填")
            return

        setattr(self.target, "label", name)
        setattr(self.target, "email", email)

        self.on_save()
        self.destroy()
