# CampusStudyHub

CampusStudyHub is a lightweight, local CustomTkinter application that helps computer science students and researchers manage coursework, track CCF-relevant conference deadlines, monitor experiment logs, and generate research-ready assets. Everything is stored locally in JSON/CSV files so it can be inspected, extended, and used offline as a teaching example.

## Features

- **Task management & reminders:** add/edit/delete tasks with overdue highlighting and upcoming deadline views.
- **File organization & stats:** scan/move study files into `Course/Semester/Type/` and export indexes; see course/status counts.
- **学校事项（School）:** GPA 计算器（必修/选修区分，专业 GPA 和总体 GPA）。
- **科研辅助（Research）:**
  - 会议通知：本地/网络来源切换、定时刷新、星标“我的关注”、提前提醒，支持 LAN+邮件双通道。
  - 实验监控：多日志并行监控，错误/收敛关键词分组，尾部快照、简单指标解析与 CSV 导出，可手动/自动提醒。
  - BibTeX 生成：会议/期刊模板切换，DOI 抓取（带缓存）、批量生成，字段校验与手动编辑。
  - 科研拼图：统一分辨率、可选 DPI/字体/粗斜体、背景色/边框/子标签位置，自动 (a)(b) 标签。
- **其他（Others）:** 番茄钟（精确倒计时、进度条、沉浸静音模式、北京时间展示、可自定义时长）。

## Requirements

- Python 3.9+
- CustomTkinter + Pillow:
  ```bash
  pip install customtkinter pillow
  ```
  CustomTkinter 自带暗色主题；Tkinter 随官方 macOS Python 一起提供。

## 快速开始（中文）

1. 在 VS Code 打开项目目录。
2. （可选）创建虚拟环境并激活：
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. CustomTkinter + Pillow：
   ```bash
   pip install customtkinter pillow
   ```
   其余功能均使用标准库；请确保 macOS Python 带有 Tkinter（官方安装包默认包含）。
4. 运行：
   ```bash
   python main.py
   ```
5. 首次启动会生成 `data/config.json`、`data/tasks.json`、`data/conferences.json` 等本地文件。

常见提示：如果在终端看到 `TSM AdjustCapsLockLED...` 或 `mach port for IMKCFRunLoopWakeUpReliable`，这是 macOS 对 Tkinter 的无害警告，可以忽略。

## Getting started on macOS (from VS Code)

1. **Clone or download** this repository and open the folder in VS Code.
2. (Optional) **Create a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. **Install dependencies:**
   ```bash
   pip install customtkinter pillow
   ```
   Ensure Tkinter is available (it ships with the official macOS installer from python.org).
4. **Run the app:**
   ```bash
   python main.py
   ```
5. **Data files:** On first run, the app will create a `data/` directory with `config.json`, `tasks.json`, and `conferences.json`. File indexes are exported to `data/files_index.csv`; GPA 条目保存在 `data/grades.json`；实验/阅读记录保存在 `data/experiments.json` 与 `data/papers.json`，可一键导出 `data/research_summary.md`。会议爬取源存放在 `config.json` 的 `conference_sources`；DOI 缓存保存在 `data/bib_cache.json`；日志监控配置保存在 `data/log_monitors.json`。

## Project structure

```
main.py                 # Entry point
campusstudyhub/
├─ __init__.py
├─ config.py            # Config defaults and persistence
├─ models.py            # Dataclasses for tasks, conferences, GPA rows, file index entries, research notes
├─ storage.py           # Load/save helpers for tasks, conferences, files, grades, research data
├─ lan.py               # UDP-based LAN notification helper
├─ gui_main.py          # CustomTkinter window and tab wiring（学校事项/科研辅助/其他）
├─ gui_pomodoro.py      # 番茄钟（进度条、沉浸静音、北京时间、自定义时长）
├─ gui_lan.py           # CCF 会议通知 + 实验日志监控（分离功能）
├─ gui_tools.py         # GPA / BibTeX / 科研拼图（CustomTkinter）
└─ 旧版 tkinter 界面    # gui_tasks.py、gui_files.py 等：保留作为示例，可逐步迁移到 CustomTkinter
```

## Usage notes

- Tasks are stored in `data/tasks.json`; you can edit or back it up manually.
- The default base directory for study materials is `~/CampusStudyMaterials`; change it in the Files tab or `data/config.json` (路径中的 `~` 会被自动展开到你的用户目录)。
- File moves are confirmed before execution and never delete files.
- The UI is intentionally simple and well-commented to serve as an educational starting point; feel free to extend it with new tabs or storage formats.
- On some macOS setups, you may see console messages such as `TSM AdjustCapsLockLEDForKeyTransitionHandling` or `error messaging the mach port for IMKCFRunLoopWakeUpReliable` when launching Tkinter apps. These are benign lower-level warnings from the macOS input manager and do not affect the app; you can safely ignore them.
- Conference deadlines live in `data/conferences.json`. You can broadcast reminders over LAN by adding peers (IP/port) in the CCF Conferences tab and clicking **Send LAN reminder**; for safer testing, the default target points to `127.0.0.1`.
