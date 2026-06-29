/**
 * search.js — 搜索功能（传统关键词 / RAG 语义）
 */
const Search = (() => {
  'use strict';

  async function execute(query, mode) {
    if (!query.trim()) return;

    App.clearSearchResults();
    App.hideEmptyState();
    App.showLoading();

    const endpoint = mode === 'keyword' ? '/api/rag/search' : '/api/rag/semantic';

    try {
      const resp = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: query, count: 20 }),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${resp.status}`);
      }

      const data = await resp.json();
      const results = data.results || [];

      App.hideLoading();

      if (results.length === 0) {
        App.DOM.searchResults.innerHTML = `
          <div class="empty-state" style="height:auto;padding:32px 0;opacity:0.5">
            <p style="color:#95A5A6;font-size:14px">未找到匹配的图书</p>
          </div>`;
        return;
      }

      // 标题
      const title = document.createElement('div');
      title.className = 'section-title';
      title.textContent = mode === 'keyword'
        ? `📖 关键词匹配 — ${data.total || results.length} 条结果`
        : `📖 语义搜索 — ${data.total || results.length} 条结果`;
      App.DOM.searchResults.appendChild(title);

      // 渲染图书卡片
      const books = results.map(r => ({
        title: r.书名 || '',
        author: r.作者 || '',
        publisher: r.出版社 || '',
        category: r.中国图书分类号 || '',
        summary: r.摘要 || '',
        keywords: r.关键词 || '',
        publish_date: r.出版年月 || '',
        similarity: r.similarity || 0,
      }));

      App.renderBookCards(books, App.DOM.searchResults);

    } catch (err) {
      App.hideLoading();
      App.DOM.searchResults.innerHTML = `
        <div class="empty-state" style="height:auto;padding:32px 0">
          <p style="color:#E74C3C;font-size:14px">❌ 搜索失败: ${App.escapeHtml(err.message)}</p>
        </div>`;
    }
  }

  return { execute };
})();
