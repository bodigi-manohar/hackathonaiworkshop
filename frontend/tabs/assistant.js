/* Assistant tab: chat bound to /chat. Template answers are tagged as such.
 * The LLM only explains pre-computed results - it never computes forecasts. */
(function () {
  "use strict";
  window.Tabs = window.Tabs || {};

  const CHIPS = [
    "Why is the evening peak high?",
    "What is the biggest risk tomorrow?",
    "How much does the battery plan save?",
    "How accurate was the forecast recently?",
  ];

  window.Tabs.assistant = {
    title: "Assistant",
    state: { msgs: [] },
    render(el, data, ctx) {
      const s = this.state;
      if (el._gsBuilt) return; // keep the conversation; do not rebuild on data refresh

      el._gsBuilt = true;
      el.innerHTML = `
        <div class="card">
          <div class="banner">
            <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" d="M12 3 5 6v5c0 4.5 3 8 7 10 4-2 7-5.5 7-10V6l-7-3z"/></svg>
            <span>Answers use <strong>pre-computed results only</strong> — the assistant never calculates a forecast.</span>
          </div>
          <div class="chat">
            <div class="chat-msgs" id="chatMsgs" aria-live="polite"></div>
            <div class="chat-chips" id="chatChips"></div>
            <form class="chat-form" id="chatForm">
              <input class="input" id="chatInput" type="text" autocomplete="off"
                     placeholder="Ask about the forecast, alerts, the battery plan, accuracy…"
                     aria-label="Ask the assistant">
              <button class="btn primary" type="submit" id="chatSend">Send</button>
            </form>
          </div>
        </div>`;

      const msgs = el.querySelector("#chatMsgs");
      const chips = el.querySelector("#chatChips");
      chips.innerHTML = CHIPS.map((q) => `<button class="chip-q" type="button">${q}</button>`).join("");
      chips.addEventListener("click", (e) => {
        const b = e.target.closest(".chip-q");
        if (b) ask(b.textContent);
      });
      el.querySelector("#chatForm").addEventListener("submit", (e) => {
        e.preventDefault();
        const input = el.querySelector("#chatInput");
        const q = input.value.trim();
        if (q) { input.value = ""; ask(q); }
      });

      async function ask(question) {
        pushMsg("user", question);
        const loading = pushLoading();
        try {
          const res = await Api.chat(question, ctx.runId);
          loading.remove();
          pushMsg("bot", res.answer, res);
        } catch (err) {
          loading.remove();
          pushMsg("bot", `Sorry, the assistant is unavailable (${err.message}). Pre-computed numbers are still shown on the other tabs.`);
        }
      }

      function pushMsg(who, text, res) {
        const div = document.createElement("div");
        div.className = `msg ${who}`;
        div.textContent = text;
        if (who === "bot" && res) {
          const meta = document.createElement("div");
          meta.className = "msg-meta";
          meta.innerHTML = res.used_llm
            ? "<span>llm answer</span>"
            : `<span class="tag-template">template answer</span>`;
          div.appendChild(meta);
        }
        msgs.appendChild(div);
        msgs.scrollTop = msgs.scrollHeight;
      }
      function pushLoading() {
        const div = document.createElement("div");
        div.className = "msg bot";
        div.innerHTML = '<div style="display:flex;gap:8px;align-items:center"><span class="spin" style="width:16px;height:16px;border-width:2px"></span><span style="color:var(--muted);font-size:12.5px">thinking…</span></div>';
        msgs.appendChild(div);
        msgs.scrollTop = msgs.scrollHeight;
        return div;
      }
    },
  };
})();
