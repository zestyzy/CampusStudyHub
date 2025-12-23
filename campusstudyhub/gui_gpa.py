"""GPA calculator widget with persistence."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import List

from .models import GradeEntry
from .storage import load_grades, save_grades


class GPACalculator(tk.Frame):
    """A GPA calculator that supports weighted averages and saving rows."""

    def __init__(self, master: tk.Misc):
        super().__init__(master)
        self.rows: List[dict] = []
        self._build_ui()
        self._load_saved()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        btn_frame = tk.Frame(self)
        btn_frame.grid(row=0, column=0, sticky="e", pady=5)
        tk.Button(btn_frame, text="新增行", command=self.add_row).pack(
            side=tk.LEFT, padx=4
        )
        tk.Button(btn_frame, text="删除选中", command=self.remove_selected).pack(
            side=tk.LEFT, padx=4
        )
        tk.Button(btn_frame, text="保存", command=self.save_rows).pack(
            side=tk.LEFT, padx=4
        )

        header = tk.Frame(self)
        header.grid(row=1, column=0, sticky="ew")
        header.columnconfigure(0, weight=3)
        header.columnconfigure(1, weight=1)
        header.columnconfigure(2, weight=1)
        tk.Label(header, text="课程名称").grid(row=0, column=0, sticky="w", padx=5)
        tk.Label(header, text="学分").grid(row=0, column=1, sticky="w", padx=5)
        tk.Label(header, text="成绩 (0-100)").grid(row=0, column=2, sticky="w", padx=5)

        self.rows_container = tk.Frame(self)
        self.rows_container.grid(row=2, column=0, sticky="nsew")
        self.rows_container.columnconfigure(0, weight=3)
        self.rows_container.columnconfigure(1, weight=1)
        self.rows_container.columnconfigure(2, weight=1)
        self.rows_container.columnconfigure(3, weight=0)

        result_frame = tk.LabelFrame(self, text="结果")
        result_frame.grid(row=3, column=0, sticky="ew", pady=10, padx=5)
        for i in range(3):
            result_frame.columnconfigure(i, weight=1)
        self.total_var = tk.StringVar(value="总学分: 0")
        self.avg_var = tk.StringVar(value="加权平均分: 0")
        self.gpa_var = tk.StringVar(value="GPA: 0.0")
        tk.Label(result_frame, textvariable=self.total_var).grid(row=0, column=0)
        tk.Label(result_frame, textvariable=self.avg_var).grid(row=0, column=1)
        tk.Label(result_frame, textvariable=self.gpa_var).grid(row=0, column=2)

        tk.Button(self, text="计算", command=self.calculate).grid(
            row=4, column=0, pady=(0, 10)
        )

    def add_row(self, entry: GradeEntry | None = None) -> None:
        """Add a new editable row."""
        row_frame = tk.Frame(self.rows_container)
        row_frame.grid_columnconfigure(0, weight=3)
        row_frame.grid_columnconfigure(1, weight=1)
        row_frame.grid_columnconfigure(2, weight=1)

        course_var = tk.StringVar(value=entry.course if entry else "")
        credit_var = tk.StringVar(
            value=str(entry.credit) if entry and entry.credit is not None else ""
        )
        score_var = tk.StringVar(
            value=str(entry.score) if entry and entry.score is not None else ""
        )
        selected_var = tk.BooleanVar(value=False)

        row_index = len(self.rows)
        row_frame.grid(row=row_index, column=0, sticky="ew", pady=2, padx=5)
        tk.Entry(row_frame, textvariable=course_var).grid(row=0, column=0, sticky="ew")
        tk.Entry(row_frame, textvariable=credit_var, width=10).grid(
            row=0, column=1, sticky="ew", padx=4
        )
        tk.Entry(row_frame, textvariable=score_var, width=10).grid(
            row=0, column=2, sticky="ew", padx=4
        )
        tk.Checkbutton(row_frame, variable=selected_var).grid(row=0, column=3, padx=4)

        self.rows.append(
            {
                "frame": row_frame,
                "course": course_var,
                "credit": credit_var,
                "score": score_var,
                "selected": selected_var,
            }
        )

    def remove_selected(self) -> None:
        remaining = []
        for row in self.rows:
            if row["selected"].get():
                row["frame"].destroy()
            else:
                remaining.append(row)
        self.rows = remaining
        for idx, row in enumerate(self.rows):
            row["frame"].grid(row=idx, column=0, sticky="ew", pady=2, padx=5)

    def calculate(self) -> None:
        entries = self._collect_entries()
        if not entries:
            messagebox.showinfo("提示", "请先填写至少一行有效数据")
            return
        total_credit = sum(e.credit for e in entries)
        weighted = sum(e.score * e.credit for e in entries)
        avg_score = weighted / total_credit if total_credit else 0.0
        gpa_values = [self._score_to_gpa(e.score) * e.credit for e in entries]
        gpa = sum(gpa_values) / total_credit if total_credit else 0.0
        self.total_var.set(f"总学分: {total_credit:.2f}")
        self.avg_var.set(f"加权平均分: {avg_score:.2f}")
        self.gpa_var.set(f"GPA: {gpa:.2f}")

    def save_rows(self) -> None:
        entries = self._collect_entries()
        save_grades(entries)
        messagebox.showinfo("已保存", "成绩数据已保存到 data/grades.json")

    def _collect_entries(self) -> List[GradeEntry]:
        collected: List[GradeEntry] = []
        for row in self.rows:
            course = row["course"].get().strip()
            credit_raw = row["credit"].get().strip()
            score_raw = row["score"].get().strip()
            if not course and not credit_raw and not score_raw:
                continue
            try:
                credit = float(credit_raw)
                score = float(score_raw)
            except ValueError:
                messagebox.showerror("错误", "学分和成绩必须是数字")
                return []
            collected.append(GradeEntry(course=course or "未命名课程", credit=credit, score=score))
        return collected

    def _load_saved(self) -> None:
        for entry in load_grades():
            self.add_row(entry)
        if not self.rows:
            self.add_row()

    @staticmethod
    def _score_to_gpa(score: float) -> float:
        """Map numerical score to 4.0 GPA using a common Chinese scale."""
        if score >= 90:
            return 4.0
        if score >= 85:
            return 3.7
        if score >= 82:
            return 3.3
        if score >= 78:
            return 3.0
        if score >= 75:
            return 2.7
        if score >= 72:
            return 2.3
        if score >= 68:
            return 2.0
        if score >= 64:
            return 1.5
        if score >= 60:
            return 1.0
        return 0.0
