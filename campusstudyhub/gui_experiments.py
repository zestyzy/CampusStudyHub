# -*- coding: utf-8 -*-
"""
gui_experiments.py
仅保留实验监控相关功能（以及共用的 PeerManager）
"""
from __future__ import annotations

import csv
import json
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .config import AppConfig, load_config
from .lan import send_lan_notifications
from .models import LanTarget, LogMonitorConfig
from .storage import load_log_monitors, save_log_monitors
from .ui_style import BG_CARD, BG_DARK, HEADER_FONT, LABEL_BOLD, TEXT_PRIMARY, card_kwargs

DATA_DIR = Path("data")
DEFAULT_MARKERS_ERROR = ["error", "failed", "exception", "nan"]
DEFAULT_MARKERS_OK = ["finished", "complete", "done"]


class PeerManager:
    """简单的同行列表持久化（旧版逻辑保留给实验监控使用）。"""

    def __init__(self) -> None:
        self.peers: List[Dict[str, str]] = []
        self._load()

    def _load(self) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        path = DATA_DIR / "peers.json"
        if path.exists():
            try:
                self.peers = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                self.peers = []
        else:
            self.peers = []

    def save(self) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        path = DATA_DIR / "peers.json"
        path.write_text(json.dumps(self.peers, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_peer(self, name: str, ip: str, port: int | None, email: str) -> None:
        self.peers.append({"name": name, "ip": ip, "port": port, "email": email})
        self.save()


class PeerChecklist(ctk.CTkFrame):
    """可复用的联系人勾选列表。"""

    def __init__(self, master: ctk.CTkBaseClass, manager: PeerManager) -> None:
        super().__init__(master)
        self.manager = manager
        self.vars: List[ctk.BooleanVar] = []
        self._render()

    def _render(self) -> None:
        for widget in self.winfo_children():
            widget.destroy()
        self.vars.clear()
        for idx, peer in enumerate(self.manager.peers):
            var = ctk.BooleanVar(value=False)
            self.vars.append(var)
            label = f"{peer['name']} - {peer.get('ip','')}{':' + str(peer['port']) if peer.get('port') else ''}"
            if peer.get("email"):
                label += f" | {peer['email']}"
            ctk.CTkCheckBox(self, text=label, variable=var).grid(row=idx, column=0, sticky="w", pady=2)

    def refresh(self) -> None:
        self._render()

    def select_all(self) -> None:
        for var in self.vars:
            var.set(True)

    def selected_peers(self) -> List[Dict[str, str]]:
        return [p for p, v in zip(self.manager.peers, self.vars) if v.get()]


class EmailSettingsDialog(ctk.CTkToplevel):
    """邮件发送设置对话框（SMTP）。"""

    def __init__(self, master: ctk.CTkBaseClass, config: AppConfig, on_save) -> None:
        super().__init__(master)
        self.title("邮件发送设置")
        self.resizable(False, False)
        self.config = config
        self.on_save = on_save
        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text="SMTP 主机").grid(row=0, column=0, padx=10, pady=6, sticky="e")
        ctk.CTkLabel(self, text="SMTP 端口").grid(row=1, column=0, padx=10, pady=6, sticky="e")
        ctk.CTkLabel(self, text="发件邮箱").grid(row=2, column=0, padx=10, pady=6, sticky="e")
        ctk.CTkLabel(self, text="用户名(可选)").grid(row=3, column=0, padx=10, pady=6, sticky="e")
        ctk.CTkLabel(self, text="密码(可选)").grid(row=4, column=0, padx=10, pady=6, sticky="e")

        self.host_entry = ctk.CTkEntry(self)
        self.host_entry.insert(0, self.config.smtp_host)
        self.host_entry.grid(row=0, column=1, padx=10, pady=6, sticky="ew")

        self.port_entry = ctk.CTkEntry(self, width=100)
        self.port_entry.insert(0, str(self.config.smtp_port))
        self.port_entry.grid(row=1, column=1, padx=10, pady=6, sticky="w")

        self.sender_entry = ctk.CTkEntry(self)
        self.sender_entry.insert(0, self.config.smtp_sender)
        self.sender_entry.grid(row=2, column=1, padx=10, pady=6, sticky="ew")

        self.user_entry = ctk.CTkEntry(self)
        self.user_entry.insert(0, self.config.smtp_username)
        self.user_entry.grid(row=3, column=1, padx=10, pady=6, sticky="ew")

        self.pass_entry = ctk.CTkEntry(self, show="*")
        self.pass_entry.insert(0, self.config.smtp_password)
        self.pass_entry.grid(row=4, column=1, padx=10, pady=6, sticky="ew")

        self.tls_var = ctk.BooleanVar(value=self.config.smtp_use_tls)
        ctk.CTkCheckBox(self, text="使用 TLS 加密", variable=self.tls_var).grid(
            row=5, column=1, padx=10, pady=4, sticky="w"
        )

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=6, column=0, columnspan=2, pady=10)
        ctk.CTkButton(btn_row, text="保存", command=self._save).grid(row=0, column=0, padx=6)
        ctk.CTkButton(btn_row, text="取消", command=self.destroy).grid(row=0, column=1, padx=6)

    def _save(self) -> None:
        host = self.host_entry.get().strip() or "localhost"
        try:
            port = int(self.port_entry.get().strip() or 25)
        except ValueError:
            messagebox.showinfo("提示", "SMTP 端口需要是数字")
            return
        sender = self.sender_entry.get().strip()
        username = self.user_entry.get().strip()
        password = self.pass_entry.get().strip()
        self.config.smtp_host = host
        self.config.smtp_port = port
        self.config.smtp_sender = sender
        self.config.smtp_username = username
        self.config.smtp_password = password
        self.config.smtp_use_tls = bool(self.tls_var.get())
        self.on_save(self.config)
        self.destroy()


