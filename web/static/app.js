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
  const navChatBtn = document.getElementById("navChat");
  const navChannelsBtn = document.getElementById("navChannels");
  const navSkillsBtn = document.getElementById("navSkills");
  const navMcpBtn = document.getElementById("navMcp");

  const pageChat = document.getElementById("page-chat");
  const pageChannels = document.getElementById("page-channels");
  const pageSkills = document.getElementById("page-skills");
  const pageMcp = document.getElementById("page-mcp");

  const skillsListEl = document.getElementById("skillsList");
  const skillsErrorEl = document.getElementById("skillsError");
  const skillsReloadBtn = document.getElementById("skillsReloadBtn");
  const skillsSaveBtn = document.getElementById("skillsSaveBtn");

  const mcpListEl = document.getElementById("mcpList");
  const mcpErrorEl = document.getElementById("mcpError");
  const mcpReloadBtn = document.getElementById("mcpReloadBtn");
  const mcpSaveBtn = document.getElementById("mcpSaveBtn");
  const channelsSaveBtn = document.getElementById("channelsSaveBtn");
  const channelsErrorEl = document.getElementById("channelsError");

  const telegramBotTokenEl = document.getElementById("telegramBotToken");
  const telegramAllowFromEl = document.getElementById("telegramAllowFrom");
  const telegramUseWebhookEl = document.getElementById("telegramUseWebhook");
  const telegramProxyEl = document.getElementById("telegramProxy");
  const telegramTimeoutEl = document.getElementById("telegramTimeout");

  const qqAppIdEl = document.getElementById("qqAppId");
  const qqAppSecretEl = document.getElementById("qqAppSecret");
  const qqSandboxEl = document.getElementById("qqSandbox");
  const mcpRawEl = document.getElementById("mcpRaw");

  const STORAGE_KEY = "iflow_agent_session_id";
  const HISTORY_PREFIX = "iflow_agent_history_";
  const MAX_HISTORY = 100;
  let sessionId = null;

  function setActivePage(pageEl) {
    if (!pageEl) return;
    const pages = [pageChat, pageChannels, pageSkills, pageMcp].filter(Boolean);
    pages.forEach((p) => {
      if (p === pageEl) p.classList.remove("hidden");
      else p.classList.add("hidden");
    });
  }

  function showError(el, msg) {
    if (!el) return;
    el.textContent = msg;
    el.classList.remove("hidden");
  }

  function clearError(el) {
    if (!el) return;
    el.textContent = "";
    el.classList.add("hidden");
  }

  if (navChatBtn && pageChat) {
    navChatBtn.addEventListener("click", function () {
      setActivePage(pageChat);
    });
  }
  if (navChannelsBtn && pageChannels) {
    navChannelsBtn.addEventListener("click", function () {
      setActivePage(pageChannels);
      loadChannelsConfig();
    });
  }
  if (navSkillsBtn && pageSkills) {
    navSkillsBtn.addEventListener("click", function () {
      setActivePage(pageSkills);
      loadSkills();
    });
  }
  if (navMcpBtn && pageMcp) {
    navMcpBtn.addEventListener("click", function () {
      setActivePage(pageMcp);
      loadMcp();
    });
  }

  // 默认进入聊天页
  if (pageChat) setActivePage(pageChat);

  async function loadSkills() {
    if (!skillsListEl) return;
    clearError(skillsErrorEl);
    skillsListEl.innerHTML = "加载中…";
    try {
      const res = await fetch(apiBase() + "/api/iflow/skills");
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      const skills = data.skills || [];
      if (!skills.length) {
        skillsListEl.innerHTML = "暂无 global skills。";
        return;
      }
      skillsListEl.innerHTML = "";
      for (const s of skills) {
        const id = s.id || "";
        const name = s.name || id;
        const desc = s.description || "";
        const item = document.createElement("div");
        item.className = "list-item";
        item.innerHTML =
          '<input type="checkbox" class="skills-del" value="' +
          id +
          '"/>' +
          '<div>' +
          '<div style="font-weight: 650;">' +
          name +
          "</div>" +
          (desc ? '<div class="muted" style="margin-top:0.25rem;">' + desc + "</div>" : "") +
          '<div class="muted" style="margin-top:0.25rem;font-size:0.75rem;">id: ' +
          id +
          "</div>" +
          "</div>";
        skillsListEl.appendChild(item);
      }
    } catch (e) {
      showError(skillsErrorEl, "加载 skills 失败: " + (e.message || e));
      skillsListEl.innerHTML = "";
    }
  }

  async function loadMcp() {
    if (!mcpListEl) return;
    clearError(mcpErrorEl);
    mcpListEl.innerHTML = "加载中…";
    try {
      const res = await fetch(apiBase() + "/api/iflow/mcp");
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      const servers = data.servers || [];
      if (mcpRawEl) {
        mcpRawEl.textContent = data.mcpListOutput || "";
      }
      if (!servers.length) {
        mcpListEl.innerHTML = "暂无 global MCP 服务器。";
        return;
      }
      mcpListEl.innerHTML = "";
      for (const s of servers) {
        const name = s.name || "";
        const item = document.createElement("div");
        item.className = "list-item";
        item.innerHTML =
          '<input type="checkbox" class="mcp-del" value="' +
          name +
          '"/>' +
          '<div>' +
          '<div style="font-weight: 650;">' +
          name +
          "</div>" +
          "</div>";
        mcpListEl.appendChild(item);
      }
    } catch (e) {
      showError(mcpErrorEl, "加载 MCP 失败: " + (e.message || e));
      mcpListEl.innerHTML = "";
      if (mcpRawEl) mcpRawEl.textContent = "";
    }
  }

  async function loadChannelsConfig() {
    if (!channelsSaveBtn || !pageChannels) return;
    // 只在元素齐全时回填
    if (!telegramBotTokenEl || !telegramAllowFromEl || !telegramUseWebhookEl || !telegramProxyEl || !telegramTimeoutEl) return;
    if (!qqAppIdEl || !qqAppSecretEl || !qqSandboxEl) return;

    clearError(channelsErrorEl);
    try {
      const res = await fetch(apiBase() + "/api/channels/config");
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();

      telegramBotTokenEl.value = data.TELEGRAM_BOT_TOKEN || "";
      telegramAllowFromEl.value = data.TELEGRAM_ALLOW_FROM || "";
      telegramUseWebhookEl.checked = !!data.TELEGRAM_USE_WEBHOOK;
      telegramProxyEl.value = data.TELEGRAM_PROXY || "";
      telegramTimeoutEl.value = data.TELEGRAM_TIMEOUT ?? 60;

      qqAppIdEl.value = data.QQ_APP_ID || "";
      qqAppSecretEl.value = data.QQ_APP_SECRET || "";
      qqSandboxEl.checked = data.QQ_SANDBOX !== undefined ? !!data.QQ_SANDBOX : true;
    } catch (e) {
      showError(channelsErrorEl, "加载渠道配置失败: " + (e.message || e));
    }
  }

  if (channelsSaveBtn) {
    channelsSaveBtn.addEventListener("click", async function () {
      clearError(channelsErrorEl);

      const ok = confirm("保存当前 Telegram/QQ 配置，并重启服务以生效。继续？");
      if (!ok) return;

      try {
        channelsSaveBtn.disabled = true;
        const telegramTimeout = parseFloat(telegramTimeoutEl?.value || "");
        const payload = {
          TELEGRAM_BOT_TOKEN: telegramBotTokenEl.value || "",
          TELEGRAM_ALLOW_FROM: telegramAllowFromEl.value || "",
          TELEGRAM_USE_WEBHOOK: telegramUseWebhookEl.checked,
          TELEGRAM_PROXY: telegramProxyEl.value || "",
          TELEGRAM_TIMEOUT: Number.isFinite(telegramTimeout) ? telegramTimeout : 60,
          QQ_APP_ID: qqAppIdEl.value || "",
          QQ_APP_SECRET: qqAppSecretEl.value || "",
          QQ_SANDBOX: qqSandboxEl.checked,
        };

        const res = await fetch(apiBase() + "/api/channels/config/save-restart", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error("HTTP " + res.status);
        const data = await res.json();
        if (!data.ok) throw new Error(data.error || "save failed");

        alert("保存成功，正在重启服务…");
        setTimeout(function () {
          try {
            window.location.reload();
          } catch (e) {}
        }, 2000);
      } catch (e) {
        showError(channelsErrorEl, "保存失败: " + (e.message || e));
      } finally {
        channelsSaveBtn.disabled = false;
      }
    });
  }

  if (skillsReloadBtn) {
    skillsReloadBtn.addEventListener("click", function () {
      setActivePage(pageSkills);
      loadSkills();
    });
  }
  if (skillsSaveBtn) {
    skillsSaveBtn.addEventListener("click", async function () {
      if (!skillsListEl) return;
      const ids = Array.from(document.querySelectorAll(".skills-del:checked")).map((c) => c.value);
      if (!ids.length) {
        alert("请选择要删除的 skill。");
        return;
      }
      const ok = confirm("将删除所选 skills，并重启 iFlow ACP 以刷新注册表。继续？");
      if (!ok) return;
      clearError(skillsErrorEl);
      try {
        const res = await fetch(apiBase() + "/api/iflow/skills/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ids: ids }),
        });
        if (!res.ok) throw new Error("HTTP " + res.status);
        await res.json();
        await loadSkills();
      } catch (e) {
        showError(skillsErrorEl, "删除 skills 失败: " + (e.message || e));
      }
    });
  }

  if (mcpReloadBtn) {
    mcpReloadBtn.addEventListener("click", function () {
      setActivePage(pageMcp);
      loadMcp();
    });
  }
  if (mcpSaveBtn) {
    mcpSaveBtn.addEventListener("click", async function () {
      if (!mcpListEl) return;
      const names = Array.from(document.querySelectorAll(".mcp-del:checked")).map((c) => c.value);
      if (!names.length) {
        alert("请选择要删除的 MCP 服务器。");
        return;
      }
      const ok = confirm("将删除所选 MCP，并重启 iFlow ACP 以刷新工具列表。继续？");
      if (!ok) return;
      clearError(mcpErrorEl);
      try {
        const res = await fetch(apiBase() + "/api/iflow/mcp/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ names: names }),
        });
        if (!res.ok) throw new Error("HTTP " + res.status);
        await res.json();
        await loadMcp();
      } catch (e) {
        showError(mcpErrorEl, "删除 MCP 失败: " + (e.message || e));
      }
    });
  }

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
