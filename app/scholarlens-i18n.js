(function () {
  const STORAGE_KEY = 'scholarlens_language_v1';
  const VALID_LANGS = new Set(['zh', 'en']);

  const normalizeLang = (value) => (VALID_LANGS.has(value) ? value : 'zh');

  const getLang = () => {
    try {
      return normalizeLang(window.localStorage && window.localStorage.getItem(STORAGE_KEY));
    } catch {
      return 'zh';
    }
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
    document.documentElement.setAttribute('data-scholar-lang', next);
    document.documentElement.lang = next === 'en' ? 'en' : 'zh-CN';
    document.dispatchEvent(new CustomEvent('scholarlens-language-change', {
      detail: { lang: next },
    }));
    return next;
  };

  const applyLang = () => {
    const lang = getLang();
    document.documentElement.setAttribute('data-scholar-lang', lang);
    document.documentElement.lang = lang === 'en' ? 'en' : 'zh-CN';
    return lang;
  };

  const ensureToggle = () => {
    if (document.getElementById('scholarlens-language-toggle')) return;
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
  };

  applyLang();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ensureToggle);
  } else {
    ensureToggle();
  }
})();
