from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Dict, List
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

from .storage import load_bib_cache, save_bib_cache

DATA_DIR = Path("data")
GRADES_FILE = DATA_DIR / "grades.json"


class GPAFrame(ctk.CTkFrame):
    """支持必修/选修区分的 GPA 计算器。"""

    def __init__(self, master: ctk.CTkBaseClass) -> None:
        super().__init__(master)
        self.rows: List[Dict[str, str]] = []
        self.row_widgets: List[Dict[str, ctk.CTkBaseClass]] = []
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text="GPA 计算器", font=("PingFang SC", 24, "bold")).grid(row=0, column=0, pady=10)
        btn_row = ctk.CTkFrame(self)
        btn_row.grid(row=1, column=0, pady=6)
        ctk.CTkButton(btn_row, text="新增课程", command=self._add_row).grid(row=0, column=0, padx=6)
        ctk.CTkButton(btn_row, text="删除选中", command=self._remove_selected).grid(row=0, column=1, padx=6)
        ctk.CTkButton(btn_row, text="计算", command=self._calculate).grid(row=0, column=2, padx=6)
        ctk.CTkButton(btn_row, text="保存", command=self._save).grid(row=0, column=3, padx=6)

        self.table = ctk.CTkScrollableFrame(self, height=280)
        self.table.grid(row=2, column=0, padx=10, pady=6, sticky="nsew")
        self.table.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        headers = ["选中", "课程名称", "学分", "成绩", "类型(必修/选修)"]
        for col, text in enumerate(headers):
            ctk.CTkLabel(self.table, text=text).grid(row=0, column=col, padx=4, pady=2)

        self.summary = ctk.CTkLabel(
            self,
            text="总学分：0 | 平均分：0 | GPA：0 | 专业GPA：0",
            font=("PingFang SC", 16, "bold"),
        )
        self.summary.grid(row=3, column=0, pady=8)

    def _add_row(self, data: Dict[str, str] | None = None) -> None:
        idx = len(self.row_widgets) + 1
        var = ctk.BooleanVar(value=False)
        chk = ctk.CTkCheckBox(self.table, text="", variable=var)
        name_entry = ctk.CTkEntry(self.table)
        credit_entry = ctk.CTkEntry(self.table, width=80)
        score_entry = ctk.CTkEntry(self.table, width=80)
        type_option = ctk.CTkOptionMenu(self.table, values=["必修", "选修"])
        if data:
            name_entry.insert(0, data.get("name", ""))
            credit_entry.insert(0, str(data.get("credit", "")))
            score_entry.insert(0, str(data.get("score", "")))
            type_option.set(data.get("type", "必修"))
        chk.grid(row=idx, column=0, padx=4, pady=2)
        name_entry.grid(row=idx, column=1, padx=4, pady=2, sticky="ew")
        credit_entry.grid(row=idx, column=2, padx=4, pady=2)
        score_entry.grid(row=idx, column=3, padx=4, pady=2)
        type_option.grid(row=idx, column=4, padx=4, pady=2)
        self.row_widgets.append({
            "var": var,
            "name": name_entry,
            "credit": credit_entry,
            "score": score_entry,
            "type": type_option,
        })

    def _remove_selected(self) -> None:
        remaining = []
        for widgets in self.row_widgets:
            if widgets["var"].get():
                for w in widgets.values():
                    if isinstance(w, ctk.CTkBaseClass):
                        w.destroy()
            else:
                remaining.append(widgets)
        self.row_widgets = remaining

    def _calculate(self) -> None:
        entries = []
        for widgets in self.row_widgets:
            try:
                credit = float(widgets["credit"].get())
                score = float(widgets["score"].get())
                entries.append({
                    "name": widgets["name"].get(),
                    "credit": credit,
                    "score": score,
                    "type": widgets["type"].get(),
                })
            except ValueError:
                continue
        if not entries:
            messagebox.showinfo("提示", "请先输入有效成绩")
            return
        total_credits = sum(e["credit"] for e in entries)
        weighted = sum(e["credit"] * e["score"] for e in entries) / total_credits
        gpa = sum(e["credit"] * self._score_to_gpa(e["score"]) for e in entries) / total_credits
        major_entries = [e for e in entries if e["type"] == "必修"]
        if major_entries:
            major_credits = sum(e["credit"] for e in major_entries)
            major_gpa = sum(e["credit"] * self._score_to_gpa(e["score"]) for e in major_entries) / major_credits
        else:
            major_gpa = 0
        self.summary.configure(
            text=f"总学分：{total_credits:.1f} | 平均分：{weighted:.2f} | GPA：{gpa:.2f} | 专业GPA：{major_gpa:.2f}"
        )

    def _score_to_gpa(self, score: float) -> float:
        if score >= 90:
            return 4.0
        if score >= 85:
            return 3.7
        if score >= 80:
            return 3.3
        if score >= 75:
            return 3.0
        if score >= 70:
            return 2.7
        if score >= 67:
            return 2.3
        if score >= 65:
            return 2.0
        if score >= 62:
            return 1.7
        if score >= 60:
            return 1.0
        return 0.0

    def _save(self) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        payload = []
        for widgets in self.row_widgets:
            payload.append({
                "name": widgets["name"].get(),
                "credit": widgets["credit"].get(),
                "score": widgets["score"].get(),
                "type": widgets["type"].get(),
            })
        GRADES_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        messagebox.showinfo("保存", "已保存到 data/grades.json")

    def _load(self) -> None:
        if GRADES_FILE.exists():
            try:
                data = json.loads(GRADES_FILE.read_text(encoding="utf-8"))
            except Exception:
                data = []
            for row in data:
                self._add_row(row)


