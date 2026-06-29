/**
 * app.js — 主应用逻辑、WebSocket 管理、全局状态
 */
const App = (() => {
  'use strict';

  // ── 状态 ──────────────────────────────────────
  const STATE = {
    ws: null,
    wsConnected: false,
    searchMode: 'keyword',   // 'keyword' | 'semantic'
    isRecording: false,
    isVoiceInteraction: false,
    chatHistory: [],
    currentBookData: null,
    ragUrl: '',
  };

  // ── DOM 引用 ──────────────────────────────────
  const $ = (id) => document.getElementById(id);
  const DOM = {};

  function cacheDom() {
    DOM.searchBtn = $('searchBtn');
    DOM.searchInput = $('searchInput');
    DOM.searchResults = $('searchResults');
    DOM.chatHistory = $('chatHistory');
    DOM.emptyState = $('emptyState');
    DOM.loading = $('loading');
    DOM.chatInput = $('chatInput');
    DOM.sendBtn = $('sendBtn');
    DOM.voiceBtn = $('voiceBtn');
    DOM.interruptBtn = $('interruptBtn');
    DOM.inputWrap = $('inputWrap');
    DOM.configBtn = $('configBtn');
    DOM.configModal = $('configModal');
    DOM.configModalClose = $('configModalClose');
    DOM.ragUrlInput = $('ragUrlInput');
    DOM.ragUrlSave = $('ragUrlSave');
    DOM.ragUrlCancel = $('ragUrlCancel');
    DOM.detailModal = $('detailModal');
    DOM.modalClose = $('modalClose');
    DOM.modalBody = $('modalBody');
    DOM.keyboardOverlay = $('keyboardOverlay');
    DOM.modeTabs = document.querySelectorAll('.mode-tab');
  }

  // ── WebSocket ─────────────────────────────────
  function connectWs() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${location.host}/ws/chat`;
    STATE.ws = new WebSocket(url);

    STATE.ws.onopen = () => {
      STATE.wsConnected = true;
      console.log('🔌 WebSocket 已连接');
    };

    STATE.ws.onclose = () => {
      STATE.wsConnected = false;
      console.log('🔌 WebSocket 已断开，3 秒后重连');
      setTimeout(connectWs, 3000);
    };

    STATE.ws.onerror = (err) => {
      console.error('WebSocket 错误:', err);
    };

    STATE.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleWsMessage(msg);
      } catch (e) {
        console.error('WS 消息解析失败:', e);
      }
    };
  }

  function sendWsMessage(text) {
    if (!STATE.wsConnected) {
      appendChatMessage('agent', '⚠️ 连接已断开，请稍后重试...');
      return;
    }
    STATE.ws.send(JSON.stringify({ text }));
  }

  // ── WebSocket 事件处理 ───────────────────────
  function handleWsMessage(msg) {
    switch (msg.type) {
      case 'text':
        appendChatStreamText(msg.content);
        break;
      case 'tool_call':
        appendChatMessage('agent', `🔧 正在查询: ${msg.args?.query_text || ''}`);
        break;
      case 'tool_result':
        // 工具返回结果，可忽略或显示简略信息
        break;
      case 'books':
        if (msg.books && msg.books.length > 0) {
          renderBookCards(msg.books, DOM.chatHistory);
        }
        break;
      case 'complete':
        finalizeChatStream();
        // 仅语音交互时显示打断按钮
        if (STATE.isVoiceInteraction) {
          showInterruptBtn();
          STATE.isVoiceInteraction = false;
        }
        break;
      case 'error':
        appendChatMessage('agent', `❌ ${msg.message}`);
        finalizeChatStream();
        break;
      case 'wakeup_text':
        // KWS 唤醒：标记为语音交互，显示用户消息 → Agent 回复
        STATE.isVoiceInteraction = true;
        if (msg.text) {
          sendUserMessage(msg.text);
        }
        break;
      case 'voice_state':
        handleVoiceState(msg.state);
        break;
    }
  }

  // ── 消息渲染 ──────────────────────────────────
  let streamContainer = null;

  function appendChatMessage(role, text) {
    hideEmptyState();

    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-msg ${role}`;

    const avatar = document.createElement('div');
    avatar.className = `chat-avatar ${role === 'agent' ? 'agent' : 'user-avatar'}`;
    avatar.textContent = role === 'agent' ? '🤖' : '👤';

    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble';
    bubble.textContent = text;

    msgDiv.appendChild(avatar);
    msgDiv.appendChild(bubble);
    DOM.chatHistory.appendChild(msgDiv);
    scrollToBottom();

    return msgDiv;
  }

  function appendChatStreamText(text) {
    if (!streamContainer) {
      const msgDiv = document.createElement('div');
      msgDiv.className = 'chat-msg agent';
      const avatar = document.createElement('div');
      avatar.className = 'chat-avatar agent';
      avatar.textContent = '🤖';
      streamContainer = document.createElement('div');
      streamContainer.className = 'chat-bubble';
      msgDiv.appendChild(avatar);
      msgDiv.appendChild(streamContainer);
      DOM.chatHistory.appendChild(msgDiv);
      hideEmptyState();
    }
    streamContainer.textContent += text;
    scrollToBottom();
  }

  function finalizeChatStream() {
    streamContainer = null;
    hideLoading();
  }

  function renderBookCards(books, container) {
    const section = document.createElement('div');
    section.className = 'book-list';

    books.forEach((book) => {
      const card = document.createElement('div');
      card.className = 'book-card';
      card.innerHTML = `
        <div class="book-card-body" data-book='${escapeAttr(JSON.stringify(book))}'>
          <span class="book-icon">📘</span>
          <div class="book-info">
            <div class="book-title">${escapeHtml(book.title || '')}</div>
            <div class="book-meta">${escapeHtml(book.author || '')} · ${escapeHtml(book.category || '未分类')}</div>
            <div class="book-desc">${escapeHtml(book.summary || book.keywords || '')}</div>
          </div>
        </div>
        <button class="nav-btn" data-category="${escapeAttr(book.category || '')}" data-title="${escapeAttr(book.title || '')}">📍</button>
      `;

      // 短按卡片 → 详情弹窗
      const body = card.querySelector('.book-card-body');
      body.addEventListener('click', () => {
        Books.showDetail(book);
      });

      // 导航按钮
      const nav = card.querySelector('.nav-btn');
      nav.addEventListener('click', (e) => {
        e.stopPropagation();
        Books.navigate(book.category, book.title);
      });

      section.appendChild(card);
    });

    container.appendChild(section);
    scrollToBottom();
  }

  // ── 用户消息发送 ──────────────────────────────
  function sendUserMessage(text) {
    if (!text.trim()) return;
    appendChatMessage('user', text);
    sendWsMessage(text);
    showLoading();
  }

  // ── 工具函数 ──────────────────────────────────
  function hideEmptyState() {
    DOM.emptyState.style.display = 'none';
  }

  function showLoading() {
    DOM.loading.style.display = 'flex';
  }

  function hideLoading() {
    DOM.loading.style.display = 'none';
  }

  // ── 打断按钮 ──────────────────────────────────
  function showInterruptBtn() {
    DOM.interruptBtn.style.display = 'flex';
    DOM.inputWrap.style.display = 'none';
    DOM.sendBtn.style.display = 'none';
  }

  function hideInterruptBtn() {
    DOM.interruptBtn.style.display = 'none';
    DOM.inputWrap.style.display = '';
    DOM.sendBtn.style.display = '';
  }

  function handleVoiceState(state) {
    if (state === 'speaking') {
      showInterruptBtn();
    } else {
      hideInterruptBtn();
    }
  }

  function sendInterrupt() {
    if (STATE.ws && STATE.wsConnected) {
      STATE.ws.send(JSON.stringify({ type: 'interrupt' }));
    }
    hideInterruptBtn();
  }

  function scrollToBottom() {
    DOM.chatHistory.scrollTo
      ? DOM.chatHistory.scrollTo(0, DOM.chatHistory.scrollHeight)
      : (DOM.chatHistory.parentElement.scrollTop = DOM.chatHistory.parentElement.scrollHeight);
    // Scroll the content container
    const content = document.querySelector('.content');
    if (content) content.scrollTop = content.scrollHeight;
  }

  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function escapeAttr(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function clearSearchResults() {
    DOM.searchResults.innerHTML = '';
  }

  function clearChatHistory() {
    DOM.chatHistory.innerHTML = '';
    streamContainer = null;
  }

  // ── 初始化 ────────────────────────────────────
  function init() {
    cacheDom();

    // 从后端获取配置
    fetch('/api/config')
      .then(r => r.json())
      .then(cfg => {
        STATE.ragUrl = cfg.rag_url || '';
        DOM.ragUrlInput.value = STATE.ragUrl;
      })
      .catch(() => {});

    // 从 localStorage 恢复 RAG URL
    const saved = localStorage.getItem('ragUrl');
    if (saved) {
      STATE.ragUrl = saved;
      DOM.ragUrlInput.value = saved;
    }

    // 连接 WebSocket
    connectWs();

    // ── 事件绑定 ──

    // 搜索按钮
    DOM.searchBtn.addEventListener('click', () => {
      const q = DOM.searchInput.value.trim();
      if (q) Search.execute(q, STATE.searchMode);
    });

    // 搜索输入框回车
    DOM.searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const q = DOM.searchInput.value.trim();
        if (q) Search.execute(q, STATE.searchMode);
      }
    });

    // 搜索模式切换
    DOM.modeTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        DOM.modeTabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        STATE.searchMode = tab.dataset.mode;
        // 更新 placeholder
        DOM.searchInput.placeholder =
          STATE.searchMode === 'keyword' ? '请输入书名/作者...' : '自然语言描述...';
      });
    });

    // 底部发送按钮
    DOM.sendBtn.addEventListener('click', () => {
      const text = DOM.chatInput.value.trim();
      if (text) {
        sendUserMessage(text);
        DOM.chatInput.value = '';
      }
    });

    // 底部输入框回车
    DOM.chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const text = DOM.chatInput.value.trim();
        if (text) {
          sendUserMessage(text);
          DOM.chatInput.value = '';
        }
      }
    });

    // 配置按钮
    DOM.configBtn.addEventListener('click', () => {
      DOM.ragUrlInput.value = STATE.ragUrl;
      DOM.configModal.style.display = 'flex';
    });

    DOM.configModalClose.addEventListener('click', () => {
      DOM.configModal.style.display = 'none';
    });

    DOM.ragUrlCancel.addEventListener('click', () => {
      DOM.configModal.style.display = 'none';
    });

    DOM.ragUrlSave.addEventListener('click', () => {
      const url = DOM.ragUrlInput.value.trim();
      if (url) {
        STATE.ragUrl = url;
        localStorage.setItem('ragUrl', url);
        DOM.configModal.style.display = 'none';
      }
    });

    // 点击遮罩关闭弹窗
    DOM.configModal.addEventListener('click', (e) => {
      if (e.target === DOM.configModal) DOM.configModal.style.display = 'none';
    });
    DOM.detailModal.addEventListener('click', (e) => {
      if (e.target === DOM.detailModal) DOM.detailModal.style.display = 'none';
    });

    // 详情弹窗关闭按钮
    DOM.modalClose.addEventListener('click', () => {
      DOM.detailModal.style.display = 'none';
    });

    // 语音按钮
    Voice.init();

    // 打断按钮
    DOM.interruptBtn.addEventListener('click', () => {
      sendInterrupt();
    });
  }

  // ── 公开 API ──────────────────────────────────
  return {
    init,
    STATE,
    DOM,
    sendUserMessage,
    appendChatMessage,
    appendChatStreamText,
    finalizeChatStream,
    renderBookCards,
    clearSearchResults,
    clearChatHistory,
    showLoading,
    hideLoading,
    hideEmptyState,
    scrollToBottom,
    escapeHtml,
    escapeAttr,
  };
})();
