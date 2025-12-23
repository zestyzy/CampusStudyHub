"""BibTeX generator and formatter."""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import messagebox
from typing import Dict


class BibtexGenerator(tk.Frame):
    """Generate or validate simple BibTeX entries from title/DOI."""

    def __init__(self, master: tk.Misc):
        super().__init__(master)
        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)
        tk.Label(self, text="论文标题").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.title_var = tk.StringVar()
        tk.Entry(self, textvariable=self.title_var).grid(
            row=0, column=1, sticky="ew", padx=5, pady=2
        )

        tk.Label(self, text="DOI (可选)").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.doi_var = tk.StringVar()
        tk.Entry(self, textvariable=self.doi_var).grid(
            row=1, column=1, sticky="ew", padx=5, pady=2
        )

        tk.Label(self, text="作者 (逗号分隔)").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.authors_var = tk.StringVar()
        tk.Entry(self, textvariable=self.authors_var).grid(
            row=2, column=1, sticky="ew", padx=5, pady=2
        )

        tk.Label(self, text="年份").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        self.year_var = tk.StringVar()
        tk.Entry(self, textvariable=self.year_var).grid(
            row=3, column=1, sticky="ew", padx=5, pady=2
        )

        tk.Label(self, text="期刊/会议").grid(row=4, column=0, sticky="w", padx=5, pady=2)
        self.venue_var = tk.StringVar()
        tk.Entry(self, textvariable=self.venue_var).grid(
            row=4, column=1, sticky="ew", padx=5, pady=2
        )

        btn_frame = tk.Frame(self)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=5)
        tk.Button(btn_frame, text="生成", command=self.generate).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="校验格式", command=self.validate).pack(
            side=tk.LEFT, padx=4
        )
        tk.Button(btn_frame, text="复制", command=self.copy_to_clipboard).pack(
            side=tk.LEFT, padx=4
        )

        tk.Label(self, text="生成的 BibTeX").grid(row=6, column=0, sticky="w", padx=5)
        self.output = tk.Text(self, height=10)
        self.output.grid(row=7, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        self.rowconfigure(7, weight=1)

    def generate(self) -> None:
        """Create a BibTeX entry based on provided fields."""
        title = self.title_var.get().strip()
        doi = self.doi_var.get().strip()
        if not title and not doi:
            messagebox.showinfo("提示", "请至少填写标题或 DOI")
            return

        authors = [a.strip() for a in self.authors_var.get().split(",") if a.strip()]
        year = self.year_var.get().strip() or "2024"
        venue = self.venue_var.get().strip() or "未知出版物"
        key = self._build_key(title=title, doi=doi, year=year)

        entry: Dict[str, str] = {
            "title": title or "未命名条目",
            "author": " and ".join(authors) if authors else "佚名",
            "year": year,
            "journal": venue,
        }
        if doi:
            entry["doi"] = doi

        lines = [f"@article{{{key},"]
        for k, v in entry.items():
            lines.append(f"  {k} = {{{v}}},")
        lines.append("}")
        bib = "\n".join(lines)
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, bib)

    def validate(self) -> None:
        """Run a tiny BibTeX-like validation to spot common mistakes."""
        content = self.output.get("1.0", tk.END).strip()
        if not content:
            messagebox.showinfo("提示", "先生成或粘贴 BibTeX 内容")
            return
        if not content.startswith("@"):
            messagebox.showerror("格式错误", "必须以 @ 开头，例如 @article{...}")
            return
        braces = 0
        for ch in content:
            if ch == "{":
                braces += 1
            elif ch == "}":
                braces -= 1
        if braces != 0:
            messagebox.showerror("格式错误", "大括号不平衡，请检查")
            return
        if not re.search(r"@[a-zA-Z]+\{[^,]+,", content):
            messagebox.showerror("格式错误", "缺少条目类型或 key")
            return
        messagebox.showinfo("通过", "看起来是有效的 BibTeX 结构")

    def copy_to_clipboard(self) -> None:
        text = self.output.get("1.0", tk.END).strip()
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("已复制", "BibTeX 已复制到剪贴板")

    @staticmethod
    def _build_key(title: str, doi: str, year: str) -> str:
        if doi:
            cleaned = re.sub(r"[^a-zA-Z0-9]", "", doi)
            return (cleaned[:20] + year)[-24:]
        words = [w for w in re.sub(r"[^a-zA-Z0-9 ]", "", title).split() if w]
        base = "".join(words[:3]) or "entry"
        return f"{base[:12]}{year}"
