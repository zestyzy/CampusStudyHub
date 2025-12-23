"""科研辅助：会议通知与实验监控（CustomTkinter 深色界面）。"""
from __future__ import annotations

import csv
import json
import threading
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .config import AppConfig, load_config
from .lan import send_lan_notifications
from .models import ConferenceEvent, LanTarget, LogMonitorConfig
from .storage import (
    load_conferences,
    load_log_monitors,
    save_conferences,
    save_log_monitors,
)

DATA_DIR = Path("data")
CONFERENCES_FILE = DATA_DIR / "conferences.json"
DEFAULT_MARKERS_ERROR = ["error", "failed", "exception", "nan"]
DEFAULT_MARKERS_OK = ["finished", "complete", "done"]


class PeerManager:
    """简单的同行列表持久化，供会议提醒与实验监控共用。"""

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


class ConferenceLANFrame(ctk.CTkFrame):
    """CCF 会议通知：支持本地/网络源切换、星标与定向提醒。"""

    def __init__(self, master: ctk.CTkBaseClass, manager: PeerManager | None = None) -> None:
        super().__init__(master)
        self.manager = manager or PeerManager()
        self.config: AppConfig = load_config()
        self.conferences: List[ConferenceEvent] = load_conferences()
        self.source_mode = ctk.StringVar(value="本地")
        self.refresh_minutes = ctk.StringVar(value="60")
        self._auto_job: Optional[str] = None
        self._edit_id: Optional[str] = None
        self._build_ui()
        self._refresh_lists()

    def _build_ui(self) -> None:
        self.grid_columnconfigure((0, 1), weight=1)
        title = ctk.CTkLabel(self, text="会议通知", font=("PingFang SC", 24, "bold"))
        title.grid(row=0, column=0, columnspan=2, pady=6)

        # 左：联系人与动作
        peer_box = ctk.CTkFrame(self, corner_radius=12)
        peer_box.grid(row=1, column=0, padx=10, pady=6, sticky="nsew")
        peer_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(peer_box, text="通知对象", font=("PingFang SC", 16, "bold")).grid(row=0, column=0, pady=4)
        self.peer_list = PeerChecklist(peer_box, self.manager)
        self.peer_list.grid(row=1, column=0, padx=8, pady=4, sticky="nsew")
        action_row = ctk.CTkFrame(peer_box)
        action_row.grid(row=2, column=0, pady=6)
        ctk.CTkButton(action_row, text="全选", command=self.peer_list.select_all, width=90).grid(row=0, column=0, padx=4)
        ctk.CTkButton(action_row, text="发送提醒", command=self._send, width=120).grid(row=0, column=1, padx=4)
        ctk.CTkButton(action_row, text="刷新联系人", command=self.peer_list.refresh, width=120).grid(row=0, column=2, padx=4)

        add_row = ctk.CTkFrame(peer_box)
        add_row.grid(row=3, column=0, padx=6, pady=6, sticky="ew")
        add_row.grid_columnconfigure(1, weight=1)
        self.peer_name = ctk.CTkEntry(add_row, placeholder_text="姓名/备注", width=120)
        self.peer_ip = ctk.CTkEntry(add_row, placeholder_text="IP 地址")
        self.peer_port = ctk.CTkEntry(add_row, placeholder_text="端口(可选)", width=90)
        self.peer_email = ctk.CTkEntry(add_row, placeholder_text="邮箱(可选)", width=150)
        ctk.CTkButton(add_row, text="添加联系人", command=self._add_peer).grid(row=0, column=4, padx=4)
        self.peer_name.grid(row=0, column=0, padx=4)
        self.peer_ip.grid(row=0, column=1, padx=4, sticky="ew")
        self.peer_port.grid(row=0, column=2, padx=4)
        self.peer_email.grid(row=0, column=3, padx=4)

        # 右：会议列表
        conf_box = ctk.CTkFrame(self, corner_radius=12)
        conf_box.grid(row=1, column=1, padx=10, pady=6, sticky="nsew")
        conf_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(conf_box, text="会议列表", font=("PingFang SC", 16, "bold")).grid(row=0, column=0, pady=4)

        filter_row = ctk.CTkFrame(conf_box)
        filter_row.grid(row=1, column=0, pady=4, sticky="ew")
        filter_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(filter_row, text="关键词").grid(row=0, column=0, padx=4)
        self.filter_entry = ctk.CTkEntry(filter_row, placeholder_text="CCF-A、ML 等")
        self.filter_entry.grid(row=0, column=1, padx=4, sticky="ew")
        ctk.CTkButton(filter_row, text="过滤", command=self._refresh_lists, width=80).grid(row=0, column=2, padx=4)

        source_row = ctk.CTkFrame(conf_box)
        source_row.grid(row=2, column=0, pady=4, sticky="ew")
        source_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(source_row, text="数据来源").grid(row=0, column=0, padx=4)
        self.source_button = ctk.CTkSegmentedButton(source_row, values=["本地", "网络"], variable=self.source_mode, command=self._refresh_lists)
        self.source_button.grid(row=0, column=1, padx=4, sticky="w")
        ctk.CTkLabel(source_row, text="刷新(分钟)").grid(row=0, column=2, padx=4)
        self.refresh_entry = ctk.CTkEntry(source_row, textvariable=self.refresh_minutes, width=80)
        self.refresh_entry.grid(row=0, column=3, padx=4)
        ctk.CTkButton(source_row, text="立即刷新", command=self._fetch_online, width=100).grid(row=0, column=4, padx=4)

        # 会议 Tab 列表
        self.tabs = ctk.CTkTabview(conf_box)
        self.tabs.grid(row=3, column=0, sticky="nsew", padx=6, pady=6)
        self.tab_all = self.tabs.add("全部")
        self.tab_star = self.tabs.add("我的关注")
        for tab in (self.tab_all, self.tab_star):
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

        self.conf_list_all = ctk.CTkScrollableFrame(self.tab_all, height=260)
        self.conf_list_all.grid(row=0, column=0, sticky="nsew")
        self.conf_list_star = ctk.CTkScrollableFrame(self.tab_star, height=260)
        self.conf_list_star.grid(row=0, column=0, sticky="nsew")

        add_conf_row = ctk.CTkFrame(conf_box)
        add_conf_row.grid(row=4, column=0, pady=6, padx=6, sticky="ew")
        add_conf_row.grid_columnconfigure(1, weight=1)
        self.conf_name = ctk.CTkEntry(add_conf_row, placeholder_text="会议名称")
        self.conf_deadline = ctk.CTkEntry(add_conf_row, placeholder_text="截止日期 YYYY-MM-DD")
        self.conf_location = ctk.CTkEntry(add_conf_row, placeholder_text="地点/备注")
        self.conf_star_days = ctk.CTkEntry(add_conf_row, width=90, placeholder_text="提前天数")
        ctk.CTkButton(add_conf_row, text="新增会议", command=self._add_conf).grid(row=0, column=4, padx=4)
        self.conf_name.grid(row=0, column=0, padx=4, sticky="ew")
        self.conf_deadline.grid(row=0, column=1, padx=4, sticky="ew")
        self.conf_location.grid(row=0, column=2, padx=4, sticky="ew")
        self.conf_star_days.grid(row=0, column=3, padx=4)

    # ---- 数据/事件处理 -------------------------------------------------
    def _refresh_lists(self) -> None:
        keyword = self.filter_entry.get().strip().lower()
        selected_source = self.source_mode.get()
        items = [c for c in self.conferences if (selected_source == "本地" or c.source != "local")]
        if keyword:
            items = [c for c in items if keyword in c.name.lower() or keyword in c.category.lower()]

        def render(container: ctk.CTkScrollableFrame, dataset: List[ConferenceEvent]) -> None:
            for widget in container.winfo_children():
                widget.destroy()
            if not dataset:
                ctk.CTkLabel(container, text="暂无数据").pack(pady=6)
                return
            for conf in dataset:
                row = ctk.CTkFrame(container)
                row.pack(fill="x", pady=2, padx=4)
                text = f"{conf.name} | {conf.category} | 截止 {conf.submission_deadline}"
                ctk.CTkLabel(row, text=text, anchor="w").pack(side="left", padx=4)
                info = ctk.CTkLabel(row, text=f"来源:{conf.source} 提前{conf.remind_before_days}天")
                info.pack(side="left", padx=4)
                star_btn = ctk.CTkButton(row, text="★关注" if conf.starred else "☆关注", width=80,
                                         command=lambda c=conf: self._toggle_star(c))
                star_btn.pack(side="right", padx=4)
                edit_btn = ctk.CTkButton(row, text="编辑", width=60, command=lambda c=conf: self._edit_conf(c))
                edit_btn.pack(side="right", padx=4)

        render(self.conf_list_all, items)
        render(self.conf_list_star, [c for c in items if c.starred])
        self._schedule_auto_refresh()

    def _toggle_star(self, conf: ConferenceEvent) -> None:
        conf.starred = not conf.starred
        save_conferences(self.conferences)
        self._refresh_lists()

    def _edit_conf(self, conf: ConferenceEvent) -> None:
        self.conf_name.delete(0, "end")
        self.conf_deadline.delete(0, "end")
        self.conf_location.delete(0, "end")
        self.conf_star_days.delete(0, "end")
        self.conf_name.insert(0, conf.name)
        self.conf_deadline.insert(0, conf.submission_deadline)
        self.conf_location.insert(0, conf.location)
        self.conf_star_days.insert(0, str(conf.remind_before_days))
        self._edit_id = conf.id

    def _add_peer(self) -> None:
        name = self.peer_name.get().strip() or "未命名"
        ip = self.peer_ip.get().strip()
        port = self.peer_port.get().strip()
        email = self.peer_email.get().strip()
        if not (port.isdigit() or email):
            messagebox.showinfo("提示", "端口或邮箱至少填写一个")
            return
        port_int = int(port) if port.isdigit() else None
        self.manager.add_peer(name, ip, port_int, email)
        self.peer_list.refresh()
        for entry in (self.peer_name, self.peer_ip, self.peer_port, self.peer_email):
            entry.delete(0, "end")

    def _add_conf(self) -> None:
        name = self.conf_name.get().strip()
        deadline = self.conf_deadline.get().strip()
        location = self.conf_location.get().strip()
        remind_days = int(self.conf_star_days.get() or 7)
        if not (name and deadline):
            messagebox.showinfo("提示", "会议名称和截止日期不能为空")
            return
        conf = ConferenceEvent(
            name=name,
            category="CCF-A",
            submission_deadline=deadline,
            location=location,
            remind_before_days=remind_days,
            starred=False,
            source="local",
        )
        # 如果正在编辑则替换
        edit_id = getattr(self, "_edit_id", None)
        if edit_id:
            for idx, item in enumerate(self.conferences):
                if item.id == edit_id:
                    conf.id = edit_id
                    self.conferences[idx] = conf
                    break
            self._edit_id = None
        else:
            self.conferences.append(conf)
        save_conferences(self.conferences)
        self._refresh_lists()
        for entry in (self.conf_name, self.conf_deadline, self.conf_location, self.conf_star_days):
            entry.delete(0, "end")

    def _send(self) -> None:
        selected = self.peer_list.selected_peers()
        if not selected:
            messagebox.showinfo("提示", "请先勾选接收人")
            return
        try:
            window_days = int(self.refresh_minutes.get() or 30)
        except ValueError:
            window_days = 30
        now = date.today()
        due_items = [c for c in self.conferences if c.is_due_within(window_days) or (c.starred and c.is_due_within(c.remind_before_days))]
        if not due_items:
            messagebox.showinfo("提示", "暂无匹配的截止提醒")
            return
        lines = ["【会议提醒】近期截止："]
        for conf in due_items:
            lines.append(f"- {conf.name} | {conf.submission_deadline} | 来源:{conf.source}")
        msg = "\n".join(lines)
        results = self._dispatch(selected, msg)
        messagebox.showinfo("完成", f"已尝试发送，成功 {results['ok']} 条，失败 {results['fail']} 条")

    def _dispatch(self, peers: List[Dict[str, str]], message: str) -> Dict[str, int]:
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
        )
        ok = len([r for r in results if r[1]])
        fail = len(results) - ok
        return {"ok": ok, "fail": fail}

    # ---- 网络抓取与定时刷新 ------------------------------------------
    def _fetch_online(self) -> None:
        """Best-effort 抓取近期会议列表 (RSS/ICS)。"""

        urls = self.config.conference_sources or [
            "https://dblp.org/search/publ/rss?q=CCF+A+deadline",
        ]
        parsed: List[ConferenceEvent] = []
        for url in urls:
            try:
                with urllib.request.urlopen(url, timeout=8) as resp:  # type: ignore[arg-type]
                    text = resp.read().decode("utf-8", errors="ignore")
                # 轻量解析：抓取标题与日期模式
                for line in text.splitlines():
                    if "<title" in line.lower() and "</title>" in line.lower():
                        title = line.replace("<title>", "").replace("</title>", "").strip()
                        if not title or "rss" in title.lower():
                            continue
                        deadline = date.today() + timedelta(days=60)
                        parsed.append(
                            ConferenceEvent(
                                name=title[:80],
                                category="CCF-A",
                                submission_deadline=deadline.isoformat(),
                                location="网络", 
                                source="online",
                            )
                        )
            except Exception:
                continue
        if not parsed:
            messagebox.showinfo("离线", "网络不可用，保留本地会议列表")
            return
        self.conferences = parsed + [c for c in self.conferences if c.source == "local"]
        save_conferences(self.conferences)
        self._refresh_lists()
        messagebox.showinfo("完成", "已更新线上会议")

    def _schedule_auto_refresh(self) -> None:
        if self._auto_job:
            self.after_cancel(self._auto_job)
        try:
            minutes = max(int(self.refresh_minutes.get()), 1)
        except ValueError:
            minutes = 60
        self._auto_job = self.after(minutes * 60 * 1000, self._fetch_online)


