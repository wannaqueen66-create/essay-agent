"""Shared configuration, model discovery and maintenance locks for esag."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlsplit, urljoin

import requests
from dotenv import dotenv_values


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_write(path, text, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".esag-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            st = path.stat()
            os.chown(name, st.st_uid, st.st_gid)
        elif path.parent.exists():
            st = path.parent.stat()
            os.chown(name, st.st_uid, st.st_gid)
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read_env(path):
    return dict(dotenv_values(path, interpolate=False)) if Path(path).exists() else {}


def write_env(path, updates):
    """Update only named keys, preserving unrelated settings and comments."""
    path = Path(path)
    lines = path.read_text().splitlines() if path.exists() else []
    keys = set(updates)
    output = []
    for line in lines:
        key = line.split("=", 1)[0].strip().removeprefix("export ")
        if key not in keys:
            output.append(line)
    for key, value in updates.items():
        if not key.replace("_", "").isalnum():
            raise ValueError("配置项名称无效")
        value = str(value)
        if "\n" in value or "\r" in value or "\0" in value:
            raise ValueError("配置值不能包含换行或空字符")
        escaped = value.replace("\\", "\\\\").replace("'", "\\'")
        output.append(f"{key}='{escaped}'")
    atomic_write(path, "\n".join(output) + "\n")


@contextmanager
def operation_lock(root, name="run"):
    """The same exclusive lock protects scheduled/manual runs and maintenance."""
    path = Path(root) / f".{name}.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o660)
    try:
        st = Path(root).stat()
        if os.geteuid() == 0:
            os.fchown(fd, st.st_uid, st.st_gid)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("任务或维护正在运行，请结束后再试") from None
        yield
    finally:
        os.close(fd)


def normalize_url(value):
    value = value.strip().rstrip("/") or "https://api.openai.com/v1"
    parsed = urlsplit(value)
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        raise ValueError("请输入完整的 http(s) API Base URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Base URL 不能包含账号密码、查询参数或片段")
    if parsed.path.endswith(("/chat/completions", "/models", "/responses")):
        raise ValueError("请填写接口根地址，不要包含 /models、/chat/completions 或 /responses")
    return value


def profile_from_env(env):
    return {
        "name": "原有接口", "base_url": normalize_url(env.get("OPENAI_BASE_URL") or ""),
        "api_key": env.get("OPENAI_API_KEY") or "", "model": env.get("OPENAI_MODEL") or "",
        "fallback": env.get("OPENAI_FALLBACK_MODEL") or "",
        "timeout": float(env.get("AI_TIMEOUT_SECONDS") or 60),
        "retries": int(env.get("AI_RETRIES") or 3),
    }


def validate_runtime_env(env):
    normalize_url(env.get("OPENAI_BASE_URL") or "")
    for key, low, high, cast in (
            ("DAYS_BACK", 1, 3650, int), ("MAX_RESULTS_PER_QUERY", 1, 10000, int),
            ("MIN_RELEVANCE_SCORE", 0, 100, int), ("REPORT_TOP_N", 1, 10000, int),
            ("EMAIL_TOP_N", 1, 10000, int), ("PENDING_POOL_DAYS", 1, 3650, int),
            ("OUTPUT_RETENTION_DAYS", 0, 36500, int), ("AI_TIMEOUT_SECONDS", 1, 600, float),
            ("AI_RETRIES", 1, 5, int), ("EMAIL_SMTP_PORT", 1, 65535, int)):
        if key in env:
            try:
                value = cast(env[key])
                valid = low <= value <= high
            except (ValueError, TypeError):
                valid = False
            if not valid:
                raise ValueError(f"{key} 必须为 {low}–{high} 范围内的数值")
    for key in ("EMAIL_ENABLED", "EMAIL_USE_TLS", "FORCE_REFRESH", "EMPTY_REPORT_EMAIL"):
        if key in env and str(env[key]).lower() not in ("true", "false", "1", "0", "yes", "no", "on", "off"):
            raise ValueError(f"{key} 应为 true 或 false")


def fingerprint(profile):
    return hashlib.sha256((profile["base_url"] + "\0" + profile["api_key"]).encode()).hexdigest()


def error_message(exc, secret=""):
    status = getattr(getattr(exc, "response", None), "status_code", None) or getattr(exc, "status_code", None)
    if status in (401, 403):
        return f"认证或权限检查失败（HTTP {status}），请检查 Key 和模型访问权限"
    if status == 404:
        return "地址或模型不存在（HTTP 404）；如不支持模型列表，可手动输入模型 ID 测试"
    if status == 429:
        return "接口限流或额度受限（HTTP 429），请检查服务商的额度和频率限制"
    if isinstance(exc, requests.Timeout) or "timeout" in type(exc).__name__.lower():
        return "请求超时，请检查网络或调整超时时间"
    # Never print arbitrary provider response bodies: they may echo credentials.
    if status:
        return f"接口请求失败（HTTP {status}）"
    if isinstance(exc, ValueError):
        message = str(exc)
        return message.replace(secret, "***") if secret else message
    return f"请求失败（{type(exc).__name__}），请检查接口、网络和配置"


def fetch_models(profile, session=None):
    session = session or requests.Session()
    base = normalize_url(profile["base_url"])
    origin = urlsplit(base)[:2]
    url = base + "/models"
    seen_pages, models = set(), set()
    for _ in range(1000):
        if url in seen_pages:
            raise ValueError("模型分页出现循环，已保留原缓存")
        if urlsplit(url)[:2] != origin:
            raise ValueError("模型分页跳转到不同服务器，已停止同步")
        seen_pages.add(url)
        response = session.get(url, headers={"Authorization": "Bearer " + profile["api_key"]},
                               timeout=profile["timeout"], allow_redirects=False)
        if 300 <= response.status_code < 400:
            raise ValueError("接口返回重定向，请直接配置最终 API 地址")
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            raise ValueError("模型列表格式无效，预期 data 数组；可手动输入模型 ID")
        for item in data["data"]:
            if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip():
                models.add(item["id"].strip())
        next_page = data.get("next") or data.get("next_page_url")
        if not next_page:
            next_page = response.links.get("next", {}).get("url")
        if next_page:
            url = urljoin(url, str(next_page))
        elif data.get("has_more"):
            from urllib.parse import urlencode
            cursor = data.get("last_id") or (data["data"][-1].get("id") if data["data"] else None)
            if not cursor:
                raise ValueError("分页缺少游标，已保留原缓存")
            url = base + "/models?" + urlencode({"after": cursor})
        else:
            return sorted(models, key=str.casefold)
    raise ValueError("分页数量异常，未覆盖原缓存")


class ProfileStore:
    def __init__(self, root):
        self.root = Path(root)
        self.path = self.root / ".ai_profiles.json"
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {"profiles": {}, "active": ""}

    def active(self):
        # .env remains the runtime source of truth, including direct edits.
        profile = profile_from_env(read_env(self.root / ".env"))
        name = self.data.get("active", "")
        saved = self.data["profiles"].get(name)
        if saved and all(saved.get(k) == profile.get(k) for k in ("base_url", "api_key", "model", "fallback", "timeout", "retries")):
            return dict(saved)
        return profile

    def activate(self, profile):
        profile = dict(profile)
        profile["base_url"] = normalize_url(profile["base_url"])
        if not profile["name"].strip() or not profile["api_key"] or not profile["model"]:
            raise ValueError("接口名称、Key 和主模型不能为空")
        if not 1 <= profile["timeout"] <= 600 or not 1 <= profile["retries"] <= 5:
            raise ValueError("超时范围 1–600 秒，重试范围 1–5 次")
        updates = {
            "OPENAI_BASE_URL": profile["base_url"], "OPENAI_API_KEY": profile["api_key"],
            "OPENAI_MODEL": profile["model"], "OPENAI_FALLBACK_MODEL": profile["fallback"],
            "AI_TIMEOUT_SECONDS": profile["timeout"], "AI_RETRIES": profile["retries"],
        }
        previous = self.active()
        data = json.loads(json.dumps(self.data))
        if previous["api_key"] and previous["model"] and previous["name"] != profile["name"]:
            data["profiles"].setdefault(previous["name"], previous)
        data["profiles"][profile["name"]] = profile
        data["active"] = profile["name"]
        env_path = self.root / ".env"
        original = env_path.read_text() if env_path.exists() else None
        try:
            write_env(env_path, updates)
            atomic_write(self.path, json.dumps(data, ensure_ascii=False, indent=2))
        except BaseException:
            if original is None:
                env_path.unlink(missing_ok=True)
            else:
                atomic_write(env_path, original)
            raise
        self.data = data

    def cache(self, profile):
        path = self.root / ".model_cache" / (fingerprint(profile) + ".json")
        return json.loads(path.read_text()) if path.exists() else {"models": [], "synced_at": None}

    def sync(self, profile):
        old = self.cache(profile)
        models = fetch_models(profile)
        cache = {"models": models, "synced_at": now(),
                 "added": sorted(set(models) - set(old["models"])),
                 "removed": sorted(set(old["models"]) - set(models))}
        path = self.root / ".model_cache" / (fingerprint(profile) + ".json")
        atomic_write(path, json.dumps(cache, ensure_ascii=False))
        return cache
