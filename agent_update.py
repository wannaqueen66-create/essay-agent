"""Transactional updates: code snapshots, isolated dependencies and rollback.

Runtime data is never copied from upstream or restored by a code rollback.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from datetime import datetime

from agent_config import atomic_write, operation_lock

REPOSITORY = "https://github.com/wannaqueen66-create/essay-agent.git"
CONSOLE_FILES = {"esag", "esag_console.py", "agent_config.py", "agent_update.py", "console_manifest.json"}
PRESERVED = {"config.yaml", ".env", "papers.db", ".ai_profiles.json", ".installed_version.json",
             ".code_manifest.json", ".update_history.json", ".last_upgrade"}
RUNTIME_DIRS = {".git", ".venv", ".venvs", ".model_cache", "output", "backups", ".updates"}


def run(args, cwd=None, capture=False):
    return subprocess.run(args, cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None)


def read_json(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def allowed(name):
    path = Path(name)
    return (not path.is_absolute() and ".." not in path.parts and name not in PRESERVED
            and bool(path.parts) and path.parts[0] not in RUNTIME_DIRS
            and not name.endswith((".db", ".db-wal", ".db-shm")))


def tracked(root):
    manifest = root / ".code_manifest.json"
    if manifest.exists():
        return read_json(manifest, [])
    return [n for n in run(["git", "ls-files", "-z"], root, True).stdout.split("\0") if n and allowed(n)]


def versions(root):
    file = root / ".installed_version.json"
    if file.exists():
        return read_json(file, {})
    sha = run(["git", "rev-parse", "HEAD"], root, True).stdout.strip()
    return {"program": sha, "console": sha}


def check_updates(root, staging):
    source = staging / "source"
    print("正在获取远程版本…")
    run(["git", "clone", "--depth=30", "--branch", "main", REPOSITORY, str(source)], capture=True)
    sha = run(["git", "rev-parse", "HEAD"], source, True).stdout.strip()
    current = versions(root)
    print("本地程序：", current.get("program", "未知"), "\n本地控制台：", current.get("console", "未知"), "\n远程版本：", sha)
    if current.get("program") == sha and current.get("console") == sha:
        print("已是最新版，无需重复更新。")
    else:
        before = current.get("program", "")
        try:
            log = run(["git", "log", "--format=%h %s", f"{before}..{sha}"], source, True).stdout
            print("更新记录：\n" + log)
        except subprocess.CalledProcessError:
            print("旧版本超出浅克隆历史，以下为远程最近提交：")
            print(run(["git", "log", "-8", "--format=%h %s"], source, True).stdout)
    files = tracked(source)
    for name in files:
        if (source / name).is_symlink():
            raise ValueError("更新包中含符号链接，已停止")
    hashes = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in files}
    return {"source": source, "sha": sha, "files": files, "hashes": hashes}


def validate_source(source, files):
    for name in files:
        if not allowed(name):
            raise ValueError("更新包包含运行数据或非法路径")
        if name.endswith(".py"):
            ast.parse((source / name).read_text(), filename=name)
    for name in ("esag", "deploy.sh"):
        if name in files:
            run(["bash", "-n", str(source / name)])
    required = {"essay_agent.py", "requirements.txt"} | CONSOLE_FILES
    if not required.issubset(set(files)):
        raise ValueError("更新包缺少核心文件，请检查目标分支")


def check_idle(root):
    result = subprocess.run(["systemctl", "is-active", "essay-agent.service"], capture_output=True, text=True)
    if result.stdout.strip() in ("active", "activating", "deactivating", "reloading"):
        raise RuntimeError("论文任务正在运行，请结束后再更新")
    # Covers manual runs from the previous release, before the shared lock existed.
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            args = (entry / "cmdline").read_bytes().split(b"\0")
            if any(Path(a.decode(errors="replace")).name == "essay_agent.py" for a in args if a):
                if (entry / "cwd").resolve() == root.resolve() or str(root / "essay_agent.py").encode() in args:
                    raise RuntimeError("检测到手动论文任务，请结束后再更新")
        except (PermissionError, FileNotFoundError, ProcessLookupError):
            continue


def safe_target(root, name):
    if not allowed(name):
        raise ValueError("非法程序文件路径")
    path = root / name
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("程序路径不能通过符号链接指向安装目录外")
    return path


def replace_file(source, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Copy through a sibling temporary file so interrupted writes do not truncate code.
    fd, name = tempfile.mkstemp(dir=dest.parent)
    os.close(fd)
    try:
        shutil.copy2(source, name)
        os.replace(name, dest)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def switch_venv(root, target):
    link = root / ".venv.next"
    link.unlink(missing_ok=True)
    link.symlink_to(target)
    os.replace(link, root / ".venv")


def snapshot(root, names, mode):
    directory = root / ".updates" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    directory.mkdir(parents=True, mode=0o700)
    metadata = {"names": sorted(names), "existing": [], "mode": mode,
                "versions": versions(root), "manifest": tracked(root),
                "venv": str((root / ".venv").resolve()), "directory": str(directory)}
    for name in names:
        target = safe_target(root, name)
        if target.is_file():
            dest = directory / "code" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, dest)
            metadata["existing"].append(name)
    launcher = Path("/usr/local/bin/esag")
    metadata["launcher_exists"] = launcher.exists()
    if launcher.exists():
        shutil.copy2(launcher, directory / "launcher")
    atomic_write(directory / "snapshot.json", json.dumps(metadata, indent=2))
    return metadata


def restore(root, metadata):
    directory = Path(metadata["directory"])
    for name in metadata["names"]:
        target = safe_target(root, name)
        if name in metadata["existing"]:
            replace_file(directory / "code" / name, target)
        else:
            target.unlink(missing_ok=True)
    if metadata["mode"] == "all":
        switch_venv(root, metadata["venv"])
    launcher = Path("/usr/local/bin/esag")
    if metadata["launcher_exists"]:
        replace_file(directory / "launcher", launcher)
    else:
        launcher.unlink(missing_ok=True)
    atomic_write(root / ".installed_version.json", json.dumps(metadata["versions"]))
    atomic_write(root / ".code_manifest.json", json.dumps(metadata["manifest"]))


def timer_pause():
    result = subprocess.run(["systemctl", "is-active", "essay-agent.timer"], capture_output=True, text=True)
    active = result.stdout.strip() == "active"
    if active:
        run(["systemctl", "stop", "essay-agent.timer"])
    return active


def install_update(root, info, mode="all"):
    source, sha = info["source"], info["sha"]
    current = versions(root)
    if (mode == "all" and current.get("program") == sha and current.get("console") == sha) or (mode == "console" and current.get("console") == sha):
        print("已是最新版，无需重复更新。")
        return False
    validate_source(source, info["files"])
    for name, digest in info["hashes"].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != digest:
            raise ValueError("下载文件校验失败，原版本未改动")
    if mode == "console":
        old_contract = read_json(root / "console_manifest.json", {})
        contract = read_json(source / "console_manifest.json", {})
        if old_contract.get("runtime_api") != contract.get("runtime_api") or (root / "requirements.txt").read_bytes() != (source / "requirements.txt").read_bytes():
            raise ValueError("本次控制台需要新版主程序或依赖，请选择一键更新全部")
    files = set(info["files"]) if mode == "all" else CONSOLE_FILES
    names = set(tracked(root)) | files if mode == "all" else files
    with operation_lock(root):
        check_idle(root)
        was_active = timer_pause()
        new_venv = None
        metadata = None
        try:
            check_idle(root)
            if mode == "all":
                venv = root / ".venv"
                versions_dir = root / ".venvs"
                versions_dir.mkdir(exist_ok=True)
                if not venv.is_symlink():
                    legacy = versions_dir / ("legacy-" + datetime.now().strftime("%Y%m%d%H%M%S%f"))
                    venv.rename(legacy)
                    try:
                        switch_venv(root, legacy)
                    except BaseException:
                        legacy.rename(venv)
                        raise
                new_venv = versions_dir / (sha[:12] + "-" + datetime.now().strftime("%Y%m%d%H%M%S%f"))
                print("构建独立依赖环境，原环境保留…")
                run(["python3", "-m", "venv", str(new_venv)])
                run([str(new_venv / "bin/python"), "-m", "pip", "install", "-r", str(source / "requirements.txt")])
                run([str(new_venv / "bin/python"), "-m", "pip", "check"])
                run([str(new_venv / "bin/python"), "-c", "import essay_agent, esag_console, agent_update"], source)
            metadata = snapshot(root, names, mode)
            print("程序快照：", metadata["directory"])
            for name in names:
                target = safe_target(root, name)
                if name in files:
                    replace_file(source / name, target)
                else:
                    target.unlink(missing_ok=True)
            if new_venv:
                switch_venv(root, new_venv)
            run([str(root / ".venv/bin/python"), "-c", "import essay_agent, esag_console, agent_update"], root)
            replace_file(root / "esag", Path("/usr/local/bin/esag"))
            Path("/usr/local/bin/esag").chmod(0o755)
            current["console"] = sha
            if mode == "all":
                current["program"] = sha
            current["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
            atomic_write(root / ".installed_version.json", json.dumps(current))
            atomic_write(root / ".code_manifest.json", json.dumps(sorted(set(info["files"]) if mode == "all" else set(tracked(root)) | files)))
            history = read_json(root / ".update_history.json", [])
            history.append(metadata["directory"])
            atomic_write(root / ".update_history.json", json.dumps(history))
            print("更新成功，配置、报告、数据库和定时设置已保留。")
            return True
        except BaseException:
            if metadata:
                restore(root, metadata)
                print("更新失败，已恢复更新前的程序和依赖。")
            else:
                print("更新准备失败，原程序仍可使用。")
            if new_venv and new_venv.exists() and (root / ".venv").resolve() != new_venv:
                shutil.rmtree(new_venv)
            raise
        finally:
            if was_active:
                run(["systemctl", "start", "essay-agent.timer"])


def rollback(root):
    with operation_lock(root):
        check_idle(root)
        history = read_json(root / ".update_history.json", [])
        if not history:
            raise ValueError("暂无可回退的程序快照")
        metadata = read_json(Path(history[-1]) / "snapshot.json", None)
        if not metadata:
            raise ValueError("快照缺失，未修改程序")
        for name in metadata["existing"]:
            if not (Path(metadata["directory"]) / "code" / name).is_file():
                raise ValueError("快照不完整，未修改程序")
        if metadata["mode"] == "all" and not (Path(metadata["venv"]) / "bin/python").exists():
            raise ValueError("旧依赖环境不存在，未修改程序")
        was_active = timer_pause()
        try:
            check_idle(root)
            recovery = snapshot(root, set(metadata["names"]), metadata["mode"])
            try:
                restore(root, metadata)
                run([str(root / ".venv/bin/python"), "-c", "import essay_agent"], root)
            except BaseException:
                restore(root, recovery)
                raise
            atomic_write(root / ".update_history.json", json.dumps(history[:-1]))
            print("已回退程序版本；当前配置和数据保持不变。")
        finally:
            if was_active:
                run(["systemctl", "start", "essay-agent.timer"])
