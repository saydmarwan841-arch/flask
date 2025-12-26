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

- `app.py`: Flask backend with `/questions` and `/check` endpoints.
- `questions.json`: quiz data (question, options, answer, image).
- `templates/index.html`: frontend UI using Tailwind CDN.
- `static/js/app.js`: frontend logic.
- `static/css/styles.css`: small custom styles.

Edit `questions.json` to add more questions. Images can be external URLs or local files placed under `static`.
