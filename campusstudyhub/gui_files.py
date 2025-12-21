"""Files tab UI for CampusStudyHub."""
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
        ttk.Label(path_frame, text="Base directory:").pack(side=tk.LEFT)
        self.base_dir_var = tk.StringVar(value=self.config_data.base_directory)
        self.base_dir_entry = ttk.Entry(path_frame, textvariable=self.base_dir_var, width=60)
        self.base_dir_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(path_frame, text="Browse", command=self._choose_dir).pack(side=tk.LEFT)
        ttk.Button(path_frame, text="Save", command=self._save_base_dir).pack(side=tk.LEFT, padx=5)

        ttk.Separator(self).pack(fill=tk.X, pady=5)

        action_frame = ttk.Frame(self)
        action_frame.pack(fill=tk.X)
        ttk.Button(action_frame, text="Scan files", command=self._scan_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Export index", command=self._export_index).pack(side=tk.LEFT, padx=5)

        organize_frame = ttk.LabelFrame(self, text="Organize", padding=10)
        organize_frame.pack(fill=tk.X, pady=10)
        ttk.Label(organize_frame, text="Course:").grid(row=0, column=0, sticky=tk.W)
        self.course_combo = ttk.Combobox(organize_frame, values=self.config_data.courses, width=20)
        self.course_combo.grid(row=0, column=1, padx=5)
        ttk.Label(organize_frame, text="Semester/Year:").grid(row=0, column=2, sticky=tk.W)
        self.semester_entry = ttk.Entry(organize_frame, width=20)
        self.semester_entry.insert(0, "2024")
        self.semester_entry.grid(row=0, column=3, padx=5)
        ttk.Label(organize_frame, text="Type:").grid(row=0, column=4, sticky=tk.W)
        self.type_combo = ttk.Combobox(organize_frame, values=["slides", "assignments", "papers", "code"], width=15)
        self.type_combo.grid(row=0, column=5, padx=5)
        ttk.Button(organize_frame, text="Move selected", command=self._move_selected).grid(row=0, column=6, padx=5)

        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True)
        columns = ("name", "path", "size", "modified")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="extended")
        headings = ["Name", "Path", "Size (KB)", "Modified"]
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
            messagebox.showerror("Base directory", "Please select a valid directory.")
            return
        self.config_data.base_directory = path
        self.on_config_update(self.config_data)
        messagebox.showinfo("Saved", "Base directory updated.")

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
        messagebox.showinfo("Scan complete", f"Found {len(self.scanned_files)} files.")

    def _move_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Move files", "Please select one or more files from the list.")
            return
        course = self.course_combo.get().strip()
        semester = self.semester_entry.get().strip()
        file_type = self.type_combo.get().strip()
        if not course or not semester or not file_type:
            messagebox.showerror("Organize", "Please specify course, semester/year, and type.")
            return
        if not messagebox.askyesno("Confirm", f"Move {len(selected)} files into course folder?"):
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
                messagebox.showerror("Move error", f"Could not move {source.name}: {exc}")
                return
        messagebox.showinfo("Move complete", f"Moved {moved_count} files.")
        self._scan_files()

    def _export_index(self) -> None:
        if not self.scanned_files:
            messagebox.showinfo("Export", "Please scan files first.")
            return
        entries: List[FileIndexEntry] = []
        base = Path(self.base_dir_var.get()).expanduser()
        for path in self.scanned_files:
            stats = path.stat()
            # Infer course/type from path structure where possible.
            rel = path.relative_to(base) if path.is_relative_to(base) else path
            parts = rel.parts
            course = parts[0] if len(parts) >= 1 else "Unknown"
            file_type = parts[2] if len(parts) >= 3 else "Uncategorized"
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
        messagebox.showinfo("Export", "File index exported to data/files_index.csv")