class BibtexFrame(ctk.CTkFrame):
    """带 DOI 缓存与批量生成的 BibTeX 生成器。"""

    def __init__(self, master: ctk.CTkBaseClass) -> None:
        super().__init__(master)
        self.mode = ctk.StringVar(value="会议")
        self.entries: Dict[str, ctk.CTkEntry] = {}
        self.cache: dict = load_bib_cache()
        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text="BibTeX 生成器", font=("PingFang SC", 24, "bold")).grid(row=0, column=0, pady=10)
        toggle = ctk.CTkSegmentedButton(self, values=["会议", "期刊"], variable=self.mode, command=self._render_fields)
        toggle.set("会议")
        toggle.grid(row=1, column=0, pady=6)

        doi_row = ctk.CTkFrame(self)
        doi_row.grid(row=2, column=0, pady=4, padx=10, sticky="ew")
        doi_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(doi_row, text="DOI (可选)").grid(row=0, column=0, padx=4)
        self.doi_entry = ctk.CTkEntry(doi_row, placeholder_text="输入 DOI 后点击抓取")
        self.doi_entry.grid(row=0, column=1, padx=4, sticky="ew")
        ctk.CTkButton(doi_row, text="DOI 抓取", command=self._fetch_doi).grid(row=0, column=2, padx=4)

        batch_row = ctk.CTkFrame(self)
        batch_row.grid(row=3, column=0, pady=4, padx=10, sticky="ew")
        batch_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(batch_row, text="批量 DOI/标题 (每行一个，可混合)").grid(row=0, column=0, sticky="w")
        self.batch_box = ctk.CTkTextbox(batch_row, height=80)
        self.batch_box.grid(row=1, column=0, sticky="ew", pady=4)
        ctk.CTkButton(batch_row, text="批量生成", command=self._batch_generate).grid(row=2, column=0, pady=2)

        self.form = ctk.CTkFrame(self)
        self.form.grid(row=4, column=0, padx=10, pady=6, sticky="ew")
        self.form.grid_columnconfigure(1, weight=1)

        self.output = ctk.CTkTextbox(self, height=180)
        self.output.grid(row=5, column=0, padx=10, pady=8, sticky="nsew")
        ctk.CTkButton(self, text="生成", command=self._generate).grid(row=6, column=0, pady=6)

        self._render_fields()

    def _render_fields(self) -> None:
        for widget in self.form.winfo_children():
            widget.destroy()
        self.entries.clear()
        is_conf = self.mode.get() == "会议"
        fields = [
            ("key", "引用 key"),
            ("author", "作者"),
            ("title", "标题"),
            ("booktitle", "会议名"),
            ("journal", "期刊名"),
            ("year", "年份"),
            ("pages", "页码"),
            ("volume", "卷"),
            ("number", "期"),
        ]
        row = 0
        for field, label in fields:
            if is_conf and field in {"journal", "volume", "number"}:
                continue
            if not is_conf and field in {"booktitle"}:
                continue
            ctk.CTkLabel(self.form, text=label).grid(row=row, column=0, sticky="e", padx=4, pady=2)
            entry = ctk.CTkEntry(self.form)
            entry.grid(row=row, column=1, sticky="ew", padx=4, pady=2)
            self.entries[field] = entry
            row += 1

    def _generate(self) -> None:
        data = {k: v.get().strip() for k, v in self.entries.items()}
        if not data.get("key"):
            messagebox.showinfo("提示", "请填写引用 key")
            return
        if self.mode.get() == "会议":
            body = """@inproceedings{{{key},
  author = {{{author}}},
  title = {{{title}}},
  booktitle = {{{booktitle}}},
  year = {{{year}}},
  pages = {{{pages}}}
}}""".format(**data)
        else:
            body = """@article{{{key},
  author = {{{author}}},
  title = {{{title}}},
  journal = {{{journal}}},
  volume = {{{volume}}},
  number = {{{number}}},
  year = {{{year}}},
  pages = {{{pages}}}
}}""".format(**data)
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("end", body)
        self.output.configure(state="disabled")

    def _fetch_doi(self) -> Dict[str, str]:
        doi = self.doi_entry.get().strip()
        if not doi:
            messagebox.showinfo("提示", "请输入 DOI")
            return {}
        # 缓存命中
        if doi in self.cache:
            info = self.cache[doi]
            self._fill_fields(info)
            messagebox.showinfo("缓存", "已从缓存填充，可直接生成")
            return info
        url = f"https://api.crossref.org/works/{doi}"
        try:
            with urllib.request.urlopen(url, timeout=8) as resp:  # type: ignore[arg-type]
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            info = data.get("message", {})
            mapping = self._map_crossref(info, doi)
            self.cache[doi] = mapping
            save_bib_cache(self.cache)
            self._fill_fields(mapping)
            messagebox.showinfo("完成", "已填充 DOI 信息，可继续校对后生成")
            return mapping
        except Exception as exc:
            messagebox.showinfo("提示", f"抓取失败：{exc}\n可手动填写字段继续生成")
            return {}

    def _fill_fields(self, mapping: Dict[str, str]) -> None:
        self.mode.set("会议" if mapping.get("entry_type") == "inproceedings" else "期刊")
        self._render_fields()
        for field, value in mapping.items():
            if field in self.entries:
                self.entries[field].delete(0, "end")
                self.entries[field].insert(0, str(value))

    def _map_crossref(self, info: dict, doi: str) -> Dict[str, str]:
        entry_type = info.get("type", "")
        is_conf = "proceeding" in entry_type or "conference" in entry_type
        authors = info.get("author", [])
        author_str = " and ".join(
            f"{a.get('family','')} {a.get('given','')}".strip() for a in authors if a
        )
        mapping = {
            "entry_type": "inproceedings" if is_conf else "article",
            "author": author_str,
            "title": info.get("title", [""])[0] if info.get("title") else "",
            "booktitle": info.get("container-title", [""])[0] if info.get("container-title") else "",
            "journal": info.get("container-title", [""])[0] if info.get("container-title") else "",
            "year": str(
                info.get("published-print", {}).get("date-parts", [[""]])[0][0]
                if info.get("published-print")
                else info.get("created", {}).get("date-parts", [[""]])[0][0]
            ),
            "pages": info.get("page", ""),
            "volume": info.get("volume", ""),
            "number": info.get("issue", ""),
            "key": (info.get("DOI", doi) or "doi").replace("/", "-"),
        }
        return mapping

    def _batch_generate(self) -> None:
        lines = [ln.strip() for ln in self.batch_box.get("1.0", "end").splitlines() if ln.strip()]
        if not lines:
            messagebox.showinfo("提示", "请输入批量 DOI 或标题")
            return
        outputs: List[str] = []
        for idx, line in enumerate(lines, start=1):
            if "/" in line or line.lower().startswith("10."):
                self.doi_entry.delete(0, "end")
                self.doi_entry.insert(0, line)
                info = self._fetch_doi()
            else:
                info = {"entry_type": "article", "title": line, "author": "", "key": f"entry{idx}"}
                self.mode.set("期刊")
                self._render_fields()
                self.entries["title"].insert(0, line)
                self.entries["key"].insert(0, f"entry{idx}")
            if info:
                outputs.append(self._build_body(info))
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("end", "\n\n".join(outputs))
        self.output.configure(state="disabled")

    def _build_body(self, info: Dict[str, str]) -> str:
        is_conf = info.get("entry_type") == "inproceedings"
        defaults = {
            "author": "",
            "title": "",
            "booktitle": "",
            "journal": "",
            "year": "",
            "pages": "",
            "volume": "",
            "number": "",
        }
        for key, default in defaults.items():
            info.setdefault(key, default)
        template_conf = """@inproceedings{{{key},
  author = {{{author}}},
  title = {{{title}}},
  booktitle = {{{booktitle}}},
  year = {{{year}}},
  pages = {{{pages}}}
}}"""
        template_jour = """@article{{{key},
  author = {{{author}}},
  title = {{{title}}},
  journal = {{{journal}}},
  volume = {{{volume}}},
  number = {{{number}}},
  year = {{{year}}},
  pages = {{{pages}}}
}}"""
        tpl = template_conf if is_conf else template_jour
        return tpl.format(**info)


