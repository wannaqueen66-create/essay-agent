#!/usr/bin/env python3
"""Chinese terminal console; no shell evaluation of configuration input."""
import argparse
import copy
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

import yaml
from agent_config import (ProfileStore, atomic_write, error_message, normalize_url,
                          now, operation_lock, read_env, write_env, validate_runtime_env)

ROOT = Path(__file__).resolve().parent


def ask(label, default=""):
    value = input(f"{label}" + (f" [{default}]" if default != "" else "") + ": ").strip()
    return value or str(default)


def yes(label, default=False):
    while True:
        value = input(label + (" [Y/n]: " if default else " [y/N]: ")).strip().lower()
        if not value:
            return default
        if value in ("y", "yes", "n", "no"):
            return value in ("y", "yes")
        print("请输入 y 或 n")


def number(label, default, low, high, cast=int):
    while True:
        try:
            value = cast(ask(label, default))
            if low <= value <= high:
                return value
        except ValueError:
            pass
        print(f"请输入 {low}–{high} 范围内的数值")


def command(args, check=True, capture=False):
    return subprocess.run(args, cwd=ROOT, check=check, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None)


def pause():
    input("按回车继续…")


def sync(store, profile):
    try:
        cache = store.sync(profile)
        print(f"同步成功：{len(cache['models'])} 个模型；新增 {len(cache['added'])}，未再返回 {len(cache['removed'])}")
        for label, key in (("新增", "added"), ("未再返回", "removed")):
            if cache[key] and yes(f"查看{label}模型？"):
                for index in range(0, len(cache[key]), 20):
                    print("\n".join(cache[key][index:index + 20]))
                    if index + 20 < len(cache[key]) and not yes("继续显示？", True):
                        break
    except Exception as exc:
        print(error_message(exc, profile["api_key"]))
        print("已保留原缓存和当前模型；可以手动输入模型 ID。")


