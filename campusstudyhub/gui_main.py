"""CustomTkinter 深色主题主界面，分为学校事项、科研辅助与其他工具。"""
from __future__ import annotations

import customtkinter as ctk

from .gui_lan import ConferenceLANFrame, ExperimentMonitorFrame, PeerManager
from .gui_monitor import ResourceMonitorFrame
from .gui_pomodoro import PomodoroFrame
from .gui_tools import BibtexFrame, FigureComposerFrame, GPAFrame


def launch_app() -> None:
    """启动 CustomTkinter 主窗口。"""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    app = ctk.CTk()
    app.title("CampusStudyHub 研究助手")
    app.geometry("1200x850")

    tabview = ctk.CTkTabview(app)
    tabview.pack(fill="both", expand=True, padx=12, pady=12)

    school_tab = tabview.add("学校事项")
    research_tab = tabview.add("科研辅助")
    other_tab = tabview.add("其他")

    # 学校事项：GPA 计算
    school_inner = ctk.CTkTabview(school_tab)
    school_inner.pack(fill="both", expand=True, padx=10, pady=10)
    gpa_tab = school_inner.add("GPA 计算")
    GPAFrame(gpa_tab).pack(fill="both", expand=True, padx=10, pady=10)

    # 科研辅助：会议通知、实验监控、资源监控、BibTeX、科研拼图
    research_inner = ctk.CTkTabview(research_tab)
    research_inner.pack(fill="both", expand=True, padx=10, pady=10)
    manager = PeerManager()
    conf_tab = research_inner.add("会议通知")
    exp_tab = research_inner.add("实验监控")
    monitor_tab = research_inner.add("资源监控")
    bib_tab = research_inner.add("BibTeX")
    fig_tab = research_inner.add("科研拼图")

    ConferenceLANFrame(conf_tab, manager).pack(fill="both", expand=True, padx=10, pady=10)
    ExperimentMonitorFrame(exp_tab, manager).pack(fill="both", expand=True, padx=10, pady=10)
    ResourceMonitorFrame(monitor_tab).pack(fill="both", expand=True, padx=10, pady=10)
    BibtexFrame(bib_tab).pack(fill="both", expand=True, padx=10, pady=10)
    FigureComposerFrame(fig_tab).pack(fill="both", expand=True, padx=10, pady=10)

    # 其他：番茄钟
    PomodoroFrame(other_tab).pack(fill="both", expand=True, padx=10, pady=10)

    app.mainloop()


if __name__ == "__main__":
    launch_app()