class ExperimentMonitorFrame(ctk.CTkFrame):
    """多日志监控，支持错误/收敛分组、尾部快照与通知。"""

    def __init__(self, master: ctk.CTkBaseClass, manager: PeerManager | None = None) -> None:
        super().__init__(master)
        self.manager = manager or PeerManager()
        self.monitors: List[LogMonitorConfig] = load_log_monitors()
        self.running_threads: Dict[str, threading.Thread] = {}
        self.latest_tail: Dict[str, str] = {}
        self.metrics: Dict[str, List[Dict[str, float]]] = {}
        self._build_ui()
        self._render_table()

    def _build_ui(self) -> None:
        self.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(self, text="实验监控", font=("PingFang SC", 24, "bold")).grid(row=0, column=0, columnspan=2, pady=6)

        peer_box = ctk.CTkFrame(self, corner_radius=12)
        peer_box.grid(row=1, column=0, padx=10, pady=6, sticky="nsew")
        peer_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(peer_box, text="通知对象", font=("PingFang SC", 16, "bold")).grid(row=0, column=0, pady=4)
        self.peer_list = PeerChecklist(peer_box, self.manager)
        self.peer_list.grid(row=1, column=0, padx=8, pady=4, sticky="nsew")
        ctk.CTkButton(peer_box, text="全选", command=self.peer_list.select_all, width=100).grid(row=2, column=0, pady=4)
        ctk.CTkButton(peer_box, text="手动提醒", command=self._manual_notify, width=120).grid(row=3, column=0, pady=4)

        config_box = ctk.CTkFrame(self, corner_radius=12)
        config_box.grid(row=1, column=1, padx=10, pady=6, sticky="nsew")
        config_box.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(config_box, text="新增监控", font=("PingFang SC", 16, "bold")).grid(row=0, column=0, columnspan=3, pady=4)
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

        table_box = ctk.CTkFrame(self, corner_radius=12)
        table_box.grid(row=2, column=0, columnspan=2, padx=10, pady=6, sticky="nsew")
        table_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(table_box, text="监控列表", font=("PingFang SC", 16, "bold")).grid(row=0, column=0, pady=4)
        self.table = ctk.CTkScrollableFrame(table_box, height=260)
        self.table.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)

        bottom = ctk.CTkFrame(self, corner_radius=12)
        bottom.grid(row=3, column=0, columnspan=2, padx=10, pady=6, sticky="nsew")
        bottom.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(bottom, text="尾部快照 / 日志", font=("PingFang SC", 16, "bold")).grid(row=0, column=0, pady=4)
        self.log_view = ctk.CTkTextbox(bottom, height=200)
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
        self._start_monitor(monitor)

    def _remove_monitor(self, monitor: LogMonitorConfig) -> None:
        self.monitors = [m for m in self.monitors if m.id != monitor.id]
        save_log_monitors(self.monitors)
        self._render_table()

    def _start_monitor(self, monitor: LogMonitorConfig) -> None:
        if monitor.id in self.running_threads:
            return

        def worker() -> None:
            last_size = 0
            path = Path(monitor.path)
            while monitor.id in self.running_threads:
                if not path.exists():
                    self._append_log(f"[WARN] 文件不存在：{path}")
                    break
                try:
                    size = path.stat().st_size
                    if size != last_size:
                        last_size = size
                        text = path.read_text(encoding="utf-8", errors="ignore")
                        tail = "\n".join(text.splitlines()[-monitor.tail_lines :])
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
        self.log_view.insert("end", line + "\n")
        self.log_view.see("end")

    def _notify_peers(self, message: str) -> None:
        selected = self.peer_list.selected_peers()
        if not selected:
            return
        msg = f"【实验监控】{message}"
        results = self._dispatch(selected, msg)
        self._append_log(f"提醒发送：成功 {results['ok']} 失败 {results['fail']}")

    def _dispatch(self, peers: List[Dict[str, str]], message: str) -> Dict[str, int]:
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
            smtp_host=load_config().smtp_host,
            smtp_port=load_config().smtp_port,
            smtp_sender=load_config().smtp_sender,
        )
        ok = len([r for r in results if r[1]])
        fail = len(results) - ok
        return {"ok": ok, "fail": fail}

    def _manual_notify(self) -> None:
        summary = []
        for mon in self.monitors:
            tail = (self.latest_tail.get(mon.id, "").splitlines() or ["无更新"])[-1]
            summary.append(f"{Path(mon.path).name}: {tail}")
        if not summary:
            messagebox.showinfo("提示", "暂无监控数据")
            return
        self._notify_peers("; ".join(summary))

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