def select_model(store, profile, field, refresh=True):
    cache = store.cache(profile)
    if refresh and profile["api_key"] and (not cache["synced_at"] or
            (datetime.now(timezone.utc) - datetime.fromisoformat(cache["synced_at"])).total_seconds() > 86400):
        print("模型列表超过 24 小时或尚未同步，正在尝试刷新…")
        sync(store, profile)
    query, page = "", 0
    while True:
        cache = store.cache(profile)
        models = [m for m in cache["models"] if query.casefold() in m.casefold()]
        pages = max(1, (len(models) + 14) // 15)
        page = min(page, pages - 1)
        print(f"\n模型选择：{len(models)} 项，第 {page + 1}/{pages} 页；同步时间 {cache['synced_at'] or '从未'}")
        for index, model in enumerate(models[page * 15:page * 15 + 15], page * 15 + 1):
            role = "主模型" if model == profile["model"] else "备用" if model == profile["fallback"] else ""
            test = profile.get("tests", {}).get(model, {})
            print(f"[{index}] {model}  {role}  {test.get('status', '未验证')}")
        if profile.get(field) and profile[field] not in cache["models"]:
            print(f"当前选择 {profile[field]} 未在缓存列表中；仍可保留并实测。")
        print("s 搜索 | n 下一页 | p 上一页 | r 同步 | m 手动输入 | 0 返回" + (" | off 关闭备用" if field == "fallback" else ""))
        value = ask("输入编号或完整模型 ID")
        if value == "0":
            return False
        if value == "s":
            query, page = ask("搜索词（空为全部）"), 0
        elif value == "n":
            page = min(page + 1, pages - 1)
        elif value == "p":
            page = max(0, page - 1)
        elif value == "r":
            sync(store, profile)
        elif value == "off" and field == "fallback":
            profile[field] = ""
            return True
        elif value == "m":
            model = ask("完整模型 ID（空则取消）")
            if model:
                profile[field] = model
                return True
        elif value.isdigit():
            index = int(value)
            if 1 <= index <= len(models):
                profile[field] = models[index - 1]
                return True
            print("编号无效，请重新选择；当前模型未变。")
        elif value in cache["models"]:
            profile[field] = value
            return True
        else:
            print("未找到该选项；列表外模型请用 m 手动填写。")


def test_profile(profile, fields=("model", "fallback")):
    from openai import OpenAI
    from essay_agent import analyze_paper
    roles = {"model": "主模型", "fallback": "备用模型"}
    targets = [(roles[field], profile[field]) for field in fields if profile[field]]
    if not targets:
        return True
    print("将用内置短摘要测试" + "、".join(role for role, _ in targets) + "，会产生少量 API 调用费用。")
    if not yes("开始测试？"):
        return None
    client = OpenAI(api_key=profile["api_key"], base_url=normalize_url(profile["base_url"]),
                    timeout=profile["timeout"], max_retries=0)
    passed = True
    profile.setdefault("tests", {})
    try:
        for role, model in targets:
            start = time.monotonic()
            result = analyze_paper(client, model, "Indoor greenery and perceived restoration",
                                   "Twenty adults viewed indoor rooms with and without plants in virtual reality. "
                                   "Perceived restoration was measured by questionnaire. Rooms with plants received higher scores.",
                                   retries=1, retry_delay=0, model_role=role)
            ok = result.get("分析状态") == "success"
            status = "通过" if ok else "失败"
            profile["tests"][model] = {"status": status, "at": now(), "seconds": round(time.monotonic() - start, 2)}
            print(f"{role} {model}: {status}，{profile['tests'][model]['seconds']} 秒")
            if not ok:
                print(result.get("原始分析", "格式验证失败"))
            passed = passed and ok
    finally:
        client.close()
    return passed


def save_profile(store, draft, require_test=True, test_fields=None):
    old = store.active()
    print(f"变更：接口 {old['name']} → {draft['name']}；主模型 {old['model'] or '未选'} → {draft['model'] or '未选'}；"
          f"备用 {old['fallback'] or '关闭'} → {draft['fallback'] or '关闭'}")
    if not draft["api_key"] or not draft["model"]:
        print("Key 和主模型不能为空，尚未保存。")
        return False
    if test_fields is None:
        shared_changed = any(old.get(key) != draft.get(key) for key in ("name", "base_url", "api_key", "timeout", "retries"))
        test_fields = tuple(field for field in ("model", "fallback")
                            if draft[field] and (shared_changed or old[field] != draft[field]))
    # Clearing a fallback never makes an API call or depends on primary health.
    test_fields = tuple(field for field in test_fields if draft[field])
    if require_test and test_fields and test_profile(draft, fields=test_fields) is not True:
        print("测试未通过或已取消，原配置保持不变。")
        return False
    if not yes("保存并从下次任务开始启用？", True):
        return False
    if draft["name"] in store.data["profiles"] and draft["name"] != store.data.get("active"):
        if not yes("同名接口档案已存在，覆盖它？"):
            return False
    store.activate(draft)
    print("已保存；正在执行的任务不受影响。")
    return True


def configure_api(store):
    old = store.active()
    draft = copy.deepcopy(old)
    draft["name"] = ask("接口名称", old["name"])
    draft["base_url"] = normalize_url(ask("API Base URL", old["base_url"]))
    key = getpass.getpass("API Key（隐藏输入；回车保留原值）: ").strip()
    draft["api_key"] = key or old["api_key"]
    if not draft["api_key"]:
        raise ValueError("API Key 不能为空")
    if (draft["base_url"], draft["api_key"]) != (old["base_url"], old["api_key"]):
        draft.pop("tests", None)
        draft["fallback"] = ""
    sync(store, draft)
    if not select_model(store, draft, "model", refresh=False):
        print("已取消，原配置保持不变。")
        return False
    if yes("配置备用模型？", bool(draft["fallback"])):
        select_model(store, draft, "fallback", refresh=False)
    else:
        draft["fallback"] = ""
    return save_profile(store, draft)


def ai_menu():
    store = ProfileStore(ROOT)
    while True:
        profile = store.active()
        cache = store.cache(profile)
        print(f"\nAI 接口与模型\n接口：{profile['name']}\n地址：{profile['base_url']}\n"
              f"Key：{'已配置，末尾 ' + profile['api_key'][-4:] if profile['api_key'] else '未配置'}\n"
              f"主模型：{profile['model'] or '未选'}；备用：{profile['fallback'] or '关闭'}\n"
              f"列表：{len(cache['models'])} 项；最近同步：{cache['synced_at'] or '从未'}")
        for model in (profile["model"], profile["fallback"]):
            if model:
                test = profile.get("tests", {}).get(model, {})
                print(f"{model} 最近测试：{test.get('status', '未验证')} {test.get('at', '')}")
        print("[1] 配置 API\n[2] 同步模型列表\n[3] 选择主模型\n[4] 设置 / 关闭备用模型\n"
              "[5] 测试 AI 配置\n[6] 切换已保存接口\n[7] 超时与重试\n[0] 返回")
        choice = ask("请选择")
        if choice == "0":
            return
        try:
            draft = copy.deepcopy(profile)
            if choice == "1":
                configure_api(store)
            elif choice == "2":
                sync(store, profile)
            elif choice in ("3", "4"):
                if select_model(store, draft, "model" if choice == "3" else "fallback"):
                    save_profile(store, draft, test_fields=("model",) if choice == "3" else ("fallback",))
            elif choice == "5":
                if test_profile(draft) is not None:
                    # Save test metadata only, without changing runtime settings.
                    store.data["profiles"][draft["name"]] = draft
                    store.data["active"] = draft["name"]
                    atomic_write(store.path, json.dumps(store.data, ensure_ascii=False, indent=2))
            elif choice == "6":
                names = list(store.data["profiles"])
                if not names:
                    print("尚无已保存接口，请先配置 API。")
                    continue
                for index, name in enumerate(names, 1):
                    print(f"[{index}] {name}")
                index = number("编号（0 取消）", 0, 0, len(names))
                if index:
                    draft = copy.deepcopy(store.data["profiles"][names[index - 1]])
                    save_profile(store, draft)
            elif choice == "7":
                draft["timeout"] = number("每次请求超时秒数", profile["timeout"], 1, 600, float)
                draft["retries"] = number("每个模型最多尝试次数", profile["retries"], 1, 5)
                save_profile(store, draft)
            else:
                print("无效选择")
        except (KeyboardInterrupt, EOFError):
            print("\n已取消，未保存的草稿已丢弃。")
            return
        except Exception as exc:
            print(error_message(exc, draft.get("api_key", "")))


def read_yaml():
    return yaml.safe_load((ROOT / "config.yaml").read_text())


def validate_yaml(data):
    if not isinstance(data, dict) or not isinstance(data.get("sources"), list):
        raise ValueError("配置须为 YAML 映射，sources 须为列表")
    if not data["sources"] or any(source not in ("arxiv", "openalex", "crossref", "semantic_scholar", "europepmc", "core") for source in data["sources"]):
        raise ValueError("请选择至少一个受支持的数据源")
    for key in ("queries", "generic_queries"):
        if key in data and not isinstance(data[key], dict):
            raise ValueError(f"{key} 须为键值映射")
    journals = data.get("target_journals", [])
    if not isinstance(journals, list) or any(not isinstance(j, dict) or not j.get("name") or not isinstance(j.get("issn"), str) or not re.fullmatch(r"\d{4}-\d{3}[\dXx]", j["issn"]) for j in journals):
        raise ValueError("期刊列表需要名称和格式正确的 ISSN")


def save_yaml(data):
    validate_yaml(data)
    atomic_write(ROOT / "config.yaml", yaml.safe_dump(data, allow_unicode=True, sort_keys=False), 0o644)


def timer_time():
    file = Path("/etc/systemd/system/essay-agent.timer")
    match = re.search(r"OnCalendar=\*-\*-\* (\d\d:\d\d)", file.read_text()) if file.exists() else None
    return match[1] if match else "07:00"


def set_timer(value):
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise ValueError("时间格式应为 HH:MM，例如 07:00（服务器时区）")
    file = Path("/etc/systemd/system/essay-agent.timer")
    old = file.read_text()
    new, count = re.subn(r"^OnCalendar=.*$", f"OnCalendar=*-*-* {value}:00", old, flags=re.M)
    if count != 1:
        raise ValueError("定时器不是单一 OnCalendar 配置，请手动检查")
    atomic_write(file, new, 0o644)
    try:
        command(["systemctl", "daemon-reload"])
        command(["systemctl", "restart", "essay-agent.timer"])
    except Exception:
        atomic_write(file, old, 0o644)
        command(["systemctl", "daemon-reload"], check=False)
        command(["systemctl", "restart", "essay-agent.timer"], check=False)
        raise


SETTINGS = [
    ("DAYS_BACK", "抓取最近几天", 1, 1, 3650),
    ("MAX_RESULTS_PER_QUERY", "每个检索式每个来源上限", 10, 1, 10000),
    ("MIN_RELEVANCE_SCORE", "最低相关性分数", 60, 0, 100),
    ("REPORT_TOP_N", "Markdown 展示篇数", 10, 1, 10000),
    ("EMAIL_TOP_N", "邮件正文展示篇数", 5, 1, 10000),
    ("PENDING_POOL_DAYS", "待展示池天数", 7, 1, 3650),
    ("OUTPUT_RETENTION_DAYS", "输出保留天数（0 不清理）", 30, 0, 36500),
]


def settings_menu():
    while True:
        env = read_env(ROOT / ".env")
        for i, (key, label, default, _, _) in enumerate(SETTINGS, 1):
            print(f"[{i}] {label}：{env.get(key, default)}")
        print(f"[8] 每日运行时间：{timer_time()}（服务器时区）\n[9] 启用 / 停用定时任务\n[0] 返回")
        index = number("请选择", 0, 0, 9)
        if not index:
            return
        if index == 9:
            if yes("启用每日任务？", True):
                if not env.get("OPENAI_API_KEY") or not env.get("OPENAI_MODEL"):
                    raise ValueError("请先完成 AI 配置")
                command(["systemctl", "enable", "--now", "essay-agent.timer"])
            else:
                command(["systemctl", "disable", "--now", "essay-agent.timer"])
        elif index == 8:
            set_timer(ask("HH:MM", timer_time()))
        else:
            key, label, default, low, high = SETTINGS[index - 1]
            write_env(ROOT / ".env", {key: number(label, env.get(key, default), low, high)})
        print("已保存")


def email_settings():
    env = read_env(ROOT / ".env")
    enabled = yes("启用邮件推送？", env.get("EMAIL_ENABLED") == "true")
    updates = {"EMAIL_ENABLED": str(enabled).lower()}
    if enabled:
        for key, label, default in [("EMAIL_SMTP_HOST", "SMTP 主机", "smtp-relay.brevo.com"),
                                    ("EMAIL_USERNAME", "SMTP 用户名", ""), ("EMAIL_FROM", "发件人", ""),
                                    ("EMAIL_TO", "收件人（英文逗号分隔）", "")]:
            updates[key] = ask(label, env.get(key) or default)
        updates["EMAIL_SMTP_PORT"] = number("SMTP 端口", env.get("EMAIL_SMTP_PORT") or 587, 1, 65535)
        password = getpass.getpass("SMTP 密码（回车保留）: ")
        if password:
            updates["EMAIL_PASSWORD"] = password
        updates["EMAIL_USE_TLS"] = str(yes("启用 STARTTLS？", env.get("EMAIL_USE_TLS", "true") == "true")).lower()
        if any(not updates.get(k, env.get(k)) for k in ("EMAIL_SMTP_HOST", "EMAIL_USERNAME", "EMAIL_PASSWORD", "EMAIL_FROM", "EMAIL_TO")):
            raise ValueError("邮件必填项不完整，未保存")
    if yes("保存邮件配置？", True):
        write_env(ROOT / ".env", updates)


def sources_menu():
    data = read_yaml()
    choices = [s for s in ("arxiv", "openalex", "crossref", "semantic_scholar", "europepmc", "core")
               if yes(f"启用 {s}？", s in data.get("sources", []))]
    if not choices:
        raise ValueError("至少启用一个来源，原配置未改动")
    env = read_env(ROOT / ".env")
    key = env.get("CORE_API_KEY") or ""
    if yes("配置 / 更新 CORE Key？"):
        key = getpass.getpass("CORE Key（回车保留）: ") or key
    if "core" in choices and not key:
        raise ValueError("启用 CORE 前请配置 Key")
    if yes("保存数据源配置？", True):
        data["sources"] = choices
        save_yaml(data)
        write_env(ROOT / ".env", {"CORE_API_KEY": key})


def journals_menu():
    while True:
        data = read_yaml()
        journals = data.setdefault("target_journals", [])
        for i, journal in enumerate(journals, 1):
            print(f"[{i}] {journal['name']} ({journal['issn']})")
        choice = ask("a 新增 / d 删除 / 0 返回")
        if choice == "0":
            return
        if choice == "a":
            name, issn = ask("期刊名称"), ask("ISSN，例如 2352-7102").upper()
            if not name or not re.fullmatch(r"\d{4}-\d{3}[\dX]", issn):
                raise ValueError("期刊名称不能为空，ISSN 格式须为 1234-567X")
            if any(j["issn"] == issn for j in journals):
                raise ValueError("此 ISSN 已存在")
            journals.append({"name": name, "issn": issn})
            save_yaml(data)
        elif choice == "d":
            index = number("删除编号（0 取消）", 0, 0, len(journals))
            if index and yes(f"删除 {journals[index - 1]['name']}？"):
                journals.pop(index - 1)
                save_yaml(data)


def dashboard():
    env = read_env(ROOT / ".env")
    print("\nessay-agent 终端控制台\n安装目录：", ROOT)
    for unit in ("essay-agent.service", "essay-agent.timer"):
        result = command(["systemctl", "is-active", unit], check=False, capture=True)
        print(f"{unit}: {result.stdout.strip()}")
    print("每日运行：", timer_time(), "（服务器时区；最多随机延迟 5 分钟）")
    print("服务为一次性任务，运行结束后 inactive 属于正常情况。")
    result = command(["systemctl", "show", "essay-agent.service", "-p", "ExecMainStartTimestamp", "-p", "Result"], check=False, capture=True)
    print(result.stdout.strip())
    print("主模型：", env.get("OPENAI_MODEL", "未配置"), "；备用：", env.get("OPENAI_FALLBACK_MODEL") or "关闭")
    for key, label, default, _, _ in SETTINGS:
        print(f"{label}：{env.get(key, default)}", end="  ")
    print("\n邮件：", env.get("EMAIL_ENABLED", "false"))
    data = read_yaml()
    print("来源：", ", ".join(data.get("sources", [])), "；期刊：", len(data.get("target_journals", [])))
    version = ROOT / ".installed_version.json"
    if version.exists():
        print("版本：", json.loads(version.read_text()))
    else:
        print("版本：", command(["git", "rev-parse", "--short", "HEAD"], check=False, capture=True).stdout.strip())
    outputs = sorted((ROOT / "output").glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
    print("最近输出：", ", ".join(p.name for p in outputs) or "暂无")
    stats = sorted((ROOT / "output").glob("*_stats.json"))
    if stats:
        data = json.loads(stats[-1].read_text())
        print("最近统计：", {k: data.get(k) for k in ("fetched", "kept", "analysis_success", "analysis_failed")})


def run_script(name):
    command(["runuser", "-u", "essay-agent", "--", str(ROOT / ".venv/bin/python"), str(ROOT / name)])


def edit_file(name):
    target = ROOT / name
    with tempfile.TemporaryDirectory(prefix="esag-edit-") as tmp:
        draft = Path(tmp) / name
        draft.write_text(target.read_text())
        draft.chmod(0o600)
        command(shlex.split(os.getenv("EDITOR", "nano")) + [str(draft)])
        if name == "config.yaml":
            data = yaml.safe_load(draft.read_text())
            validate_yaml(data)
        else:
            from dotenv.parser import parse_stream
            with draft.open() as stream:
                if any(binding.error for binding in parse_stream(stream)):
                    raise ValueError("环境配置语法无效，未保存")
            validate_runtime_env(read_env(draft))
        if yes("保存编辑结果？", True):
            atomic_write(target, draft.read_text(), 0o600 if name == ".env" else 0o644)


def backup_create():
    directory = ROOT / "backups" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    directory.mkdir(parents=True, mode=0o700)
    for name in (".env", "config.yaml", ".ai_profiles.json"):
        if (ROOT / name).exists():
            shutil.copy2(ROOT / name, directory / name)
    db = ROOT / read_yaml().get("db_path", "papers.db")
    if db.exists():
        with sqlite3.connect(db) as src, sqlite3.connect(directory / "papers.db") as dest:
            src.backup(dest)
    print("备份：", directory)
    return directory


def backup_menu():
    choice = ask("1 创建备份 / 2 恢复备份 / 0 返回")
    if choice == "1":
        with operation_lock(ROOT):
            backup_create()
    elif choice == "2":
        backups = sorted((ROOT / "backups").glob("*"), reverse=True)
        for i, path in enumerate(backups, 1):
            print(f"[{i}] {path.name}")
        index = number("恢复编号（0 取消）", 0, 0, len(backups))
        if index and yes("恢复将替换配置和数据库，继续？"):
            with operation_lock(ROOT):
                backup_create()
                source = backups[index - 1]
                for name in (".env", "config.yaml", ".ai_profiles.json"):
                    if (source / name).exists():
                        atomic_write(ROOT / name, (source / name).read_text(), 0o644 if name == "config.yaml" else 0o600)
                if (source / "papers.db").exists():
                    dest = ROOT / read_yaml().get("db_path", "papers.db")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with sqlite3.connect(source / "papers.db") as src, sqlite3.connect(dest) as db:
                        src.backup(db)
                    import pwd
                    user = pwd.getpwnam("essay-agent")
                    os.chown(dest, user.pw_uid, user.pw_gid)
                print("已恢复；恢复前也已创建备份。")


def updates_menu():
    from agent_update import check_updates, install_update, rollback
    while True:
        print("\n更新 / 升级\n[1] 一键更新全部\n[2] 仅更新交互脚本\n[3] 检查更新\n[4] 回退上次程序版本\n[0] 返回")
        choice = ask("请选择")
        if choice == "0":
            return
        if choice == "4":
            if yes("回退上次程序版本（保留当前配置和数据）？"):
                rollback(ROOT)
                restart_console()
        elif choice in ("1", "2", "3"):
            with tempfile.TemporaryDirectory(prefix="esag-update-") as tmp:
                info = check_updates(ROOT, Path(tmp))
                if choice != "3" and yes("应用上述更新？"):
                    changed = install_update(ROOT, info, "all" if choice == "1" else "console")
                    if changed:
                        restart_console()


def restart_console():
    print("更新完成，正在重新打开控制台…", flush=True)
    # The previous release may be the original Bash-only console.
    os.execv("/usr/local/bin/esag", ["esag"])


def uninstall():
    print(f"将删除服务、控制台、服务用户及 {ROOT} 中所有数据和备份。")
    if ask("输入 yes 确认") != "yes":
        return
    with operation_lock(ROOT):
        command(["systemctl", "disable", "--now", "essay-agent.timer"], check=False)
        command(["systemctl", "stop", "essay-agent.service"], check=False)
        for file in ("/etc/systemd/system/essay-agent.timer", "/etc/systemd/system/essay-agent.service", "/usr/local/bin/esag"):
            Path(file).unlink(missing_ok=True)
        command(["systemctl", "daemon-reload"])
        shutil.rmtree(ROOT)
        subprocess.run(["userdel", "essay-agent"], check=False)
    raise SystemExit(0)


def main():
    global ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument("--configure", action="store_true")
    args = parser.parse_args()
    if not sys.stdin.isatty():
        sys.stdin = open("/dev/tty")
    if os.geteuid() != 0:
        raise SystemExit("请用 sudo esag 或 root 运行")
    # Serialise configuration writers; normal analysis remains independent.
    with operation_lock(ROOT, "console"):
        if args.configure:
            if not configure_api(ProfileStore(ROOT)):
                raise SystemExit(1)
            return
        while True:
            try:
                dashboard()
                print("\n[1] AI 接口与模型\n[2] 抓取与报告设置\n[3] 立即运行一次\n[4] 邮件配置\n"
                      "[5] 数据源 / CORE\n[6] 目标期刊管理\n[7] 最近日志\n[8] 数据库总览\n"
                      "[9] 待展示池\n[10] 测试邮箱\n[11] 更新 / 升级\n[12] 备份 / 恢复\n"
                      "[13] 编辑 config.yaml\n[14] 编辑 .env\n[15] 重新配置 AI\n[16] 卸载\n[0] 退出")
                choice = ask("请选择")
                if choice == "0":
                    return
                actions = {"1": ai_menu, "2": settings_menu, "3": lambda: command(["systemctl", "start", "essay-agent.service"]),
                           "4": email_settings, "5": sources_menu, "6": journals_menu,
                           "7": lambda: command(["journalctl", "-u", "essay-agent.service", "-n", "200", "--no-pager"]),
                           "8": lambda: run_script("inspect_db.py"), "9": lambda: run_script("show_pending_pool.py"),
                           "10": lambda: run_script("test_email.py") if yes("实际发送测试邮件？") else None,
                           "11": updates_menu, "12": backup_menu, "13": lambda: edit_file("config.yaml"),
                           "14": lambda: edit_file(".env"), "15": lambda: configure_api(ProfileStore(ROOT)), "16": uninstall}
                if choice in actions:
                    actions[choice]()
                else:
                    print("无效选择")
                pause()
            except (EOFError, KeyboardInterrupt):
                print("\n已取消。")
                return
            except Exception as exc:
                print(error_message(exc))
                pause()


if __name__ == "__main__":
    main()
