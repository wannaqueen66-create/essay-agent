window.EssayAgentWorkbench = (function () {
  const ACCESS_TOKEN_KEY = 'essay_agent_supabase_access_token_v1';

  const escapeHtml = (value) => String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

  const normalizeText = (value) => String(value || '').trim();

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
    if (!token) throw new Error('Paste a Supabase access token before saving user state.');
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
    const analysis = paper.analysis && typeof paper.analysis === 'object' ? paper.analysis : {};
    const score = Number(paper.domain_relevance_score || 0);
    const note = userState && userState.note ? userState.note : '';
    return `
      <article class="essay-agent-card" data-paper-id="${escapeHtml(paper.id)}">
        <div class="essay-agent-card-topline">
          <span>${escapeHtml(paper.source || 'source')}</span>
          <span>${escapeHtml((paper.published || '').slice(0, 10))}</span>
          <span class="essay-agent-score">Score ${score}</span>
          ${paper.domain_query ? `<span>${escapeHtml(paper.domain_query)}</span>` : ''}
        </div>
        <h2>${escapeHtml(paper.title)}</h2>
        <p class="essay-agent-summary">${escapeHtml(paper.chinese_summary || analysis['中文摘要'] || paper.abstract || '')}</p>
        <div class="essay-agent-fields">
          ${analysis['研究主题'] ? `<span>主题: ${escapeHtml(analysis['研究主题'])}</span>` : ''}
          ${analysis['研究方法'] ? `<span>方法: ${escapeHtml(analysis['研究方法'])}</span>` : ''}
          ${analysis['主要结论'] ? `<span>结论: ${escapeHtml(analysis['主要结论'])}</span>` : ''}
        </div>
        <details>
          <summary>Abstract / structured analysis</summary>
          <p>${escapeHtml(paper.abstract || '')}</p>
          <pre>${escapeHtml(JSON.stringify(analysis, null, 2))}</pre>
        </details>
        <div class="essay-agent-card-actions">
          <a href="${escapeHtml(paper.link || '#')}" target="_blank" rel="noopener">Original</a>
          <button type="button" data-action="favorite">${userState && userState.is_favorite ? 'Unfavorite' : 'Favorite'}</button>
          <button type="button" data-action="read">${userState && userState.is_read ? 'Mark unread' : 'Mark read'}</button>
        </div>
        <label class="essay-agent-note-label">
          Personal note
          <textarea data-role="note" placeholder="Saved to Supabase after login">${escapeHtml(note)}</textarea>
        </label>
        <button type="button" data-action="save-note">Save note</button>
      </article>
    `;
  };

  const renderShell = (root) => {
    root.innerHTML = `
      <section class="essay-agent-workbench">
        <header class="essay-agent-hero">
          <p class="essay-agent-kicker">essay-agent fusion</p>
          <h1>中文文献阅读工作台</h1>
          <p>Browse essay-agent multi-source papers, Chinese structured analysis, domain relevance scores, and personal reading state.</p>
        </header>
        <div class="essay-agent-toolbar">
          <input data-role="query" placeholder="Search title, abstract, or Chinese summary" />
          <input data-role="source" placeholder="Source: arxiv / openalex" />
          <input data-role="min-score" type="number" min="0" max="100" placeholder="Min score" />
          <button type="button" data-action="search">Search</button>
        </div>
        <div class="essay-agent-auth">
          <input data-role="access-token" type="password" placeholder="Supabase access token for favorite/read/note" />
          <button type="button" data-action="save-token">Save token</button>
          <button type="button" data-action="clear-token">Clear</button>
          <span data-role="auth-status"></span>
        </div>
        <div class="essay-agent-status" data-role="status">Ready.</div>
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
    if (authStatusEl) authStatusEl.textContent = getAccessToken() ? 'Token saved' : 'Read-only';

    const load = async () => {
      try {
        statusEl.textContent = 'Loading...';
        const rows = await requestJson(cfg, buildPapersQuery(cfg, state));
        const papers = Array.isArray(rows) ? rows : [];
        const userStates = await loadUserStates(cfg, papers.map((p) => p.id).filter(Boolean));
        listEl.innerHTML = papers.map((paper) => renderPaperCard(paper, userStates[paper.id])).join('');
        statusEl.textContent = `Loaded ${papers.length} papers`;
      } catch (err) {
        statusEl.textContent = `Load failed: ${err && err.message ? err.message : err}`;
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
      if (authStatusEl) authStatusEl.textContent = getAccessToken() ? 'Token saved' : 'Read-only';
      load();
    });

    root.querySelector('[data-action="clear-token"]').addEventListener('click', () => {
      setAccessToken('');
      if (tokenInput) tokenInput.value = '';
      if (authStatusEl) authStatusEl.textContent = 'Read-only';
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
          const next = button.textContent.indexOf('Unfavorite') < 0;
          await upsertUserState(cfg, paperId, { is_favorite: next });
          await load();
        } else if (action === 'read') {
          const next = button.textContent.indexOf('unread') < 0;
          await upsertUserState(cfg, paperId, { is_read: next });
          await load();
        } else if (action === 'save-note') {
          const note = card.querySelector('[data-role="note"]');
          await upsertUserState(cfg, paperId, { note: note ? note.value : '' });
          statusEl.textContent = 'Note saved';
        }
      } catch (err) {
        statusEl.textContent = `Save failed: ${err && err.message ? err.message : err}`;
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
      if (!nav || nav.querySelector('[data-essay-agent-workbench-link]')) return;
      const ul = nav.querySelector('ul') || nav;
      const li = document.createElement('li');
      li.innerHTML = '<a class="dpr-sidebar-root-link" data-essay-agent-workbench-link href="#/essay-agent-workbench">essay-agent Workbench</a>';
      ul.insertBefore(li, ul.children && ul.children.length > 1 ? ul.children[1] : null);
    } catch {
      // ignore
    }
  };

  document.addEventListener('DOMContentLoaded', installSidebarEntry);
  document.addEventListener('dpr-docsify-ready', installSidebarEntry);
  document.addEventListener('dpr-deferred-assets-ready', installSidebarEntry);

  return { render, installSidebarEntry };
})();
