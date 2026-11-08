#!/usr/bin/env python3
"""扫描账号下的公开仓库，生成 README.md 总表。

本地运行：
    GH_TOKEN=$(gh auth token) python scripts/generate.py
"""

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

USERNAME = "alanchan20121201-prog"
OUT_FILE = "README.md"

# 这些仓库不上榜：profile 仓库自身、以及其他你不想展示的
EXCLUDE = {USERNAME.lower(), ".github"}

MAX_DESC = 110


def api_get(url):
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USERNAME,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_all_repos():
    """用 /users/{name}/repos 而不是 /user/repos —— 后者在 Actions 里返回的是 bot 自己的仓库。"""
    repos, page = [], 1
    while True:
        url = (
            f"https://api.github.com/users/{USERNAME}/repos"
            f"?per_page=100&page={page}&sort=updated&type=owner"
        )
        batch = api_get(url)
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos


def clean_desc(text):
    if not text:
        return "—"
    s = re.sub(r"\s+", " ", text).strip()
    # 描述被重复粘贴两遍时只留一份
    for size in range(len(s) // 2, 15, -1):
        if s[:size].rstrip("。.") == s[size : size * 2].rstrip("。."):
            s = s[:size].strip()
            break
    if len(s) > MAX_DESC:
        cut = s[:MAX_DESC]
        # 优先在句子边界收尾，避免把句子从中间切断
        for sep in ("。", "！", "？", "; ", ". ", ".", ";"):
            pos = cut.rfind(sep)
            if pos >= MAX_DESC * 0.6:
                return cut[: pos + len(sep)].strip().replace("|", "\\|")
        s = cut.rstrip(" ,，、;；") + "…"
    return s.replace("|", "\\|")


def short_date(iso):
    try:
        return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return "—"


def build_readme(repos):
    rows = []
    for i, r in enumerate(repos, 1):
        lang = f"`{r['language']}`" if r.get("language") else "—"
        stars = r.get("stargazers_count", 0)
        rows.append(
            "| {i} | [{name}]({url}) | {desc} | {lang} | {stars} | {updated} |".format(
                i=i,
                name=r["name"],
                url=r["html_url"],
                desc=clean_desc(r.get("description")),
                lang=lang,
                stars=f"⭐ {stars}" if stars else "—",
                updated=short_date(r.get("updated_at")),
            )
        )

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = len(repos)

    return f"""<div align="center">

# 專案合集

自製工具與實驗專案 · 全部開源 · 共 {total} 個

[![Repos](https://img.shields.io/badge/repos-{total}-blue?style=flat-square)](https://github.com/{USERNAME}?tab=repositories)

</div>

| # | 專案 | 說明 | 語言 | ⭐ | 最近更新 |
|:-:|:-----|:-----|:-----|:-:|:---------|
{os.linesep.join(rows)}

---

<sub>本清單由 GitHub Actions 每小時自動同步，最後更新於 {stamp} · <a href="https://github.com/{USERNAME}/{USERNAME}/actions">執行記錄</a></sub>
"""


def main():
    repos = [
        r
        for r in fetch_all_repos()
        if r["name"].lower() not in EXCLUDE and not r.get("fork")
    ]
    repos.sort(key=lambda r: r.get("updated_at") or "", reverse=True)

    content = build_readme(repos)

    if os.path.exists(OUT_FILE):
        with open(OUT_FILE, encoding="utf-8") as f:
            if f.read() == content:
                print(f"未變更，跳過寫入（共 {len(repos)} 個專案）")
                return
        status = "已更新"
    else:
        status = "已建立"

    with open(OUT_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print(f"{status} {OUT_FILE}（共 {len(repos)} 個專案）")


if __name__ == "__main__":
    main()
