# CampusStudyHub

CampusStudyHub is a lightweight, local Tkinter application that helps university students track course tasks, organize study materials, and view simple progress statistics. Everything is stored locally in JSON/CSV files so it can be inspected, extended, and used offline as a teaching example.

## Features

- **Task management:** add/edit/delete tasks with course, type, due date, priority, and status. Filter by course/status and highlight overdue items.
- **Reminders:** shows upcoming deadlines within a configurable window and lists overdue tasks.
- **File organization:** choose a base study directory, scan files, move them into `Course/Semester/Type/` folders, and export an index to CSV.
- **Statistics:** simple counts per course and status plus a completion progress indicator.
- **Settings:** edit the list of courses and default base directory; configuration is saved to `data/config.json`.

## Requirements

- Python 3.9+
- Tkinter (included with standard Python on macOS)
- No external dependencies beyond the standard library.

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
5. **Data files:** On first run, the app will create a `data/` directory with `config.json` and `tasks.json`. File indexes are exported to `data/files_index.csv`.

## Project structure

```
main.py                 # Entry point
campusstudyhub/
├─ __init__.py
├─ config.py            # Config defaults and persistence
├─ models.py            # Dataclasses for tasks and file index entries
├─ storage.py           # Load/save helpers for tasks and files
├─ gui_main.py          # Application window and tab wiring
├─ gui_tasks.py         # Task management UI and reminders
├─ gui_files.py         # File scanning/organizing UI
└─ gui_stats.py         # Statistics UI
```

## Usage notes

- Tasks are stored in `data/tasks.json`; you can edit or back it up manually.
- The default base directory for study materials is `~/CampusStudyMaterials`; change it in the Files tab or `data/config.json`.
- File moves are confirmed before execution and never delete files.
- The UI is intentionally simple and well-commented to serve as an educational starting point; feel free to extend it with new tabs or storage formats.
