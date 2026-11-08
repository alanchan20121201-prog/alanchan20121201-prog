#!/usr/bin/env python3
"""扫描账号下的公开仓库，生成四语言 README.md。

新仓库第一次出现时会自动翻译成四语言，结果记入 descriptions.json；
翻译失败则回落到 GitHub 上的原始描述，不影响 README 生成。

译者走 OpenAI 兼容接口，默认智谱 GLM-4-Flash（免费额度）。没配 LLM_API_KEY 时
跳过翻译、直接显示原文，不会报错。

本地运行（默认不翻译，避免污染数据）：
    GH_TOKEN=$(gh auth token) python scripts/generate.py
启用自动翻译：
    GH_TOKEN=$(gh auth token) LLM_API_KEY=xxx AUTO_TRANSLATE=1 python scripts/generate.py
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime

# 允许从任意工作目录运行本脚本
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import i18n  # noqa: E402

USERNAME = "alanchan20121201-prog"
OUT_FILE = "README.md"

# 这些仓库不上榜：profile 仓库自身、以及其他你不想展示的
EXCLUDE = {USERNAME.lower(), ".github"}

MAX_DESC = 110
# 一次跑只翻一个仓库，避免拖长任务耗时（失败的下次定时任务会重试）
MAX_TRANSLATE_PER_RUN = 1

HERE = os.path.dirname(os.path.abspath(__file__))
DESC_FILE = os.path.join(HERE, "descriptions.json")

# 翻译走任意 OpenAI 兼容接口，默认智谱 GLM-4-Flash（免费、国内直连、无需信用卡）。
# 想换供应商只改 LLM_BASE_URL / LLM_MODEL 两个 secret，代码不用动。
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
LLM_MODEL = os.environ.get("LLM_MODEL", "glm-4-flash")

PROMPT = """Translate this GitHub repository description into 4 locales.

Original description: {desc}

Locales:
- zh-cn: Simplified Chinese
- zh-tw: Traditional Chinese (Taiwan)
- en: English
- ja: Japanese

Rules:
- Under 100 characters
- Keep technical terms, product names and version numbers unchanged
- Describe what it does, no marketing fluff
- Do not invent facts absent from the original

Return ONLY a JSON object with keys "zh-cn", "zh-tw", "en", "ja". No markdown fence."""


def token():
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def api_get(url):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USERNAME,
    }
    tk = token()
    if tk:
        headers["Authorization"] = f"Bearer {tk}"
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
    """去掉重复粘贴的描述、超长截断。不转义竖线，留给表格渲染处理。"""
    if not text:
        return "—"
    s = re.sub(r"\s+", " ", text).strip()
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
                return cut[: pos + len(sep)].strip()
        s = cut.rstrip(" ,，、;；") + "…"
    return s


def cell(text):
    """Markdown 表格单元格转义。"""
    return text.replace("|", "\\|")


def short_date(iso):
    try:
        return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return "—"


def load_descriptions():
    if not os.path.exists(DESC_FILE):
        return {}
    with open(DESC_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_descriptions(data):
    with open(DESC_FILE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _chat(key, prompt):
    """调 OpenAI 兼容接口，返回文本或 None。"""
    body = json.dumps(
        {
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 800,
        }
    ).encode()
    req = urllib.request.Request(
        f"{LLM_BASE_URL}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        print(f"      请求失败：{exc}")
        return None


def translate(desc):
    """一次请求拿到四语言结果；没配 key 或解析失败都返回 None。"""
    key = os.environ.get("LLM_API_KEY")
    if not key:
        print("      未配置 LLM_API_KEY，跳过翻译")
        return None

    raw = _chat(key, PROMPT.format(desc=desc))
    if not raw:
        return None

    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip()).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        print(f"      无法解析响应：{raw[:120]}")
        return None

    out = {}
    for code in i18n.LANGS:
        v = payload.get(code)
        if not isinstance(v, str) or not v.strip():
            print(f"      缺少语言 {code}")
            return None
        out[code] = re.sub(r"\s+", " ", v).strip()
    return out


def sync_translations(repos, descs):
    """给缺少翻译、或 GitHub 上描述已改动的仓库补翻译。返回是否有改动。"""
    dirty = False
    budget = MAX_TRANSLATE_PER_RUN

    for r in repos:
        if budget <= 0:
            print(f"    本轮翻译已达上限 {MAX_TRANSLATE_PER_RUN} 个，其余下次继续")
            break

        name = r["name"]
        src = (r.get("description") or "").strip()
        if not src:
            continue

        entry = descs.get(name) or {}
        if entry.get("_source") == src and all(entry.get(c) for c in i18n.LANGS):
            continue

        print(f"    翻译 {name} ...")
        got = translate(src)
        budget -= 1
        if got:
            got["_source"] = src
            descs[name] = got
            dirty = True
            print(f"      ✓ {got['en'][:50]}")
        else:
            print("      ✗ 翻译失败，本次回落原文")

    return dirty


def build_readme(repos, descs):
    total = len(repos)

    # GitHub 会给 HTML 锚点 id 加上 user-content- 前缀，链接必须照着写
    nav = " · ".join(
        f'<a href="#user-content-{code}">{i18n.LANG_LABEL[code]}</a>'
        for code in i18n.LANGS
    )

    blocks = []
    for code in i18n.LANGS:
        ui = i18n.UI[code]
        rows = []
        for i, r in enumerate(repos, 1):
            lang = f"`{r['language']}`" if r.get("language") else "—"
            stars = r.get("stargazers_count", 0)
            # 优先用已翻译的描述；没有则回落 GitHub 上的原文
            desc = (descs.get(r["name"]) or {}).get(code) or clean_desc(
                r.get("description")
            )
            rows.append(
                "| {i} | [{name}]({url}) | {desc} | {lang} | {stars} | {updated} |".format(
                    i=i,
                    name=r["name"],
                    url=r["html_url"],
                    desc=cell(desc),
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

<sub>Auto-synced every 15 min by GitHub Actions · 每 15 分鐘自動同步 · <a href="https://github.com/{USERNAME}/{USERNAME}/actions">Actions</a></sub>
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

    descs = load_descriptions()

    if os.environ.get("AUTO_TRANSLATE") == "1":
        if sync_translations(repos, descs):
            save_descriptions(descs)

    content = build_readme(repos, descs)

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
