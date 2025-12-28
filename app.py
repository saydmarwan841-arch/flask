from flask import Flask, jsonify, request, render_template
import json
import os

app = Flask(__name__, static_folder='static', template_folder='templates')

QUESTIONS_FILE = os.path.join(app.root_path, 'questions.json')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/questions')
def questions():
    with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
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
    with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
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
    # accept JSON array in payload as `questions` or reject
    questions_payload = payload.get('questions') if isinstance(payload, dict) else None
    if pwd != ADMIN_PASSWORD:
        return jsonify({'error': 'invalid password'}), 403
    if questions_payload is None:
        return jsonify({'error': 'missing questions array'}), 400
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
    # backup
    backup_path = os.path.join(app.root_path, 'questions_backup.json')
    try:
        shutil.copyfile(QUESTIONS_FILE, backup_path)
    except Exception:
        # if backup fails, continue but warn
        pass
    # write new questions
    with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)
    return jsonify({'ok': True, 'count': len(parsed)})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
