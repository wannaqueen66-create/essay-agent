const DEFAULT_MODELS = ["deepseek-v4-flash", "deepseek-v4-pro"];

type JsonRecord = Record<string, unknown>;

const env = (name: string, fallback = ""): string => {
  try {
    return (Deno.env.get(name) || fallback).trim();
  } catch {
    return fallback;
  }
};

const corsHeaders = (origin: string | null): HeadersInit => {
  const allowed = env("SCHOLARLENS_ALLOWED_ORIGINS", "*");
  const allowOrigin = allowed === "*"
    ? "*"
    : allowed.split(",").map((item) => item.trim()).includes(origin || "")
      ? origin || ""
      : allowed.split(",")[0]?.trim() || "*";
  return {
    "Access-Control-Allow-Origin": allowOrigin,
    "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
  };
};

const jsonResponse = (payload: JsonRecord, status: number, origin: string | null) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: {
      ...corsHeaders(origin),
      "Content-Type": "application/json; charset=utf-8",
    },
  });

const normalizeBaseUrl = (value: string): string => value.trim().replace(/\/+$/g, "");

const buildChatCompletionsEndpoint = (baseUrl: string): string => {
  const raw = normalizeBaseUrl(baseUrl);
  if (!raw) return "";
  if (/\/chat\/completions$/i.test(raw)) return raw;
  if (/\/v\d+$/i.test(raw)) return `${raw}/chat/completions`;
  return `${raw}/v1/chat/completions`;
};

const parseAllowedModels = (): string[] => {
  const configured = env("SCHOLARLENS_CHAT_MODELS")
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
  const fallbackModel = env("SUMMARY_MODEL") || env("DEEPSEEK_MODEL");
  const models = configured.length ? configured : [fallbackModel, ...DEFAULT_MODELS].filter(Boolean);
  return Array.from(new Set(models));
};

const requireUser = async (authHeader: string, origin: string | null): Promise<JsonRecord> => {
  const supabaseUrl = env("SUPABASE_URL");
  const anonKey = env("SUPABASE_ANON_KEY") || env("SUPABASE_ANON_PUBLIC_KEY");
  if (!supabaseUrl || !anonKey) {
    throw new Error("Supabase auth environment is missing.");
  }
  const res = await fetch(`${normalizeBaseUrl(supabaseUrl)}/auth/v1/user`, {
    headers: {
      apikey: anonKey,
      Authorization: authHeader,
      Accept: "application/json",
    },
  });
  if (!res.ok) {
    throw new Error(`Unauthorized: ${res.status}`);
  }
  const user = await res.json() as JsonRecord;
  const email = String(user.email || "").trim().toLowerCase();
  if (!email) {
    throw new Error("Authenticated user has no email.");
  }

  const serviceKey = env("SUPABASE_SERVICE_ROLE_KEY") || env("SUPABASE_SERVICE_KEY") || anonKey;
  const allowlistUrl = `${normalizeBaseUrl(supabaseUrl)}/rest/v1/scholarlens_users?select=email,role,is_active&email=eq.${encodeURIComponent(email)}&is_active=eq.true&limit=1`;
  const allowRes = await fetch(allowlistUrl, {
    headers: {
      apikey: serviceKey,
      Authorization: `Bearer ${serviceKey}`,
      Accept: "application/json",
    },
  });
  if (!allowRes.ok) {
    throw new Error(`Allowlist check failed: ${allowRes.status}`);
  }
  const rows = await allowRes.json() as JsonRecord[];
  if (!Array.isArray(rows) || rows.length === 0) {
    throw new Error("This email is not enabled for ScholarLens.");
  }
  return { ...user, scholarlens_role: rows[0]?.role || "member" };
};

Deno.serve(async (req) => {
  const origin = req.headers.get("Origin");
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders(origin) });
  }
  if (req.method !== "POST") {
    return jsonResponse({ error: "method_not_allowed" }, 405, origin);
  }

  const authHeader = req.headers.get("Authorization") || "";
  if (!/^Bearer\s+\S+/i.test(authHeader)) {
    return jsonResponse({ error: "missing_authorization" }, 401, origin);
  }

  try {
    await requireUser(authHeader, origin);
  } catch (error) {
    return jsonResponse({ error: error instanceof Error ? error.message : String(error) }, 403, origin);
  }

  let payload: JsonRecord;
  try {
    payload = await req.json() as JsonRecord;
  } catch {
    return jsonResponse({ error: "invalid_json" }, 400, origin);
  }

  const apiKey = env("SUMMARY_API_KEY") || env("DEEPSEEK_API_KEY") || env("OPENAI_API_KEY");
  const baseUrl = env("SUMMARY_BASE_URL") || env("DEEPSEEK_BASE_URL") || env("OPENAI_BASE_URL") || "https://api.deepseek.com";
  const endpoint = buildChatCompletionsEndpoint(baseUrl);
  if (!apiKey || !endpoint) {
    return jsonResponse({ error: "shared_llm_not_configured" }, 500, origin);
  }

  const allowedModels = parseAllowedModels();
  const requestedModel = String(payload.model || "").trim();
  const defaultModel = env("SUMMARY_MODEL") || env("DEEPSEEK_MODEL") || allowedModels[0] || DEFAULT_MODELS[0];
  const selectedModel = allowedModels.includes(requestedModel) ? requestedModel : defaultModel;
  const upstreamPayload = {
    ...payload,
    model: selectedModel,
  };

  const authHeaderName = env("SCHOLARLENS_LLM_AUTH_HEADER", "authorization").toLowerCase();
  const headers = new Headers({
    "Content-Type": "application/json",
    Accept: payload.stream === true ? "text/event-stream" : "application/json",
  });
  if (authHeaderName === "x-api-key") {
    headers.set("x-api-key", apiKey);
  } else {
    headers.set("Authorization", `Bearer ${apiKey}`);
  }

  const upstream = await fetch(endpoint, {
    method: "POST",
    headers,
    body: JSON.stringify(upstreamPayload),
  });

  const responseHeaders = new Headers(corsHeaders(origin));
  responseHeaders.set(
    "Content-Type",
    upstream.headers.get("Content-Type") || (payload.stream === true ? "text/event-stream" : "application/json"),
  );
  responseHeaders.set("Cache-Control", "no-store");

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
});
