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

- `app.py`: Flask backend with `/questions` and `/check` endpoints (now uses **in-memory** storage; no file writes).
- `questions.json`: optional file used only to pre-populate the in-memory store on startup (no writes are performed).
- `templates/index.html`: frontend UI (no external libraries required).
- `static/js/app.js`: frontend logic.
- `static/css/styles.css`: custom styles.

Use the hidden admin page (`/admin`) to update questions at runtime (password protected). Note: questions are stored only in memory and will be lost when the server restarts — this is intentional for free-hosting compatibility.
