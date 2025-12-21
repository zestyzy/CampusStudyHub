"""系统资源监视面板，展示 GPU/CPU/磁盘使用情况。"""
from __future__ import annotations

import platform
import shutil
import subprocess
from typing import Iterable

import customtkinter as ctk


class ResourceMonitorFrame(ctk.CTkFrame):
    """展示常用资源监控命令输出（gpustat、top、df -h）。"""

    def __init__(self, master: ctk.CTkBaseClass) -> None:
        super().__init__(master)
        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        header = ctk.CTkLabel(
            self, text="计算资源监控", font=("PingFang SC", 22, "bold")
        )
        header.grid(row=0, column=0, pady=(4, 8))

        btn_row = ctk.CTkFrame(self)
        btn_row.grid(row=1, column=0, pady=4)
        ctk.CTkButton(btn_row, text="刷新全部", command=self.refresh_all).pack(side="left", padx=6)

        self.gpu_box = ctk.CTkTextbox(self, height=120)
        self.cpu_box = ctk.CTkTextbox(self, height=180)
        self.disk_box = ctk.CTkTextbox(self, height=140)

        ctk.CTkLabel(self, text="GPU (gpustat -i)", anchor="w").grid(
            row=2, column=0, sticky="w", padx=4, pady=(6, 2)
        )
        self.gpu_box.grid(row=3, column=0, sticky="nsew", padx=4)

        ctk.CTkLabel(self, text="CPU / 进程 (top)", anchor="w").grid(
            row=4, column=0, sticky="w", padx=4, pady=(6, 2)
        )
        self.cpu_box.grid(row=5, column=0, sticky="nsew", padx=4)

        ctk.CTkLabel(self, text="磁盘 (df -h)", anchor="w").grid(
            row=6, column=0, sticky="w", padx=4, pady=(6, 2)
        )
        self.disk_box.grid(row=7, column=0, sticky="nsew", padx=4, pady=(0, 6))

    def refresh_all(self) -> None:
        """刷新所有监控信息。"""
        self._fill_box(self.gpu_box, self._run_variants("gpustat", [("gpustat", "-i")]))

        if platform.system().lower() == "darwin":
            top_cmds = [("top", "-l", "1", "-n", "5")]
        else:
            top_cmds = [("top", "-b", "-n", "1")]
        self._fill_box(self.cpu_box, self._run_variants("top", top_cmds))

        self._fill_box(self.disk_box, self._run_variants("df", [("df", "-h")]))

    def _run_variants(self, name: str, variants: Iterable[tuple[str, ...]]) -> str:
        """尝试多个命令变体，返回成功输出或错误提示。"""

        for cmd in variants:
            if not shutil.which(cmd[0]):
                continue
            try:
                out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
                return out.strip()
            except subprocess.CalledProcessError as exc:  # pragma: no cover - 外部命令错误
                return f"{name} 执行失败：\n{exc.output}"
            except Exception as exc:  # pragma: no cover - 异常保护
                return f"{name} 执行异常：{exc}"
        return f"未找到命令：{name}，请确认已安装。"

    def _fill_box(self, box: ctk.CTkTextbox, content: str) -> None:
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("end", content)
        box.configure(state="disabled")
