const API = {
    questions: '/questions',
    meta: '/questions_meta',
    check: '/check',
    adminVerify: '/admin/verify',
    adminUpdate: '/admin/update_questions'
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

async function refreshQuestionsPreserveProgress() {
    try {
        const oldIndex = index;
        const res = await fetch(API.questions);
        const newQs = await res.json();
        // preserve score and index as much as possible
        questions = newQs;
        if (questions.length === 0) {
            index = 0;
            score = 0;
            renderQuestion();
            showUpdateToast('تم تحديث الأسئلة: لا توجد أسئلة حالياً.');
            return;
        }
        if (oldIndex >= questions.length) index = questions.length - 1;
        // re-render current question without resetting score
        renderQuestion();
        showUpdateToast('تم تحديث الأسئلة تلقائيًا.');
    } catch (e) { console.warn('refresh failed', e); }
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
        btn.className = 'option bg-gray-100 hover:bg-gray-200 p-3 rounded-lg shadow-sm text-right transition';
        // label + icon right side
        btn.innerHTML = `<span class="label">${opt}</span><span class="icon" aria-hidden="true">•</span>`;
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
        btn.classList.add('correct');
        btn.classList.remove('wrong');
        btn.querySelector('.icon').textContent = '✓';
        $('#feedback').innerHTML = `<div class="text-green-700 font-semibold">صح! ${randomCongrats()}</div>`;
        score += 1;
    } else {
        btn.classList.add('wrong');
        btn.querySelector('.icon').textContent = '✕';
        $('#feedback').innerHTML = `<div class="text-red-700 font-semibold">غلط — الإجابة الصحيحة: ${data.answer}</div>`;
        // highlight correct option
        document.querySelectorAll('.option').forEach(b => {
            if (b.querySelector('.label') && b.querySelector('.label').textContent === data.answer) b.classList.add('correct');
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
    const msgs = ['أحسنتِ! 👏', 'عمل رائع! 🌟', 'ممتاز — استمري!', 'مبروك! 🎉'];
    return msgs[Math.floor(Math.random() * msgs.length)];
}

// handle zero questions gracefully
function renderQuestion() {
    if (!questions || questions.length === 0) {
        $('#question-text').textContent = 'لا توجد أسئلة حالياً. انتظري الإضافة من المشرف.';
        $('#options').innerHTML = '';
        $('#feedback').innerHTML = '';
        setProgress();
        return;
    }
    if (index >= questions.length) return showResult();
    setProgress();
    const q = questions[index];
    $('#question-text').textContent = q.question || '';
    const opts = $('#options');
    opts.innerHTML = '';
    q.options.forEach((opt) => {
        const btn = document.createElement('button');
        btn.className = 'option bg-gray-100 hover:bg-gray-200 p-3 rounded-lg shadow-sm text-right transition';
        // label + icon right side
        btn.innerHTML = `<span class="label">${opt}</span><span class="icon" aria-hidden="true">•</span>`;
        btn.onclick = () => handleAnswer(opt, btn);
        opts.appendChild(btn);
    });
    $('#feedback').innerHTML = '';
}

function showResult() {
    $('#card').classList.add('hidden');
    const res = $('#result');
    res.classList.remove('hidden');
    const msgs = ['عمل رائع! حافظي على الاجتهاد.', 'رائع! استمري في التعلم.', 'ممتاز! أنتِ تتقدمين يومًا بعد يوم.'];
    $('#final-message').textContent = msgs[Math.floor(Math.random() * msgs.length)];
    $('#final-message').classList.add('final-anim');
    $('#final-score').textContent = `أحرزتِ ${score} من أصل ${questions.length}.`;
    // small confetti (emoji) burst
    const conf = document.createElement('div');
    conf.className = 'confetti';
    conf.style.right = '20px';
    conf.style.top = '10px';
    conf.style.fontSize = '28px';
    conf.textContent = '🎉✨🌟';
    res.appendChild(conf);
    setTimeout(() => conf.remove(), 2400);
    $('#restart').onclick = () => { index = 0; score = 0; $('#card').classList.remove('hidden'); res.classList.add('hidden'); renderQuestion(); };
}

let currentMeta = 0;

async function fetchMeta() {
    try {
        const res = await fetch(API.meta);
        if (!res.ok) return null;
        const data = await res.json();
        return Number(data.mtime) || 0;
    } catch (e) { return null; }
}

function showUpdateToast(msg) {
    const f = document.getElementById('feedback');
    if (!f) return;
    const prev = f.querySelector('.update-toast');
    if (prev) prev.remove();
    const d = document.createElement('div');
    d.className = 'update-toast text-sm text-green-700 font-semibold';
    d.textContent = msg;
    f.prepend(d);
    setTimeout(() => { d.remove(); }, 3000);
}

function startSSE() {
    if (!window.EventSource) return;
    let es = new EventSource('/events');
    es.onmessage = (e) => {
        try {
            const data = JSON.parse(e.data);
            if (data && data.event === 'questions_updated') {
                // fetch new questions but preserve user's progress
                refreshQuestionsPreserveProgress();
            }
        } catch (err) {
            // ignore non-json or comment
        }
    };
    es.onerror = () => {
        // reconnect after a delay
        es.close();
        setTimeout(startSSE, 2000);
    };
}

// replaced polling with SSE
// function startMetaPolling(interval = 5000) { ... }


// hook up on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    load();
    startSSE();
});