class ExperimentMonitorFrame(ctk.CTkFrame):
    """多日志监控，支持错误/收敛分组、尾部快照与通知。"""

    def __init__(self, master: ctk.CTkBaseClass, manager: PeerManager | None = None) -> None:
        super().__init__(master)
        self.manager = manager or PeerManager()
        self.monitors: List[LogMonitorConfig] = load_log_monitors()
        self.running_threads: Dict[str, threading.Thread] = {}
        self.latest_tail: Dict[str, str] = {}
        self.metrics: Dict[str, List[Dict[str, float]]] = {}
        self.config = load_config()
        self._build_ui()
        self._render_table()

    def _build_ui(self) -> None:
        self.grid_columnconfigure((0, 1), weight=1)
        self.configure(fg_color=BG_DARK)
        ctk.CTkLabel(self, text="实验监控", font=HEADER_FONT, text_color=TEXT_PRIMARY).grid(
            row=0, column=0, columnspan=2, pady=6
        )

        peer_box = ctk.CTkFrame(self, **card_kwargs())
        peer_box.grid(row=1, column=0, padx=10, pady=6, sticky="nsew")
        peer_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(peer_box, text="通知对象", font=LABEL_BOLD, text_color=TEXT_PRIMARY).grid(
            row=0, column=0, pady=4
        )
        self.peer_list = PeerChecklist(peer_box, self.manager)
        self.peer_list.grid(row=1, column=0, padx=8, pady=4, sticky="nsew")
        ctk.CTkButton(peer_box, text="全选", command=self.peer_list.select_all, width=100).grid(row=2, column=0, pady=4)
        ctk.CTkButton(peer_box, text="手动提醒", command=self._manual_notify, width=120).grid(row=3, column=0, pady=4)
        ctk.CTkButton(peer_box, text="邮件设置", command=self._open_email_settings, width=120).grid(
            row=4, column=0, pady=4
        )

        config_box = ctk.CTkFrame(self, **card_kwargs())
        config_box.grid(row=1, column=1, padx=10, pady=6, sticky="nsew")
        config_box.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(config_box, text="新增监控", font=LABEL_BOLD, text_color=TEXT_PRIMARY).grid(
            row=0, column=0, columnspan=3, pady=4
        )
        self.log_path_entry = ctk.CTkEntry(config_box, placeholder_text="日志路径")
        self.log_path_entry.grid(row=1, column=0, columnspan=2, padx=4, pady=2, sticky="ew")
        ctk.CTkButton(config_box, text="选择", width=80, command=self._choose_log).grid(row=1, column=2, padx=4)
        ctk.CTkLabel(config_box, text="错误关键词").grid(row=2, column=0, padx=4, sticky="e")
        self.err_entry = ctk.CTkEntry(config_box)
        self.err_entry.insert(0, ",".join(DEFAULT_MARKERS_ERROR))
        self.err_entry.grid(row=2, column=1, padx=4, sticky="ew")
        ctk.CTkLabel(config_box, text="收敛关键词").grid(row=3, column=0, padx=4, sticky="e")
        self.ok_entry = ctk.CTkEntry(config_box)
        self.ok_entry.insert(0, ",".join(DEFAULT_MARKERS_OK))
        self.ok_entry.grid(row=3, column=1, padx=4, sticky="ew")
        ctk.CTkLabel(config_box, text="轮询秒").grid(row=4, column=0, padx=4, sticky="e")
        self.interval_entry = ctk.CTkEntry(config_box, width=80)
        self.interval_entry.insert(0, "2")
        self.interval_entry.grid(row=4, column=1, padx=4, sticky="w")
        ctk.CTkLabel(config_box, text="尾部行数").grid(row=5, column=0, padx=4, sticky="e")
        self.tail_entry = ctk.CTkEntry(config_box, width=80)
        self.tail_entry.insert(0, "20")
        self.tail_entry.grid(row=5, column=1, padx=4, sticky="w")
        ctk.CTkButton(config_box, text="添加监控", command=self._add_monitor).grid(row=6, column=0, columnspan=3, pady=6)

        table_box = ctk.CTkFrame(self, **card_kwargs())
        table_box.grid(row=2, column=0, columnspan=2, padx=10, pady=6, sticky="nsew")
        table_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(table_box, text="监控列表", font=LABEL_BOLD, text_color=TEXT_PRIMARY).grid(
            row=0, column=0, pady=4
        )
        self.table = ctk.CTkScrollableFrame(table_box, height=260)
        self.table.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)

        bottom = ctk.CTkFrame(self, **card_kwargs())
        bottom.grid(row=3, column=0, columnspan=2, padx=10, pady=6, sticky="nsew")
        bottom.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(bottom, text="尾部快照 / 日志", font=LABEL_BOLD, text_color=TEXT_PRIMARY).grid(
            row=0, column=0, pady=4
        )
        self.log_view = ctk.CTkTextbox(bottom, height=200, fg_color=BG_CARD)
        self.log_view.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)
        btn_row = ctk.CTkFrame(bottom)
        btn_row.grid(row=2, column=0, pady=4)
        ctk.CTkButton(btn_row, text="导出指标 CSV", command=self._export_metrics).grid(row=0, column=0, padx=4)
        ctk.CTkButton(btn_row, text="刷新联系人", command=self.peer_list.refresh).grid(row=0, column=1, padx=4)

    def _render_table(self) -> None:
        for widget in self.table.winfo_children():
            widget.destroy()
        if not self.monitors:
            ctk.CTkLabel(self.table, text="暂无监控，添加一个吧").pack(pady=6)
            return
        for idx, monitor in enumerate(self.monitors):
            row = ctk.CTkFrame(self.table)
            row.pack(fill="x", pady=3, padx=4)
            info = f"{Path(monitor.path).name} | 间隔{monitor.interval}s | 尾部{monitor.tail_lines}行"
            ctk.CTkLabel(row, text=info, anchor="w").pack(side="left", padx=4)
            ctk.CTkButton(row, text="尾部快照", width=90, command=lambda m=monitor: self._show_tail(m)).pack(side="right", padx=2)
            ctk.CTkButton(row, text="停止", width=70, command=lambda m=monitor: self._stop_monitor(m)).pack(side="right", padx=2)
            ctk.CTkButton(row, text="开始", width=70, command=lambda m=monitor: self._start_monitor(m)).pack(side="right", padx=2)
            ctk.CTkButton(row, text="删除", width=70, command=lambda m=monitor: self._remove_monitor(m)).pack(side="right", padx=2)

    def _choose_log(self) -> None:
        path = filedialog.askopenfilename(title="选择日志文件")
        if path:
            self.log_path_entry.delete(0, "end")
            self.log_path_entry.insert(0, path)

    def _add_monitor(self) -> None:
        path = self.log_path_entry.get().strip()
        if not path:
            messagebox.showinfo("提示", "请选择日志文件")
            return
        try:
            interval = float(self.interval_entry.get() or 2.0)
        except ValueError:
            interval = 2.0
        try:
            tail = int(self.tail_entry.get() or 20)
        except ValueError:
            tail = 20
        monitor = LogMonitorConfig(
            path=path,
            keywords_error=[s.strip() for s in self.err_entry.get().split(",") if s.strip()],
            keywords_success=[s.strip() for s in self.ok_entry.get().split(",") if s.strip()],
            interval=interval,
            tail_lines=tail,
        )
        self.monitors.append(monitor)
        save_log_monitors(self.monitors)
        self._render_table()

    def _manual_notify(self) -> None:
        summary = []
        for mon in self.monitors:
            tail = (self.latest_tail.get(mon.id, "").splitlines() or ["无更新"])[-1]
            summary.append(f"{Path(mon.path).name}: {tail}")
        if not summary:
            messagebox.showinfo("提示", "暂无监控数据")
            return
        self._notify_peers("; ".join(summary))

    def _dispatch(self, peers: List[Dict[str, str]], message: str) -> Dict[str, int]:
        if any(peer.get("email") for peer in peers) and not self.config.smtp_sender:
            messagebox.showinfo("提示", "请先在“邮件设置”中填写发件邮箱")
            return {"ok": 0, "fail": len(peers)}
        targets = []
        for peer in peers:
            targets.append(
                LanTarget(
                    label=peer.get("name", "peer"),
                    host=peer.get("ip", "127.0.0.1"),
                    port=int(peer.get("port")) if peer.get("port") else None,
                    email=peer.get("email", ""),
                )
            )
        results = send_lan_notifications(
            message,
            targets,
            smtp_host=self.config.smtp_host,
            smtp_port=self.config.smtp_port,
            smtp_sender=self.config.smtp_sender,
            smtp_username=self.config.smtp_username,
            smtp_password=self.config.smtp_password,
            smtp_use_tls=self.config.smtp_use_tls,
        )
        ok = len([r for r in results if r[1]])
        fail = len(results) - ok
        return {"ok": ok, "fail": fail}

    def _open_email_settings(self) -> None:
        EmailSettingsDialog(self, self.config, self._save_email_settings)

    def _save_email_settings(self, config: AppConfig) -> None:
        self.config = config
        from .config import save_config

        save_config(config)

    def _export_metrics(self) -> None:
        if not self.metrics:
            messagebox.showinfo("提示", "暂无可导出的指标")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["monitor_id", "ts", "key", "value"])
            for mid, rows in self.metrics.items():
                for row in rows:
                    for key, val in row.items():
                        if key == "ts":
                            continue
                        writer.writerow([mid, datetime.fromtimestamp(row.get("ts", 0)).isoformat(), key, val])
        messagebox.showinfo("完成", "已导出 CSV")

    def _remove_monitor(self, monitor: LogMonitorConfig) -> None:
        self._stop_monitor(monitor)
        self.monitors = [m for m in self.monitors if m.id != monitor.id]
        save_log_monitors(self.monitors)
        self._render_table()

    def _start_monitor(self, monitor: LogMonitorConfig) -> None:
        if monitor.id in self.running_threads:
            return

        def worker() -> None:
            last_pos = 0
            path = Path(monitor.path)
            buffer = deque(maxlen=monitor.tail_lines)
            while monitor.id in self.running_threads:
                if not path.exists():
                    self._append_log(f"[WARN] 文件不存在：{path}")
                    break
                try:
                    size = path.stat().st_size
                    if size < last_pos:
                        last_pos = 0
                        buffer.clear()
                    if size != last_pos:
                        if last_pos == 0:
                            tail_text = _read_tail_lines(path, monitor.tail_lines)
                            buffer.extend(tail_text.splitlines())
                            last_pos = size
                        else:
                            with path.open("r", encoding="utf-8", errors="ignore") as f:
                                f.seek(last_pos)
                                new_text = f.read()
                                last_pos = f.tell()
                                buffer.extend(new_text.splitlines())
                        tail = "\n".join(buffer)
                        self.latest_tail[monitor.id] = tail
                        self._check_markers(monitor, tail)
                        self._parse_metrics(monitor, tail)
                    time.sleep(max(monitor.interval, 0.5))
                except Exception:
                    time.sleep(max(monitor.interval, 0.5))
            self.running_threads.pop(monitor.id, None)

        thread = threading.Thread(target=worker, daemon=True)
        self.running_threads[monitor.id] = thread
        thread.start()
        self._append_log(f"[INFO] 已启动监控：{monitor.path}")

    def _stop_monitor(self, monitor: LogMonitorConfig) -> None:
        self.running_threads.pop(monitor.id, None)
        self._append_log(f"[INFO] 已停止监控：{monitor.path}")

    def _check_markers(self, monitor: LogMonitorConfig, text: str) -> None:
        lower = text.lower()
        hit_error = [m for m in monitor.keywords_error if m.lower() in lower]
        hit_ok = [m for m in monitor.keywords_success if m.lower() in lower]
        if hit_error:
            message = f"检测到错误关键词：{', '.join(hit_error)} | {Path(monitor.path).name}"
            self._append_log(message)
            self._notify_peers(message)
        elif hit_ok:
            message = f"检测到收敛关键词：{', '.join(hit_ok)} | {Path(monitor.path).name}"
            self._append_log(message)

    def _parse_metrics(self, monitor: LogMonitorConfig, text: str) -> None:
        records = self.metrics.setdefault(monitor.id, [])
        for token in text.split():
            if "=" in token:
                key, val = token.split("=", 1)
                try:
                    num = float(val)
                    records.append({key: num, "ts": time.time()})
                except ValueError:
                    continue

    def _show_tail(self, monitor: LogMonitorConfig) -> None:
        tail = self.latest_tail.get(monitor.id, "暂无内容")
        self.log_view.delete("1.0", "end")
        self.log_view.insert("end", tail)
        self.log_view.see("end")

    def _append_log(self, line: str) -> None:
        def _write() -> None:
            self.log_view.insert("end", line + "\n")
            self.log_view.see("end")

        if threading.current_thread() is threading.main_thread():
            _write()
        else:
            self.after(0, _write)

    def _notify_peers(self, message: str) -> None:
        selected = self.peer_list.selected_peers()
        if not selected:
            return
        msg = f"【实验监控】{message}"
        results = self._dispatch(selected, msg)
        self._append_log(f"提醒发送：成功 {results['ok']} 失败 {results['fail']}")


def _read_tail_lines(path: Path, limit: int, max_bytes: int = 200_000) -> str:
    """从文件尾部读取最近的若干行，避免全量读取超大日志。"""

    if limit <= 0 or not path.exists():
        return ""
    with path.open("rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(size - max_bytes, 0))
        chunk = f.read().decode("utf-8", errors="ignore")
    lines = chunk.splitlines()
    return "\n".join(lines[-limit:])