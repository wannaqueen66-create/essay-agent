const assert = require('node:assert/strict');

const listeners = {};
const attrs = {};
const storage = {};

function createEl(attrMap = {}) {
  return {
    textContent: '',
    title: '',
    attrs: { ...attrMap },
    getAttribute(name) {
      return this.attrs[name] || '';
    },
    setAttribute(name, value) {
      this.attrs[name] = String(value);
    },
  };
}

global.CustomEvent = function CustomEvent(type, init = {}) {
  this.type = type;
  this.detail = init.detail;
};

global.window = {
  localStorage: {
    getItem(key) {
      return Object.prototype.hasOwnProperty.call(storage, key) ? storage[key] : null;
    },
    setItem(key, value) {
      storage[key] = String(value);
    },
  },
};

global.document = {
  readyState: 'loading',
  documentElement: {
    lang: '',
    setAttribute(name, value) {
      attrs[name] = String(value);
    },
  },
  addEventListener(type, handler) {
    listeners[type] = handler;
  },
  dispatchEvent(event) {
    if (listeners[event.type]) listeners[event.type](event);
  },
  querySelectorAll() {
    return [];
  },
};

require('../app/scholarlens-i18n.js');

const api = global.window.ScholarLensI18n;

function testLanguageSwitchAndFallback() {
  assert.equal(api.getLang(), 'zh');
  assert.equal(api.t('missing.key'), 'missing.key');

  let changedTo = '';
  global.document.addEventListener('scholarlens-language-change', (event) => {
    changedTo = event.detail.lang;
  });

  assert.equal(api.setLang('en'), 'en');
  assert.equal(api.getLang(), 'en');
  assert.equal(changedTo, 'en');
  assert.equal(attrs['data-scholar-lang'], 'en');
  assert.equal(global.document.documentElement.lang, 'en');
  assert.equal(api.t('workbench.search'), 'Filter');
}

function testTranslateDom() {
  const textEl = createEl({ 'data-i18n': 'admin.title' });
  const titleEl = createEl({ 'data-i18n-title': 'admin.quickRun' });
  const placeholderEl = createEl({ 'data-i18n-placeholder': 'workbench.searchPlaceholder' });
  const ariaEl = createEl({ 'data-i18n-aria-label': 'admin.secret' });
  const root = {
    querySelectorAll(selector) {
      return {
        '[data-i18n]': [textEl],
        '[data-i18n-title]': [titleEl],
        '[data-i18n-placeholder]': [placeholderEl],
        '[data-i18n-aria-label]': [ariaEl],
      }[selector] || [];
    },
  };

  api.translateDom(root);

  assert.equal(textEl.textContent, 'Admin');
  assert.equal(titleEl.title, 'Quick fetch');
  assert.equal(placeholderEl.attrs.placeholder, 'Search title, abstract, DOI, or Chinese analysis');
  assert.equal(ariaEl.attrs['aria-label'], 'Token setup');
}

testLanguageSwitchAndFallback();
testTranslateDom();

console.log('scholarlens i18n tests passed');
