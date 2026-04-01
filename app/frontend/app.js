/* Sustainable Remedies Chatbot — frontend logic */
(function () {
  "use strict";

  const API = "/api/chat";
  const HEALTH = "/api/health";

  const messagesEl = document.getElementById("messages");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("query-input");
  const sendBtn = document.getElementById("send-btn");
  const personaSel = document.getElementById("persona-select");
  const modeSel = document.getElementById("mode-select");
  const healthEl = document.getElementById("health-status");

  // ── Helpers ──────────────────────────────────────────
  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function addMessage(role, html, sourceBadge) {
    const wrapper = document.createElement("div");
    wrapper.className = `message ${role}`;
    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.innerHTML = html;
    if (sourceBadge) {
      const badge = document.createElement("span");
      badge.className = `source-badge ${sourceBadge.toLowerCase()}`;
      badge.textContent = sourceBadge;
      bubble.appendChild(badge);
    }
    wrapper.appendChild(bubble);
    messagesEl.appendChild(wrapper);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return wrapper;
  }

  function showTyping() {
    const wrapper = document.createElement("div");
    wrapper.className = "message bot";
    wrapper.id = "typing";
    wrapper.innerHTML = `<div class="message-bubble"><div class="typing-dots"><span></span><span></span><span></span></div></div>`;
    messagesEl.appendChild(wrapper);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function hideTyping() {
    const el = document.getElementById("typing");
    if (el) el.remove();
  }

  function formatAnswer(text) {
    // Minimal markdown-like rendering
    return escapeHtml(text)
      .replace(/\n{2,}/g, "</p><p>")
      .replace(/\n/g, "<br>")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>");
  }

  // ── Health check ───────────────────────────────────
  async function checkHealth() {
    try {
      const res = await fetch(HEALTH);
      const data = await res.json();
      healthEl.textContent = `✓ ${data.vectorstore_records} remedies indexed`;
    } catch {
      healthEl.textContent = "⚠ Server unreachable";
    }
  }

  // ── Send message ───────────────────────────────────
  async function send(query) {
    addMessage("user", `<p>${escapeHtml(query)}</p>`);
    input.value = "";
    sendBtn.disabled = true;
    showTyping();

    try {
      const res = await fetch(API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          mode: modeSel.value,
          persona: personaSel.value,
        }),
      });

      hideTyping();

      if (!res.ok) {
        const err = await res.text();
        addMessage("bot", `<p>⚠ Server error: ${escapeHtml(err)}</p>`);
        return;
      }

      const data = await res.json();
      const html = `<p>${formatAnswer(data.answer)}</p>`;
      addMessage("bot", html, data.source);
    } catch (err) {
      hideTyping();
      addMessage("bot", `<p>⚠ Network error: ${escapeHtml(err.message)}</p>`);
    } finally {
      sendBtn.disabled = false;
      input.focus();
    }
  }

  // ── Events ─────────────────────────────────────────
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    send(q);
  });

  // Allow Enter to submit, Shift+Enter for newline (input is single-line so just submit)
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.dispatchEvent(new Event("submit"));
    }
  });

  // Boot
  checkHealth();
})();
