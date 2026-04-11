// ── State ──────────────────────────────────────────────────────────────────────
let currentUser = null;   // { email, user_id }
let currentToken = null;  // JWT access token (stored in memory only)
let sessionId = generateSessionId();

// ── Helpers ───────────────────────────────────────────────────────────────────
function generateSessionId() {
    return 'sess-' + Math.random().toString(36).substring(2, 11);
}

function escapeHTML(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
              .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function authHeaders() {
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${currentToken}`,
    };
}

marked.setOptions({ headerIds: false, mangle: false });

// ── DOM Refs ───────────────────────────────────────────────────────────────────
const authScreen    = document.getElementById('auth-screen');
const appScreen     = document.getElementById('app-screen');
const authForm      = document.getElementById('auth-form');
const authEmail     = document.getElementById('auth-email');
const authPassword  = document.getElementById('auth-password');
const authTitle     = document.getElementById('auth-title');
const authSubtitle  = document.querySelector('.auth-subtitle');
const authBtnText   = document.getElementById('auth-btn-text');
const authBtnLoader = document.getElementById('auth-btn-loader');
const authError     = document.getElementById('auth-error');
const authToggle    = document.getElementById('auth-toggle-btn');

let isSignUp = false;

// ── Auth Toggle ────────────────────────────────────────────────────────────────
authToggle.addEventListener('click', () => {
    isSignUp = !isSignUp;
    authTitle.textContent    = isSignUp ? 'Create account'  : 'Welcome back';
    authSubtitle.textContent = isSignUp
        ? 'Sign up to access your enterprise AI agent'
        : 'Sign in to access your enterprise AI agent';
    authBtnText.textContent  = isSignUp ? 'Create Account'  : 'Sign In';
    authToggle.textContent   = isSignUp ? 'Sign in instead' : 'Create account';
    authError.classList.add('hidden');
});

// ── Auth Submit ────────────────────────────────────────────────────────────────
authForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    authError.classList.add('hidden');
    authBtnLoader.classList.remove('hidden');
    authBtnText.textContent = isSignUp ? 'Creating...' : 'Signing in...';

    const endpoint = isSignUp ? '/auth/signup' : '/auth/login';

    try {
        const resp = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: authEmail.value.trim(),
                password: authPassword.value,
            }),
        });

        const data = await resp.json();

        if (resp.status === 202) {
            showAuthError(data.detail || 'Check your email to confirm your account.');
            return;
        }

        if (!resp.ok) {
            throw new Error(data.detail || 'Authentication failed.');
        }

        // Store token in memory (never localStorage for security)
        currentToken = data.access_token;
        currentUser  = { email: data.email, user_id: data.user_id };
        showApp();

    } catch (err) {
        showAuthError(err.message);
    } finally {
        authBtnLoader.classList.add('hidden');
        authBtnText.textContent = isSignUp ? 'Create Account' : 'Sign In';
    }
});

function showAuthError(msg) {
    authError.textContent = msg;
    authError.classList.remove('hidden');
}

// ── Show/Hide Screens ──────────────────────────────────────────────────────────
function showApp() {
    authScreen.classList.add('hidden');
    appScreen.classList.remove('hidden');
    document.getElementById('user-email-display').textContent = currentUser.email;
    loadSessions();
}

function showAuth() {
    appScreen.classList.add('hidden');
    authScreen.classList.remove('hidden');
}

// Show auth screen on load
showAuth();
authScreen.classList.remove('hidden');

// ── Logout ─────────────────────────────────────────────────────────────────────
document.getElementById('logout-btn').addEventListener('click', async () => {
    try {
        await fetch('/auth/logout', {
            method: 'POST',
            headers: authHeaders(),
        });
    } catch (_) {}
    currentToken = null;
    currentUser  = null;
    sessionId    = generateSessionId();
    chatHistory.innerHTML = '';
    renderWelcome();
    showAuth();
});

// ── Chat ───────────────────────────────────────────────────────────────────────
const form        = document.getElementById('chat-form');
const input       = document.getElementById('query-input');
const sendBtn     = document.getElementById('send-btn');
const chatHistory = document.getElementById('chat-history');

sendBtn.disabled = true;
input.addEventListener('input', () => { sendBtn.disabled = input.value.trim() === ''; });

document.querySelectorAll('.suggestion-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        input.value = btn.textContent;
        handleSend(new Event('submit'));
    });
});

document.getElementById('new-chat-btn').addEventListener('click', () => {
    sessionId = generateSessionId();
    chatHistory.innerHTML = '';
    renderWelcome();
});

form.addEventListener('submit', handleSend);

async function handleSend(e) {
    e.preventDefault();
    const query = input.value.trim();
    if (!query || !currentToken) return;

    input.value = '';
    sendBtn.disabled = true;

    document.querySelector('.welcome-msg')?.remove();
    appendUserMessage(query);
    const typingEl = appendTypingIndicator();
    scrollToBottom();

    try {
        const response = await fetch('/stream', {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify({ query, session_id: sessionId }),
        });

        typingEl.remove();

        if (!response.ok) {
            if (response.status === 401) {
                showAuth();
                return;
            }
            throw new Error(`Server error: ${response.status}`);
        }

        const agentDiv = appendAgentMessageStreaming();
        const reader   = response.body.getReader();
        const decoder  = new TextDecoder();
        let fullText   = '';
        let buffer     = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const raw = line.slice(6).trim();
                if (raw === '[DONE]') {
                    finalizeStreamMessage(agentDiv, fullText);
                    loadSessions();
                    break;
                }
                try {
                    const parsed = JSON.parse(raw);
                    if (parsed.token) {
                        fullText += parsed.token.replace(/\\n/g, '\n');
                        agentDiv.querySelector('.stream-text').textContent = fullText;
                        scrollToBottom();
                    }
                    if (parsed.session_id) sessionId = parsed.session_id;
                } catch (_) {}
            }
        }

    } catch (err) {
        typingEl?.remove();
        appendAgentMessage('Sorry, I encountered an error. Please try again.', []);
    }

    scrollToBottom();
}

// ── Message Rendering ──────────────────────────────────────────────────────────
function appendUserMessage(text) {
    const div = document.createElement('div');
    div.className = 'message user';
    div.innerHTML = `
        <div class="message-inner">
            <div class="avatar">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            </div>
            <div class="message-content"><p>${escapeHTML(text)}</p></div>
        </div>`;
    chatHistory.appendChild(div);
}

function appendAgentMessageStreaming() {
    const div = document.createElement('div');
    div.className = 'message assistant';
    div.innerHTML = `
        <div class="message-inner">
            <div class="avatar">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a10 10 0 1 0 10 10H12V2z"/></svg>
            </div>
            <div class="message-content">
                <div class="markdown-body"><span class="stream-text"></span><span class="cursor-blink">▋</span></div>
            </div>
        </div>`;
    chatHistory.appendChild(div);
    return div;
}

function finalizeStreamMessage(div, fullText) {
    div.querySelector('.markdown-body').innerHTML = marked.parse(fullText);
}

function appendAgentMessage(text, sources = []) {
    const div = document.createElement('div');
    div.className = 'message assistant';
    const htmlText = marked.parse(text);
    let sourcesHtml = '';
    if (sources && sources.length > 0) {
        const chips = sources.map(s => {
            const name = s.replace(/_/g, ' ').replace('.txt', '').replace('.pdf', '');
            return `<span class="source-chip">${name}</span>`;
        }).join('');
        sourcesHtml = `<div class="sources-container"><div class="sources-label">Sources:</div><div class="sources-list">${chips}</div></div>`;
    }
    div.innerHTML = `
        <div class="message-inner">
            <div class="avatar"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a10 10 0 1 0 10 10H12V2z"/></svg></div>
            <div class="message-content"><div class="markdown-body">${htmlText}</div>${sourcesHtml}</div>
        </div>`;
    chatHistory.appendChild(div);
}

function appendTypingIndicator() {
    const template = document.getElementById('typing-template');
    const clone    = template.content.cloneNode(true);
    const div      = clone.querySelector('.message');
    chatHistory.appendChild(div);
    return document.querySelector('.typing-indicator');
}

function scrollToBottom() { chatHistory.scrollTop = chatHistory.scrollHeight; }

function renderWelcome() {
    const div = document.createElement('div');
    div.className = 'message assistant welcome-msg';
    div.innerHTML = `
        <div class="message-inner">
            <div class="avatar"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a10 10 0 1 0 10 10H12V2z"/></svg></div>
            <div class="message-content">
                <h3>Welcome to AcmeAssist</h3>
                <p>I am your intelligent enterprise assistant. Ask me anything about company policies, leave, IT support, and more.</p>
                <div class="suggestions">
                    <button class="suggestion-btn">What is the annual leave policy?</button>
                    <button class="suggestion-btn">What are the rules for remote work?</button>
                    <button class="suggestion-btn">Who do I contact for IT support?</button>
                </div>
            </div>
        </div>`;
    chatHistory.appendChild(div);
    div.querySelectorAll('.suggestion-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            input.value = btn.textContent;
            handleSend(new Event('submit'));
        });
    });
}

// ── Session Sidebar ────────────────────────────────────────────────────────────
async function loadSessions() {
    if (!currentToken) return;
    try {
        const resp = await fetch('/sessions', { headers: authHeaders() });
        if (!resp.ok) return;
        const data = await resp.json();
        renderSessions(data.sessions || []);
    } catch (_) {}
}

function renderSessions(sessions) {
    const list = document.getElementById('sessions-list');
    if (!sessions.length) {
        list.innerHTML = '<p class="sessions-empty">No sessions yet</p>';
        return;
    }
    list.innerHTML = sessions.map(s => `
        <button class="session-item" data-session-id="${s.session_id}">
            <span class="session-preview">${escapeHTML(s.preview)}</span>
            <span class="session-date">${new Date(s.created_at).toLocaleDateString()}</span>
        </button>
    `).join('');

    list.querySelectorAll('.session-item').forEach(btn => {
        btn.addEventListener('click', () => loadSessionHistory(btn.dataset.sessionId));
    });
}

async function loadSessionHistory(sid) {
    if (!currentToken) return;
    sessionId = sid;
    chatHistory.innerHTML = '';
    try {
        const resp = await fetch(`/history/${sid}`, { headers: authHeaders() });
        const data = await resp.json();
        (data.messages || []).forEach(msg => {
            if (msg.role === 'user') appendUserMessage(msg.content);
            else appendAgentMessage(msg.content, msg.sources || []);
        });
        scrollToBottom();
    } catch (_) {
        appendAgentMessage('Could not load history.', []);
    }
}

// ── File Upload ────────────────────────────────────────────────────────────────
const uploadModal    = document.getElementById('upload-modal');
const uploadBtn      = document.getElementById('upload-btn');
const modalCloseBtn  = document.getElementById('modal-close-btn');
const dropZone       = document.getElementById('drop-zone');
const fileInput      = document.getElementById('file-input');
const uploadStatus   = document.getElementById('upload-status');
const uploadResult   = document.getElementById('upload-result');
const uploadError    = document.getElementById('upload-error');
const uploadResultTxt= document.getElementById('upload-result-text');
const progressFill   = document.getElementById('upload-progress-fill');

uploadBtn.addEventListener('click', () => { uploadModal.classList.remove('hidden'); resetUploadModal(); });
modalCloseBtn.addEventListener('click', () => uploadModal.classList.add('hidden'));
uploadModal.addEventListener('click', (e) => { if (e.target === uploadModal) uploadModal.classList.add('hidden'); });

dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]);
});

fileInput.addEventListener('change', () => { if (fileInput.files[0]) uploadFile(fileInput.files[0]); });

async function uploadFile(file) {
    if (!currentToken) return;

    uploadStatus.classList.remove('hidden');
    uploadResult.classList.add('hidden');
    uploadError.classList.add('hidden');
    dropZone.classList.add('hidden');
    document.getElementById('upload-status-text').textContent = `Uploading "${file.name}"...`;

    let progress = 0;
    const interval = setInterval(() => {
        progress = Math.min(progress + 10, 85);
        progressFill.style.width = progress + '%';
    }, 200);

    try {
        const formData = new FormData();
        formData.append('file', file);

        const resp = await fetch('/upload', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${currentToken}` }, // no Content-Type for multipart
            body: formData,
        });

        clearInterval(interval);
        progressFill.style.width = '100%';

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || 'Upload failed');
        }

        const data = await resp.json();
        uploadStatus.classList.add('hidden');
        uploadResult.classList.remove('hidden');
        uploadResultTxt.textContent = data.message;

    } catch (err) {
        clearInterval(interval);
        uploadStatus.classList.add('hidden');
        dropZone.classList.remove('hidden');
        uploadError.textContent = err.message;
        uploadError.classList.remove('hidden');
    }
}

function resetUploadModal() {
    uploadStatus.classList.add('hidden');
    uploadResult.classList.add('hidden');
    uploadError.classList.add('hidden');
    dropZone.classList.remove('hidden');
    progressFill.style.width = '0%';
    fileInput.value = '';
}
