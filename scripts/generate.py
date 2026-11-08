#!/usr/bin/env python3
"""扫描账号下的公开仓库，生成四语言 README.md。

新仓库第一次出现时会自动翻译成四语言，结果记入 descriptions.json；
翻译失败则回落到 GitHub 上的原始描述，不影响 README 生成。

译者走智谱（国内少数不卡实名认证的平台）。没配 LLM_API_KEY 时跳过翻译、
直接显示原文，不会报错。

本地运行（默认不翻译，避免污染数据）：
    GH_TOKEN=$(gh auth token) python scripts/generate.py
启用自动翻译：
    GH_TOKEN=$(gh auth token) LLM_API_KEY=xxx AUTO_TRANSLATE=1 python scripts/generate.py
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

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

# 翻译走智谱。国内几家免费平台（硅基流动 / ModelScope / 阿里百炼）都卡实名认证，
# 智谱是目前唯一验证可用的。glm-5.3-flash 是最便宜的一档：输入 0.8 元、输出 2.8 元
# 每百万 tokens，单次翻译约 0.0004 元；新账号还送 2000 万 tokens，实际支出接近零。
# 换供应商只设 LLM_BASE_URL 这一个 secret，代码不用动。
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")

# 两档模型，都是官方免费的：
#   QUALITY_MODEL 质量好，但访问量极大、经常 429（只静等，不硬撞，避免触发账户限流）
#   DRAFT_MODEL   视觉模型，翻得糙但基本不挤，用来先出一版草稿保证有内容
# 策略：新仓库先用草稿模型立即上表，之后每次定时任务试一次质量模型，
# 抢到名额就自动覆盖成高质量版。全程零成本。
QUALITY_MODEL = "glm-4.7-flash"
DRAFT_MODEL = "glm-4.6v-flash"

LANG_NAMES = {
    "zh-cn": "简体中文",
    "zh-tw": "繁体中文",
    "en": "英语",
    "ja": "日语",
}

# 逐语言调用，比一次性吐 JSON 更稳。最后一句约束字形，防止简繁混用
# （实测免费模型容易把「区域网络」写成「區域网络」、「传檔」这种半简半繁）
MT_PROMPT = """把下面的文本翻译成{tlang}，只输出译文本身，不要解释，不要加引号。

要求：
- 全文必须统一使用{tlang}的标准字形，不要混入简体字或繁体字
- 专有名词、技术术语、版本号保持原样
- 不要添加原文没有的信息