class FigureComposerFrame(ctk.CTkFrame):
    """高 DPI 科研拼图工具，提供字体/背景/边框等精细设置。"""

    def __init__(self, master: ctk.CTkBaseClass) -> None:
        super().__init__(master)
        self.images: List[Path] = []
        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text="科研拼图", font=("PingFang SC", 24, "bold")).grid(row=0, column=0, pady=10)

        top_row = ctk.CTkFrame(self)
        top_row.grid(row=1, column=0, pady=6, padx=10, sticky="ew")
        ctk.CTkButton(top_row, text="选择图片", command=self._choose_files).grid(row=0, column=0, padx=6)
        self.file_label = ctk.CTkLabel(top_row, text="未选择")
        self.file_label.grid(row=0, column=1, padx=6)

        grid_row = ctk.CTkFrame(self)
        grid_row.grid(row=2, column=0, pady=6)
        self.rows_entry = ctk.CTkEntry(grid_row, width=80, placeholder_text="行")
        self.cols_entry = ctk.CTkEntry(grid_row, width=80, placeholder_text="列")
        self.pad_entry = ctk.CTkEntry(grid_row, width=80, placeholder_text="间距")
        for idx, widget in enumerate([self.rows_entry, self.cols_entry, self.pad_entry]):
            widget.grid(row=0, column=idx, padx=4)

        title_row = ctk.CTkFrame(self)
        title_row.grid(row=3, column=0, pady=6)
        self.title_entry = ctk.CTkEntry(title_row, width=260, placeholder_text="主标题（可选）")
        self.title_entry.grid(row=0, column=0, padx=4)
        self.sublabel_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(title_row, text="自动子标签 (a)(b)...", variable=self.sublabel_var).grid(row=0, column=1, padx=4)

        font_row = ctk.CTkFrame(self)
        font_row.grid(row=4, column=0, pady=6)
        ctk.CTkLabel(font_row, text="字体：").grid(row=0, column=0)
        self.font_family = ctk.CTkOptionMenu(font_row, values=["Arial", "Times New Roman", "Helvetica", "PingFang SC"])
        self.font_family.grid(row=0, column=1, padx=4)
        self.font_size = ctk.CTkEntry(font_row, width=80, placeholder_text="字号", fg_color="#1f6aa5")
        self.font_size.insert(0, "40")
        self.font_size.grid(row=0, column=2, padx=4)
        self.bold_var = ctk.BooleanVar(value=False)
        self.italic_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(font_row, text="粗体", variable=self.bold_var).grid(row=0, column=3, padx=4)
        ctk.CTkCheckBox(font_row, text="斜体", variable=self.italic_var).grid(row=0, column=4, padx=4)

        styling_row = ctk.CTkFrame(self)
        styling_row.grid(row=5, column=0, pady=6)
        ctk.CTkLabel(styling_row, text="背景色 #RRGGBB").grid(row=0, column=0, padx=4)
        self.bg_entry = ctk.CTkEntry(styling_row, width=100)
        self.bg_entry.insert(0, "#121212")
        self.bg_entry.grid(row=0, column=1, padx=4)
        ctk.CTkLabel(styling_row, text="边框像素").grid(row=0, column=2, padx=4)
        self.border_entry = ctk.CTkEntry(styling_row, width=80)
        self.border_entry.insert(0, "0")
        self.border_entry.grid(row=0, column=3, padx=4)
        ctk.CTkLabel(styling_row, text="子标签位置").grid(row=0, column=4, padx=4)
        self.label_pos = ctk.CTkOptionMenu(styling_row, values=["左上", "底部居中"])
        self.label_pos.grid(row=0, column=5, padx=4)

        dpi_row = ctk.CTkFrame(self)
        dpi_row.grid(row=6, column=0, pady=6)
        ctk.CTkLabel(dpi_row, text="DPI：").grid(row=0, column=0)
        self.dpi_option = ctk.CTkOptionMenu(dpi_row, values=["72", "150", "300", "600"])
        self.dpi_option.set("300")
        self.dpi_option.grid(row=0, column=1, padx=4)

        ctk.CTkButton(self, text="生成并保存", command=self._compose).grid(row=7, column=0, pady=10)

    def _choose_files(self) -> None:
        files = filedialog.askopenfilenames(title="选择图片", filetypes=[("Images", "*.png *.jpg *.jpeg")])
        if files:
            self.images = [Path(f) for f in files]
            self.file_label.configure(text=f"已选 {len(self.images)} 张")

    def _compose(self) -> None:
        if not self.images:
            messagebox.showinfo("提示", "请先选择图片")
            return
        try:
            rows = int(self.rows_entry.get() or 1)
            cols = int(self.cols_entry.get() or 1)
            pad = int(self.pad_entry.get() or 10)
            dpi = int(self.dpi_option.get())
            font_size = int(self.font_size.get() or 40)
            border = int(self.border_entry.get() or 0)
        except ValueError:
            messagebox.showinfo("提示", "行/列/间距/DPI/字号/边框需要为数字")
            return

        images = [Image.open(p) for p in self.images]
        base_w, base_h = images[0].size
        resized = []
        for img in images:
            resized.append(img.resize((base_w, base_h), Image.Resampling.LANCZOS))

        title_text = self.title_entry.get().strip()
        font = self._resolve_font(self.font_family.get(), font_size, self.bold_var.get(), self.italic_var.get())

        title_height = font_size + 10 if title_text else 0
        canvas_w = cols * base_w + (cols + 1) * pad + 2 * border
        canvas_h = rows * base_h + (rows + 1) * pad + title_height + 2 * border
        bg_color = self._parse_color(self.bg_entry.get())
        canvas = Image.new("RGB", (canvas_w, canvas_h), color=bg_color)
        draw = ImageDraw.Draw(canvas)

        y_offset = border
        if title_text:
            tw, th = draw.textsize(title_text, font=font)
            draw.text(((canvas_w - tw) / 2, border + pad), title_text, font=font, fill="white", stroke_width=1, stroke_fill="black")
            y_offset += title_height

        for idx in range(rows * cols):
            if idx >= len(resized):
                break
            r = idx // cols
            c = idx % cols
            x = border + pad + c * (base_w + pad)
            y = y_offset + pad + r * (base_h + pad)
            canvas.paste(resized[idx], (x, y))
            if self.sublabel_var.get():
                label = f"({chr(97 + idx)})"
                pos = (x + 10, y + 10)
                if self.label_pos.get() == "底部居中":
                    tw, th = draw.textsize(label, font=font)
                    pos = (x + (base_w - tw) / 2, y + base_h - th - 10)
                draw.text(pos, label, font=font, fill="black", stroke_width=1, stroke_fill="white")

        save_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if save_path:
            canvas.save(save_path, dpi=(dpi, dpi))
            messagebox.showinfo("完成", "已输出高分辨率拼图")

    def _parse_color(self, text: str) -> tuple[int, int, int]:
        try:
            text = text.lstrip("#")
            return tuple(int(text[i : i + 2], 16) for i in (0, 2, 4))
        except Exception:
            return (18, 18, 18)

    def _font_path(self, name: str, bold: bool, italic: bool) -> str | None:
        mapping = {
            ("Arial", False, False): "/Library/Fonts/Arial.ttf",
            ("Arial", True, False): "/Library/Fonts/Arial Bold.ttf",
            ("Arial", False, True): "/Library/Fonts/Arial Italic.ttf",
            ("Arial", True, True): "/Library/Fonts/Arial Bold Italic.ttf",
            ("Times New Roman", False, False): "/Library/Fonts/Times New Roman.ttf",
            ("Times New Roman", True, False): "/Library/Fonts/Times New Roman Bold.ttf",
            ("Times New Roman", False, True): "/Library/Fonts/Times New Roman Italic.ttf",
            ("Times New Roman", True, True): "/Library/Fonts/Times New Roman Bold Italic.ttf",
            ("Helvetica", False, False): "/System/Library/Fonts/Helvetica.ttc",
            ("PingFang SC", False, False): "/System/Library/Fonts/PingFang.ttc",
        }
        return mapping.get((name, bold, italic)) or mapping.get((name, False, False))

    def _resolve_font(self, family: str, size: int, bold: bool, italic: bool) -> ImageFont.FreeTypeFont:
        path = self._font_path(family, bold, italic)
        try:
            return ImageFont.truetype(path or "Arial", size=size)
        except Exception:
            return ImageFont.load_default()

