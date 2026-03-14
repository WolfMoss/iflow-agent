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

  let sessionId = null;

  function apiBase() {
    const a = document.createElement("a");
    a.href = "/";
    return a.origin;
  }

  function appendMessage(role, content, meta) {
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
    if (sessionIdEl) sessionIdEl.textContent = "会话: " + sessionId.slice(0, 8) + "...";
    return sessionId;
  }

  newSessionBtn.addEventListener("click", async function () {
    try {
      await createSession();
    } catch (e) {
      console.error(e);
    }
  });

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    const text = (input.value || "").trim();
    if (!text) return;

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

    const contentEl = appendMessage("assistant", "…");
    const metaEl = contentEl.previousElementSibling;
    let full = "";

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
              if (event.type === "assistant_chunk" && event.text) {
                full += event.text;
                contentEl.textContent = full;
                if (metaEl) metaEl.textContent = "";
              } else if (event.type === "tool_call" && metaEl) {
                metaEl.textContent = "工具: " + (event.tool_name || event.status || "调用中");
              } else if (event.type === "plan" && event.entries && metaEl) {
                metaEl.textContent = "计划: " + event.entries.length + " 步";
              } else if (event.type === "task_finish") {
                if (metaEl) metaEl.textContent = "完成";
              } else if (event.type === "error") {
                contentEl.textContent = event.message || "错误";
                contentEl.classList.add("error");
              }
            } catch (_) {}
          }
        }
        chat.scrollTop = chat.scrollHeight;
      }
      if (!full && contentEl.textContent === "…") contentEl.textContent = "(无文本回复)";
    } catch (err) {
      contentEl.textContent = "请求异常: " + err.message;
      contentEl.classList.add("error");
    } finally {
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
