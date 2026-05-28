window.EssayAgentWorkbench = (function () {
  const ACCESS_TOKEN_KEY = 'essay_agent_supabase_access_token_v1';
  const DEFAULT_PAGE_SIZE = 20;
  const DEFAULT_FETCH_LIMIT = 200;
  const DEFAULT_SOURCES = ['arxiv', 'openalex', 'crossref', 'biorxiv', 'medrxiv', 'chemrxiv'];

  const FALLBACK_I18N = {
    zh: {
      capabilities: ['多源监测', '中文结构化分析', '领域筛选', '相关性排序', '个人阅读状态', '分页浏览'],
      skeleton: '加载论文卡片...',
    },
    en: {
      capabilities: ['Multi-source monitoring', 'Chinese analysis', 'Domain filters', 'Relevance sorting', 'Personal state', 'Pagination'],
      skeleton: 'Loading paper cards...',
    },
  };

  const escapeHtml = (value) => String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

  const normalizeText = (value) => String(value || '').trim();

  const helper = () => window.ScholarLensI18n || {};

  const currentLang = () => {
    const i18n = helper();
    return i18n && typeof i18n.getLang === 'function' ? i18n.getLang() : 'zh';
  };

  const tr = (key, params) => {
    const i18n = helper();
    if (i18n && typeof i18n.t === 'function') return i18n.t(key, params);
    const fallback = {
      zh: {
        'workbench.kicker': 'ScholarLens',
        'workbench.title': 'ScholarLens 文献工作台',
        'workbench.subtitle': '集中浏览 essay-agent 多源监测论文、中文结构化分析、领域相关性和个人阅读状态。',
        'workbench.searchPlaceholder': '搜索标题、摘要、DOI 或中文分析',
        'workbench.sourceAll': '全部来源',
        'workbench.domainAll': '全部领域',
        'workbench.minScore': '最低相关性',
        'workbench.sortScore': '相关性优先',
        'workbench.sortNewest': '最新优先',
        'workbench.sortOldest': '最早优先',
        'workbench.sortTitle': '标题 A-Z',
        'workbench.search': '筛选',
        'workbench.reset': '重置',
        'workbench.loadMore': '加载更多',
        'workbench.loading': '正在加载论文...',
        'workbench.ready': '准备就绪。',
        'workbench.emptyTitle': '没有匹配论文',
        'workbench.emptyDesc': '请降低最低相关性、清空关键词或切换来源后重试。',
        'workbench.total': '论文总数',
        'workbench.avgScore': '平均相关性',
        'workbench.sources': '来源数',
        'workbench.domains': '领域数',
        'workbench.loaded': '已显示 {visible} / {total} 篇论文',
        'workbench.tokenPlaceholder': 'Supabase access token，用于收藏、已读和笔记',
        'workbench.saveToken': '保存 token',
        'workbench.clearToken': '清除 token',
        'workbench.tokenSaved': 'Token 已保存，可同步个人状态。',
        'workbench.readOnly': '游客只读模式',
        'workbench.readOnlyHint': '配置 token 后可收藏、标记已读和保存笔记。',
        'workbench.sourceFallback': '来源',
        'workbench.relevance': '相关性',
        'workbench.topic': '主题',
        'workbench.method': '方法',
        'workbench.conclusion': '结论',
        'workbench.details': '摘要 / 结构化分析',
        'workbench.original': '原文链接',
        'workbench.favorite': '收藏',
        'workbench.unfavorite': '取消收藏',
        'workbench.markRead': '标记已读',
        'workbench.markUnread': '标记未读',
        'workbench.noteLabel': '个人笔记',
        'workbench.notePlaceholder': '配置 token 后可保存到 Supabase',
        'workbench.saveNote': '保存笔记',
        'workbench.noteSaved': '笔记已保存',
        'workbench.saveFailed': '保存失败：{message}',
        'sidebar.workbench': 'ScholarLens 文献工作台',
      },
      en: {
        'workbench.kicker': 'ScholarLens',
        'workbench.title': 'ScholarLens Paper Workbench',
        'workbench.subtitle': 'Browse essay-agent monitored papers, Chinese structured analysis, domain relevance, and personal reading state in one place.',
        'workbench.searchPlaceholder': 'Search title, abstract, DOI, or Chinese analysis',
        'workbench.sourceAll': 'All sources',
        'workbench.domainAll': 'All domains',
        'workbench.minScore': 'Minimum relevance',
        'workbench.sortScore': 'Relevance first',
        'workbench.sortNewest': 'Newest first',
        'workbench.sortOldest': 'Oldest first',
        'workbench.sortTitle': 'Title A-Z',
        'workbench.search': 'Filter',
        'workbench.reset': 'Reset',
        'workbench.loadMore': 'Load more',
        'workbench.loading': 'Loading papers...',
        'workbench.ready': 'Ready.',
        'workbench.emptyTitle': 'No matching papers',
        'workbench.emptyDesc': 'Lower the minimum relevance, clear the keyword, or switch source and try again.',
        'workbench.total': 'Papers',
        'workbench.avgScore': 'Avg relevance',
        'workbench.sources': 'Sources',
        'workbench.domains': 'Domains',
        'workbench.loaded': 'Showing {visible} / {total} papers',
        'workbench.tokenPlaceholder': 'Supabase access token for favorites, read state, and notes',
        'workbench.saveToken': 'Save token',
        'workbench.clearToken': 'Clear token',
        'workbench.tokenSaved': 'Token saved. Personal state sync is enabled.',
        'workbench.readOnly': 'Guest read-only mode',
        'workbench.readOnlyHint': 'Configure a token to favorite, mark read, and save notes.',
        'workbench.sourceFallback': 'Source',
        'workbench.relevance': 'Relevance',
        'workbench.topic': 'Topic',
        'workbench.method': 'Method',
        'workbench.conclusion': 'Conclusion',
        'workbench.details': 'Abstract / Structured Analysis',
        'workbench.original': 'Original',
        'workbench.favorite': 'Favorite',
        'workbench.unfavorite': 'Unfavorite',
        'workbench.markRead': 'Mark read',
        'workbench.markUnread': 'Mark unread',
        'workbench.noteLabel': 'Personal note',
        'workbench.notePlaceholder': 'Configure a token to save to Supabase',
        'workbench.saveNote': 'Save note',
        'workbench.noteSaved': 'Note saved',
        'workbench.saveFailed': 'Save failed: {message}',
        'sidebar.workbench': 'ScholarLens Workbench',
      },
    };
    const lang = currentLang();
    const value = (fallback[lang] && fallback[lang][key]) || (fallback.zh && fallback.zh[key]) || key;
    if (!params || typeof params !== 'object') return value;
    return String(value).replace(/\{([A-Za-z0-9_]+)\}/g, (m, name) => (
      Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : m
    ));
  };

  const getCopy = (lang) => ({
    capabilities: (FALLBACK_I18N[lang || currentLang()] || FALLBACK_I18N.zh).capabilities,
    skeleton: (FALLBACK_I18N[lang || currentLang()] || FALLBACK_I18N.zh).skeleton,
    emptyTitle: tr('workbench.emptyTitle'),
    readOnlyHint: tr('workbench.readOnlyHint'),
  });

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

  const isReadOnly = (token) => !normalizeText(token == null ? getAccessToken() : token);

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
    const sort = state.sort || 'score_desc';
    if (sort === 'published_desc') params.set('order', 'published.desc.nullslast,domain_relevance_score.desc');
    else if (sort === 'published_asc') params.set('order', 'published.asc.nullslast,domain_relevance_score.desc');
    else if (sort === 'title_asc') params.set('order', 'title.asc.nullslast');
    else params.set('order', 'domain_relevance_score.desc,published.desc.nullslast');
    params.set('limit', String(state.limit || DEFAULT_FETCH_LIMIT));
    if (state.source) params.set('source', `eq.${state.source}`);
    if (state.query) {
      const q = state.query.replace(/[%*,()]/g, ' ').replace(/\s+/g, ' ').trim();
      if (q) {
        params.set('or', `(title.ilike.*${q}*,abstract.ilike.*${q}*,chinese_summary.ilike.*${q}*,doi.ilike.*${q}*,domain_query.ilike.*${q}*)`);
      }
    }
    if (state.minScore) params.set('domain_relevance_score', `gte.${Number(state.minScore) || 0}`);
    return `${cfg.papersTable}?${params.toString()}`;
  };

  const getPaperDomain = (paper) => normalizeText(
    paper && (
      paper.domain_query ||
      (paper.analysis && typeof paper.analysis === 'object' && (
        paper.analysis['研究主题'] ||
        paper.analysis.topic ||
        paper.analysis.domain
      ))
    ),
  );

  const uniqueSorted = (values) => Array.from(new Set(
    (Array.isArray(values) ? values : [])
      .map((item) => normalizeText(item))
      .filter(Boolean),
  )).sort((a, b) => a.localeCompare(b));

  const getSourceOptions = (papers) => uniqueSorted([
    ...DEFAULT_SOURCES,
    ...(Array.isArray(papers) ? papers.map((paper) => paper && paper.source) : []),
  ]);

  const getDomainOptions = (papers) => uniqueSorted(
    (Array.isArray(papers) ? papers : []).map(getPaperDomain),
  );

  const sortPapers = (papers, sort) => {
    const list = [...(Array.isArray(papers) ? papers : [])];
    if (sort === 'published_desc') {
      return list.sort((a, b) => String(b.published || '').localeCompare(String(a.published || '')));
    }
    if (sort === 'published_asc') {
      return list.sort((a, b) => String(a.published || '').localeCompare(String(b.published || '')));
    }
    if (sort === 'title_asc') {
      return list.sort((a, b) => String(a.title || '').localeCompare(String(b.title || '')));
    }
    return list.sort((a, b) => {
      const scoreDelta = Number(b.domain_relevance_score || 0) - Number(a.domain_relevance_score || 0);
      if (scoreDelta) return scoreDelta;
      return String(b.published || '').localeCompare(String(a.published || ''));
    });
  };

  const getFilteredSortedRows = (rows, state) => {
    const selectedDomain = normalizeText(state.domain || '');
    const filtered = selectedDomain
      ? (Array.isArray(rows) ? rows : []).filter((paper) => getPaperDomain(paper) === selectedDomain)
      : (Array.isArray(rows) ? rows : []);
    return sortPapers(filtered, state.sort || 'score_desc');
  };

  const paginateRows = (rows, visibleCount) => {
    const list = Array.isArray(rows) ? rows : [];
    const count = Math.max(Number(visibleCount) || DEFAULT_PAGE_SIZE, 0);
    return {
      items: list.slice(0, count),
      visible: Math.min(count, list.length),
      total: list.length,
      hasMore: list.length > count,
    };
  };

  const computeMetrics = (papers) => {
    const list = Array.isArray(papers) ? papers : [];
    const scores = list
      .map((paper) => Number(paper && paper.domain_relevance_score))
      .filter((score) => Number.isFinite(score));
    const avg = scores.length
      ? scores.reduce((sum, score) => sum + score, 0) / scores.length
      : 0;
    return {
      total: list.length,
      avgScore: avg ? avg.toFixed(avg >= 10 ? 1 : 2) : '0',
      sources: uniqueSorted(list.map((paper) => paper && paper.source)).length,
      domains: getDomainOptions(list).length,
    };
  };

  const createInitialState = (options = {}) => ({
    pageSize: Math.max(Number(options.pageSize) || DEFAULT_PAGE_SIZE, 1),
    visibleCount: Math.max(Number(options.pageSize) || DEFAULT_PAGE_SIZE, 1),
    limit: Math.max(Number(options.limit) || DEFAULT_FETCH_LIMIT, DEFAULT_PAGE_SIZE),
    query: normalizeText(options.query || ''),
    source: normalizeText(options.source || ''),
    domain: normalizeText(options.domain || ''),
    minScore: normalizeText(options.minScore || ''),
    sort: normalizeText(options.sort || 'score_desc') || 'score_desc',
    rows: [],
    userStates: {},
    loading: false,
    error: '',
  });

  const resetFilters = (state) => {
    state.query = '';
    state.source = '';
    state.domain = '';
    state.minScore = '';
    state.sort = 'score_desc';
    state.visibleCount = state.pageSize || DEFAULT_PAGE_SIZE;
    return state;
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
    if (!token) throw new Error(tr('workbench.readOnlyHint'));
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

  const getAnalysis = (paper) => (
    paper && paper.analysis && typeof paper.analysis === 'object' ? paper.analysis : {}
  );

  const renderSkeleton = () => {
    const copy = getCopy();
    return Array.from({ length: 6 }).map(() => `
      <article class="essay-agent-card essay-agent-skeleton" aria-busy="true">
        <div class="essay-agent-skeleton-line essay-agent-skeleton-line--short"></div>
        <div class="essay-agent-skeleton-line essay-agent-skeleton-line--title"></div>
        <div class="essay-agent-skeleton-line"></div>
        <div class="essay-agent-skeleton-line"></div>
        <span class="sr-only">${escapeHtml(copy.skeleton)}</span>
      </article>
    `).join('');
  };

  const renderMetricCards = (metrics) => `
    <div class="essay-agent-metrics" data-role="metrics">
      <div class="essay-agent-metric"><span>${escapeHtml(tr('workbench.total'))}</span><strong>${metrics.total}</strong></div>
      <div class="essay-agent-metric"><span>${escapeHtml(tr('workbench.avgScore'))}</span><strong>${escapeHtml(metrics.avgScore)}</strong></div>
      <div class="essay-agent-metric"><span>${escapeHtml(tr('workbench.sources'))}</span><strong>${metrics.sources}</strong></div>
      <div class="essay-agent-metric"><span>${escapeHtml(tr('workbench.domains'))}</span><strong>${metrics.domains}</strong></div>
    </div>
  `;

  const renderDomainChips = (domains, selected) => {
    const allActive = !selected;
    const rows = [
      `<button type="button" class="essay-agent-domain-chip${allActive ? ' is-active' : ''}" data-domain-value="" aria-pressed="${allActive ? 'true' : 'false'}">${escapeHtml(tr('workbench.domainAll'))}</button>`,
      ...domains.map((domain) => {
        const active = domain === selected;
        return `<button type="button" class="essay-agent-domain-chip${active ? ' is-active' : ''}" data-domain-value="${escapeHtml(domain)}" aria-pressed="${active ? 'true' : 'false'}">${escapeHtml(domain)}</button>`;
      }),
    ];
    return `<div class="essay-agent-domain-chips" data-role="domain-chips">${rows.join('')}</div>`;
  };

  const renderSourceOptions = (sources, selected) => [
    `<option value="">${escapeHtml(tr('workbench.sourceAll'))}</option>`,
    ...sources.map((source) => `<option value="${escapeHtml(source)}"${source === selected ? ' selected' : ''}>${escapeHtml(source)}</option>`),
  ].join('');

  const renderPaperCard = (paper, userState = {}, options = {}) => {
    const analysis = getAnalysis(paper);
    const score = Number(paper.domain_relevance_score || 0);
    const note = userState && userState.note ? userState.note : '';
    const favoriteLabel = userState && userState.is_favorite ? tr('workbench.unfavorite') : tr('workbench.favorite');
    const readLabel = userState && userState.is_read ? tr('workbench.markUnread') : tr('workbench.markRead');
    const readOnly = !!options.readOnly;
    const disabledAttrs = readOnly
      ? `disabled aria-disabled="true" title="${escapeHtml(tr('workbench.readOnlyHint'))}"`
      : '';
    const notePlaceholder = readOnly ? tr('workbench.readOnlyHint') : tr('workbench.notePlaceholder');
    const source = paper.source || tr('workbench.sourceFallback');
    const domain = getPaperDomain(paper);
    const link = normalizeText(paper.link || '');
    return `
      <article class="essay-agent-card${readOnly ? ' is-readonly' : ''}" data-paper-id="${escapeHtml(paper.id)}">
        <div class="essay-agent-card-topline">
          <span>${escapeHtml(source)}</span>
          ${paper.published ? `<span>${escapeHtml(String(paper.published).slice(0, 10))}</span>` : ''}
          <span class="essay-agent-score">${escapeHtml(tr('workbench.relevance'))} ${escapeHtml(score.toFixed(score >= 10 ? 1 : 2))}</span>
          ${domain ? `<span>${escapeHtml(domain)}</span>` : ''}
        </div>
        <h2>${escapeHtml(paper.title || paper.id || '')}</h2>
        <p class="essay-agent-summary">${escapeHtml(paper.chinese_summary || analysis['中文摘要'] || paper.abstract || '')}</p>
        <div class="essay-agent-fields">
          ${analysis['研究主题'] ? `<span>${escapeHtml(tr('workbench.topic'))}: ${escapeHtml(analysis['研究主题'])}</span>` : ''}
          ${analysis['研究方法'] ? `<span>${escapeHtml(tr('workbench.method'))}: ${escapeHtml(analysis['研究方法'])}</span>` : ''}
          ${analysis['主要结论'] ? `<span>${escapeHtml(tr('workbench.conclusion'))}: ${escapeHtml(analysis['主要结论'])}</span>` : ''}
        </div>
        <details>
          <summary>${escapeHtml(tr('workbench.details'))}</summary>
          <p>${escapeHtml(paper.abstract || '')}</p>
          <pre>${escapeHtml(JSON.stringify(analysis, null, 2))}</pre>
        </details>
        <div class="essay-agent-card-actions">
          ${link ? `<a href="${escapeHtml(link)}" target="_blank" rel="noopener">${escapeHtml(tr('workbench.original'))}</a>` : ''}
          <button type="button" data-action="favorite" data-next="${userState && userState.is_favorite ? '0' : '1'}" ${disabledAttrs}>${escapeHtml(favoriteLabel)}</button>
          <button type="button" data-action="read" data-next="${userState && userState.is_read ? '0' : '1'}" ${disabledAttrs}>${escapeHtml(readLabel)}</button>
        </div>
        <label class="essay-agent-note-label">
          ${escapeHtml(tr('workbench.noteLabel'))}
          <textarea data-role="note" placeholder="${escapeHtml(notePlaceholder)}" ${readOnly ? 'disabled aria-disabled="true"' : ''}>${escapeHtml(note)}</textarea>
        </label>
        <button type="button" data-action="save-note" ${disabledAttrs}>${escapeHtml(tr('workbench.saveNote'))}</button>
      </article>
    `;
  };

  const renderShell = (root, state) => {
    const copy = getCopy();
    root.innerHTML = `
      <section class="essay-agent-workbench">
        <header class="essay-agent-hero">
          <p class="essay-agent-kicker">${escapeHtml(tr('workbench.kicker'))}</p>
          <h1>${escapeHtml(tr('workbench.title'))}</h1>
          <p>${escapeHtml(tr('workbench.subtitle'))}</p>
          <div class="essay-agent-capability-strip">
            ${copy.capabilities.map((item) => `<span>${escapeHtml(item)}</span>`).join('')}
          </div>
        </header>
        <div data-role="metrics">${renderMetricCards(computeMetrics([]))}</div>
        <div class="essay-agent-filter-panel">
          <div class="essay-agent-toolbar">
            <input data-role="query" value="${escapeHtml(state.query)}" placeholder="${escapeHtml(tr('workbench.searchPlaceholder'))}" />
            <select data-role="source">${renderSourceOptions(DEFAULT_SOURCES, state.source)}</select>
            <input data-role="min-score" type="number" min="0" max="100" step="0.01" value="${escapeHtml(state.minScore)}" placeholder="${escapeHtml(tr('workbench.minScore'))}" />
            <select data-role="sort">
              <option value="score_desc"${state.sort === 'score_desc' ? ' selected' : ''}>${escapeHtml(tr('workbench.sortScore'))}</option>
              <option value="published_desc"${state.sort === 'published_desc' ? ' selected' : ''}>${escapeHtml(tr('workbench.sortNewest'))}</option>
              <option value="published_asc"${state.sort === 'published_asc' ? ' selected' : ''}>${escapeHtml(tr('workbench.sortOldest'))}</option>
              <option value="title_asc"${state.sort === 'title_asc' ? ' selected' : ''}>${escapeHtml(tr('workbench.sortTitle'))}</option>
            </select>
            <button type="button" data-action="search">${escapeHtml(tr('workbench.search'))}</button>
            <button type="button" data-action="reset" class="essay-agent-secondary-btn">${escapeHtml(tr('workbench.reset'))}</button>
          </div>
          <div data-role="domain-chips">${renderDomainChips([], state.domain)}</div>
        </div>
        <div class="essay-agent-auth">
          <input data-role="access-token" type="password" value="${escapeHtml(getAccessToken())}" placeholder="${escapeHtml(tr('workbench.tokenPlaceholder'))}" />
          <button type="button" data-action="save-token">${escapeHtml(tr('workbench.saveToken'))}</button>
          <button type="button" data-action="clear-token" class="essay-agent-secondary-btn">${escapeHtml(tr('workbench.clearToken'))}</button>
          <span data-role="auth-status" class="${isReadOnly() ? 'essay-agent-readonly-hint' : ''}">${escapeHtml(isReadOnly() ? tr('workbench.readOnlyHint') : tr('workbench.tokenSaved'))}</span>
        </div>
        <div class="essay-agent-status" data-role="status">${escapeHtml(tr('workbench.ready'))}</div>
        <div class="essay-agent-grid" data-role="list">${renderSkeleton()}</div>
        <div class="essay-agent-load-more-wrap">
          <button type="button" class="essay-agent-load-more" data-action="load-more" hidden>${escapeHtml(tr('workbench.loadMore'))}</button>
        </div>
      </section>
    `;
  };

  const readControlsIntoState = (root, state) => {
    const queryEl = root.querySelector('[data-role="query"]');
    const sourceEl = root.querySelector('[data-role="source"]');
    const minScoreEl = root.querySelector('[data-role="min-score"]');
    const sortEl = root.querySelector('[data-role="sort"]');
    state.query = normalizeText(queryEl && queryEl.value);
    state.source = normalizeText(sourceEl && sourceEl.value);
    state.minScore = normalizeText(minScoreEl && minScoreEl.value);
    state.sort = normalizeText(sortEl && sortEl.value) || 'score_desc';
    state.visibleCount = state.pageSize || DEFAULT_PAGE_SIZE;
  };

  const syncControlValues = (root, state) => {
    const queryEl = root.querySelector('[data-role="query"]');
    const sourceEl = root.querySelector('[data-role="source"]');
    const minScoreEl = root.querySelector('[data-role="min-score"]');
    const sortEl = root.querySelector('[data-role="sort"]');
    if (queryEl) queryEl.value = state.query;
    if (sourceEl) sourceEl.value = state.source;
    if (minScoreEl) minScoreEl.value = state.minScore;
    if (sortEl) sortEl.value = state.sort;
  };

  const paintState = (root, state) => {
    const listEl = root.querySelector('[data-role="list"]');
    const statusEl = root.querySelector('[data-role="status"]');
    const metricsEl = root.querySelector('[data-role="metrics"]');
    const domainEl = root.querySelector('[data-role="domain-chips"]');
    const sourceEl = root.querySelector('[data-role="source"]');
    const authStatusEl = root.querySelector('[data-role="auth-status"]');
    const loadMoreBtn = root.querySelector('[data-action="load-more"]');
    const rows = getFilteredSortedRows(state.rows, state);
    const page = paginateRows(rows, state.visibleCount);
    const readOnly = isReadOnly();

    if (metricsEl) metricsEl.innerHTML = renderMetricCards(computeMetrics(rows));
    if (domainEl) domainEl.innerHTML = renderDomainChips(getDomainOptions(state.rows), state.domain);
    if (sourceEl) sourceEl.innerHTML = renderSourceOptions(getSourceOptions(state.rows), state.source);
    syncControlValues(root, state);
    if (authStatusEl) {
      authStatusEl.textContent = readOnly ? tr('workbench.readOnlyHint') : tr('workbench.tokenSaved');
      authStatusEl.classList.toggle('essay-agent-readonly-hint', readOnly);
    }
    if (state.loading) {
      if (statusEl) statusEl.textContent = tr('workbench.loading');
      if (listEl) listEl.innerHTML = renderSkeleton();
      if (loadMoreBtn) loadMoreBtn.hidden = true;
      return;
    }
    if (state.error) {
      if (statusEl) statusEl.textContent = state.error;
      if (listEl) {
        listEl.innerHTML = `
          <div class="essay-agent-empty essay-agent-empty--error">
            <h2>${escapeHtml(tr('workbench.errorTitle'))}</h2>
            <p>${escapeHtml(state.error)}</p>
          </div>
        `;
      }
      if (loadMoreBtn) loadMoreBtn.hidden = true;
      return;
    }
    if (!rows.length) {
      if (statusEl) statusEl.textContent = tr('workbench.loaded', { visible: 0, total: 0 });
      if (listEl) {
        listEl.innerHTML = `
          <div class="essay-agent-empty">
            <h2>${escapeHtml(tr('workbench.emptyTitle'))}</h2>
            <p>${escapeHtml(tr('workbench.emptyDesc'))}</p>
          </div>
        `;
      }
      if (loadMoreBtn) loadMoreBtn.hidden = true;
      return;
    }
    if (listEl) {
      listEl.innerHTML = page.items
        .map((paper) => renderPaperCard(paper, state.userStates[paper.id], { readOnly }))
        .join('');
    }
    if (statusEl) {
      statusEl.textContent = tr('workbench.loaded', {
        visible: page.visible,
        total: page.total,
      });
    }
    if (loadMoreBtn) loadMoreBtn.hidden = !page.hasMore;
  };

  const loadPapers = async (root, state) => {
    const cfg = getConfig();
    state.loading = true;
    state.error = '';
    paintState(root, state);
    try {
      const rows = await requestJson(cfg, buildPapersQuery(cfg, state));
      state.rows = Array.isArray(rows) ? rows : [];
      state.userStates = await loadUserStates(cfg, state.rows.map((paper) => paper.id).filter(Boolean));
      state.error = '';
    } catch (err) {
      state.rows = [];
      state.userStates = {};
      state.error = err && err.message ? err.message : String(err);
    } finally {
      state.loading = false;
      paintState(root, state);
    }
  };

  const bindActions = (root, state) => {
    root.__essayAgentWorkbenchState = state;
    if (root.dataset.essayAgentWorkbenchBound === '1') return;
    root.dataset.essayAgentWorkbenchBound = '1';
    const cfg = getConfig();
    root.addEventListener('click', async (event) => {
      const state = root.__essayAgentWorkbenchState;
      const button = event.target && event.target.closest ? event.target.closest('button[data-action]') : null;
      if (!button) return;
      const action = button.getAttribute('data-action') || '';
      if (action === 'search') {
        readControlsIntoState(root, state);
        await loadPapers(root, state);
        return;
      }
      if (action === 'reset') {
        resetFilters(state);
        syncControlValues(root, state);
        await loadPapers(root, state);
        return;
      }
      if (action === 'load-more') {
        state.visibleCount += state.pageSize || DEFAULT_PAGE_SIZE;
        paintState(root, state);
        return;
      }
      if (action === 'save-token') {
        const input = root.querySelector('[data-role="access-token"]');
        setAccessToken(input ? input.value : '');
        await loadPapers(root, state);
        return;
      }
      if (action === 'clear-token') {
        const input = root.querySelector('[data-role="access-token"]');
        setAccessToken('');
        if (input) input.value = '';
        state.userStates = {};
        paintState(root, state);
        return;
      }

      const card = button.closest('.essay-agent-card');
      if (!card || button.disabled || isReadOnly()) return;
      const paperId = card.getAttribute('data-paper-id') || '';
      const statusEl = root.querySelector('[data-role="status"]');
      try {
        if (action === 'favorite') {
          await upsertUserState(cfg, paperId, { is_favorite: button.getAttribute('data-next') === '1' });
          await loadPapers(root, state);
        } else if (action === 'read') {
          await upsertUserState(cfg, paperId, { is_read: button.getAttribute('data-next') === '1' });
          await loadPapers(root, state);
        } else if (action === 'save-note') {
          const note = card.querySelector('[data-role="note"]');
          await upsertUserState(cfg, paperId, { note: note ? note.value : '' });
          if (statusEl) statusEl.textContent = tr('workbench.noteSaved');
        }
      } catch (err) {
        if (statusEl) {
          statusEl.textContent = tr('workbench.saveFailed', {
            message: err && err.message ? err.message : String(err),
          });
        }
      }
    });
    root.addEventListener('click', (event) => {
      const state = root.__essayAgentWorkbenchState;
      const chip = event.target && event.target.closest
        ? event.target.closest('.essay-agent-domain-chip')
        : null;
      if (!chip) return;
      state.domain = normalizeText(chip.getAttribute('data-domain-value') || '');
      state.visibleCount = state.pageSize || DEFAULT_PAGE_SIZE;
      paintState(root, state);
    });
    root.addEventListener('keydown', (event) => {
      const state = root.__essayAgentWorkbenchState;
      if (event.key !== 'Enter') return;
      const target = event.target;
      if (!target || !target.matches || !target.matches('[data-role="query"], [data-role="min-score"]')) return;
      readControlsIntoState(root, state);
      loadPapers(root, state);
    });
  };

  const render = (root, options = {}) => {
    if (!root) return;
    const state = createInitialState(options);
    root.__essayAgentWorkbenchState = state;
    renderShell(root, state);
    bindActions(root, state);
    loadPapers(root, state);
  };

  const installSidebarEntry = () => {
    try {
      const nav = document.querySelector('.sidebar-nav');
      if (!nav) return;
      let link = nav.querySelector('[data-essay-agent-workbench-link]');
      if (!link) {
        link = Array.from(nav.querySelectorAll('a')).find((item) => {
          const href = item.getAttribute('href') || item.getAttribute('data-dpr-hash') || '';
          return String(href).includes('#/essay-agent-workbench');
        });
      }
      if (!link) {
        const ul = nav.querySelector('ul') || nav;
        const li = document.createElement('li');
        li.innerHTML = '<a class="dpr-sidebar-root-link dpr-sidebar-noactive-link" data-essay-agent-workbench-link href="#/essay-agent-workbench"></a>';
        ul.insertBefore(li, ul.children && ul.children.length > 1 ? ul.children[1] : null);
        link = li.querySelector('[data-essay-agent-workbench-link]');
      }
      if (link) {
        link.setAttribute('data-essay-agent-workbench-link', '1');
        link.classList.add('dpr-sidebar-root-link', 'dpr-sidebar-noactive-link');
        link.textContent = tr('sidebar.workbench');
      }
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

  return {
    render,
    installSidebarEntry,
    __test: {
      ACCESS_TOKEN_KEY,
      DEFAULT_PAGE_SIZE,
      buildPapersQuery,
      createInitialState,
      resetFilters,
      paginateRows,
      getFilteredSortedRows,
      computeMetrics,
      isReadOnly,
      getCopy,
      renderPaperCard,
      getSourceOptions,
      getDomainOptions,
    },
  };
})();
