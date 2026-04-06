document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('chat-form');
    const input = document.getElementById('query-input');
    const sendBtn = document.getElementById('send-btn');
    const chatHistory = document.getElementById('chat-history');
    const newSessionBtn = document.getElementById('new-chat-btn');
    const suggestionBtns = document.querySelectorAll('.suggestion-btn');
    
    // Generate a unique session ID for this browser tab
    let sessionId = 'idx-' + Math.random().toString(36).substring(2, 9);

    // Disable marked warnings
    marked.setOptions({
        headerIds: false,
        mangle: false
    });

    // Event Listeners
    form.addEventListener('submit', handleSend);
    newSessionBtn.addEventListener('click', resetSession);
    
    suggestionBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            input.value = btn.textContent;
            handleSend(new Event('submit'));
        });
    });

    input.addEventListener('input', () => {
        sendBtn.disabled = input.value.trim() === '';
    });
    
    // Initially disable send button
    sendBtn.disabled = true;

    async function handleSend(e) {
        e.preventDefault();
        
        const query = input.value.trim();
        if (!query) return;

        // Clear input
        input.value = '';
        sendBtn.disabled = true;

        // Hide welcome message if it's the first query
        const welcomeMsg = document.querySelector('.welcome-msg');
        if (welcomeMsg) {
            welcomeMsg.style.display = 'none';
        }

        // Add user message to UI
        appendUserMessage(query);
        
        // Show typing indicator
        const typingEl = appendTypingIndicator();
        
        // Scroll to bottom
        scrollToBottom();

        try {
            // Send to FastAPI Backend
            const response = await fetch('/ask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: query, session_id: sessionId })
            });

            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }

            const data = await response.json();
            
            // Remove typing indicator
            typingEl.remove();
            
            // Add Agent response
            appendAgentMessage(data.answer, data.sources);
            
        } catch (error) {
            console.error('API Error:', error);
            typingEl.remove();
            appendAgentMessage('Sorry, I encountered an error communicating with the server. Please check if the backend is running.', []);
        }
        
        // Final scroll
        scrollToBottom();
    }

    function appendUserMessage(text) {
        const div = document.createElement('div');
        div.className = 'message user';
        div.innerHTML = `
            <div class="message-inner">
                <div class="avatar">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" class="text-white" stroke="white" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                </div>
                <div class="message-content">
                    <p>${escapeHTML(text)}</p>
                </div>
            </div>
        `;
        chatHistory.appendChild(div);
    }

    function appendAgentMessage(text, sources) {
        const div = document.createElement('div');
        div.className = 'message assistant';
        
        // Parse markdown text to HTML
        const htmlText = marked.parse(text);
        
        let sourcesHtml = '';
        if (sources && sources.length > 0) {
            const chips = sources.map(s => {
                const cleanName = s.replace(/_/g, ' ').replace('.txt', '').replace('.pdf', '');
                return `<span class="source-chip">${cleanName}</span>`;
            }).join('');
            
            sourcesHtml = `
                <div class="sources-container">
                    <div class="sources-label">Information Sources used:</div>
                    <div class="sources-list">${chips}</div>
                </div>
            `;
        }

        div.innerHTML = `
            <div class="message-inner">
                <div class="avatar">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a10 10 0 1 0 10 10H12V2z"></path><path d="M12 12 2.1 7.1"></path><path d="M12 12l9.9 4.9"></path></svg>
                </div>
                <div class="message-content">
                    <div class="markdown-body">${htmlText}</div>
                    ${sourcesHtml}
                </div>
            </div>
        `;
        chatHistory.appendChild(div);
    }

    function appendTypingIndicator() {
        const template = document.getElementById('typing-template');
        const clone = template.content.cloneNode(true);
        const div = clone.querySelector('.message');
        chatHistory.appendChild(div);
        return document.querySelector('.typing-indicator'); // Returns the newly appended element
    }

    function scrollToBottom() {
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    function resetSession() {
        sessionId = 'idx-' + Math.random().toString(36).substring(2, 9);
        chatHistory.innerHTML = '';
        
        // Re-inject welcome message
        const welcomeDiv = document.createElement('div');
        welcomeDiv.className = 'message assistant welcome-msg';
        welcomeDiv.innerHTML = `
            <div class="message-inner">
                <div class="avatar">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a10 10 0 1 0 10 10H12V2z"></path><path d="M12 12 2.1 7.1"></path><path d="M12 12l9.9 4.9"></path></svg>
                </div>
                <div class="message-content">
                    <h3>New Session Started</h3>
                    <p>Session memory cleared. What would you like to ask?</p>
                </div>
            </div>
        `;
        chatHistory.appendChild(welcomeDiv);
    }

    function escapeHTML(str) {
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }
});
