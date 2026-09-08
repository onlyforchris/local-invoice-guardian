# -*- coding: utf-8 -*-
"""发票管家在线升级：下载 GitHub main 分支压缩包并覆盖更新。

- 不走 GitHub API（免速率限制），直接下载分支 zip；
- 保护用户数据：config.json / invoice_ledger.json / python_path.txt / .venv 等绝不覆盖；
- 用法：python update.py [--dry] [--yes] [--force] [--url 下载地址]
"""
import io
import os
import re
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ZIP = os.environ.get("INVOICE_UPDATE_URL") or \
    "https://github.com/onlyforchris/local-invoice-guardian/archive/refs/heads/main.zip"
PROTECT_FILES = {"config.json", "invoice_ledger.json", "python_path.txt"}
PROTECT_DIRS = {".venv", "__pycache__", ".git"}
VERSION_RE = re.compile(r'APP_VERSION\s*=\s*"([^"]+)"')


def read_version(text):
    m = VERSION_RE.search(text or "")
    return m.group(1) if m else "?"


def fetch(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": "invoice-manager-updater"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def collect(zf):
    """解出 (相对路径, 字节) 列表，跳过目录/保护项；返回 (updates, 远端版本)。"""
    names = zf.namelist()
    prefix = names[0].split("/")[0] + "/" if names else ""
    updates, new_ver = [], "?"
    for info in zf.infolist():
        name = info.filename
        if name.endswith("/"):
            continue
        rel = name[len(prefix):] if name.startswith(prefix) else name
        if not rel or rel.startswith(".git/"):
            continue
        parts = rel.replace("\\", "/").split("/")
        if any(p in PROTECT_DIRS for p in parts):
            continue
        if len(parts) == 1 and rel in PROTECT_FILES:
            continue
        blob = zf.read(info)
        if parts[-1] == "app.py":
            new_ver = read_version(blob.decode("utf-8", "ignore"))
        updates.append((rel, blob))
    return updates, new_ver


def main():
    args = sys.argv[1:]
    dry = "--dry" in args
    local_path = os.path.join(HERE, "app.py")
    with open(local_path, encoding="utf-8") as f:
        local_ver = read_version(f.read())
    print("本地版本:", local_ver)
    print("正在下载最新代码（GitHub main 分支）…")
    try:
        data = fetch(REPO_ZIP)
    except Exception as e:
        print("[失败] 下载出错:", e)
        print("国内网络直连 GitHub 可能不稳定，可设置代理后重试：")
        print("  1. 打开 cmd 执行:  set HTTPS_PROXY=http://127.0.0.1:7890  （端口按实际填）")
        print("  2. 在同一个 cmd 窗口里重新运行本升级脚本")
        return 1
    updates, new_ver = collect(zipfile.ZipFile(io.BytesIO(data)))
    print("远端版本:", new_ver, "| 待更新文件数:", len(updates))
    if dry:
        print("[dry-run] 仅检查，未写入任何文件。")
        return 0
    if new_ver == local_ver and "--force" not in args:
        print("本地已是最新版本，无需升级。")
        return 0
    if "--yes" not in args:
        try:
            input("回车确认升级到 %s（配置/台账等用户数据不会覆盖），Ctrl+C 取消…" % new_ver)
        except KeyboardInterrupt:
            print("\n已取消。")
            return 0
    root = os.path.normpath(HERE)
    n = 0
    for rel, blob in updates:
        dest = os.path.normpath(os.path.join(HERE, rel))
        if not dest.startswith(root + os.sep):
            continue  # 防路径穿越
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(blob)
        n += 1
    print("已更新 %d 个文件 → 版本 %s" % (n, new_ver))
    return 0


if __name__ == "__main__":
    sys.exit(main())
