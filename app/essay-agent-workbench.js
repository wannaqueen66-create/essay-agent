window.EssayAgentWorkbench = (function () {
  const ACCESS_TOKEN_KEY = 'essay_agent_supabase_access_token_v1';

  const I18N = {
    zh: {
      sourceFallback: '来源',
      relevance: '相关性',
      topic: '主题',
      method: '方法',
      conclusion: '结论',
      details: '摘要 / 结构化分析',
      original: '原文链接',
      favorite: '收藏',
      unfavorite: '取消收藏',
      markRead: '标记已读',
      markUnread: '标记未读',
      noteLabel: '个人笔记',
      notePlaceholder: '登录后保存到 Supabase',
      saveNote: '保存笔记',
      kicker: 'ScholarLens',
      title: 'essay-agent 文献工作台',
      subtitle: '以 essay-agent 的建筑学、体育空间、VR、空间行为、行为轨迹与疗愈空间配置为准，集中浏览多源监测、中文结构化分析、领域相关性和个人阅读状态。',
      capabilities: [
        '多源监测',
        '中文结构化分析',
        '语义召回',
        '智能重排',
        'AI 精读',
        '知识库同步',
        '分享快照',
        '邮件日报',
        '每日备份',
      ],
      queryPlaceholder: '搜索标题、摘要或中文分析',
      sourcePlaceholder: '来源：arxiv / openalex / crossref',
      minScorePlaceholder: '最低相关性',
      search: '筛选',
      tokenPlaceholder: 'Supabase access token，用于收藏、已读和笔记',
      saveToken: '保存 token',
      clear: '清除',
      ready: '准备就绪。',
      tokenSaved: 'Token 已保存',
      readOnly: '只读模式',
      loading: '正在加载...',
      loaded: (count) => `已加载 ${count} 篇论文`,
      loadFailed: (message) => `加载失败：${message}`,
      saveFailed: (message) => `保存失败：${message}`,
      noteSaved: '笔记已保存',
      missingToken: '请先粘贴 Supabase access token，再保存个人状态。',
      sidebar: 'ScholarLens 文献工作台',
    },
    en: {
      sourceFallback: 'Source',
      relevance: 'Relevance',
      topic: 'Topic',
      method: 'Method',
      conclusion: 'Conclusion',
      details: 'Abstract / Structured Analysis',
      original: 'Original',
      favorite: 'Favorite',
      unfavorite: 'Unfavorite',
      markRead: 'Mark read',
      markUnread: 'Mark unread',
      noteLabel: 'Personal note',
      notePlaceholder: 'Saved to Supabase after sign-in',
      saveNote: 'Save note',
      kicker: 'ScholarLens',
      title: 'essay-agent Paper Workbench',
      subtitle: 'Browse multi-source monitoring, Chinese structured analysis, domain relevance, and personal reading state driven by essay-agent domains: architecture, sports space, VR, spatial behavior, movement traces, and healing space.',
      capabilities: [
        'Multi-source monitoring',
        'Chinese structured analysis',
        'Semantic recall',
        'Intelligent reranking',
        'AI reading',
        'Knowledge sync',
        'Share snapshot',
        'Email digest',
        'Daily backup',
      ],
      queryPlaceholder: 'Search title, abstract, or Chinese analysis',
      sourcePlaceholder: 'Source: arxiv / openalex / crossref',
      minScorePlaceholder: 'Min relevance',
      search: 'Filter',
      tokenPlaceholder: 'Supabase access token for favorites, read state, and notes',
      saveToken: 'Save token',
      clear: 'Clear',
      ready: 'Ready.',
      tokenSaved: 'Token saved',
      readOnly: 'Read-only',
      loading: 'Loading...',
      loaded: (count) => `Loaded ${count} papers`,
      loadFailed: (message) => `Load failed: ${message}`,
      saveFailed: (message) => `Save failed: ${message}`,
      noteSaved: 'Note saved',
      missingToken: 'Paste a Supabase access token before saving user state.',
      sidebar: 'ScholarLens Workbench',
    },
  };

  const escapeHtml = (value) => String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

  const normalizeText = (value) => String(value || '').trim();

  const currentLang = () => {
    const helper = window.ScholarLensI18n;
    return helper && typeof helper.getLang === 'function' ? helper.getLang() : 'zh';
  };

  const t = () => I18N[currentLang()] || I18N.zh;

  const getConfig = () => {
    const backend =
      window.DPR_RUNTIME_SOURCE_BACKENDS &&
      window.DPR_RUNTIME_SOURCE_BACKENDS.essay_agent
        ? window.DPR_RUNTIME_SOURCE_BACKENDS.essay_agent
        : {};
    return {
      url: normalizeText(backend.url || ''),
      anonKey: normalizeText(backend.anon_key || backend.anonKey || ''),
      schema: normalizeText(backend.schema || 'public') || 'public',
      papersTable: normalizeText(backend.papers_table || 'essay_agent_papers') || 'essay_agent_papers',
      statesTable: normalizeText(backend.states_table || 'user_paper_states') || 'user_paper_states',
    };
  };

  const getAccessToken = () => {
    try {
      return normalizeText(window.localStorage && window.localStorage.getItem(ACCESS_TOKEN_KEY));
    } catch {
      return '';
    }
  };

  const setAccessToken = (token) => {
    try {
      if (!window.localStorage) return;
      const value = normalizeText(token);
      if (value) window.localStorage.setItem(ACCESS_TOKEN_KEY, value);
      else window.localStorage.removeItem(ACCESS_TOKEN_KEY);
    } catch {
      // ignore
    }
  };

  const buildHeaders = (cfg, options = {}) => {
    const token = normalizeText(options.accessToken || '');
    return {
      apikey: cfg.anonKey,
      Authorization: `Bearer ${token || cfg.anonKey}`,
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'Accept-Profile': cfg.schema,
      'Content-Profile': cfg.schema,
      Prefer: options.prefer || '',
    };
  };

  const requestJson = async (cfg, path, options = {}) => {
    if (!cfg.url || !cfg.anonKey) {
      throw new Error('Supabase URL / anon key is missing. Check source_backends.essay_agent.');
    }
    const endpoint = `${cfg.url.replace(/\/+$/, '')}/rest/v1/${path.replace(/^\/+/, '')}`;
    const res = await fetch(endpoint, {
      method: options.method || 'GET',
      headers: buildHeaders(cfg, options),
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
    const text = await res.text();
    const data = text ? JSON.parse(text) : null;
    if (!res.ok) {
      const message = data && data.message ? data.message : `HTTP ${res.status}`;
      throw new Error(message);
    }
    return data;
  };

  const buildPapersQuery = (cfg, state) => {
    const params = new URLSearchParams();
    params.set('select', [
      'id',
      'title',
      'abstract',
      'chinese_summary',
      'source',
      'doi',
      'authors',
      'published',
      'link',
      'domain_query',
      'domain_relevance_score',
      'analysis',
      'meets_threshold',
      'eligible_for_pending',
    ].join(','));
    params.set('order', 'domain_relevance_score.desc,published.desc');
    params.set('limit', String(state.limit || 50));
    if (state.source) params.set('source', `eq.${state.source}`);
    if (state.query) {
      const q = state.query.replace(/[%*,]/g, ' ').trim();
      if (q) params.set('or', `(title.ilike.*${q}*,abstract.ilike.*${q}*,chinese_summary.ilike.*${q}*)`);
    }
    if (state.minScore) params.set('domain_relevance_score', `gte.${Number(state.minScore) || 0}`);
    return `${cfg.papersTable}?${params.toString()}`;
  };

  const loadUserStates = async (cfg, paperIds) => {
    const token = getAccessToken();
    if (!token || !paperIds.length) return {};
    const encoded = paperIds.map((id) => `"${String(id).replace(/"/g, '\\"')}"`).join(',');
    const params = new URLSearchParams();
    params.set('select', 'paper_id,is_favorite,is_read,note,updated_at');
    params.set('source_table', 'eq.essay_agent_papers');
    params.set('paper_id', `in.(${encoded})`);
    const rows = await requestJson(cfg, `${cfg.statesTable}?${params.toString()}`, { accessToken: token });
    const out = {};
    (Array.isArray(rows) ? rows : []).forEach((row) => {
      if (row && row.paper_id) out[row.paper_id] = row;
    });
    return out;
  };

  const upsertUserState = async (cfg, paperId, patch) => {
    const token = getAccessToken();
    if (!token) throw new Error(t().missingToken);
    const payload = {
      paper_id: paperId,
      source_table: 'essay_agent_papers',
      ...patch,
      updated_at: new Date().toISOString(),
    };
    await requestJson(cfg, `${cfg.statesTable}?on_conflict=user_id,paper_id,source_table`, {
      method: 'POST',
      accessToken: token,
      prefer: 'resolution=merge-duplicates,return=minimal',
      body: payload,
    });
  };

  const renderPaperCard = (paper, userState) => {
    const copy = t();
    const analysis = paper.analysis && typeof paper.analysis === 'object' ? paper.analysis : {};
    const score = Number(paper.domain_relevance_score || 0);
    const note = userState && userState.note ? userState.note : '';
    const favoriteLabel = userState && userState.is_favorite ? copy.unfavorite : copy.favorite;
    const readLabel = userState && userState.is_read ? copy.markUnread : copy.markRead;
    return `
      <article class="essay-agent-card" data-paper-id="${escapeHtml(paper.id)}">
        <div class="essay-agent-card-topline">
          <span>${escapeHtml(paper.source || copy.sourceFallback)}</span>
          <span>${escapeHtml((paper.published || '').slice(0, 10))}</span>
          <span class="essay-agent-score">${copy.relevance} ${score}</span>
          ${paper.domain_query ? `<span>${escapeHtml(paper.domain_query)}</span>` : ''}
        </div>
        <h2>${escapeHtml(paper.title)}</h2>
        <p class="essay-agent-summary">${escapeHtml(paper.chinese_summary || analysis['中文摘要'] || paper.abstract || '')}</p>
        <div class="essay-agent-fields">
          ${analysis['研究主题'] ? `<span>${copy.topic}: ${escapeHtml(analysis['研究主题'])}</span>` : ''}
          ${analysis['研究方法'] ? `<span>${copy.method}: ${escapeHtml(analysis['研究方法'])}</span>` : ''}
          ${analysis['主要结论'] ? `<span>${copy.conclusion}: ${escapeHtml(analysis['主要结论'])}</span>` : ''}
        </div>
        <details>
          <summary>${copy.details}</summary>
          <p>${escapeHtml(paper.abstract || '')}</p>
          <pre>${escapeHtml(JSON.stringify(analysis, null, 2))}</pre>
        </details>
        <div class="essay-agent-card-actions">
          <a href="${escapeHtml(paper.link || '#')}" target="_blank" rel="noopener">${copy.original}</a>
          <button type="button" data-action="favorite" data-next="${userState && userState.is_favorite ? '0' : '1'}">${favoriteLabel}</button>
          <button type="button" data-action="read" data-next="${userState && userState.is_read ? '0' : '1'}">${readLabel}</button>
        </div>
        <label class="essay-agent-note-label">
          ${copy.noteLabel}
          <textarea data-role="note" placeholder="${escapeHtml(copy.notePlaceholder)}">${escapeHtml(note)}</textarea>
        </label>
        <button type="button" data-action="save-note">${copy.saveNote}</button>
      </article>
    `;
  };

  const renderShell = (root) => {
    const copy = t();
    root.innerHTML = `
      <section class="essay-agent-workbench">
        <header class="essay-agent-hero">
          <p class="essay-agent-kicker">${copy.kicker}</p>
          <h1>${copy.title}</h1>
          <p>${copy.subtitle}</p>
          <div class="essay-agent-capability-strip">
            ${copy.capabilities.map((item) => `<span>${escapeHtml(item)}</span>`).join('')}
          </div>
        </header>
        <div class="essay-agent-toolbar">
          <input data-role="query" placeholder="${escapeHtml(copy.queryPlaceholder)}" />
          <input data-role="source" placeholder="${escapeHtml(copy.sourcePlaceholder)}" />
          <input data-role="min-score" type="number" min="0" max="100" placeholder="${escapeHtml(copy.minScorePlaceholder)}" />
          <button type="button" data-action="search">${copy.search}</button>
        </div>
        <div class="essay-agent-auth">
          <input data-role="access-token" type="password" placeholder="${escapeHtml(copy.tokenPlaceholder)}" />
          <button type="button" data-action="save-token">${copy.saveToken}</button>
          <button type="button" data-action="clear-token">${copy.clear}</button>
          <span data-role="auth-status"></span>
        </div>
        <div class="essay-agent-status" data-role="status">${copy.ready}</div>
        <div class="essay-agent-grid" data-role="list"></div>
      </section>
    `;
  };

  const bindActions = (root, state) => {
    const cfg = getConfig();
    const statusEl = root.querySelector('[data-role="status"]');
    const listEl = root.querySelector('[data-role="list"]');
    const authStatusEl = root.querySelector('[data-role="auth-status"]');
    const tokenInput = root.querySelector('[data-role="access-token"]');
    if (tokenInput) tokenInput.value = getAccessToken();
    if (authStatusEl) authStatusEl.textContent = getAccessToken() ? t().tokenSaved : t().readOnly;

    const load = async () => {
      try {
        statusEl.textContent = t().loading;
        const rows = await requestJson(cfg, buildPapersQuery(cfg, state));
        const papers = Array.isArray(rows) ? rows : [];
        const userStates = await loadUserStates(cfg, papers.map((p) => p.id).filter(Boolean));
        listEl.innerHTML = papers.map((paper) => renderPaperCard(paper, userStates[paper.id])).join('');
        statusEl.textContent = t().loaded(papers.length);
      } catch (err) {
        statusEl.textContent = t().loadFailed(err && err.message ? err.message : err);
      }
    };

    root.querySelector('[data-action="search"]').addEventListener('click', () => {
      state.query = normalizeText(root.querySelector('[data-role="query"]').value);
      state.source = normalizeText(root.querySelector('[data-role="source"]').value);
      state.minScore = normalizeText(root.querySelector('[data-role="min-score"]').value);
      load();
    });

    root.querySelector('[data-action="save-token"]').addEventListener('click', () => {
      setAccessToken(root.querySelector('[data-role="access-token"]').value);
      if (authStatusEl) authStatusEl.textContent = getAccessToken() ? t().tokenSaved : t().readOnly;
      load();
    });

    root.querySelector('[data-action="clear-token"]').addEventListener('click', () => {
      setAccessToken('');
      if (tokenInput) tokenInput.value = '';
      if (authStatusEl) authStatusEl.textContent = t().readOnly;
      load();
    });

    root.addEventListener('click', async (event) => {
      const button = event.target && event.target.closest ? event.target.closest('button[data-action]') : null;
      if (!button) return;
      const card = button.closest('.essay-agent-card');
      if (!card) return;
      const paperId = card.getAttribute('data-paper-id') || '';
      const action = button.getAttribute('data-action');
      try {
        if (action === 'favorite') {
          await upsertUserState(cfg, paperId, { is_favorite: button.getAttribute('data-next') === '1' });
          await load();
        } else if (action === 'read') {
          await upsertUserState(cfg, paperId, { is_read: button.getAttribute('data-next') === '1' });
          await load();
        } else if (action === 'save-note') {
          const note = card.querySelector('[data-role="note"]');
          await upsertUserState(cfg, paperId, { note: note ? note.value : '' });
          statusEl.textContent = t().noteSaved;
        }
      } catch (err) {
        statusEl.textContent = t().saveFailed(err && err.message ? err.message : err);
      }
    });

    load();
  };

  const render = (root) => {
    if (!root) return;
    const state = { limit: 50, query: '', source: '', minScore: '' };
    renderShell(root);
    bindActions(root, state);
  };

  const installSidebarEntry = () => {
    try {
      const nav = document.querySelector('.sidebar-nav');
      if (!nav) return;
      let link = nav.querySelector('[data-essay-agent-workbench-link]');
      if (!link) {
        const ul = nav.querySelector('ul') || nav;
        const li = document.createElement('li');
        li.innerHTML = '<a class="dpr-sidebar-root-link" data-essay-agent-workbench-link href="#/essay-agent-workbench"></a>';
        ul.insertBefore(li, ul.children && ul.children.length > 1 ? ul.children[1] : null);
        link = li.querySelector('[data-essay-agent-workbench-link]');
      }
      if (link) link.textContent = t().sidebar;
    } catch {
      // ignore
    }
  };

  document.addEventListener('DOMContentLoaded', installSidebarEntry);
  document.addEventListener('dpr-docsify-ready', installSidebarEntry);
  document.addEventListener('dpr-deferred-assets-ready', installSidebarEntry);
  document.addEventListener('scholarlens-language-change', () => {
    installSidebarEntry();
    const root = document.getElementById('essay-agent-workbench-root');
    if (root) render(root);
  });

  return { render, installSidebarEntry };
})();
