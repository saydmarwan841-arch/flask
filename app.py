from flask import Flask, jsonify, request, render_template
import json
import os
import shutil
import time
import sqlite3
from contextlib import closing

app = Flask(__name__, static_folder='static', template_folder='templates')
# session for admin auth
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Persisting to disk is disabled for free-host compatibility; use in-memory storage
QUESTIONS_FILE = os.path.join(app.root_path, 'questions.json')
BACKUP_FILE = os.path.join(app.root_path, 'questions_backup.json')

# DB settings
DB_PATH = os.path.join(app.root_path, 'data.sqlite3')
QUESTIONS_MTIME = int(time.time())

# Database helpers
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if missing and pre-populate from questions.json if DB is empty."""
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ord INTEGER NOT NULL,
                question TEXT NOT NULL,
                options TEXT NOT NULL,
                answer TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            )
        ''')
        conn.commit()
        # if empty, try load from questions.json (best-effort)
        cur.execute('SELECT COUNT(1) as c FROM questions')
        row = cur.fetchone()
        if row and row['c'] == 0 and os.path.exists(QUESTIONS_FILE):
            try:
                with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list) and data:
                    ts = int(time.time())
                    for i, q in enumerate(data):
                        cur.execute('INSERT INTO questions (ord, question, options, answer, updated_at) VALUES (?,?,?,?,?)',
                                    (i, q.get('question',''), json.dumps(q.get('options',[]), ensure_ascii=False), q.get('answer',''), ts))
                    conn.commit()
            except Exception:
                app.logger.exception('Failed seeding DB from questions.json')


def fetch_all_questions():
    """Return list of question dicts ordered by ord."""
    try:
        with closing(get_conn()) as conn:
            cur = conn.cursor()
            cur.execute('SELECT ord, question, options, answer FROM questions ORDER BY ord')
            out = []
            for r in cur.fetchall():
                opts = json.loads(r['options']) if r['options'] else []
                out.append({'question': r['question'], 'options': opts, 'answer': r['answer']})
            return out
    except Exception:
        app.logger.exception('Failed to fetch questions from DB')
        return []


def get_latest_mtime():
    try:
        with closing(get_conn()) as conn:
            cur = conn.cursor()
            cur.execute('SELECT MAX(updated_at) as m FROM questions')
            row = cur.fetchone()
            return int(row['m']) if row and row['m'] else 0
    except Exception:
        app.logger.exception('Failed to read latest mtime from DB')
        return 0


def replace_questions(parsed):
    """Replace all questions in a single transaction and return new mtime."""
    ts = int(time.time())
    try:
        with closing(get_conn()) as conn:
            cur = conn.cursor()
            cur.execute('DELETE FROM questions')
            for i, q in enumerate(parsed):
                cur.execute('INSERT INTO questions (ord, question, options, answer, updated_at) VALUES (?,?,?,?,?)',
                            (i, q.get('question',''), json.dumps(q.get('options',[]), ensure_ascii=False), q.get('answer',''), ts))
            conn.commit()
        return ts
    except Exception:
        app.logger.exception('Failed to replace questions in DB')
        raise

# initialize DB and set QUESTIONS_MTIME
try:
    init_db()
    QUESTIONS_MTIME = get_latest_mtime() or int(time.time())
    app.logger.info(f'DB initialized at {DB_PATH}, questions_mtime={QUESTIONS_MTIME}')
except Exception:
    app.logger.exception('DB initialization failed')
    QUESTIONS_MTIME = int(time.time())

import tempfile


def _ensure_file_exists(path):
    """Ensure file exists and contains a JSON array. If missing or corrupted, create a safe JSON array file."""
    try:
        if not os.path.exists(path):
            with open(path, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            try:
                os.chmod(path, 0o664)
            except Exception:
                pass
            return
        # validate JSON
        with open(path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except Exception:
                # backup corrupted file with timestamp
                ts = int(time.time())
                corrupt_backup = f"{path}.corrupt.{ts}"
                try:
                    shutil.copyfile(path, corrupt_backup)
                    app.logger.warning(f"Backed up corrupted questions file to {corrupt_backup}")
                except Exception:
                    app.logger.exception('Failed to backup corrupted questions file')
                # reset file
                with open(path, 'w', encoding='utf-8') as out:
                    json.dump([], out, ensure_ascii=False, indent=2)
                try:
                    os.chmod(path, 0o664)
                except Exception:
                    pass
    except Exception:
        app.logger.exception('Failed initializing questions file')


def load_questions_safe():
    """Return questions from persistent DB."""
    return fetch_all_questions()


def atomic_write_json(path, data, max_tries=3):
    """Write JSON data atomically to path with retries.

    On platforms like Windows, replacing a file can fail if another process briefly
    has the file open. This function will attempt a few retries and will fall back
    to a direct copy-over approach if os.replace fails.
    """
    dirn = os.path.dirname(path) or '.'
    last_exc = None
    for attempt in range(1, max_tries + 1):
        fd, tmp = tempfile.mkstemp(dir=dirn)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as tmpf:
                json.dump(data, tmpf, ensure_ascii=False, indent=2)
                tmpf.flush()
                os.fsync(tmpf.fileno())
            try:
                os.replace(tmp, path)
                try:
                    os.chmod(path, 0o664)
                except Exception:
                    pass
                return
            except Exception as e_replace:
                app.logger.exception(f'os.replace failed (attempt {attempt}) for {path}')
                last_exc = e_replace
                # Fallback: try copying the tmp file over the destination
                try:
                    with open(tmp, 'rb') as src, open(path, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                        dst.flush()
                        os.fsync(dst.fileno())
                    try:
                        os.chmod(path, 0o664)
                    except Exception:
                        pass
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass
                    return
                except Exception as e_copy:
                    app.logger.exception(f'Fallback copy failed (attempt {attempt}) for {path}')
                    last_exc = e_copy
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass
                    time.sleep(0.1 * attempt)
                    continue
        except Exception as e:
            app.logger.exception(f'atomic_write_json failed while preparing tmp file (attempt {attempt}) for {path}')
            last_exc = e
            try:
                os.remove(tmp)
            except Exception:
                pass
            time.sleep(0.1 * attempt)
            continue
    # If we get here, all attempts failed
    raise Exception(f'atomic_write_json failed after {max_tries} attempts') from last_exc


# Running with in-memory storage — no filesystem setup necessary
app.logger.info('Starting with in-memory question storage. No file writes will be performed.')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/questions')
def questions():
    data = load_questions_safe()
    # Send questions without the correct answers to the client
    safe = []
    for q in data:
        copy = {k: v for k, v in q.items() if k != 'answer'}
        safe.append(copy)
    return jsonify(safe)


@app.route('/questions_meta')
def questions_meta():
    # Return mtime of persistent questions (timestamp when they were last updated)
    try:
        return jsonify({'mtime': int(QUESTIONS_MTIME)})
    except Exception:
        return jsonify({'mtime': 0})


@app.route('/events')
def events():
    """SSE endpoint that notifies clients when questions are updated."""
    # capture request args here so generator does not access `request` while streaming
    try:
        since = int(request.args.get('since') or 0)
    except Exception:
        since = 0

    def gen(last=since):
        # send a comment to open connection
        yield ': connected\n\n'
        while True:
            try:
                current = QUESTIONS_MTIME
                if current and current != last:
                    last = current
                    data = json.dumps({'event': 'questions_updated', 'mtime': current})
                    yield f'data: {data}\n\n'
                time.sleep(1)
            except GeneratorExit:
                break
            except Exception:
                app.logger.exception('SSE generator error')
                time.sleep(1)

    return app.response_class(gen(), mimetype='text/event-stream', headers={'Cache-Control': 'no-cache'})


@app.route('/check', methods=['POST'])
def check():
    payload = request.get_json(force=True)
    try:
        idx = int(payload.get('index', -1))
    except Exception:
        return jsonify({'error': 'invalid index'}), 400
    selected = payload.get('selected')
    data = load_questions_safe()
    if idx < 0 or idx >= len(data):
        return jsonify({'error': 'invalid index'}), 400
    correct = data[idx].get('answer')
    is_correct = str(selected) == str(correct)
    return jsonify({'correct': is_correct, 'answer': correct})


# --- Admin endpoints: verify password and update questions (with backup) ---

ADMIN_PASSWORD = os.environ.get('ADMIN_PASS', '012868')

from flask import session

@app.route('/admin/verify', methods=['POST'])
def admin_verify():
    payload = request.get_json(force=True)
    pwd = payload.get('password', '')
    if pwd == ADMIN_PASSWORD:
        session['admin'] = True
        return jsonify({'ok': True})
    return jsonify({'error': 'invalid password'}), 403


def parse_bulk_questions(content):
    parts = [p.strip() for p in content.split('\n\n') if p.strip()]
    out = []
    for p in parts:
        lines = [l.strip() for l in p.splitlines() if l.strip()]
        if len(lines) < 2:
            raise ValueError('تنسيق غير صالح لكل سؤال')
        qtext = lines[0]
        options = [l[1:].strip() for l in lines if l.startswith('|')]
        answers = [l[1:].strip() for l in lines if l.startswith('=')]
        if len(options) < 2:
            raise ValueError('كل سؤال يجب أن يحتوي على خيارين على الأقل')
        if len(answers) != 1:
            raise ValueError('يجب أن يكون هناك سطر واحد يبدأ بـ = يحتوي الإجابة الصحيحة')
        answer = answers[0]
        if answer not in options:
            raise ValueError('الإجابة الصحيحة يجب أن تكون أحد الخيارات')
        out.append({'question': qtext, 'options': options, 'answer': answer})
    return out


@app.route('/admin')
def admin_page():
    return render_template('admin.html', logged_in=bool(session.get('admin', False)))


@app.route('/admin/update_questions', methods=['POST'])
def admin_update_questions():
    payload = request.get_json(force=True)
    pwd = payload.get('password', '')

    # allow either a valid session or a direct password in payload
    if not session.get('admin') and pwd != ADMIN_PASSWORD:
        return jsonify({'error': 'invalid password'}), 403

    # accept either JSON array under 'questions' or raw text under 'questions_raw'
    questions_payload = None
    raw_text = None
    if isinstance(payload, dict):
        questions_payload = payload.get('questions')
        raw_text = payload.get('questions_raw')

    # If raw text is provided, try to parse it on the server using the bulk parser
    if raw_text:
        try:
            parsed = parse_bulk_questions(raw_text)
        except Exception as e:
            return jsonify({'error': f'failed to parse bulk questions: {str(e)}'}), 400
    else:
        if questions_payload is None:
            return jsonify({'error': 'missing questions array or raw text'}), 400
        # validate structure
        try:
            if not isinstance(questions_payload, list):
                raise ValueError('questions must be a JSON array')
            parsed = []
            for i, q in enumerate(questions_payload):
                if not isinstance(q, dict):
                    raise ValueError(f'question {i+1} invalid')
                qtext = q.get('question')
                opts = q.get('options')
                ans = q.get('answer')
                if not isinstance(qtext, str) or not qtext.strip():
                    raise ValueError(f'question {i+1} has no question text')
                if not isinstance(opts, list) or len(opts) < 2:
                    raise ValueError(f'question {i+1} options invalid')
                if not isinstance(ans, str) or ans not in opts:
                    raise ValueError(f'question {i+1} answer invalid')
                parsed.append({'question': qtext, 'options': opts, 'answer': ans})
        except Exception as e:
            return jsonify({'error': str(e)}), 400

    if len(parsed) > 50:
        return jsonify({'error': 'limit 50 questions'}), 400

    # Persist parsed questions to DB (replace all)
    try:
        app.logger.info(f'admin_update_questions: parsed {len(parsed)} questions; replacing DB')
        new_mtime = replace_questions(parsed)
        # update in-memory marker
        global QUESTIONS_MTIME
        QUESTIONS_MTIME = new_mtime
        # notify: SSE clients will pick up new mtime
        resp = {'ok': True, 'count': len(parsed), 'mtime': QUESTIONS_MTIME}
        return jsonify(resp)
    except Exception as e:
        app.logger.exception('Failed persisting questions to DB')
        return jsonify({'error': 'failed to persist questions', 'detail': str(e)}), 500


@app.route('/admin/test_storage', methods=['GET'])
def admin_test_storage():
    """Report DB storage and basic info."""
    try:
        count = 0
        with closing(get_conn()) as conn:
            cur = conn.cursor()
            cur.execute('SELECT COUNT(1) as c FROM questions')
            row = cur.fetchone()
            count = int(row['c']) if row and row['c'] else 0
        return jsonify({'persistent': True, 'engine': 'sqlite', 'questions_mtime': QUESTIONS_MTIME, 'count': count})
    except Exception:
        app.logger.exception('admin_test_storage failed')
        return jsonify({'persistent': False, 'questions_mtime': 0, 'count': 0})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
