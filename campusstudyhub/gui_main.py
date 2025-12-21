"""CustomTkinter 版主界面，整合科研辅助工具。"""
from __future__ import annotations

import customtkinter as ctk

from .gui_pomodoro import PomodoroFrame
from .gui_lan import LANTrackerFrame
from .gui_tools import GPAFrame, BibtexFrame, FigureComposerFrame


def launch_app() -> None:
    """启动 CustomTkinter 主窗口。"""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    app = ctk.CTk()
    app.title("CampusStudyHub 研究助手")
    app.geometry("1100x800")

    tabview = ctk.CTkTabview(app)
    tabview.pack(fill="both", expand=True, padx=10, pady=10)

    pomodoro_tab = tabview.add("番茄钟")
    lan_tab = tabview.add("CCF 联网")
    tools_tab = tabview.add("GPA / 拼图 / BibTeX")

    PomodoroFrame(pomodoro_tab).pack(fill="both", expand=True, padx=10, pady=10)
    LANTrackerFrame(lan_tab).pack(fill="both", expand=True, padx=10, pady=10)

    tools_inner = ctk.CTkTabview(tools_tab)
    tools_inner.pack(fill="both", expand=True, padx=10, pady=10)
    gpa_tab = tools_inner.add("GPA 计算")
    fig_tab = tools_inner.add("科研拼图")
    bib_tab = tools_inner.add("BibTeX")

    GPAFrame(gpa_tab).pack(fill="both", expand=True, padx=6, pady=6)
    FigureComposerFrame(fig_tab).pack(fill="both", expand=True, padx=6, pady=6)
    BibtexFrame(bib_tab).pack(fill="both", expand=True, padx=6, pady=6)

    app.mainloop()


if __name__ == "__main__":
    launch_app()

