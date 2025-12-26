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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
