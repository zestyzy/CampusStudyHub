"""Research-focused utilities: experiment tracker and reading list."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from .models import ExperimentEntry, PaperEntry
from .storage import (
    export_research_summary,
    load_experiments,
    load_papers,
    save_experiments,
    save_papers,
)


class ResearchHubFrame(tk.Frame):
    """Combined research utilities for experiments and reading queue."""

    def __init__(self, master: tk.Widget) -> None:
        super().__init__(master)
        self.experiments: List[ExperimentEntry] = load_experiments()
        self.papers: List[PaperEntry] = load_papers()

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True)

        self.exp_tab = ttk.Frame(notebook)
        notebook.add(self.exp_tab, text="Experiments")
        self.paper_tab = ttk.Frame(notebook)
        notebook.add(self.paper_tab, text="Reading List")

        self._build_experiment_tab()
        self._build_paper_tab()

    # ---------------- Experiment tracker -----------------
    def _build_experiment_tab(self) -> None:
        form = ttk.LabelFrame(self.exp_tab, text="记录 / 编辑实验")
        form.pack(fill=tk.X, padx=10, pady=10)

        self.exp_title_var = tk.StringVar()
        self.exp_project_var = tk.StringVar()
        self.exp_command_var = tk.StringVar()
        self.exp_status_var = tk.StringVar(value="planned")
        self.exp_metric_var = tk.StringVar()
        self.exp_notes = tk.Text(form, height=3, width=60)

        row = 0
        ttk.Label(form, text="实验标题").grid(row=row, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(form, textvariable=self.exp_title_var, width=40).grid(
            row=row, column=1, padx=5, pady=5, sticky=tk.W
        )
        ttk.Label(form, text="所属课题/项目").grid(row=row, column=2, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(form, textvariable=self.exp_project_var, width=30).grid(
            row=row, column=3, padx=5, pady=5, sticky=tk.W
        )

        row += 1
        ttk.Label(form, text="运行命令/脚本").grid(row=row, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(form, textvariable=self.exp_command_var, width=40).grid(
            row=row, column=1, padx=5, pady=5, sticky=tk.W
        )
        ttk.Label(form, text="状态").grid(row=row, column=2, padx=5, pady=5, sticky=tk.W)
        ttk.Combobox(
            form,
            textvariable=self.exp_status_var,
            values=["planned", "running", "done", "failed"],
            width=12,
            state="readonly",
        ).grid(row=row, column=3, padx=5, pady=5, sticky=tk.W)

        row += 1
        ttk.Label(form, text="指标/成绩").grid(row=row, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(form, textvariable=self.exp_metric_var, width=20).grid(
            row=row, column=1, padx=5, pady=5, sticky=tk.W
        )
        ttk.Label(form, text="备注").grid(row=row, column=2, padx=5, pady=5, sticky=tk.W)
        self.exp_notes.grid(row=row, column=3, padx=5, pady=5, sticky=tk.W)

        btn_row = ttk.Frame(form)
        btn_row.grid(row=row + 1, column=0, columnspan=4, sticky=tk.W, padx=5, pady=5)
        ttk.Button(btn_row, text="新增/保存", command=self._save_experiment).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="删除", command=self._delete_experiment).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="标记完成", command=self._mark_experiment_done).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="导出 Markdown", command=self._export_research_md).pack(side=tk.LEFT, padx=4)

        # Table
        self.exp_tree = ttk.Treeview(
            self.exp_tab,
            columns=("title", "project", "status", "metric", "updated"),
            show="headings",
            height=10,
        )
        for col, label, width in [
            ("title", "标题", 200),
            ("project", "项目", 120),
            ("status", "状态", 90),
            ("metric", "指标", 80),
            ("updated", "更新时间", 120),
        ]:
            self.exp_tree.heading(col, text=label)
            self.exp_tree.column(col, width=width, anchor=tk.W)
        self.exp_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.exp_tree.bind("<<TreeviewSelect>>", self._on_exp_select)

        self._refresh_experiments()

    def _refresh_experiments(self) -> None:
        for item in self.exp_tree.get_children():
            self.exp_tree.delete(item)
        for exp in self.experiments:
            self.exp_tree.insert(
                "",
                tk.END,
                iid=exp.id,
                values=(exp.title, exp.project, exp.status, exp.metric, exp.updated_at or ""),
            )

    def _on_exp_select(self, _event: tk.Event) -> None:
        sel = self.exp_tree.selection()
        if not sel:
            return
        exp_id = sel[0]
        exp = next((e for e in self.experiments if e.id == exp_id), None)
        if not exp:
            return
        self.exp_title_var.set(exp.title)
        self.exp_project_var.set(exp.project)
        self.exp_command_var.set(exp.command)
        self.exp_status_var.set(exp.status)
        self.exp_metric_var.set(exp.metric)
        self.exp_notes.delete("1.0", tk.END)
        self.exp_notes.insert(tk.END, exp.notes)

    def _collect_experiment(self, exp_id: Optional[str] = None) -> ExperimentEntry:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        return ExperimentEntry(
            id=exp_id or str(uuid4()),  # type: ignore[arg-type]
            title=self.exp_title_var.get().strip(),
            project=self.exp_project_var.get().strip(),
            command=self.exp_command_var.get().strip(),
            status=self.exp_status_var.get(),
            metric=self.exp_metric_var.get().strip(),
            notes=self.exp_notes.get("1.0", tk.END).strip(),
            updated_at=now_str,
        )

    def _save_experiment(self) -> None:
        if not self.exp_title_var.get().strip():
            messagebox.showwarning("缺少信息", "请填写实验标题")
            return
        sel = self.exp_tree.selection()
        if sel:
            exp_id = sel[0]
            new_entry = self._collect_experiment(exp_id)
            for idx, exp in enumerate(self.experiments):
                if exp.id == exp_id:
                    self.experiments[idx] = new_entry
                    break
        else:
            new_entry = self._collect_experiment()
            self.experiments.append(new_entry)
        save_experiments(self.experiments)
        self._refresh_experiments()
        messagebox.showinfo("已保存", "实验记录已保存")

    def _delete_experiment(self) -> None:
        sel = self.exp_tree.selection()
        if not sel:
            messagebox.showwarning("未选择", "请选择一条实验记录")
            return
        exp_id = sel[0]
        self.experiments = [e for e in self.experiments if e.id != exp_id]
        save_experiments(self.experiments)
        self._refresh_experiments()

    def _mark_experiment_done(self) -> None:
        sel = self.exp_tree.selection()
        if not sel:
            messagebox.showwarning("未选择", "请选择一条实验记录")
            return
        exp_id = sel[0]
        for idx, exp in enumerate(self.experiments):
            if exp.id == exp_id:
                exp.status = "done"
                exp.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
                self.experiments[idx] = exp
        save_experiments(self.experiments)
        self._refresh_experiments()

    def _export_research_md(self) -> None:
        export_research_summary(self.experiments, self.papers)
        messagebox.showinfo("已导出", "已生成 data/research_summary.md")

    # ---------------- Reading list -----------------
    def _build_paper_tab(self) -> None:
        form = ttk.LabelFrame(self.paper_tab, text="论文 / 文献")
        form.pack(fill=tk.X, padx=10, pady=10)

        self.paper_title_var = tk.StringVar()
        self.paper_doi_var = tk.StringVar()
        self.paper_status_var = tk.StringVar(value="to_read")
        self.paper_venue_var = tk.StringVar()
        self.paper_url_var = tk.StringVar()
        self.paper_notes = tk.Text(form, height=3, width=60)

        row = 0
        ttk.Label(form, text="标题").grid(row=row, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(form, textvariable=self.paper_title_var, width=40).grid(
            row=row, column=1, padx=5, pady=5, sticky=tk.W
        )
        ttk.Label(form, text="DOI").grid(row=row, column=2, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(form, textvariable=self.paper_doi_var, width=30).grid(
            row=row, column=3, padx=5, pady=5, sticky=tk.W
        )

        row += 1
        ttk.Label(form, text="期刊/会议").grid(row=row, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(form, textvariable=self.paper_venue_var, width=30).grid(
            row=row, column=1, padx=5, pady=5, sticky=tk.W
        )
        ttk.Label(form, text="状态").grid(row=row, column=2, padx=5, pady=5, sticky=tk.W)
        ttk.Combobox(
            form,
            textvariable=self.paper_status_var,
            values=["to_read", "reading", "done"],
            state="readonly",
            width=12,
        ).grid(row=row, column=3, padx=5, pady=5, sticky=tk.W)

        row += 1
        ttk.Label(form, text="链接").grid(row=row, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(form, textvariable=self.paper_url_var, width=40).grid(
            row=row, column=1, padx=5, pady=5, sticky=tk.W
        )
        ttk.Label(form, text="备注").grid(row=row, column=2, padx=5, pady=5, sticky=tk.W)
        self.paper_notes.grid(row=row, column=3, padx=5, pady=5, sticky=tk.W)

        btn_row = ttk.Frame(form)
        btn_row.grid(row=row + 1, column=0, columnspan=4, sticky=tk.W, padx=5, pady=5)
        ttk.Button(btn_row, text="新增/保存", command=self._save_paper).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="删除", command=self._delete_paper).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="标记完成", command=self._mark_paper_done).pack(side=tk.LEFT, padx=4)

        self.paper_tree = ttk.Treeview(
            self.paper_tab,
            columns=("title", "doi", "status"),
            show="headings",
            height=10,
        )
        for col, label, width in [
            ("title", "标题", 240),
            ("doi", "DOI", 200),
            ("status", "状态", 90),
        ]:
            self.paper_tree.heading(col, text=label)
            self.paper_tree.column(col, width=width, anchor=tk.W)
        self.paper_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.paper_tree.bind("<<TreeviewSelect>>", self._on_paper_select)

        self._refresh_papers()

    def _refresh_papers(self) -> None:
        for item in self.paper_tree.get_children():
            self.paper_tree.delete(item)
        for paper in self.papers:
            self.paper_tree.insert(
                "",
                tk.END,
                iid=paper.id,
                values=(paper.title, paper.doi, paper.status),
            )

    def _on_paper_select(self, _event: tk.Event) -> None:
        sel = self.paper_tree.selection()
        if not sel:
            return
        paper_id = sel[0]
        paper = next((p for p in self.papers if p.id == paper_id), None)
        if not paper:
            return
        self.paper_title_var.set(paper.title)
        self.paper_doi_var.set(paper.doi)
        self.paper_status_var.set(paper.status)
        self.paper_venue_var.set(paper.venue)
        self.paper_url_var.set(paper.url)
        self.paper_notes.delete("1.0", tk.END)
        self.paper_notes.insert(tk.END, paper.notes)

    def _collect_paper(self, paper_id: Optional[str] = None) -> PaperEntry:
        return PaperEntry(
            id=paper_id or str(uuid4()),  # type: ignore[arg-type]
            title=self.paper_title_var.get().strip(),
            doi=self.paper_doi_var.get().strip(),
            venue=self.paper_venue_var.get().strip(),
            url=self.paper_url_var.get().strip(),
            status=self.paper_status_var.get(),
            notes=self.paper_notes.get("1.0", tk.END).strip(),
        )

    def _save_paper(self) -> None:
        if not self.paper_title_var.get().strip():
            messagebox.showwarning("缺少信息", "请填写论文标题")
            return
        sel = self.paper_tree.selection()
        if sel:
            paper_id = sel[0]
            updated = self._collect_paper(paper_id)
            for idx, paper in enumerate(self.papers):
                if paper.id == paper_id:
                    self.papers[idx] = updated
                    break
        else:
            new_entry = self._collect_paper()
            self.papers.append(new_entry)
        save_papers(self.papers)
        self._refresh_papers()
        messagebox.showinfo("已保存", "已保存到阅读清单")

    def _delete_paper(self) -> None:
        sel = self.paper_tree.selection()
        if not sel:
            messagebox.showwarning("未选择", "请选择一条记录")
            return
        paper_id = sel[0]
        self.papers = [p for p in self.papers if p.id != paper_id]
        save_papers(self.papers)
        self._refresh_papers()

    def _mark_paper_done(self) -> None:
        sel = self.paper_tree.selection()
        if not sel:
            messagebox.showwarning("未选择", "请选择一条记录")
            return
        paper_id = sel[0]
        for idx, paper in enumerate(self.papers):
            if paper.id == paper_id:
                paper.status = "done"
                self.papers[idx] = paper
                break
        save_papers(self.papers)
        self._refresh_papers()
