"""Shared optimistic commit boundary for result TXT and cache files."""
import os
import tempfile
from contextlib import ExitStack, contextmanager
from pathlib import Path


def canonical(path):
    return Path(os.path.normcase(str(Path(path).resolve())))


def snapshot(path):
    try:
        return Path(path).read_bytes()
    except FileNotFoundError:
        return None


def distinct_paths(paths):
    paths = [canonical(path) for path in paths]
    if len(paths) != len(set(paths)):
        raise ValueError("输出、缓存及配置路径不能重复")
    return paths


@contextmanager
def file_locks(paths):
    from duan_app.persistence.cache import _cache_file_lock
    with ExitStack() as stack:
        for path in sorted({canonical(path) for path in paths}, key=str):
            stack.enter_context(_cache_file_lock(path, timeout=5))
        yield


def capture(paths):
    paths = distinct_paths(paths)
    with file_locks(paths):
        return {path: snapshot(path) for path in paths}


def replace_bytes(path, data):
    if data is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".writing-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def commit_updates(before, updates):
    before = {canonical(path): data for path, data in before.items()}
    distinct_paths(updates)
    updates = {canonical(path): (text.encode("utf-8-sig") if isinstance(text, str) else text)
               for path, text in updates.items()}
    if not set(updates) <= set(before):
        raise ValueError("提交文件缺少运行前快照")
    with file_locks(before):
        if any(snapshot(path) != data for path, data in before.items()):
            raise ValueError("运行期间结果、缓存或配置被修改，停止写入，请重试")
        attempted = []
        try:
            for path, data in updates.items():
                attempted.append(path)
                replace_bytes(path, data)
        except Exception as original:
            errors = []
            for path in reversed(attempted):
                try:
                    replace_bytes(path, before[path])
                except Exception as exc:
                    errors.append((path, exc))
            if errors:
                evidence = []
                for path, exc in errors:
                    try:
                        fd, name = tempfile.mkstemp(prefix=path.name + ".recovery-", dir=path.parent)
                        with os.fdopen(fd, "wb") as handle:
                            handle.write(before[path] or b"")
                        evidence.append(f"{path}: {exc}; 原文件{'不存在' if before[path] is None else '备份'}={name}")
                    except Exception as backup_error:
                        evidence.append(f"{path}: {exc}; 恢复证据保存失败={backup_error}")
                raise OSError("回滚未完成：" + "；".join(evidence)) from original
            raise
