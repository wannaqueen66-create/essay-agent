(function () {
  const STORAGE_KEY = 'scholarlens_language_v1';
  const VALID_LANGS = new Set(['zh', 'en']);

  const DICTIONARY = {
    zh: {
      'sidebar.home': 'ScholarLens 首页',
      'sidebar.workbench': 'ScholarLens 文献工作台',
      'sidebar.zotero': 'Zotero 使用说明',
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
      'workbench.errorTitle': '论文加载失败',
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
      'admin.title': '后台管理',
      'admin.daily': '日常管理',
      'admin.conference': '会议论文',
      'admin.save': '保存',
      'admin.secret': '密钥配置',
      'admin.close': '关闭',
      'admin.addProfile': '新增词条',
      'admin.quickRun': '快速抓取',
      'admin.conferenceRun': '会议论文检索',
      'admin.noProfilesDaily': '暂无词条。先点「新增」创建检索词条，再发起快速抓取。',
      'admin.noProfilesConference': '暂无词条。先点「新增」创建检索词条，再发起会议论文检索。',
      'admin.pendingYear': '{year} 论文暂未开放/暂未接入，暂不可选择。',
      'chat.quickRun': '快速抓取',
      'chat.placeholder': '针对这篇论文提问，仅自己可见...',
      'secret.config': '密钥配置',
      'secret.unlock': '解锁密钥',
      'secret.guest': '以游客身份访问',
    },
    en: {
      'sidebar.home': 'ScholarLens Home',
      'sidebar.workbench': 'ScholarLens Workbench',
      'sidebar.zotero': 'Zotero Guide',
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
      'workbench.errorTitle': 'Paper loading failed',
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
      'admin.title': 'Admin',
      'admin.daily': 'Daily',
      'admin.conference': 'Conferences',
      'admin.save': 'Save',
      'admin.secret': 'Token setup',
      'admin.close': 'Close',
      'admin.addProfile': 'Add profile',
      'admin.quickRun': 'Quick fetch',
      'admin.conferenceRun': 'Conference retrieval',
      'admin.noProfilesDaily': 'No profiles yet. Add a profile first, then start quick fetch.',
      'admin.noProfilesConference': 'No profiles yet. Add a profile first, then start conference retrieval.',
      'admin.pendingYear': '{year} papers are not open/integrated yet.',
      'chat.quickRun': 'Quick fetch',
      'chat.placeholder': 'Ask about this paper. Only visible on this device...',
      'secret.config': 'Token setup',
      'secret.unlock': 'Unlock secrets',
      'secret.guest': 'Continue as guest',
    },
  };

  const normalizeLang = (value) => (VALID_LANGS.has(value) ? value : 'zh');

  const formatTemplate = (template, params) => {
    if (!params || typeof params !== 'object') return template;
    return String(template).replace(/\{([A-Za-z0-9_]+)\}/g, (m, key) => (
      Object.prototype.hasOwnProperty.call(params, key) ? String(params[key]) : m
    ));
  };

  const getLang = () => {
    try {
      return normalizeLang(window.localStorage && window.localStorage.getItem(STORAGE_KEY));
    } catch {
      return 'zh';
    }
  };

  const t = (key, params) => {
    const lang = getLang();
    const text = (DICTIONARY[lang] && DICTIONARY[lang][key]) ||
      (DICTIONARY.zh && DICTIONARY.zh[key]) ||
      key;
    return formatTemplate(text, params);
  };

  const applyDocumentLang = (lang) => {
    if (!document || !document.documentElement) return;
    document.documentElement.setAttribute('data-scholar-lang', lang);
    document.documentElement.lang = lang === 'en' ? 'en' : 'zh-CN';
  };

  const translateDom = (root) => {
    const scope = root || document;
    if (!scope || typeof scope.querySelectorAll !== 'function') return;
    const applyText = (selector, attr, setter) => {
      scope.querySelectorAll(selector).forEach((el) => {
        const key = el.getAttribute(attr);
        if (!key) return;
        setter(el, t(key));
      });
    };
    applyText('[data-i18n]', 'data-i18n', (el, value) => {
      el.textContent = value;
    });
    applyText('[data-i18n-title]', 'data-i18n-title', (el, value) => {
      el.title = value;
    });
    applyText('[data-i18n-placeholder]', 'data-i18n-placeholder', (el, value) => {
      el.setAttribute('placeholder', value);
    });
    applyText('[data-i18n-aria-label]', 'data-i18n-aria-label', (el, value) => {
      el.setAttribute('aria-label', value);
    });
  };

  const setLang = (lang) => {
    const next = normalizeLang(lang);
    try {
      if (window.localStorage) {
        window.localStorage.setItem(STORAGE_KEY, next);
      }
    } catch {
      // ignore
    }
    applyDocumentLang(next);
    translateDom(document);
    try {
      document.dispatchEvent(new CustomEvent('scholarlens-language-change', {
        detail: { lang: next },
      }));
    } catch {
      // ignore
    }
    return next;
  };

  const applyLang = () => {
    const lang = getLang();
    applyDocumentLang(lang);
    translateDom(document);
    return lang;
  };

  const ensureToggle = () => {
    if (!document || !document.body || document.getElementById('scholarlens-language-toggle')) return;
    const button = document.createElement('button');
    button.id = 'scholarlens-language-toggle';
    button.type = 'button';
    button.className = 'scholarlens-language-toggle';
    const sync = () => {
      const lang = getLang();
      button.textContent = lang === 'zh' ? 'EN' : '中文';
      button.setAttribute(
        'aria-label',
        lang === 'zh' ? 'Switch to English' : '切换到中文',
      );
      button.title = lang === 'zh' ? 'Switch to English' : '切换到中文';
    };
    button.addEventListener('click', () => {
      setLang(getLang() === 'zh' ? 'en' : 'zh');
      sync();
    });
    document.addEventListener('scholarlens-language-change', sync);
    sync();
    document.body.appendChild(button);
  };

  window.ScholarLensI18n = {
    getLang,
    setLang,
    applyLang,
    ensureToggle,
    t,
    translateDom,
    dictionary: DICTIONARY,
  };

  applyLang();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ensureToggle);
  } else {
    ensureToggle();
  }
})();
