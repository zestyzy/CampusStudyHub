"""CustomTkinter 会议提醒与实验日志监控（分离的科研辅助工具）。"""
from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path
from typing import Dict, List
from tkinter import filedialog, messagebox

import customtkinter as ctk

DATA_DIR = Path("data")
PEERS_FILE = DATA_DIR / "peers.json"
CONFERENCES_FILE = DATA_DIR / "conferences.json"
DEFAULT_MARKERS = ["error", "failed", "exception", "nan", "finished", "complete"]


class PeerManager:
    """简单的同行列表持久化，供会议提醒与实验监控共用。"""

    def __init__(self) -> None:
        self.peers: List[Dict[str, str]] = []
        self._load()

    def _load(self) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        if PEERS_FILE.exists():
            try:
                self.peers = json.loads(PEERS_FILE.read_text(encoding="utf-8"))
            except Exception:
                self.peers = []
        else:
            self.peers = []

    def save(self) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        PEERS_FILE.write_text(json.dumps(self.peers, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_peer(self, name: str, ip: str, port: int) -> None:
        self.peers.append({"name": name, "ip": ip, "port": port})
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
            label = f"{peer['name']} - {peer['ip']}:{peer['port']}"
            ctk.CTkCheckBox(self, text=label, variable=var).grid(row=idx, column=0, sticky="w", pady=2)

    def refresh(self) -> None:
        self._render()

    def select_all(self) -> None:
        for var in self.vars:
            var.set(True)

    def selected_peers(self) -> List[Dict[str, str]]:
        return [p for p, v in zip(self.manager.peers, self.vars) if v.get()]


class ConferenceLANFrame(ctk.CTkFrame):
    """CCF 会议通知：管理同行、筛选会议并定向发送提醒。"""

    def __init__(self, master: ctk.CTkBaseClass, manager: PeerManager | None = None) -> None:
        super().__init__(master)
        self.manager = manager or PeerManager()
        self.conferences: List[Dict[str, str]] = []
        self._load_confs()
        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(self, text="CCF 会议通知", font=("PingFang SC", 24, "bold")).grid(row=0, column=0, columnspan=2, pady=8)

        peer_box = ctk.CTkFrame(self, corner_radius=12)
        peer_box.grid(row=1, column=0, padx=10, pady=6, sticky="nsew")
        peer_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(peer_box, text="通知对象", font=("PingFang SC", 16, "bold")).grid(row=0, column=0, pady=6)
        self.peer_list = PeerChecklist(peer_box, self.manager)
        self.peer_list.grid(row=1, column=0, padx=8, pady=4, sticky="nsew")
        action_row = ctk.CTkFrame(peer_box)
        action_row.grid(row=2, column=0, pady=6)
        ctk.CTkButton(action_row, text="全选", command=self.peer_list.select_all, width=90).grid(row=0, column=0, padx=4)
        ctk.CTkButton(action_row, text="发送提醒", command=self._send, width=120).grid(row=0, column=1, padx=4)

        add_row = ctk.CTkFrame(peer_box)
        add_row.grid(row=3, column=0, padx=6, pady=6, sticky="ew")
        add_row.grid_columnconfigure(1, weight=1)
        self.peer_name = ctk.CTkEntry(add_row, placeholder_text="姓名/备注", width=120)
        self.peer_ip = ctk.CTkEntry(add_row, placeholder_text="IP 地址")
        self.peer_port = ctk.CTkEntry(add_row, placeholder_text="端口", width=90)
        ctk.CTkButton(add_row, text="添加联系人", command=self._add_peer).grid(row=0, column=3, padx=4)
        self.peer_name.grid(row=0, column=0, padx=4)
        self.peer_ip.grid(row=0, column=1, padx=4, sticky="ew")
        self.peer_port.grid(row=0, column=2, padx=4)

        conf_box = ctk.CTkFrame(self, corner_radius=12)
        conf_box.grid(row=1, column=1, padx=10, pady=6, sticky="nsew")
        conf_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(conf_box, text="会议列表", font=("PingFang SC", 16, "bold")).grid(row=0, column=0, pady=6)

        filter_row = ctk.CTkFrame(conf_box)
        filter_row.grid(row=1, column=0, pady=4, sticky="ew")
        filter_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(filter_row, text="关键词").grid(row=0, column=0, padx=4)
        self.filter_entry = ctk.CTkEntry(filter_row)
        self.filter_entry.grid(row=0, column=1, padx=4, sticky="ew")
        ctk.CTkButton(filter_row, text="过滤", command=self._refresh).grid(row=0, column=2, padx=4)

        self.conf_text = ctk.CTkTextbox(conf_box, height=220)
        self.conf_text.grid(row=2, column=0, padx=8, pady=4, sticky="nsew")

        add_conf_row = ctk.CTkFrame(conf_box)
        add_conf_row.grid(row=3, column=0, pady=6, padx=6, sticky="ew")
        add_conf_row.grid_columnconfigure(1, weight=1)
        self.conf_name = ctk.CTkEntry(add_conf_row, placeholder_text="会议名称")
        self.conf_deadline = ctk.CTkEntry(add_conf_row, placeholder_text="截止日期 YYYY-MM-DD")
        self.conf_location = ctk.CTkEntry(add_conf_row, placeholder_text="地点/备注")
        ctk.CTkButton(add_conf_row, text="新增会议", command=self._add_conf).grid(row=0, column=3, padx=4)
        self.conf_name.grid(row=0, column=0, padx=4, sticky="ew")
        self.conf_deadline.grid(row=0, column=1, padx=4, sticky="ew")
        self.conf_location.grid(row=0, column=2, padx=4, sticky="ew")

        self._refresh()

    def _load_confs(self) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        if CONFERENCES_FILE.exists():
            try:
                self.conferences = json.loads(CONFERENCES_FILE.read_text(encoding="utf-8"))
            except Exception:
                self.conferences = []
        else:
            self.conferences = []

    def _save_confs(self) -> None:
        CONFERENCES_FILE.write_text(json.dumps(self.conferences, ensure_ascii=False, indent=2), encoding="utf-8")

    def _refresh(self) -> None:
        keyword = self.filter_entry.get().strip().lower()
        confs = self.conferences
        if keyword:
            confs = [c for c in confs if keyword in c.get("name", "").lower()]
        self.conf_text.configure(state="normal")
        self.conf_text.delete("1.0", "end")
        if not confs:
            self.conf_text.insert("end", "暂无会议，请添加或导入 data/conferences.json\n")
        for conf in confs:
            line = f"{conf.get('name','')} | 截止：{conf.get('deadline','')} | 备注：{conf.get('location','')}\n"
            self.conf_text.insert("end", line)
        self.conf_text.configure(state="disabled")

    def _add_peer(self) -> None:
        name = self.peer_name.get().strip()
        ip = self.peer_ip.get().strip()
        port = self.peer_port.get().strip()
        if not (name and ip and port.isdigit()):
            messagebox.showinfo("提示", "请填写姓名/IP/端口")
            return
        self.manager.add_peer(name, ip, int(port))
        self.peer_list.refresh()
        self.peer_name.delete(0, "end")
        self.peer_ip.delete(0, "end")
        self.peer_port.delete(0, "end")

    def _add_conf(self) -> None:
        name = self.conf_name.get().strip()
        deadline = self.conf_deadline.get().strip()
        location = self.conf_location.get().strip()
        if not (name and deadline):
            messagebox.showinfo("提示", "会议名称和截止日期不能为空")
            return
        self.conferences.append({"name": name, "deadline": deadline, "location": location})
        self._save_confs()
        self._refresh()
        self.conf_name.delete(0, "end")
        self.conf_deadline.delete(0, "end")
        self.conf_location.delete(0, "end")

    def _send(self) -> None:
        selected = self.peer_list.selected_peers()
        if not selected:
            messagebox.showinfo("提示", "请先勾选接收人")
            return
        msg = self._build_message()
        for peer in selected:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.sendto(msg.encode("utf-8"), (peer["ip"], int(peer["port"])))
            except OSError:
                continue
        messagebox.showinfo("完成", "提醒已发送给选中联系人")

    def _build_message(self) -> str:
        lines = ["【会议提醒】近期截止："]
        for conf in self.conferences[:5]:
            lines.append(f"- {conf.get('name','')} | 截止：{conf.get('deadline','')}")
        return "\n".join(lines)


class ExperimentMonitorFrame(ctk.CTkFrame):
    """本地实验日志监控，异常时向选定联系人发送 LAN 提醒。"""

    def __init__(self, master: ctk.CTkBaseClass, manager: PeerManager | None = None) -> None:
        super().__init__(master)
        self.manager = manager or PeerManager()
        self.log_path: Path | None = None
        self.monitoring = False
        self._thread: threading.Thread | None = None
        self._last_size = 0
        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(self, text="实验日志监控", font=("PingFang SC", 24, "bold")).grid(row=0, column=0, columnspan=2, pady=8)

        peer_box = ctk.CTkFrame(self, corner_radius=12)
        peer_box.grid(row=1, column=0, padx=10, pady=6, sticky="nsew")
        peer_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(peer_box, text="通知对象", font=("PingFang SC", 16, "bold")).grid(row=0, column=0, pady=6)
        self.peer_list = PeerChecklist(peer_box, self.manager)
        self.peer_list.grid(row=1, column=0, padx=8, pady=4, sticky="nsew")
        action_row = ctk.CTkFrame(peer_box)
        action_row.grid(row=2, column=0, pady=6)
        ctk.CTkButton(action_row, text="全选", command=self.peer_list.select_all, width=90).grid(row=0, column=0, padx=4)
        ctk.CTkButton(action_row, text="刷新联系人", command=self.peer_list.refresh, width=120).grid(row=0, column=1, padx=4)

        log_box = ctk.CTkFrame(self, corner_radius=12)
        log_box.grid(row=1, column=1, padx=10, pady=6, sticky="nsew")
        log_box.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(log_box, text="日志文件", font=("PingFang SC", 16, "bold")).grid(row=0, column=0, columnspan=3, pady=6)
        ctk.CTkLabel(log_box, text="路径：").grid(row=1, column=0, padx=4, sticky="e")
        self.log_label = ctk.CTkLabel(log_box, text="未选择")
        self.log_label.grid(row=1, column=1, padx=4, sticky="w")
        ctk.CTkButton(log_box, text="选择", command=self._choose_log, width=90).grid(row=1, column=2, padx=4)

        ctk.CTkLabel(log_box, text="关键字 (逗号分隔)").grid(row=2, column=0, padx=4, pady=4, sticky="e")
        self.keyword_entry = ctk.CTkEntry(log_box)
        self.keyword_entry.insert(0, ",".join(DEFAULT_MARKERS))
        self.keyword_entry.grid(row=2, column=1, padx=4, pady=4, sticky="ew")

        ctk.CTkLabel(log_box, text="轮询秒数").grid(row=3, column=0, padx=4, pady=4, sticky="e")
        self.interval_entry = ctk.CTkEntry(log_box, width=100)
        self.interval_entry.insert(0, "2")
        self.interval_entry.grid(row=3, column=1, padx=4, pady=4, sticky="w")

        btn_row = ctk.CTkFrame(log_box)
        btn_row.grid(row=4, column=0, columnspan=3, pady=8)
        self.monitor_btn = ctk.CTkButton(btn_row, text="开始监控", command=self._toggle)
        self.monitor_btn.grid(row=0, column=0, padx=6)
        self.state_label = ctk.CTkLabel(btn_row, text="状态：空闲")
        self.state_label.grid(row=0, column=1, padx=6)

        self.log_view = ctk.CTkTextbox(log_box, height=200)
        self.log_view.grid(row=5, column=0, columnspan=3, padx=8, pady=6, sticky="nsew")
        self._append_log("提示：选择日志文件并开始监控。")

    def _choose_log(self) -> None:
        path = filedialog.askopenfilename(title="选择日志文件")
        if path:
            self.log_path = Path(path)
            self._last_size = self.log_path.stat().st_size if self.log_path.exists() else 0
            self.log_label.configure(text=str(self.log_path))

    def _toggle(self) -> None:
        if self.monitoring:
            self.monitoring = False
            self.monitor_btn.configure(text="开始监控")
            self.state_label.configure(text="状态：已停止")
        else:
            if not self.log_path:
                messagebox.showinfo("提示", "请先选择日志文件")
                return
            self.monitoring = True
            self.monitor_btn.configure(text="停止监控")
            self.state_label.configure(text="状态：监控中")
            self._start_thread()

    def _start_thread(self) -> None:
        def worker() -> None:
            interval = 2.0
            try:
                interval = max(float(self.interval_entry.get()), 0.5)
            except ValueError:
                pass
            while self.monitoring and self.log_path:
                if not self.log_path.exists():
                    self._append_log("日志文件不存在，监控停止")
                    break
                try:
                    size = self.log_path.stat().st_size
                    if size != self._last_size:
                        self._last_size = size
                        tail = self.log_path.read_text(encoding="utf-8", errors="ignore")[-800:].lower()
                        self._check_markers(tail)
                    time.sleep(interval)
                except Exception:
                    time.sleep(interval)
            self.monitoring = False
            self.monitor_btn.configure(text="开始监控")
            self.state_label.configure(text="状态：空闲")

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()

    def _check_markers(self, text: str) -> None:
        markers = [m.strip().lower() for m in self.keyword_entry.get().split(",") if m.strip()]
        matched = [m for m in markers if m and m in text]
        if matched:
            line = f"检测到关键词：{', '.join(matched)}"
            self._append_log(line)
            self._notify_peers(line)

    def _notify_peers(self, message: str) -> None:
        selected = self.peer_list.selected_peers()
        if not selected:
            return
        msg = f"【实验监控】{message} | 文件：{self.log_path.name if self.log_path else ''}"
        for peer in selected:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.sendto(msg.encode("utf-8"), (peer["ip"], int(peer["port"])))
            except OSError:
                continue

    def _append_log(self, line: str) -> None:
        self.log_view.configure(state="normal")
        self.log_view.insert("end", line + "\n")
        self.log_view.see("end")
        self.log_view.configure(state="disabled")
