from flask import Flask, jsonify, request, render_template
import json
import os

app = Flask(__name__, static_folder='static', template_folder='templates')

QUESTIONS_FILE = os.path.join(app.root_path, 'questions.json')
BACKUP_FILE = os.path.join(app.root_path, 'questions_backup.json')

import time
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
    """Load questions, returning a list. If file is invalid, reset to empty list after backing up."""
    try:
        with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, list):
                raise ValueError('questions.json must contain a JSON array')
            return data
    except Exception as e:
        app.logger.exception('Error reading questions file; resetting to empty list')
        # try to preserve original
        try:
            ts = int(time.time())
            shutil.copyfile(QUESTIONS_FILE, f"{QUESTIONS_FILE}.corrupt.{ts}")
        except Exception:
            pass
        with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        return []


def atomic_write_json(path, data):
    """Write JSON data atomically to path, ensuring utf-8 and replace in-place."""
    dirn = os.path.dirname(path) or '.'
    fd, tmp = tempfile.mkstemp(dir=dirn)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as tmpf:
            json.dump(data, tmpf, ensure_ascii=False, indent=2)
            tmpf.flush()
            os.fsync(tmpf.fileno())
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o664)
        except Exception:
            pass
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass
        raise


# ensure files exist on startup
_ensure_file_exists(QUESTIONS_FILE)
_ensure_file_exists(BACKUP_FILE)


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
    try:
        mtime = os.path.getmtime(QUESTIONS_FILE)
    except Exception:
        mtime = 0
    return jsonify({'mtime': int(mtime)})


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
import shutil

ADMIN_PASSWORD = os.environ.get('ADMIN_PASS', '012868')

@app.route('/admin/verify', methods=['POST'])
def admin_verify():
    payload = request.get_json(force=True)
    pwd = payload.get('password', '')
    if pwd == ADMIN_PASSWORD:
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
    return render_template('admin.html')


@app.route('/admin/update_questions', methods=['POST'])
def admin_update_questions():
    payload = request.get_json(force=True)
    pwd = payload.get('password', '')

    if pwd != ADMIN_PASSWORD:
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

    # attempt to backup existing file first
    try:
        shutil.copyfile(QUESTIONS_FILE, BACKUP_FILE)
    except Exception:
        app.logger.exception('Failed to create backup copy of questions.json')
        # continue but include a warning in the response
        warn_backup = True
    else:
        warn_backup = False

    # atomically write new questions (replace file)
    try:
        atomic_write_json(QUESTIONS_FILE, parsed)
    except Exception as e:
        app.logger.exception('Failed to write questions file')
        return jsonify({'error': 'failed to save questions'}), 500

    resp = {'ok': True, 'count': len(parsed)}
    if warn_backup:
        resp['warning'] = 'backup_failed'
    return jsonify(resp)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
