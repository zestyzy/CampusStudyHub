"""系统资源监视面板，展示 GPU/CPU/磁盘使用情况（多线程防卡顿版）。"""
from __future__ import annotations

import platform
import shutil
import subprocess
import threading
from typing import Iterable

import customtkinter as ctk

from .ui_style import ACCENT, ACCENT_ALT, BG_CARD, BG_DARK, LABEL_BOLD, TEXT_PRIMARY, HEADER_FONT

class ResourceMonitorFrame(ctk.CTkFrame):
    """展示常用资源监控命令输出（gpustat、top、df -h）。"""

    def __init__(self, master: ctk.CTkBaseClass) -> None:
        super().__init__(master, fg_color=BG_DARK)
        self._build_ui()
        # 延迟一点启动，避免初始化卡顿
        self.after(500, self.refresh_all)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        # 让内容区域可伸缩
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # 头部
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=10)
        
        ctk.CTkLabel(header_frame, text="资源监控", font=HEADER_FONT, text_color=TEXT_PRIMARY).pack(side="left")
        
        self.refresh_btn = ctk.CTkButton(
            header_frame,
            text="刷新数据",
            command=self.refresh_all,
            width=100,
            fg_color=ACCENT,
            hover_color=ACCENT_ALT,
            font=LABEL_BOLD,
        )
        self.refresh_btn.pack(side="right")

        # 卡片区域
        self.gpu_box = self._create_card(row=2, title="GPU / 显卡")
        self.cpu_box = self._create_card(row=3, title="CPU / 内存 / 进程")
        self.disk_box = self._create_card(row=4, title="磁盘存储")

    def _create_card(self, row: int, title: str) -> ctk.CTkTextbox:
        """创建带标题的卡片式文本框。"""
        card = ctk.CTkFrame(self, corner_radius=10, fg_color=BG_CARD)
        card.grid(row=row, column=0, padx=12, pady=6, sticky="nsew")
        
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(card, text=title, font=LABEL_BOLD, text_color=TEXT_PRIMARY).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))
        
        # 关键修改：使用等宽字体 (Consolas, Courier New, or Monospace) 确保表格对齐
        # wrap="none" 防止长行自动换行破坏格式
        box = ctk.CTkTextbox(card, height=120, font=("Consolas", 11), wrap="none") 
        box.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        box.configure(state="disabled")
        return box

    def refresh_all(self) -> None:
        """启动后台线程刷新，防止卡UI。"""
        self.refresh_btn.configure(state="disabled", text="刷新中...")
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self) -> None:
        """后台执行耗时命令。"""
        is_mac = platform.system().lower() == "darwin"
        
        # 1. GPU
        if is_mac:
            # macOS: 优先 system_profiler，或者 powermetrics (需要sudo，通常不行，略过)
            gpu_res = self._run_cmd(["system_profiler", "SPDisplaysDataType"])
            # 尝试精简输出 
            if "Graphics/Displays:" in gpu_res:
                lines = [line for line in gpu_res.splitlines() if "Chipset Model" in line or "VRAM" in line]
                gpu_res = "\n".join(lines) if lines else gpu_res
        else:
            # Linux/Win: 优先 nvidia-smi 或 gpustat
            gpu_res = self._run_variants([
                ("gpustat", "-i"),
                ("nvidia-smi",)
            ])

        # 2. CPU (top)
        if is_mac:
            # -l 1: 1个sample (不阻塞), -n 10: 显示10行
            cpu_res = self._run_cmd(["top", "-l", "1", "-n", "10", "-s", "0"]) 
        else:
            # Linux: -b batch mode, -n 1 iteration
            cpu_res = self._run_cmd(["top", "-b", "-n", "1"])
            # 只取前20行避免太长 
            cpu_res = "\n".join(cpu_res.splitlines()[:20])

        # 3. Disk
        disk_res = self._run_cmd(["df", "-h"])

        # 回到主线程更新UI
        self.after(0, lambda: self._update_ui(gpu_res, cpu_res, disk_res))

    def _update_ui(self, gpu_text, cpu_text, disk_text):
        self._fill_box(self.gpu_box, gpu_text or "未检测到 GPU 信息")
        self._fill_box(self.cpu_box, cpu_text or "无法获取 CPU 信息")
        self._fill_box(self.disk_box, disk_text or "无法获取磁盘信息")
        self.refresh_btn.configure(state="normal", text="刷新数据")

    def _fill_box(self, box: ctk.CTkTextbox, content: str) -> None:
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("end", content.strip())
        box.configure(state="disabled")

    def _run_variants(self, commands: list[tuple]) -> str:
        """尝试多个命令，返回第一个成功的。"""
        for cmd in commands:
            if shutil.which(cmd[0]):
                res = self._run_cmd(list(cmd))
                if res: return res
        return ""

    def _run_cmd(self, cmd_list: list[str]) -> str:
        try:
            # timeout防止死锁
            return subprocess.check_output(cmd_list, stderr=subprocess.STDOUT, text=True, timeout=3)
        except Exception as e:
            return ""