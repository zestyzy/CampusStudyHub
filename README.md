# CampusStudyHub

CampusStudyHub is a lightweight, local Tkinter application that helps university students track course tasks, follow CCF-relevant conference deadlines, organize study materials, and view simple progress statistics. Everything is stored locally in JSON/CSV files so it can be inspected, extended, and used offline as a teaching example.

## Features

- **Task management:** add/edit/delete tasks with course, type, due date, priority, and status. Filter by course/status and highlight overdue items.
- **Reminders:** shows upcoming deadlines within a configurable window and lists overdue tasks.
- **CCF conference tracker:** built-in list of common CCF-A conferences, customizable rows, filtering by category and upcoming window, and one-click LAN broadcast for approaching deadlines.
- **File organization:** choose a base study directory, scan files, move them into `Course/Semester/Type/` folders, and export an index to CSV.
- **Statistics:** simple counts per course and status plus a completion progress indicator.
- **Figure Tool:** stitch multiple PNG/JPGs into高分辨率论文配图（支持标题、子图标签、300DPI 输出）。
- **Pomodoro:** 极简番茄钟，专注/休息循环并在到时提醒。
- **GPA Calc:** 按学分加权计算平均分与 4.0 GPA，支持本地保存到 `data/grades.json`。
- **BibTeX:** 输入论文标题或 DOI，生成并校验 BibTeX 条目，便于快速引用。
- **Settings & LAN peers:** edit the list of courses, default base directory, upcoming window, and LAN notification peers; configuration is saved to `data/config.json`.

## Requirements

- Python 3.9+
- Tkinter (included with standard Python on macOS)
- Pillow (for the figure stitching tool):
  ```bash
  pip install pillow
  ```
  Tkinter uses the system libraries and is included with the official macOS Python installer.

## 快速开始（中文）

1. 在 VS Code 打开项目目录。
2. （可选）创建虚拟环境并激活：
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. 图像拼接工具需要 Pillow：
   ```bash
   pip install pillow
   ```
   其余功能均使用标准库；请确保 macOS Python 带有 Tkinter。
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
3. **Install dependencies:** None required beyond the standard library. If using a minimal Python distribution, ensure Tkinter is installed (on macOS it ships with the official installer from python.org).
4. **Run the app:**
   ```bash
   python main.py
   ```
5. **Data files:** On first run, the app will create a `data/` directory with `config.json`, `tasks.json`, and `conferences.json`. File indexes are exported to `data/files_index.csv`; GPA 条目保存在 `data/grades.json`。

## Project structure

```
main.py                 # Entry point
campusstudyhub/
├─ __init__.py
├─ config.py            # Config defaults and persistence
├─ models.py            # Dataclasses for tasks, conferences, GPA rows, file index entries
├─ storage.py           # Load/save helpers for tasks, conferences, files, grades
├─ lan.py               # UDP-based LAN notification helper
├─ gui_main.py          # Application window and tab wiring
├─ gui_tasks.py         # Task management UI and reminders
├─ gui_files.py         # File scanning/organizing UI
├─ gui_stats.py         # Statistics UI
├─ gui_conferences.py   # CCF conference deadlines and LAN broadcasting
├─ gui_plot.py          # Publication figure stitching with Pillow
├─ gui_pomodoro.py      # Pomodoro timer
├─ gui_gpa.py           # GPA calculator with persistence
└─ gui_bibtex.py        # BibTeX generator/validator
```

## Usage notes

- Tasks are stored in `data/tasks.json`; you can edit or back it up manually.
- The default base directory for study materials is `~/CampusStudyMaterials`; change it in the Files tab or `data/config.json` (路径中的 `~` 会被自动展开到你的用户目录)。
- File moves are confirmed before execution and never delete files.
- The UI is intentionally simple and well-commented to serve as an educational starting point; feel free to extend it with new tabs or storage formats.
- On some macOS setups, you may see console messages such as `TSM AdjustCapsLockLEDForKeyTransitionHandling` or `error messaging the mach port for IMKCFRunLoopWakeUpReliable` when launching Tkinter apps. These are benign lower-level warnings from the macOS input manager and do not affect the app; you can safely ignore them.
- Conference deadlines live in `data/conferences.json`. You can broadcast reminders over LAN by adding peers (IP/port) in the CCF Conferences tab and clicking **Send LAN reminder**; for safer testing, the default target points to `127.0.0.1`.
