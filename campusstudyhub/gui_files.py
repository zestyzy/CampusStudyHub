"""学习资料管理页（扫描 / 移动 / 导出索引）。"""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from typing import Callable, Dict, List

from .config import AppConfig
from .models import FileIndexEntry, format_datetime
from .storage import export_file_index, move_file_safe, scan_files


class FilesFrame(ttk.Frame):
    """Frame that scans and organizes study material files."""

    def __init__(
        self, master: tk.Widget, config: AppConfig, on_config_update: Callable[[AppConfig], None]
    ) -> None:
        super().__init__(master, padding=10)
        self.config_data = config
        self.on_config_update = on_config_update
        self.scanned_files: List[Path] = []

        self._build_widgets()

    def _build_widgets(self) -> None:
        path_frame = ttk.Frame(self)
        path_frame.pack(fill=tk.X)
        ttk.Label(path_frame, text="资料根目录：").pack(side=tk.LEFT)
        self.base_dir_var = tk.StringVar(value=self.config_data.base_directory)
        self.base_dir_entry = ttk.Entry(path_frame, textvariable=self.base_dir_var, width=60)
        self.base_dir_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(path_frame, text="浏览", command=self._choose_dir).pack(side=tk.LEFT)
        ttk.Button(path_frame, text="保存", command=self._save_base_dir).pack(side=tk.LEFT, padx=5)

        ttk.Separator(self).pack(fill=tk.X, pady=5)

        action_frame = ttk.Frame(self)
        action_frame.pack(fill=tk.X)
        ttk.Button(action_frame, text="扫描文件", command=self._scan_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="导出索引", command=self._export_index).pack(side=tk.LEFT, padx=5)

        organize_frame = ttk.LabelFrame(self, text="整理到课程目录", padding=10)
        organize_frame.pack(fill=tk.X, pady=10)
        ttk.Label(organize_frame, text="课程：").grid(row=0, column=0, sticky=tk.W)
        self.course_combo = ttk.Combobox(organize_frame, values=self.config_data.courses, width=20)
        self.course_combo.grid(row=0, column=1, padx=5)
        ttk.Label(organize_frame, text="学期/年份：").grid(row=0, column=2, sticky=tk.W)
        self.semester_entry = ttk.Entry(organize_frame, width=20)
        self.semester_entry.insert(0, "2024")
        self.semester_entry.grid(row=0, column=3, padx=5)
        ttk.Label(organize_frame, text="类型：").grid(row=0, column=4, sticky=tk.W)
        self.type_combo = ttk.Combobox(
            organize_frame, values=["课件", "作业", "论文", "代码"], width=15
        )
        self.type_combo.grid(row=0, column=5, padx=5)
        ttk.Button(organize_frame, text="移动所选", command=self._move_selected).grid(row=0, column=6, padx=5)

        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True)
        columns = ("name", "path", "size", "modified")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="extended")
        headings = ["文件名", "路径", "大小(KB)", "修改时间"]
        widths = [150, 400, 80, 150]
        for col, head, width in zip(columns, headings, widths):
            self.tree.heading(col, text=head)
            self.tree.column(col, width=width, anchor=tk.W)
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def refresh_config(self, config: AppConfig) -> None:
        """Refresh controls when configuration changes."""
        self.config_data = config
        self.base_dir_var.set(config.base_directory)
        self.course_combo.configure(values=config.courses)

    def _choose_dir(self) -> None:
        chosen = filedialog.askdirectory()
        if chosen:
            self.base_dir_var.set(chosen)

    def _save_base_dir(self) -> None:
        path = str(Path(self.base_dir_var.get().strip()).expanduser())
        if not path:
            messagebox.showerror("根目录无效", "请选择有效的资料根目录。")
            return
        self.config_data.base_directory = path
        self.on_config_update(self.config_data)
        messagebox.showinfo("已保存", "资料根目录已更新。")

    def _scan_files(self) -> None:
        base = Path(self.base_dir_var.get()).expanduser()
        self.scanned_files = scan_files(base)
        for item in self.tree.get_children():
            self.tree.delete(item)
        for path in self.scanned_files:
            stats = path.stat()
            self.tree.insert(
                "",
                tk.END,
                iid=str(path),
                values=(path.name, str(path.parent), f"{stats.st_size // 1024}", format_datetime(stats.st_mtime)),
            )
        messagebox.showinfo("扫描完成", f"共找到 {len(self.scanned_files)} 个文件。")

    def _move_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("请选择", "请先在列表中勾选要移动的文件。")
            return
        course = self.course_combo.get().strip()
        semester = self.semester_entry.get().strip()
        file_type = self.type_combo.get().strip()
        if not course or not semester or not file_type:
            messagebox.showerror("信息不完整", "请填写课程、学期/年份和类型。")
            return
        if not messagebox.askyesno("确认", f"确定将 {len(selected)} 个文件移动到课程目录吗？"):
            return

        base_dir = Path(self.base_dir_var.get()).expanduser()
        moved_count = 0
        for iid in selected:
            source = Path(iid)
            dest = base_dir / course / semester / file_type / source.name
            try:
                move_file_safe(source, dest)
                moved_count += 1
            except Exception as exc:
                messagebox.showerror("移动失败", f"无法移动 {source.name}: {exc}")
                return
        messagebox.showinfo("移动完成", f"已移动 {moved_count} 个文件。")
        self._scan_files()

    def _export_index(self) -> None:
        if not self.scanned_files:
            messagebox.showinfo("提示", "请先进行文件扫描。")
            return
        entries: List[FileIndexEntry] = []
        base = Path(self.base_dir_var.get()).expanduser()
        for path in self.scanned_files:
            stats = path.stat()
            # Infer course/type from path structure where possible.
            rel = path.relative_to(base) if path.is_relative_to(base) else path
            parts = rel.parts
            course = parts[0] if len(parts) >= 1 else "未分类课程"
            file_type = parts[2] if len(parts) >= 3 else "未分类类型"
            entries.append(
                FileIndexEntry(
                    course=course,
                    file_type=file_type,
                    filename=path.name,
                    full_path=str(path),
                    modified=format_datetime(stats.st_mtime),
                )
            )
        export_file_index(entries)
        messagebox.showinfo("导出完成", "索引已保存到 data/files_index.csv")
