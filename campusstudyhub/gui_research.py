"""Research-focused utilities: experiment tracker and reading list (CustomTkinter Version)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

import customtkinter as ctk

from .models import ExperimentEntry, PaperEntry
from .storage import (
    export_research_summary,
    load_experiments,
    load_papers,
    save_experiments,
    save_papers,
)
from .ui_style import (
    BG_CARD,
    HEADER_FONT,
    LABEL_BOLD,
    TEXT_PRIMARY,
    TEXT_MUTED,
    card_kwargs,
)

# 深色 Treeview 样式补丁（复用）
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


class ResearchHubFrame(ctk.CTkFrame):
    """Combined research utilities for experiments and reading queue."""

    def __init__(self, master: tk.Widget) -> None:
        super().__init__(master, fg_color="transparent")
        self.experiments: List[ExperimentEntry] = load_experiments()
        self.papers: List[PaperEntry] = load_papers()

        setup_treeview_style()

        # 使用 CTkTabview 替代 Notebook
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True)
        
        self.tab_exp = self.tabview.add("实验记录 (Experiments)")
        self.tab_paper = self.tabview.add("文献阅读 (Reading List)")

        self._build_experiment_tab(self.tab_exp)
        self._build_paper_tab(self.tab_paper)

    # ---------------- Experiment tracker -----------------
    def _build_experiment_tab(self, parent) -> None:
        # 左右分栏：左列表，右表单
        parent.columnconfigure(0, weight=3)
        parent.columnconfigure(1, weight=2)
        parent.rowconfigure(0, weight=1)

        # === 左侧：列表 ===
        list_frame = ctk.CTkFrame(parent, fg_color="transparent")
        list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        cols = ("title", "project", "status", "metric", "updated")
        self.exp_tree = ttk.Treeview(list_frame, columns=cols, show="headings", selectmode="browse")
        
        self.exp_tree.heading("title", text="标题"); self.exp_tree.column("title", width=180)
        self.exp_tree.heading("project", text="项目"); self.exp_tree.column("project", width=100)
        self.exp_tree.heading("status", text="状态"); self.exp_tree.column("status", width=80)
        self.exp_tree.heading("metric", text="指标"); self.exp_tree.column("metric", width=80)
        self.exp_tree.heading("updated", text="更新时间"); self.exp_tree.column("updated", width=120)

        ysb = ttk.Scrollbar(list_frame, orient="vertical", command=self.exp_tree.yview)
        self.exp_tree.configure(yscroll=ysb.set)
        
        self.exp_tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")
        self.exp_tree.bind("<<TreeviewSelect>>", self._on_exp_select)

        # === 右侧：表单 ===
        form_frame = ctk.CTkFrame(parent, **card_kwargs())
        form_frame.grid(row=0, column=1, sticky="nsew")
        
        ctk.CTkLabel(form_frame, text="记录 / 编辑实验", font=HEADER_FONT).pack(anchor="w", padx=15, pady=(15, 10))

        # 表单行构建
        def _add_row(label, widget):
            f = ctk.CTkFrame(form_frame, fg_color="transparent")
            f.pack(fill="x", padx=15, pady=4)
            ctk.CTkLabel(f, text=label, width=80, anchor="w").pack(side="left")
            widget.pack(side="left", fill="x", expand=True)
            return widget

        self.exp_title_entry = _add_row("标题", ctk.CTkEntry(form_frame))
        self.exp_proj_entry = _add_row("项目", ctk.CTkEntry(form_frame))
        self.exp_cmd_entry = _add_row("运行命令", ctk.CTkEntry(form_frame))
        self.exp_status_combo = _add_row("状态", ctk.CTkComboBox(form_frame, values=["planned", "running", "done", "failed"], state="readonly"))
        self.exp_metric_entry = _add_row("指标/成绩", ctk.CTkEntry(form_frame))
        
        ctk.CTkLabel(form_frame, text="备注").pack(anchor="w", padx=15, pady=(8, 0))
        self.exp_notes = ctk.CTkTextbox(form_frame, height=80)
        self.exp_notes.pack(fill="x", padx=15, pady=(5, 15))

        # 按钮
        btn_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkButton(btn_row, text="清空/新建", fg_color="transparent", border_width=1, width=80, command=self._clear_exp_form).pack(side="left", padx=(0, 5))
        ctk.CTkButton(btn_row, text="保存", command=self._save_experiment).pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(btn_row, text="删除", fg_color="#b33636", hover_color="#8f2a2a", width=60, command=self._delete_experiment).pack(side="right")
        
        export_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        export_row.pack(fill="x", padx=15, pady=(0, 15))
        ctk.CTkButton(export_row, text="导出 Markdown 汇总", fg_color="#E08e00", hover_color="#B06e00", command=self._export_research_md).pack(fill="x")

        self._refresh_experiments()

    def _refresh_experiments(self) -> None:
        for item in self.exp_tree.get_children():
            self.exp_tree.delete(item)
        for exp in self.experiments:
            self.exp_tree.insert("", "end", iid=exp.id, values=(exp.title, exp.project, exp.status, exp.metric, exp.updated_at or ""))

    def _on_exp_select(self, _event) -> None:
        sel = self.exp_tree.selection()
        if not sel: return
        exp = next((e for e in self.experiments if e.id == sel[0]), None)
        if not exp: return
        
        self.exp_title_entry.delete(0, "end"); self.exp_title_entry.insert(0, exp.title)
        self.exp_proj_entry.delete(0, "end"); self.exp_proj_entry.insert(0, exp.project)
        self.exp_cmd_entry.delete(0, "end"); self.exp_cmd_entry.insert(0, exp.command)
        self.exp_status_combo.set(exp.status)
        self.exp_metric_entry.delete(0, "end"); self.exp_metric_entry.insert(0, exp.metric)
        self.exp_notes.delete("1.0", "end"); self.exp_notes.insert("1.0", exp.notes)

    def _clear_exp_form(self):
        self.exp_tree.selection_remove(self.exp_tree.selection())
        self.exp_title_entry.delete(0, "end")
        self.exp_proj_entry.delete(0, "end")
        self.exp_cmd_entry.delete(0, "end")
        self.exp_metric_entry.delete(0, "end")
        self.exp_notes.delete("1.0", "end")
        self.exp_status_combo.set("planned")

    def _save_experiment(self) -> None:
        title = self.exp_title_entry.get().strip()
        if not title:
            messagebox.showwarning("提示", "标题不能为空")
            return
            
        sel = self.exp_tree.selection()
        exp_id = sel[0] if sel else str(uuid4())
        
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_entry = ExperimentEntry(
            id=exp_id,
            title=title,
            project=self.exp_proj_entry.get().strip(),
            command=self.exp_cmd_entry.get().strip(),
            status=self.exp_status_combo.get(),
            metric=self.exp_metric_entry.get().strip(),
            notes=self.exp_notes.get("1.0", "end").strip(),
            updated_at=now_str
        )

        if sel:
            for idx, e in enumerate(self.experiments):
                if e.id == exp_id:
                    self.experiments[idx] = new_entry
                    break
        else:
            self.experiments.append(new_entry)
            
        save_experiments(self.experiments)
        self._refresh_experiments()

    def _delete_experiment(self) -> None:
        sel = self.exp_tree.selection()
        if not sel: return
        if not messagebox.askyesno("确认", "删除此记录？"): return
        self.experiments = [e for e in self.experiments if e.id != sel[0]]
        save_experiments(self.experiments)
        self._refresh_experiments()
        self._clear_exp_form()

    def _export_research_md(self) -> None:
        export_research_summary(self.experiments, self.papers)
        messagebox.showinfo("已导出", "已生成 data/research_summary.md")

    # ---------------- Reading List -----------------
    def _build_paper_tab(self, parent) -> None:
        # 布局逻辑同上
        parent.columnconfigure(0, weight=3)
        parent.columnconfigure(1, weight=2)
        parent.rowconfigure(0, weight=1)

        # 左侧列表
        list_frame = ctk.CTkFrame(parent, fg_color="transparent")
        list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        cols = ("title", "doi", "status")
        self.paper_tree = ttk.Treeview(list_frame, columns=cols, show="headings", selectmode="browse")
        self.paper_tree.heading("title", text="标题"); self.paper_tree.column("title", width=240)
        self.paper_tree.heading("doi", text="DOI"); self.paper_tree.column("doi", width=150)
        self.paper_tree.heading("status", text="状态"); self.paper_tree.column("status", width=80)

        ysb = ttk.Scrollbar(list_frame, orient="vertical", command=self.paper_tree.yview)
        self.paper_tree.configure(yscroll=ysb.set)
        self.paper_tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")
        self.paper_tree.bind("<<TreeviewSelect>>", self._on_paper_select)

        # 右侧表单
        form_frame = ctk.CTkFrame(parent, **card_kwargs())
        form_frame.grid(row=0, column=1, sticky="nsew")
        
        ctk.CTkLabel(form_frame, text="论文 / 文献", font=HEADER_FONT).pack(anchor="w", padx=15, pady=(15, 10))

        def _add_row(label, widget):
            f = ctk.CTkFrame(form_frame, fg_color="transparent")
            f.pack(fill="x", padx=15, pady=4)
            ctk.CTkLabel(f, text=label, width=80, anchor="w").pack(side="left")
            widget.pack(side="left", fill="x", expand=True)
            return widget

        self.paper_title_entry = _add_row("标题", ctk.CTkEntry(form_frame))
        self.paper_doi_entry = _add_row("DOI", ctk.CTkEntry(form_frame))
        self.paper_venue_entry = _add_row("期刊/会议", ctk.CTkEntry(form_frame))
        self.paper_status_combo = _add_row("状态", ctk.CTkComboBox(form_frame, values=["to_read", "reading", "done"], state="readonly"))
        self.paper_url_entry = _add_row("链接", ctk.CTkEntry(form_frame))
        
        ctk.CTkLabel(form_frame, text="备注").pack(anchor="w", padx=15, pady=(8, 0))
        self.paper_notes = ctk.CTkTextbox(form_frame, height=80)
        self.paper_notes.pack(fill="x", padx=15, pady=(5, 15))

        btn_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=10)
        ctk.CTkButton(btn_row, text="清空", fg_color="transparent", border_width=1, width=60, command=self._clear_paper_form).pack(side="left", padx=(0, 5))
        ctk.CTkButton(btn_row, text="保存", command=self._save_paper).pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(btn_row, text="删除", fg_color="#b33636", hover_color="#8f2a2a", width=60, command=self._delete_paper).pack(side="right")

        self._refresh_papers()

    def _refresh_papers(self) -> None:
        for item in self.paper_tree.get_children():
            self.paper_tree.delete(item)
        for p in self.papers:
            self.paper_tree.insert("", "end", iid=p.id, values=(p.title, p.doi, p.status))

    def _on_paper_select(self, _event) -> None:
        sel = self.paper_tree.selection()
        if not sel: return
        p = next((x for x in self.papers if x.id == sel[0]), None)
        if not p: return
        
        self.paper_title_entry.delete(0, "end"); self.paper_title_entry.insert(0, p.title)
        self.paper_doi_entry.delete(0, "end"); self.paper_doi_entry.insert(0, p.doi)
        self.paper_venue_entry.delete(0, "end"); self.paper_venue_entry.insert(0, p.venue)
        self.paper_status_combo.set(p.status)
        self.paper_url_entry.delete(0, "end"); self.paper_url_entry.insert(0, p.url)
        self.paper_notes.delete("1.0", "end"); self.paper_notes.insert("1.0", p.notes)

    def _clear_paper_form(self):
        self.paper_tree.selection_remove(self.paper_tree.selection())
        self.paper_title_entry.delete(0, "end")
        self.paper_doi_entry.delete(0, "end")
        self.paper_venue_entry.delete(0, "end")
        self.paper_url_entry.delete(0, "end")
        self.paper_notes.delete("1.0", "end")
        self.paper_status_combo.set("to_read")

    def _save_paper(self) -> None:
        title = self.paper_title_entry.get().strip()
        if not title:
            messagebox.showwarning("提示", "标题不能为空")
            return
            
        sel = self.paper_tree.selection()
        pid = sel[0] if sel else str(uuid4())
        
        new_p = PaperEntry(
            id=pid,
            title=title,
            doi=self.paper_doi_entry.get().strip(),
            venue=self.paper_venue_entry.get().strip(),
            url=self.paper_url_entry.get().strip(),
            status=self.paper_status_combo.get(),
            notes=self.paper_notes.get("1.0", "end").strip()
        )

        if sel:
            for idx, p in enumerate(self.papers):
                if p.id == pid:
                    self.papers[idx] = new_p
                    break
        else:
            self.papers.append(new_p)
            
        save_papers(self.papers)
        self._refresh_papers()

    def _delete_paper(self) -> None:
        sel = self.paper_tree.selection()
        if not sel: return
        if not messagebox.askyesno("确认", "删除此记录？"): return
        self.papers = [p for p in self.papers if p.id != sel[0]]
        save_papers(self.papers)
        self._refresh_papers()
        self._clear_paper_form()