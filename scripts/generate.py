#!/usr/bin/env python3
"""扫描账号下的公开仓库，生成 README.md 总表。

本地运行：
    GH_TOKEN=$(gh auth token) python scripts/generate.py
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

# 允许从任意工作目录运行本脚本
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import i18n  # noqa: E402

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
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = len(repos)

    nav = " · ".join(
        f'<a href="#{code}">{i18n.LANG_LABEL[code]}</a>' for code in i18n.LANGS
    )

    blocks = []
    for code in i18n.LANGS:
        ui = i18n.UI[code]
        rows = []
        for i, r in enumerate(repos, 1):
            lang = f"`{r['language']}`" if r.get("language") else "—"
            stars = r.get("stargazers_count", 0)
            # 优先用手写翻译；没有就用 GitHub 上的原始描述
            desc = i18n.DESCRIPTIONS.get(r["name"], {}).get(code) or clean_desc(
                r.get("description")
            )
            rows.append(
                "| {i} | [{name}]({url}) | {desc} | {lang} | {stars} | {updated} |".format(
                    i=i,
                    name=r["name"],
                    url=r["html_url"],
                    desc=desc,
                    lang=lang,
                    stars=f"⭐ {stars}" if stars else "—",
                    updated=short_date(r.get("updated_at")),
                )
            )

        header = "| " + " | ".join(ui["cols"]) + " |"
        blocks.append(
            f'<a id="{code}"></a>\n\n'
            f"## {i18n.LANG_LABEL[code]}\n\n"
            f'{ui["tagline"].format(count=total)}\n\n'
            f"{header}\n|:-:|:--|:--|:--|:-:|:--|\n" + "\n".join(rows)
        )

    sep = "\n\n---\n\n"
    titles = " · ".join(i18n.UI[c]["title"] for c in i18n.LANGS)

    return f"""<div align="center">

# {titles}

{nav}

[![Repos](https://img.shields.io/badge/repos-{total}-blue?style=flat-square)](https://github.com/{USERNAME}?tab=repositories)

</div>

---

{sep.join(blocks)}

---

<sub>Auto-synced every 15 min by GitHub Actions · 每 15 分鐘自動同步 · 最后更新 {stamp} · <a href="https://github.com/{USERNAME}/{USERNAME}/actions">Actions</a></sub>
"""


def main():
    repos = [
        r
        for r in fetch_all_repos()
        if r["name"].lower() not in EXCLUDE
        # 过滤 fork
        and not r.get("fork")
        # 只收公开仓库：带 token 请求 /users/{name}/repos 会返回自己的 private 仓库，
        # 一旦上榜就等于把仓库名公开泄露，务必保留这道判断
        and not r.get("private")
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
