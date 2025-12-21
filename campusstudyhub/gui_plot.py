"""Figure composition tool using Pillow for publication-ready grids."""
from __future__ import annotations

import string
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import List

from PIL import Image, ImageDraw, ImageFont


class FigureComposer(tk.Frame):
    """Tk Frame that stitches multiple images into a single high-resolution figure."""

    def __init__(self, master: tk.Misc):
        super().__init__(master)
        self.selected_files: List[Path] = []
        self._build_ui()

    def _build_ui(self) -> None:
        """Construct layout controls."""
        self.columnconfigure(0, weight=1)

        file_frame = tk.Frame(self)
        file_frame.grid(row=0, column=0, sticky="ew", pady=5, padx=10)
        tk.Button(file_frame, text="选择图片", command=self.select_files).pack(
            side=tk.LEFT, padx=(0, 10)
        )
        self.file_count_var = tk.StringVar(value="未选择文件")
        tk.Label(file_frame, textvariable=self.file_count_var).pack(side=tk.LEFT)

        grid_frame = tk.LabelFrame(self, text="布局设置")
        grid_frame.grid(row=1, column=0, sticky="ew", pady=5, padx=10)
        for i in range(4):
            grid_frame.columnconfigure(i, weight=1)

        tk.Label(grid_frame, text="行 (Rows)").grid(row=0, column=0, sticky="w")
        self.rows_var = tk.IntVar(value=2)
        tk.Entry(grid_frame, textvariable=self.rows_var, width=6).grid(
            row=0, column=1, sticky="w"
        )

        tk.Label(grid_frame, text="列 (Cols)").grid(row=0, column=2, sticky="w")
        self.cols_var = tk.IntVar(value=2)
        tk.Entry(grid_frame, textvariable=self.cols_var, width=6).grid(
            row=0, column=3, sticky="w"
        )

        tk.Label(grid_frame, text="内边距 / Padding (px)").grid(row=1, column=0, sticky="w")
        self.padding_var = tk.IntVar(value=20)
        tk.Entry(grid_frame, textvariable=self.padding_var, width=6).grid(
            row=1, column=1, sticky="w"
        )

        title_frame = tk.LabelFrame(self, text="标题与标注")
        title_frame.grid(row=2, column=0, sticky="ew", pady=5, padx=10)
        for i in range(2):
            title_frame.columnconfigure(i, weight=1)

        tk.Label(title_frame, text="主标题（可选）").grid(
            row=0, column=0, sticky="w", pady=2
        )
        self.title_var = tk.StringVar()
        tk.Entry(title_frame, textvariable=self.title_var).grid(
            row=0, column=1, sticky="ew", pady=2
        )

        self.sublabel_var = tk.BooleanVar(value=True)
        tk.Checkbutton(title_frame, text="添加子图标签 (a)(b)...", variable=self.sublabel_var).grid(
            row=1, column=0, sticky="w", pady=2
        )

        tk.Label(title_frame, text="字体大小").grid(row=1, column=1, sticky="w")
        self.font_size_var = tk.IntVar(value=40)
        tk.Entry(title_frame, textvariable=self.font_size_var, width=6).grid(
            row=1, column=1, sticky="e"
        )

        action_frame = tk.Frame(self)
        action_frame.grid(row=3, column=0, pady=10, padx=10, sticky="e")
        tk.Button(action_frame, text="生成并保存", command=self.generate_and_save).pack()

    def select_files(self) -> None:
        """Allow user to pick multiple image files."""
        paths = filedialog.askopenfilenames(
            title="选择图片", filetypes=[("Images", "*.png *.jpg *.jpeg")]
        )
        if not paths:
            return
        self.selected_files = [Path(p) for p in paths]
        self.file_count_var.set(f"已选择 {len(self.selected_files)} 张图片")

    def generate_and_save(self) -> None:
        """Compose images and save with 300 DPI."""
        if not self.selected_files:
            messagebox.showinfo("提示", "请先选择图片文件")
            return

        try:
            rows = max(1, int(self.rows_var.get()))
            cols = max(1, int(self.cols_var.get()))
            padding = max(0, int(self.padding_var.get()))
            font_size = max(10, int(self.font_size_var.get()))
        except ValueError:
            messagebox.showerror("错误", "行/列/间距/字体大小必须是数字")
            return

        images: List[Image.Image] = []
        try:
            for path in self.selected_files:
                images.append(Image.open(path))
        except Exception as exc:  # pragma: no cover - GUI message
            messagebox.showerror("错误", f"无法打开图片: {exc}")
            return

        if not images:
            messagebox.showerror("错误", "未能加载任何图片")
            return

        first_w, first_h = images[0].size
        resized: List[Image.Image] = []
        for img in images:
            resized.append(img.resize((first_w, first_h), Image.Resampling.LANCZOS))

        cell_w, cell_h = first_w, first_h
        title_text = self.title_var.get().strip()
        font = self._load_font(font_size)
        draw_dummy = ImageDraw.Draw(resized[0])
        title_bbox = draw_dummy.textbbox((0, 0), title_text, font=font) if title_text else None
        title_height = (title_bbox[3] - title_bbox[1]) if title_bbox else 0

        canvas_w = cols * cell_w + padding * (cols + 1)
        canvas_h = rows * cell_h + padding * (rows + 1) + title_height
        composed = Image.new("RGB", (canvas_w, canvas_h), "white")
        drawer = ImageDraw.Draw(composed)

        if title_text and title_bbox:
            title_width = title_bbox[2] - title_bbox[0]
            title_x = (canvas_w - title_width) // 2
            title_y = max(padding // 2, 5)
            drawer.text(
                (title_x, title_y),
                title_text,
                fill="black",
                font=font,
                stroke_width=2,
                stroke_fill="white",
            )

        usable_images = resized[: rows * cols]
        label_iter = iter(string.ascii_lowercase)
        start_y = padding + title_height
        for idx, img in enumerate(usable_images):
            r = idx // cols
            c = idx % cols
            x = padding + c * (cell_w + padding)
            y = start_y + r * (cell_h + padding)
            composed.paste(img, (x, y))
            if self.sublabel_var.get():
                try:
                    label = f"({next(label_iter)})"
                except StopIteration:
                    label = f"({idx+1})"
                label_x = x + 10
                label_y = y + 10
                drawer.text(
                    (label_x, label_y),
                    label,
                    fill="black",
                    font=font,
                    stroke_width=2,
                    stroke_fill="white",
                )

        save_path = filedialog.asksaveasfilename(
            title="保存合成图", defaultextension=".png", filetypes=[("PNG", "*.png")]
        )
        if not save_path:
            return

        try:
            composed.save(save_path, dpi=(300, 300))
            messagebox.showinfo("完成", f"已保存到 {save_path}")
        except Exception as exc:  # pragma: no cover - GUI message
            messagebox.showerror("错误", f"保存失败: {exc}")

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Try to load a readable font, fallback to default."""
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size=size)
        except Exception:
            return ImageFont.load_default()
