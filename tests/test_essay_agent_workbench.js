const assert = require('node:assert/strict');

const storage = {};

global.window = {
  localStorage: {
    getItem(key) {
      return Object.prototype.hasOwnProperty.call(storage, key) ? storage[key] : null;
    },
    setItem(key, value) {
      storage[key] = String(value);
    },
    removeItem(key) {
      delete storage[key];
    },
  },
  DPR_RUNTIME_SOURCE_BACKENDS: {
    essay_agent: {
      url: 'https://example.supabase.co',
      anon_key: 'anon',
      schema: 'public',
      papers_table: 'essay_agent_papers',
      states_table: 'user_paper_states',
    },
  },
  ScholarLensI18n: {
    getLang() {
      return storage.lang || 'zh';
    },
    t(key, params) {
      const dict = {
        zh: {
          'workbench.emptyTitle': '没有匹配论文',
          'workbench.readOnlyHint': '配置 token 后可收藏、标记已读和保存笔记。',
          'workbench.sourceFallback': '来源',
          'workbench.relevance': '相关性',
          'workbench.favorite': '收藏',
          'workbench.markRead': '标记已读',
          'workbench.noteLabel': '个人笔记',
          'workbench.notePlaceholder': '配置 token 后可保存到 Supabase',
          'workbench.saveNote': '保存笔记',
          'workbench.details': '摘要 / 结构化分析',
          'workbench.original': '原文链接',
          'workbench.readInSite': '站内阅读',
        },
        en: {
          'workbench.emptyTitle': 'No matching papers',
          'workbench.readOnlyHint': 'Configure a token to favorite, mark read, and save notes.',
          'workbench.sourceFallback': 'Source',
          'workbench.relevance': 'Relevance',
          'workbench.favorite': 'Favorite',
          'workbench.markRead': 'Mark read',
          'workbench.noteLabel': 'Personal note',
          'workbench.notePlaceholder': 'Configure a token to save to Supabase',
          'workbench.saveNote': 'Save note',
          'workbench.details': 'Abstract / Structured Analysis',
          'workbench.original': 'Original',
          'workbench.readInSite': 'Read in site',
        },
      };
      const value = (dict[this.getLang()] && dict[this.getLang()][key]) || (dict.zh && dict.zh[key]) || key;
      if (!params) return value;
      return value.replace(/\{([A-Za-z0-9_]+)\}/g, (m, name) => (
        Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : m
      ));
    },
  },
};

global.document = {
  addEventListener() {},
  getElementById() {
    return null;
  },
};

require('../app/essay-agent-workbench.js');

const api = global.window.EssayAgentWorkbench.__test;

function testBuildPapersQuery() {
  const path = api.buildPapersQuery(
    {
      papersTable: 'essay_agent_papers',
    },
    {
      limit: 20,
      query: 'healing garden',
      source: 'openalex',
      minScore: '0.4',
      sort: 'published_desc',
    },
  );
  const query = path.split('?')[1];
  const params = new URLSearchParams(query);

  assert.equal(path.startsWith('essay_agent_papers?'), true);
  assert.equal(params.get('limit'), '20');
  assert.equal(params.get('source'), 'eq.openalex');
  assert.equal(params.get('domain_relevance_score'), 'gte.0.4');
  assert.match(params.get('or'), /healing garden/);
  assert.equal(params.get('order'), 'published.desc.nullslast,domain_relevance_score.desc');
}

function testPaginationAndReset() {
  const rows = Array.from({ length: 25 }, (_, index) => ({ id: String(index + 1) }));
  const page = api.paginateRows(rows, 20);
  assert.equal(page.items.length, 20);
  assert.equal(page.visible, 20);
  assert.equal(page.total, 25);
  assert.equal(page.hasMore, true);

  const state = api.createInitialState({ pageSize: 20 });
  state.query = 'healing';
  state.source = 'crossref';
  state.domain = 'healing garden';
  state.minScore = '0.5';
  state.sort = 'published_asc';
  state.visibleCount = 40;
  api.resetFilters(state);

  assert.equal(state.query, '');
  assert.equal(state.source, '');
  assert.equal(state.domain, '');
  assert.equal(state.minScore, '');
  assert.equal(state.sort, 'score_desc');
  assert.equal(state.visibleCount, 20);
}

function testReadOnlyCardAndEnglishCopy() {
  assert.equal(api.isReadOnly(''), true);
  assert.equal(api.isReadOnly('token'), false);

  const html = api.renderPaperCard(
    {
      id: 'p1',
      title: 'Healing Garden Study',
      abstract: 'abstract',
      source: 'openalex',
      domain_relevance_score: 0.82,
      domain_query: 'healing garden',
      analysis: {},
      link: 'https://example.test/p1',
    },
    {},
    { readOnly: true },
  );

  assert.match(html, /disabled aria-disabled="true"/);
  assert.match(html, /配置 token 后可收藏/);

  storage.lang = 'en';
  assert.equal(api.getCopy().emptyTitle, 'No matching papers');
}

function testFilteringAndMetrics() {
  const rows = [
    { id: '1', source: 'openalex', domain_query: 'healing garden', domain_relevance_score: 0.7, published: '2026-01-02' },
    { id: '2', source: 'crossref', domain_query: 'sports space', domain_relevance_score: 0.9, published: '2026-01-01' },
  ];
  const filtered = api.getFilteredSortedRows(rows, { domain: 'healing garden', sort: 'score_desc' });
  assert.deepEqual(filtered.map((row) => row.id), ['1']);

  const metrics = api.computeMetrics(rows);
  assert.equal(metrics.total, 2);
  assert.equal(metrics.sources, 2);
  assert.equal(metrics.domains, 2);
}

function testReaderIndexMappingAndCardLink() {
  storage.lang = 'zh';
  const index = api.normalizeReaderIndex({
    routes: {
      'doi:10.1000/demo': '202605/28/demo-paper',
    },
    papers: {
      'openalex:https://example.test/paper': {
        route: '202605/28/by-url',
      },
    },
  });
  assert.equal(api.getReaderRoute({ id: 'doi:10.1000/demo' }, index), '202605/28/demo-paper');
  assert.equal(
    api.getReaderRoute({ id: 'missing', source: 'openalex', link: 'https://example.test/paper' }, index),
    '202605/28/by-url',
  );

  const html = api.renderPaperCard(
    {
      id: 'p-reader',
      title: 'Reader Paper',
      abstract: 'abstract',
      source: 'openalex',
      domain_relevance_score: 88,
      analysis: {},
    },
    {},
    { readerRoute: '202605/28/demo-paper' },
  );
  assert.match(html, /href="#\/202605\/28\/demo-paper"/);
  assert.match(html, /站内阅读/);
}

testBuildPapersQuery();
testPaginationAndReset();
testReadOnlyCardAndEnglishCopy();
testFilteringAndMetrics();
testReaderIndexMappingAndCardLink();

console.log('essay agent workbench tests passed');
