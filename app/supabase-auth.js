(function (root, factory) {
  const api = factory(root || {});
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  }
  if (root) {
    root.ScholarLensAuth = api;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function (root) {
  const SESSION_KEY = 'scholarlens_supabase_session_v1';
  const DEFAULT_SHARED_LLM_FUNCTION = 'scholarlens-llm';
  const DEFAULT_SHARED_MODELS = ['deepseek-v4-flash', 'deepseek-v4-pro'];

  const normalizeText = (value) => String(value || '').trim();
  const normalizeEmail = (value) => normalizeText(value).toLowerCase();

  const getBackend = () => {
    const backends = root.DPR_RUNTIME_SOURCE_BACKENDS || {};
    return backends.essay_agent || backends.supabase || {};
  };

  const getConfig = () => {
    const backend = getBackend();
    const shared = backend.shared_llm || root.DPR_SHARED_LLM || {};
    const url = normalizeText(backend.url || root.SUPABASE_URL || '');
    const anonKey = normalizeText(backend.anon_key || backend.anonKey || root.SUPABASE_ANON_KEY || '');
    const functionName = normalizeText(shared.function_name || shared.functionName || DEFAULT_SHARED_LLM_FUNCTION);
    const proxyUrl = normalizeText(shared.proxy_url || shared.proxyUrl || (
      url && functionName ? `${url.replace(/\/+$/, '')}/functions/v1/${functionName}` : ''
    ));
    const rawModels = Array.isArray(shared.models) && shared.models.length
      ? shared.models
      : DEFAULT_SHARED_MODELS;
    const models = rawModels.map((item) => normalizeText(item)).filter(Boolean);
    return {
      url,
      anonKey,
      authEnabled: backend.auth_enabled !== false && backend.authEnabled !== false,
      sharedLlmEnabled: shared.enabled !== false,
      proxyUrl,
      models,
    };
  };

  const nowSeconds = () => Math.floor(Date.now() / 1000);

  const saveSession = (session) => {
    try {
      if (!root.localStorage) return;
      if (!session || !session.access_token) {
        root.localStorage.removeItem(SESSION_KEY);
        return;
      }
      const payload = {
        access_token: session.access_token,
        refresh_token: session.refresh_token || '',
        token_type: session.token_type || 'bearer',
        expires_at: Number(session.expires_at || 0) || (
          session.expires_in ? nowSeconds() + Number(session.expires_in) : 0
        ),
        user: session.user || null,
        saved_at: new Date().toISOString(),
      };
      root.localStorage.setItem(SESSION_KEY, JSON.stringify(payload));
    } catch {
      // ignore
    }
  };

  const loadSession = () => {
    try {
      if (!root.localStorage) return null;
      const raw = root.localStorage.getItem(SESSION_KEY);
      if (!raw) return null;
      const session = JSON.parse(raw);
      return session && session.access_token ? session : null;
    } catch {
      return null;
    }
  };

  const clearSession = () => saveSession(null);

  const getAccessToken = () => {
    const session = loadSession();
    return normalizeText(session && session.access_token);
  };

  const getUserEmail = () => {
    const session = loadSession();
    const user = session && session.user && typeof session.user === 'object' ? session.user : {};
    return normalizeEmail(user.email || '');
  };

  const authHeaders = (extra = {}) => {
    const cfg = getConfig();
    return {
      apikey: cfg.anonKey,
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...extra,
    };
  };

  const requestAuth = async (path, body, options = {}) => {
    const cfg = getConfig();
    if (!cfg.url || !cfg.anonKey) {
      throw new Error('Supabase URL / anon key is missing.');
    }
    const endpoint = `${cfg.url.replace(/\/+$/, '')}${path}`;
    const headers = authHeaders(options.headers || {});
    const res = await fetch(endpoint, {
      method: options.method || 'POST',
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    const text = await res.text();
    const data = text ? JSON.parse(text) : null;
    if (!res.ok) {
      const message = data && (data.msg || data.message || data.error_description || data.error)
        ? data.msg || data.message || data.error_description || data.error
        : `HTTP ${res.status}`;
      throw new Error(message);
    }
    return data;
  };

  const signInWithPassword = async (email, password) => {
    const data = await requestAuth('/auth/v1/token?grant_type=password', {
      email: normalizeEmail(email),
      password: normalizeText(password),
    });
    saveSession(data);
    return data;
  };

  const sendOtp = async (email) => {
    await requestAuth('/auth/v1/otp', {
      email: normalizeEmail(email),
      create_user: true,
    });
    return true;
  };

  const verifyOtp = async (email, token) => {
    const data = await requestAuth('/auth/v1/verify', {
      email: normalizeEmail(email),
      token: normalizeText(token),
      type: 'email',
    });
    saveSession(data);
    return data;
  };

  const signOut = async () => {
    const token = getAccessToken();
    if (token) {
      try {
        await requestAuth('/auth/v1/logout', null, {
          headers: { Authorization: `Bearer ${token}` },
        });
      } catch {
        // Local sign-out should still happen if the remote token is already invalid.
      }
    }
    clearSession();
  };

  const consumeUrlSession = () => {
    try {
      const loc = root.location;
      if (!loc) return null;
      const hash = new URLSearchParams(String(loc.hash || '').replace(/^#/, ''));
      const search = new URLSearchParams(String(loc.search || '').replace(/^\?/, ''));
      const params = hash.get('access_token') ? hash : search;
      const accessToken = params.get('access_token');
      if (!accessToken) return null;
      const session = {
        access_token: accessToken,
        refresh_token: params.get('refresh_token') || '',
        token_type: params.get('token_type') || 'bearer',
        expires_in: Number(params.get('expires_in') || 0) || 0,
        user: null,
      };
      saveSession(session);
      if (root.history && typeof root.history.replaceState === 'function') {
        root.history.replaceState(null, '', loc.pathname || '/');
      }
      return session;
    } catch {
      return null;
    }
  };

  const isSignedIn = () => !!getAccessToken();

  const buildSharedModelEntries = () => {
    const cfg = getConfig();
    if (!cfg.sharedLlmEnabled || !cfg.proxyUrl || !getAccessToken()) return [];
    return cfg.models.map((name) => ({
      name,
      apiKey: '',
      baseUrl: cfg.proxyUrl,
      provider: 'shared',
      shared: true,
    }));
  };

  const getSharedSummaryLLM = () => {
    const entries = buildSharedModelEntries();
    if (!entries.length) return null;
    return entries[0];
  };

  const buildSharedFetchHeaders = () => {
    const token = getAccessToken();
    if (!token) {
      throw new Error('请先使用邮箱登录 ScholarLens。');
    }
    return {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      Authorization: `Bearer ${token}`,
    };
  };

  consumeUrlSession();

  return {
    getConfig,
    loadSession,
    saveSession,
    clearSession,
    getAccessToken,
    getUserEmail,
    isSignedIn,
    signInWithPassword,
    sendOtp,
    verifyOtp,
    signOut,
    consumeUrlSession,
    buildSharedModelEntries,
    getSharedSummaryLLM,
    buildSharedFetchHeaders,
  };
});
