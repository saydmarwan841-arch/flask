# Habiba — Interactive Quiz

Simple, lightweight quiz app built with Flask (backend) and a modern Tailwind-based frontend.

Quick start

1. Create a Python environment (optional but recommended):

```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

2. Run the app:

```bash
python app.py
```

3. Open http://127.0.0.1:5000 in your browser.

Files

- `app.py`: Flask backend with `/questions` and `/check` endpoints — **now uses SQLite for persistent storage** (data persists across restarts).
- `data.sqlite3`: SQLite database file used to store questions persistently.
- `templates/index.html`: frontend UI (no external libraries required). Automatic updates are delivered to clients via Server-Sent Events (SSE).
- `static/js/app.js`: frontend logic (includes SSE client to refresh questions automatically without requiring users to reload the page).
- `static/css/styles.css`: custom styles.

Use the hidden admin page (`/admin`) to update questions at runtime (password protected). Changes are stored in the database and will be visible to all users instantly via SSE (no manual refresh needed).
