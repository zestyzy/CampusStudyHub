"""CustomTkinter 深色主题主界面，分为学校事项、科研辅助与其他工具。"""
from __future__ import annotations

import customtkinter as ctk

from .config import load_config, save_config
from .gui_dashboard import DashboardFrame
from .gui_lan import ConferenceLANFrame, ExperimentMonitorFrame, PeerManager
from .gui_monitor import ResourceMonitorFrame
from .gui_pomodoro import PomodoroFrame
from .gui_tools import BibtexFrame, FigureComposerFrame, GPAFrame
from .gui_tasks import TasksFrame
from .storage import load_tasks


def launch_app() -> None:
    """启动 CustomTkinter 主窗口。"""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    app = ctk.CTk()
    app.title("CampusStudyHub 研究助手")
    app.geometry("1200x850")

    tabview = ctk.CTkTabview(app)
    tabview.pack(fill="both", expand=True, padx=12, pady=12)

    overview_tab = tabview.add("总览")
    school_tab = tabview.add("学校事项")
    research_tab = tabview.add("科研辅助")
    other_tab = tabview.add("其他")

    # 预先加载配置与任务
    config = load_config()
    tasks_data = load_tasks()

    # 学校事项：任务与 GPA
    school_inner = ctk.CTkTabview(school_tab)
    school_inner.pack(fill="both", expand=True, padx=10, pady=10)
    tasks_tab = school_inner.add("任务")
    gpa_tab = school_inner.add("GPA 计算")

    def on_tasks_updated(updated):
        nonlocal tasks_data
        tasks_data = updated

    def on_config_update(updated_cfg):
        nonlocal config
        config = updated_cfg
        save_config(config)

    TasksFrame(tasks_tab, tasks_data, config, on_tasks_updated, on_config_update).pack(
        fill="both", expand=True, padx=10, pady=10
    )
    GPAFrame(gpa_tab).pack(fill="both", expand=True, padx=10, pady=10)

    # 科研辅助：会议通知、实验监控、资源监控、BibTeX、科研拼图
    research_inner = ctk.CTkTabview(research_tab)
    research_inner.pack(fill="both", expand=True, padx=10, pady=10)
    manager = PeerManager()
    conf_tab = research_inner.add("会议通知")
    exp_tab = research_inner.add("实验监控")
    monitor_tab = research_inner.add("资源监控")
    bib_tab = research_inner.add("BibTeX 生成")
    fig_tab = research_inner.add("科研拼图")

    ConferenceLANFrame(conf_tab, manager).pack(fill="both", expand=True, padx=10, pady=10)
    ExperimentMonitorFrame(exp_tab, manager).pack(fill="both", expand=True, padx=10, pady=10)
    ResourceMonitorFrame(monitor_tab).pack(fill="both", expand=True, padx=10, pady=10)
    BibtexFrame(bib_tab).pack(fill="both", expand=True, padx=10, pady=10)
    FigureComposerFrame(fig_tab).pack(fill="both", expand=True, padx=10, pady=10)

    # 其他：番茄钟
    PomodoroFrame(other_tab).pack(fill="both", expand=True, padx=10, pady=10)

    # 总览：需要导航回调以跳转到各功能
    navigator = {
        "tasks": lambda: (tabview.set("学校事项"), school_inner.set("任务")),
        "research": lambda: (tabview.set("科研辅助"), research_inner.set("BibTeX 生成")),
        "conferences": lambda: (tabview.set("科研辅助"), research_inner.set("会议通知")),
        "experiments": lambda: (tabview.set("科研辅助"), research_inner.set("实验监控")),
        "monitor": lambda: (tabview.set("科研辅助"), research_inner.set("资源监控")),
        "clock": lambda: tabview.set("其他"),
    }
    DashboardFrame(overview_tab, navigator=navigator).pack(fill="both", expand=True, padx=10, pady=10)

    app.mainloop()


if __name__ == "__main__":
    launch_app()
