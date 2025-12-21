"""局域网 CCF 截止提醒与实验监控工具（CustomTkinter 版）。"""
from __future__ import annotations

import json
import socket
import threading
from pathlib import Path
from typing import Dict, List

import customtkinter as ctk
from tkinter import messagebox, filedialog

DATA_DIR = Path("data")
PEERS_FILE = DATA_DIR / "peers.json"
LOG_MARKERS = ["finished", "complete", "error", "exception"]


class LANTrackerFrame(ctk.CTkFrame):
    """提供 CCF 会议提醒的定向广播，以及简单的本地实验日志监控。"""

    def __init__(self, master: ctk.CTkBaseClass) -> None:
        super().__init__(master)
        self.peers: List[Dict[str, str]] = []
        self.peer_vars: List[ctk.BooleanVar] = []
        self.log_path: Path | None = None
        self.monitoring = False
        self._monitor_thread: threading.Thread | None = None

        self._load_peers()
        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(self, text="CCF 截止提醒 / 实验监控", font=("PingFang SC", 24, "bold"))
        title.grid(row=0, column=0, pady=(10, 6))

        # Peer list section
        peers_frame = ctk.CTkFrame(self, corner_radius=10)
        peers_frame.grid(row=1, column=0, padx=12, pady=6, sticky="nsew")
        peers_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(peers_frame, text="通知对象", font=("PingFang SC", 16, "bold")).grid(row=0, column=0, pady=6)

        self.peer_list_frame = ctk.CTkScrollableFrame(peers_frame, height=180)
        self.peer_list_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)

        add_row = ctk.CTkFrame(peers_frame)
        add_row.grid(row=2, column=0, pady=6, padx=8, sticky="ew")
        add_row.grid_columnconfigure(1, weight=1)
        self.peer_name = ctk.CTkEntry(add_row, placeholder_text="姓名/备注")
        self.peer_ip = ctk.CTkEntry(add_row, placeholder_text="IP")
        self.peer_port = ctk.CTkEntry(add_row, placeholder_text="端口", width=90)
        add_btn = ctk.CTkButton(add_row, text="添加", command=self._add_peer)
        self.peer_name.grid(row=0, column=0, padx=4, sticky="ew")
        self.peer_ip.grid(row=0, column=1, padx=4, sticky="ew")
        self.peer_port.grid(row=0, column=2, padx=4)
        add_btn.grid(row=0, column=3, padx=4)

        action_row = ctk.CTkFrame(peers_frame)
        action_row.grid(row=3, column=0, pady=(4, 8))
        select_all = ctk.CTkButton(action_row, text="全选", command=self._select_all)
        send_btn = ctk.CTkButton(action_row, text="发送提醒", command=self._send_reminder)
        select_all.grid(row=0, column=0, padx=6)
        send_btn.grid(row=0, column=1, padx=6)

        # Conference filter & list
        conf_frame = ctk.CTkFrame(self, corner_radius=10)
        conf_frame.grid(row=2, column=0, padx=12, pady=6, sticky="nsew")
        conf_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(conf_frame, text="CCF-A 会议", font=("PingFang SC", 16, "bold")).grid(row=0, column=0, pady=6)
        filter_row = ctk.CTkFrame(conf_frame)
        filter_row.grid(row=1, column=0, pady=4)
        ctk.CTkLabel(filter_row, text="关键词：").grid(row=0, column=0, padx=4)
        self.filter_entry = ctk.CTkEntry(filter_row, width=200)
        self.filter_entry.grid(row=0, column=1, padx=4)
        ctk.CTkButton(filter_row, text="过滤", command=self._refresh_confs).grid(row=0, column=2, padx=4)

        self.conf_box = ctk.CTkTextbox(conf_frame, height=160)
        self.conf_box.grid(row=2, column=0, padx=8, pady=6, sticky="nsew")

        # Log monitor
        log_frame = ctk.CTkFrame(self, corner_radius=10)
        log_frame.grid(row=3, column=0, padx=12, pady=6, sticky="ew")
        log_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(log_frame, text="实验日志监控", font=("PingFang SC", 16, "bold")).grid(row=0, column=0, columnspan=3, pady=6)
        self.log_label = ctk.CTkLabel(log_frame, text="未选择文件")
        self.log_label.grid(row=1, column=0, padx=6, sticky="w")
        choose_btn = ctk.CTkButton(log_frame, text="选择日志", command=self._choose_log)
        choose_btn.grid(row=1, column=1, padx=6)
        self.monitor_btn = ctk.CTkButton(log_frame, text="开始监控", command=self._toggle_monitor)
        self.monitor_btn.grid(row=1, column=2, padx=6)

        self._refresh_peers()
        self._refresh_confs()

    # Peer logic
    def _load_peers(self) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        if PEERS_FILE.exists():
            try:
                self.peers = json.loads(PEERS_FILE.read_text(encoding="utf-8"))
            except Exception:
                self.peers = []

    def _save_peers(self) -> None:
        PEERS_FILE.write_text(json.dumps(self.peers, ensure_ascii=False, indent=2), encoding="utf-8")

    def _refresh_peers(self) -> None:
        for widget in self.peer_list_frame.winfo_children():
            widget.destroy()
        self.peer_vars.clear()
        for idx, peer in enumerate(self.peers):
            var = ctk.BooleanVar(value=False)
            self.peer_vars.append(var)
            row = ctk.CTkFrame(self.peer_list_frame)
            row.grid(row=idx, column=0, sticky="ew", pady=2, padx=4)
            ctk.CTkCheckBox(row, text=f"{peer['name']} - {peer['ip']}:{peer['port']}", variable=var).grid(row=0, column=0, sticky="w")

    def _add_peer(self) -> None:
        name = self.peer_name.get().strip()
        ip = self.peer_ip.get().strip()
        port = self.peer_port.get().strip()
        if not (name and ip and port.isdigit()):
            messagebox.showerror("提示", "请填写有效的姓名、IP 和端口")
            return
        self.peers.append({"name": name, "ip": ip, "port": int(port)})
        self._save_peers()
        self._refresh_peers()
        self.peer_name.delete(0, "end")
        self.peer_ip.delete(0, "end")
        self.peer_port.delete(0, "end")

    def _select_all(self) -> None:
        for var in self.peer_vars:
            var.set(True)

    def _send_reminder(self) -> None:
        selected = [p for p, v in zip(self.peers, self.peer_vars) if v.get()]
        if not selected:
            messagebox.showinfo("提示", "请先选择接收方")
            return
        msg = self._build_message()
        for peer in selected:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.sendto(msg.encode("utf-8"), (peer["ip"], int(peer["port"])))
            except OSError:
                continue
        messagebox.showinfo("完成", "提醒已发送")

    def _build_message(self) -> str:
        lines = ["【会议提醒】即将到期的 CCF-A 截止："]
        for conf in self._get_confs()[:3]:
            lines.append(f"- {conf['name']} / 截止：{conf['deadline']}")
        return "\n".join(lines)

    # Conference logic
    def _get_confs(self) -> List[Dict[str, str]]:
        conf_path = DATA_DIR / "conferences.json"
        if conf_path.exists():
            try:
                return json.loads(conf_path.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _refresh_confs(self) -> None:
        keyword = self.filter_entry.get().strip().lower()
        confs = self._get_confs()
        if keyword:
            confs = [c for c in confs if keyword in c.get("name", "").lower()]
        self.conf_box.configure(state="normal")
        self.conf_box.delete("1.0", "end")
        if not confs:
            self.conf_box.insert("end", "暂无数据，请在 data/conferences.json 填写\n")
        for conf in confs:
            self.conf_box.insert("end", f"{conf.get('name')} | 截止：{conf.get('deadline')} | 地点：{conf.get('location','')}\n")
        self.conf_box.configure(state="disabled")

    # Log monitor
    def _choose_log(self) -> None:
        path = filedialog.askopenfilename(title="选择日志文件")
        if path:
            self.log_path = Path(path)
            self.log_label.configure(text=str(self.log_path))

    def _toggle_monitor(self) -> None:
        if self.monitoring:
            self.monitoring = False
            self.monitor_btn.configure(text="开始监控")
        else:
            if not self.log_path:
                messagebox.showinfo("提示", "请先选择日志文件")
                return
            self.monitoring = True
            self.monitor_btn.configure(text="停止监控")
            self._start_monitor_thread()

    def _start_monitor_thread(self) -> None:
        def worker() -> None:
            last_mtime = self.log_path.stat().st_mtime if self.log_path and self.log_path.exists() else 0
            while self.monitoring:
                if not self.log_path or not self.log_path.exists():
                    break
                mtime = self.log_path.stat().st_mtime
                if mtime != last_mtime:
                    last_mtime = mtime
                    try:
                        content = self.log_path.read_text(encoding="utf-8", errors="ignore")
                        tail = content.lower()[-500:]
                        if any(marker in tail for marker in LOG_MARKERS):
                            messagebox.showinfo("实验提示", f"日志触发关键字：{self.log_path.name}")
                    except Exception:
                        pass
                time.sleep(2)
        import time

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        self._monitor_thread = t

