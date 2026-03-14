/* LF */
(function () {
  const chat = document.getElementById("chat");
  const messages = document.getElementById("messages");
  const welcome = document.getElementById("welcome");
  const form = document.getElementById("form");
  const input = document.getElementById("input");
  const sendBtn = document.getElementById("sendBtn");
  const sessionIdEl = document.getElementById("sessionId");
  const newSessionBtn = document.getElementById("newSessionBtn");

  const STORAGE_KEY = "iflow_agent_session_id";
  const HISTORY_PREFIX = "iflow_agent_history_";
  const MAX_HISTORY = 100;
  let sessionId = null;

  function getStoredSessionId() {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      return null;
    }
  }

  function setStoredSessionId(id) {
    try {
      if (id) localStorage.setItem(STORAGE_KEY, id);
      else localStorage.removeItem(STORAGE_KEY);
    } catch (e) {}
  }

  function getHistory(sid) {
    if (!sid) return [];
    try {
      const raw = localStorage.getItem(HISTORY_PREFIX + sid);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      return [];
    }
  }

  function setHistory(sid, list) {
    if (!sid) return;
    try {
      const trimmed = list.slice(-MAX_HISTORY);
      localStorage.setItem(HISTORY_PREFIX + sid, JSON.stringify(trimmed));
    } catch (e) {}
  }

  function addMessageToHistory(role, content, meta) {
    if (!sessionId) return;
    const list = getHistory(sessionId);
    list.push({ role: role, content: content || "", meta: meta || "" });
    setHistory(sessionId, list);
  }

  function renderMessage(role, content, meta) {
    if (welcome && welcome.classList) welcome.classList.add("hidden");
    const div = document.createElement("div");
    div.className = "msg " + role;
    let html = "";
    if (meta) html += '<div class="meta">' + meta + "</div>";
    html += '<div class="content"></div>';
    div.innerHTML = html;
    const contentEl = div.querySelector(".content");
    contentEl.textContent = content;
    messages.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
    return contentEl;
  }

  function appendMessage(role, content, meta) {
    addMessageToHistory(role, content, meta);
    return renderMessage(role, content, meta);
  }

  function loadAndRenderHistory() {
    if (!sessionId || !messages) return;
    messages.innerHTML = "";
    if (welcome && welcome.classList) welcome.classList.remove("hidden");
    const list = getHistory(sessionId);
    for (let i = 0; i < list.length; i++) {
      const m = list[i];
      renderMessage(m.role, m.content, m.meta);
    }
    if (list.length > 0 && welcome && welcome.classList) welcome.classList.add("hidden");
  }

  function apiBase() {
    const a = document.createElement("a");
    a.href = "/";
    return a.origin;
  }

  async function createSession() {
    const res = await fetch(apiBase() + "/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        channel: "web",
        channel_user_id: "default",
        channel_session_id: "",
      }),
    });
    if (!res.ok) throw new Error("创建会话失败");
    const data = await res.json();
    sessionId = data.session_id;
    setStoredSessionId(sessionId);
    if (sessionIdEl) sessionIdEl.textContent = "会话: " + sessionId.slice(0, 8) + "...";
    return sessionId;
  }

  function initSession() {
    sessionId = getStoredSessionId();
    if (sessionIdEl && sessionId) {
      sessionIdEl.textContent = "会话: " + sessionId.slice(0, 8) + "...";
      loadAndRenderHistory();
      return;
    }
    if (sessionIdEl) sessionIdEl.textContent = "未创建会话";
    createSession().then(function () {
      if (sessionIdEl) sessionIdEl.textContent = "会话: " + sessionId.slice(0, 8) + "...";
      loadAndRenderHistory();
    }).catch(function () {});
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSession);
  } else {
    initSession();
  }

  newSessionBtn.addEventListener("click", async function () {
    try {
      await createSession();
      loadAndRenderHistory();
    } catch (e) {
      console.error(e);
    }
  });

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    const text = (input.value || "").trim();
    if (!text) return;

    if (text.toLowerCase() === "/new") {
      input.value = "";
      try {
        await createSession();
        loadAndRenderHistory();
        appendMessage("assistant", "已新建会话，可以继续发消息。", "系统");
      } catch (err) {
        appendMessage("assistant", "新建会话失败: " + err.message, "错误").classList.add("error");
      }
      return;
    }

    if (!sessionId) {
      try {
        await createSession();
      } catch (err) {
        appendMessage("assistant", "无法创建会话: " + err.message, "错误").classList.add("error");
        return;
      }
    }

    appendMessage("user", text);
    input.value = "";
    sendBtn.disabled = true;

    const contentEl = renderMessage("assistant", "…", "");
    const metaEl = contentEl.previousElementSibling;
    const typingEl = document.getElementById("typingIndicator");
    let full = "";

    function showTyping() {
      if (typingEl) typingEl.classList.remove("hidden");
    }
    function hideTyping() {
      if (typingEl) typingEl.classList.add("hidden");
    }

    try {
      const res = await fetch(apiBase() + "/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          session_id: sessionId,
          channel: "web",
          channel_user_id: "default",
          channel_session_id: sessionId,
        }),
      });
      if (!res.ok) {
        contentEl.textContent = "请求失败: " + res.status;
        contentEl.classList.add("error");
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const event = JSON.parse(line.slice(6));
              if (event.type === "typing_start") {
                showTyping();
              } else if (event.type === "assistant_chunk" && event.text) {
                hideTyping();
                full += event.text;
                contentEl.textContent = full;
                if (metaEl) metaEl.textContent = "";
              } else if (event.type === "tool_call" && metaEl) {
                hideTyping();
                metaEl.textContent = "工具: " + (event.tool_name || event.status || "调用中");
              } else if (event.type === "plan" && event.entries && metaEl) {
                hideTyping();
                metaEl.textContent = "计划: " + event.entries.length + " 步";
              } else if (event.type === "task_finish") {
                hideTyping();
                if (metaEl) metaEl.textContent = "完成";
              } else if (event.type === "error") {
                hideTyping();
                contentEl.textContent = event.message || "错误";
                contentEl.classList.add("error");
              }
            } catch (_) {}
          }
        }
        chat.scrollTop = chat.scrollHeight;
      }
      if (!full && contentEl.textContent === "…") contentEl.textContent = "(无文本回复)";
      addMessageToHistory("assistant", full || contentEl.textContent, metaEl ? metaEl.textContent : "");
    } catch (err) {
      hideTyping();
      contentEl.textContent = "请求异常: " + err.message;
      contentEl.classList.add("error");
      addMessageToHistory("assistant", "请求异常: " + err.message, "错误");
    } finally {
      hideTyping();
      sendBtn.disabled = false;
    }
  });

  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });
})();
