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
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(4, weight=1)
        self.grid_rowconfigure(6, weight=1)

        header = ctk.CTkLabel(
            self, text="计算资源监控", font=("PingFang SC", 22, "bold")
        )
        header.grid(row=0, column=0, pady=(4, 8))

        btn_row = ctk.CTkFrame(self, fg_color=("#1f1f1f", "#1f1f1f"))
        btn_row.grid(row=1, column=0, pady=4, padx=8, sticky="ew")
        btn_row.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            btn_row, text="刷新全部", command=self.refresh_all, width=140
        ).grid(row=0, column=0, padx=6, pady=6, sticky="w")

        # 采用“卡片式”布局让各监控区域更清晰。
        self.gpu_box = self._create_card(
            row=2, title="GPU (gpustat / macOS 降级)", height=140
        )
        self.cpu_box = self._create_card(row=4, title="CPU / 进程 (top)", height=200)
        self.disk_box = self._create_card(row=6, title="磁盘 (df -h)", height=160)

    def refresh_all(self) -> None:
        """刷新所有监控信息。"""
        macos = platform.system().lower() == "darwin"
        gpu_variants: list[tuple[str, ...]] = [("gpustat", "-i")]
        if macos:
            # macOS 无 NVIDIA 时，尝试提供基础的显卡信息或功耗采样。
            gpu_variants.extend(
                [
                    ("system_profiler", "SPDisplaysDataType"),
                    ("powermetrics", "--samplers", "smc", "-n", "1"),
                ]
            )
        gpu_content = self._run_variants("GPU", gpu_variants)
        if "未找到命令" in gpu_content or not gpu_content.strip():
            gpu_content = (
                "未检测到 NVIDIA GPU 或缺少 gpustat；"
                "在 macOS 将尝试 system_profiler / powermetrics 作为降级。\n\n"
                + gpu_content
            )
        elif macos and ("未检测到" in gpu_content or "没有设备" in gpu_content):
            gpu_content = (
                "未检测到 NVIDIA GPU，已提供 macOS 显卡/功耗信息供参考。\n\n"
                + gpu_content
            )
        self._fill_box(self.gpu_box, gpu_content)

        if platform.system().lower() == "darwin":
            top_cmds = [("top", "-l", "1", "-n", "5")]
        else:
            top_cmds = [("top", "-b", "-n", "1")]
        self._fill_box(self.cpu_box, self._run_variants("top", top_cmds))

        self._fill_box(self.disk_box, self._run_variants("df", [("df", "-h")]))

    def _create_card(self, row: int, title: str, height: int) -> ctk.CTkTextbox:
        """创建带标题的卡片式文本框。"""

        card = ctk.CTkFrame(self, corner_radius=10, fg_color=("#171717", "#171717"))
        card.grid(row=row, column=0, padx=8, pady=(6, 2), sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        title_label = ctk.CTkLabel(
            card, text=title, anchor="w", font=("PingFang SC", 15, "bold")
        )
        title_label.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))

        box = ctk.CTkTextbox(card, height=height)
        box.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        return box

    def _run_variants(self, name: str, variants: Iterable[tuple[str, ...]]) -> str:
        """尝试多个命令变体，返回成功输出或错误提示。"""

        tried: list[str] = []
        for cmd in variants:
            tried.append(cmd[0])
            if not shutil.which(cmd[0]):
                continue
            try:
                out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
                return out.strip()
            except subprocess.CalledProcessError as exc:  # pragma: no cover - 外部命令错误
                return f"{name} 执行失败：\n{exc.output}"
            except Exception as exc:  # pragma: no cover - 异常保护
                return f"{name} 执行异常：{exc}"
        tried_list = ", ".join(dict.fromkeys(tried)) or name
        return f"未找到可用命令（尝试：{tried_list}）。"

    def _fill_box(self, box: ctk.CTkTextbox, content: str) -> None:
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("end", content)
        box.configure(state="disabled")
