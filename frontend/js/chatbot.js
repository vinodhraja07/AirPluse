/**
 * AirPulse AI — Claude Sonnet 5 Copilot Frontend Controller (UI/UX Pro Max)
 * Manages conversational state, interactive prompt chips, and real-time station grounding.
 */

let chatHistory = [];
let isChatbotOpen = false;

document.addEventListener('DOMContentLoaded', () => {
  initChatbot();
});

function initChatbot() {
  const toggleBtn = document.getElementById('chatToggleBtn');
  const chatPanel = document.getElementById('chatPanel');
  const closeBtn = document.getElementById('chatCloseBtn');
  const sendBtn = document.getElementById('chatSendBtn');
  const inputEl = document.getElementById('chatInput');
  const promptChips = document.querySelectorAll('.chat-prompt-chip');

  if (toggleBtn) {
    toggleBtn.onclick = () => {
      isChatbotOpen = !isChatbotOpen;
      chatPanel.classList.toggle('active', isChatbotOpen);
      if (isChatbotOpen && inputEl) {
        inputEl.focus();
      }
    };
  }

  if (closeBtn) {
    closeBtn.onclick = () => {
      isChatbotOpen = false;
      chatPanel.classList.remove('active');
    };
  }

  if (sendBtn) {
    sendBtn.onclick = sendUserChatMessage;
  }

  if (inputEl) {
    inputEl.onkeydown = (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendUserChatMessage();
      }
    };
  }

  // Quick Prompt Chips
  promptChips.forEach(chip => {
    chip.onclick = () => {
      const promptText = chip.getAttribute('data-prompt') || chip.textContent;
      if (inputEl) {
        inputEl.value = promptText.trim();
        sendUserChatMessage();
      }
    };
  });
}

async function sendUserChatMessage() {
  const inputEl = document.getElementById('chatInput');
  const messagesContainer = document.getElementById('chatMessages');
  if (!inputEl || !messagesContainer) return;

  const text = inputEl.value.trim();
  if (!text) return;

  // Clear input
  inputEl.value = '';

  // Append user message bubble
  appendMessageBubble('user', text);
  chatHistory.push({ role: 'user', content: text });

  // Append typing indicator
  const typingId = 'typing-' + Date.now();
  const typingDiv = document.createElement('div');
  typingDiv.className = 'chat-msg assistant';
  typingDiv.id = typingId;
  typingDiv.innerHTML = `
    <div class="chat-msg-bubble" style="color: var(--text-muted);">
      <span class="pulse-dot" style="display:inline-block; margin-right:6px;"></span> Analyzing environmental telemetry...
    </div>
  `;
  messagesContainer.appendChild(typingDiv);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;

  // Active station context
  const stnSelect = document.getElementById('stationSelect');
  const stationId = stnSelect ? stnSelect.value : 'DEL-01';

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        station_id: stationId,
        history: chatHistory.slice(-6)
      })
    });

    // Remove typing bubble
    const typingEl = document.getElementById(typingId);
    if (typingEl) typingEl.remove();

    if (!res.ok) throw new Error(`Server returned HTTP ${res.status}`);
    const data = await res.json();

    const replyText = data.reply || 'No response received.';
    appendMessageBubble('assistant', replyText);
    chatHistory.push({ role: 'assistant', content: replyText });

  } catch (err) {
    const typingEl = document.getElementById(typingId);
    if (typingEl) typingEl.remove();

    appendMessageBubble('assistant', `⚠️ **Connection notice**: ${err.message}. Please check if the AirPulse server is running.`);
  }
}

function appendMessageBubble(role, rawContent) {
  const messagesContainer = document.getElementById('chatMessages');
  if (!messagesContainer) return;

  const msgDiv = document.createElement('div');
  msgDiv.className = `chat-msg ${role}`;

  // Formatter for markdown bold (**), bullets (*), and newlines
  let formatted = rawContent
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/\$(.*?)\$/g, '<code style="font-family:var(--font-mono); color:var(--accent-cyan);">$1</code>');

  msgDiv.innerHTML = `
    <div class="chat-msg-bubble">
      ${formatted}
    </div>
  `;

  messagesContainer.appendChild(msgDiv);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}