原文：
{text}"""


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


# release 标题常写成「ClipHist v1.0.0」这类，只截取其中的版本号片段
VERSION_RE = re.compile(r"v?\d+(?:\.\d+){0,3}", re.I)


def fetch_version(full_name):
    """取「发布页」最新正式 release 里的版本号。

    优先看 release 标题（name，常是「项目名 v1.2.3」），再看 tag 名；
    都找不到版本号片段就返回 None，表格显示「—」。
    """
    try:
        rel = api_get(f"https://api.github.com/repos/{full_name}/releases/latest")
    except Exception:
        return None  # 没发过 release 会 404，正常
    for cand in (rel.get("name"), rel.get("tag_name")):
        if cand:
            m = VERSION_RE.search(str(cand))
            if m:
                return m.group()
    return None


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


CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
LATIN_RE = re.compile(r"[A-Za-z]")


def split_languages(text):
    """把中英混排的描述按句子拆开、同语言合并，返回 {lang: 文本}。"""
    # 先按竖线/换行/句末标点切句。最后一条专门处理「英文句号紧跟中文」
    # 这种没空格的情况（例："no cloud.區網快傳…"），否则中英会黏成一句。
    raw = re.split(
        r"[|\n]+|(?<=[。！？；])|(?<=[.!?;])(?=\s|$)|(?<=[.!?])(?=[\u4e00-\u9fff])",
        text,
    )
    buckets = {}
    for seg in raw:
        seg = seg.strip()
        if len(seg) < 4:
            continue
        cjk = len(CJK_RE.findall(seg))
        latin = len(LATIN_RE.findall(seg))
        if cjk == 0 and latin == 0:
            continue
        lang = "zh" if cjk >= latin else "en"
        buckets.setdefault(lang, []).append(seg)

    # 中文句子直接拼接（加空格反而难看），英文用空格分隔
    return {
        k: ("" if k == "zh" else " ").join(v).strip() for k, v in buckets.items()
    }


def pick_source(desc):
    """中英混排时拆开，取信息量最大的单语段作为翻译源。

    仓库描述常见「英文一句 + 中文一句」互为翻译的写法，整段丢给模型
    只会翻一半，出来还是半中半英。这里先分离，再挑内容最全的一段。
    """
    parts = split_languages(desc)
    if len(parts) <= 1:
        return desc, list(parts)

    ranked = sorted(parts.items(), key=lambda kv: len(kv[1]), reverse=True)
    top_len = len(ranked[0][1])

    # 两段长度接近（差 25% 内）时优先用中文：母语描述通常写得更细
    picked = ranked[0]
    for lang, text in ranked:
        if lang == "zh" and len(text) >= top_len * 0.75:
            picked = (lang, text)
            break

    print(f"      检测到 {'/'.join(sorted(parts))} 混排，取 {picked[0]} 段作源")
    return picked[1], ranked


def short_date(iso):
    """ISO 时间转本地日期（UTC+8）。

    GitHub 返回的是 UTC，直接截日期会让凌晨的提交显示成前一天，所以先转时区。
    """
    try:
        return (
            datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=timezone.utc)
            .astimezone(timezone(timedelta(hours=8)))
            .strftime("%Y-%m-%d")
        )
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


def _chat(key, prompt, model, max_tokens=1200, retries=1):
    """调 OpenAI 兼容接口，返回文本或 None。

    两个坑：
    1. 智谱 glm-5 系列是推理模型，先输出 reasoning_content 再给 content。
       max_tokens 太小会被思考吃光、content 变空串，所以给得宽松（答完即 stop）。
    2. 免费模型（glm-4.7-flash）常年 429。这里**故意不重试**——密集重试会升级成
       账户级限流（1302），反而更糟。429 就返回 None，交给下一次定时任务再试。
    """
    for attempt in range(retries):
        body = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": max_tokens,
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
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < retries - 1:
                time.sleep(5 * (attempt + 1))  # 免费模型拥挤，退避后重试
                continue
            print(f"      {model}: HTTP {exc.code}")
            return None
        except Exception as exc:
            print(f"      {model}: {exc}")
            return None
    return None


def _translate_one(key, model, text, tlang):
    """让模型把 text 译成 tlang，返回干净译文或 None。"""
    raw = _chat(key, MT_PROMPT.format(tlang=tlang, text=text), model)
    if not raw:
        return None
    s = raw.strip()
    # 有些模型会回「译文：xxx」或者包一层引号，清掉
    s = re.sub(r"^(译文|翻译|Translation)\s*[:：]\s*", "", s, flags=re.I)
    s = s.strip().strip('"').strip("「」").strip()
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def _translate_with(key, model, src):
    """用指定模型把 src 翻成四语言，任一语言失败就整体放弃。"""
    out = {}
    for code in i18n.LANGS:
        got = _translate_one(key, model, src, LANG_NAMES[code])
        if not got:
            print(f"      {model} 译 {LANG_NAMES[code]} 失败")
            return None
        out[code] = got
    return out


def translate(desc, quality_only=False):
    """翻译成四语言，返回 (结果, 是否草稿)；失败返回 (None, False)。

    先用质量模型，抢不到名额时（除非 quality_only）再用草稿模型兜底，
    保证新仓库至少立刻有内容。
    """
    key = os.environ.get("LLM_API_KEY")
    if not key:
        print("      未配置 LLM_API_KEY，跳过翻译")
        return None, False

    # 中英混排的描述先拆开，只拿单语的那段去翻，避免译出来还是半中半英
    src, _parts = pick_source(desc)

    override = os.environ.get("LLM_MODEL")
    if override:
        out = _translate_with(key, override, src)
        return (out, False) if out else (None, False)

    out = _translate_with(key, QUALITY_MODEL, src)
    if out:
        print(f"      使用 {QUALITY_MODEL}（免费·高质量）")
        return out, False

    if quality_only:
        return None, False  # 已有草稿，只等升级，不重复出草稿

    out = _translate_with(key, DRAFT_MODEL, src)
    if out:
        print(f"      使用 {DRAFT_MODEL}（免费·草稿，后续自动升级）")
        return out, True

    return None, False


def sync_translations(repos, descs):
    """给缺少翻译、描述已改动、或是草稿状态的仓库做翻译。返回是否有改动。"""
    dirty = False
    budget = MAX_TRANSLATE_PER_RUN

    for r in repos:
        if budget <= 0:
            print(f"    本轮处理达上限 {MAX_TRANSLATE_PER_RUN} 个，其余下次继续")
            break

        name = r["name"]
        src = (r.get("description") or "").strip()
        if not src:
            continue

        entry = descs.get(name) or {}
        is_draft = bool(entry.get("_draft")) and entry.get("_source") == src
        done = (
            entry.get("_source") == src
            and all(entry.get(c) for c in i18n.LANGS)
            and not is_draft
        )
        if done:
            continue

        print(f"    {'升级草稿' if is_draft else '翻译'} {name} ...")
        got, draft = translate(src, quality_only=is_draft)
        budget -= 1
        if got:
            got["_source"] = src
            if draft:
                got["_draft"] = True
            descs[name] = got
            dirty = True
            print(f"      ✓ {got['en'][:50]}")
        else:
            print("      · 本次未抢到名额，下次定时任务再试")

    return dirty


def build_readme(repos, descs):
    total = len(repos)

    # GitHub 会给 HTML 锚点 id 加上 user-content- 前缀，链接必须照着写
    nav = " · ".join(
        f'<a href="#user-content-{code}">{i18n.LANG_LABEL[code]}</a>'
        for code in i18n.LANGS
    )

    # 各语言表下方标注的生成时间（本地 UTC+8），让用户知道数据新鲜度
    GEN_TIME = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    GEN_LABEL = {
        "zh-cn": "最后更新",
        "zh-tw": "最後更新",
        "en": "Last updated",
        "ja": "最終更新",
    }

    # 版本号只查一次，四个语言表共用（不然同一仓库会重复请求四遍）
    versions = {}
    for r in repos:
        versions[r["name"]] = fetch_version(r["full_name"]) or "—"

    blocks = []
    for code in i18n.LANGS:
        ui = i18n.UI[code]
        rows = []
        for i, r in enumerate(repos, 1):
            lang = f"`{r['language']}`" if r.get("language") else "—"
            # GitHub 对无法识别的授权文件会回 NOASSERTION，这种情况不显示
            spdx = (r.get("license") or {}).get("spdx_id") or ""
            lic = f"`{spdx}`" if spdx and spdx != "NOASSERTION" else ""
            # 许可证跟在项目名后面，紧凑又不占单独一列
            name_cell = f"[{r['name']}]({r['html_url']}){' ' + lic if lic else ''}"
            ver = versions[r["name"]]
            # 优先用已翻译的描述；没有则回落 GitHub 上的原文
            desc = (descs.get(r["name"]) or {}).get(code) or clean_desc(
                r.get("description")
            )
            rows.append(
                "| {i} | {name} | {desc} | {lang} | {ver} | {updated} |".format(
                    i=i,
                    name=name_cell,
                    desc=cell(desc),
                    lang=lang,
                    ver=f"`{ver}`" if ver != "—" else "—",
                    # 用 pushed_at（代码最后提交）而不是 updated_at（改描述、改设置都会刷新）
                    updated=short_date(r.get("pushed_at") or r.get("updated_at")),
                )
            )

        header = "| " + " | ".join(ui["cols"]) + " |"
        blocks.append(
            f'<a id="{code}"></a>\n\n'
            f"## {i18n.LANG_LABEL[code]}\n\n"
            f'{ui["tagline"].format(count=total)}\n\n'
            f"{header}\n|:-:|:--|:--|:--|:-:|:--|\n"
            + "\n".join(rows)
            + f"\n\n> {GEN_LABEL[code]}：{GEN_TIME:%Y-%m-%d %H:%M}（UTC+8）"
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
    # 与表格里的「最近更新」保持一致，按代码提交时间排
    repos.sort(key=lambda r: r.get("pushed_at") or r.get("updated_at") or "", reverse=True)

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
