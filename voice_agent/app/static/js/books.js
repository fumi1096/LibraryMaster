/**
 * books.js — 图书卡片详情弹窗、导航
 */
const Books = (() => {
  'use strict';

  /**
   * 显示图书详情弹窗
   */
  function showDetail(book) {
    const body = App.DOM.modalBody;
    body.innerHTML = `
      <div class="detail-icon">📘</div>
      <div class="detail-title">${App.escapeHtml(book.title || '')}</div>
      <div class="detail-field">
        <span class="detail-label">作者</span>
        <span class="detail-value">${App.escapeHtml(book.author || '—')}</span>
      </div>
      <div class="detail-field">
        <span class="detail-label">出版社</span>
        <span class="detail-value">${App.escapeHtml(book.publisher || '—')}</span>
      </div>
      <div class="detail-field">
        <span class="detail-label">分类号</span>
        <span class="detail-value">${App.escapeHtml(book.category || '—')}</span>
      </div>
      <div class="detail-field">
        <span class="detail-label">出版年月</span>
        <span class="detail-value">${App.escapeHtml(book.publish_date || '—')}</span>
      </div>
      <div class="detail-field">
        <span class="detail-label">关键词</span>
        <span class="detail-value">${App.escapeHtml(book.keywords || '—')}</span>
      </div>
      <div class="detail-summary">${App.escapeHtml(book.summary || '暂无摘要')}</div>
      <button class="detail-nav-btn" id="modalNavBtn">
        📍 导航到该分类位置
      </button>
    `;

    // 弹窗内的导航按钮
    const navBtn = body.querySelector('#modalNavBtn');
    if (navBtn) {
      navBtn.addEventListener('click', () => {
        navigate(book.category, book.title);
        App.DOM.detailModal.style.display = 'none';
      });
    }

    App.DOM.detailModal.style.display = 'flex';
  }

  /**
   * 发送导航请求
   */
  async function navigate(category, title) {
    if (!category && !title) {
      App.appendChatMessage('agent', '⚠️ 该图书没有分类信息，无法导航');
      return;
    }

    App.appendChatMessage('user', `📍 导航到: ${title || category}`);

    try {
      const resp = await fetch('/api/navigate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category: category || '', book_title: title || '' }),
      });
      const data = await resp.json();

      if (resp.ok) {
        App.appendChatMessage('agent', `✅ ${data.message || '导航请求已发送'}`);
      } else {
        App.appendChatMessage('agent', `❌ 导航失败: ${data.detail || '未知错误'}`);
      }
    } catch (err) {
      App.appendChatMessage('agent', `❌ 导航请求失败: ${err.message}`);
    }
  }

  return { showDetail, navigate };
})();
