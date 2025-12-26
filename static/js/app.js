const API = {
    questions: '/questions',
    check: '/check'
};

let questions = [];
let index = 0;
let score = 0;

const $ = (sel) => document.querySelector(sel);

async function load() {
    const res = await fetch(API.questions);
    questions = await res.json();
    renderQuestion();
}

function setProgress() {
    const pct = questions.length ? ((index) / questions.length) * 100 : 0;
    const bar = $('#progress-bar');
    if (bar) bar.style.width = pct + '%';
    $('#progress-text').textContent = `السؤال ${Math.min(index + 1, questions.length)}/${questions.length}`;
    $('#score').textContent = `النتيجة: ${score}`;
}

function renderQuestion() {
    if (index >= questions.length) return showResult();
    setProgress();
    const q = questions[index];
    $('#question-text').textContent = q.question || '';
    const opts = $('#options');
    opts.innerHTML = '';
    q.options.forEach((opt) => {
        const btn = document.createElement('button');
        btn.className = 'option bg-gray-100 hover:bg-gray-200 p-3 rounded-lg shadow-sm text-right';
        btn.textContent = opt;
        btn.onclick = () => handleAnswer(opt, btn);
        opts.appendChild(btn);
    });
    $('#feedback').innerHTML = '';
}

let awaiting = false;

async function handleAnswer(selected, btn) {
    if (awaiting) return;
    awaiting = true;
    // disable all buttons
    document.querySelectorAll('.option').forEach(b => b.disabled = true);
    const payload = { index, selected };
    const res = await fetch(API.check, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.correct) {
        btn.classList.remove('bg-gray-100');
        btn.classList.add('bg-green-200');
        $('#feedback').innerHTML = `<div class="text-green-700 font-semibold">صح! ${randomCongrats()}</div>`;
        score += 1;
    } else {
        btn.classList.remove('bg-gray-100');
        btn.classList.add('bg-red-200');
        $('#feedback').innerHTML = `<div class="text-red-700 font-semibold">غلط — الإجابة الصحيحة: ${data.answer}</div>`;
        // highlight correct option
        document.querySelectorAll('.option').forEach(b => {
            if (b.textContent === data.answer) b.classList.add('bg-green-200');
        });
    }
    setProgress();
    // advance after short delay
    setTimeout(() => {
        index += 1;
        awaiting = false;
        if (index < questions.length) renderQuestion(); else showResult();
    }, 1200);
}

function randomCongrats() {
    const msgs = ['أحسنت!', 'رائع!', 'ممتاز!', 'مبروك!'];
    return msgs[Math.floor(Math.random() * msgs.length)];
}

function showResult() {
    $('#card').classList.add('hidden');
    const res = $('#result');
    res.classList.remove('hidden');
    $('#final-message').textContent = `تهانينا، حبيبة!`;
    $('#final-score').textContent = `أحرزت ${score} من أصل ${questions.length}.`;
    $('#restart').onclick = () => { index = 0; score = 0; $('#card').classList.remove('hidden'); res.classList.add('hidden'); renderQuestion(); };
}

document.addEventListener('DOMContentLoaded', load);
