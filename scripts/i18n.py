"""四语言界面文案。

仓库描述不在这里——它们存在 descriptions.json 里，由脚本自动维护：
新仓库第一次出现时会调用 GitHub Models 自动翻译并写回该文件。
"""

LANGS = ["zh-cn", "zh-tw", "en", "ja"]

LANG_LABEL = {
    "zh-cn": "简体中文",
    "zh-tw": "繁體中文",
    "en": "English",
    "ja": "日本語",
}

UI = {
    "zh-cn": {
        "title": "项目合集",
        "tagline": "自制工具与实验项目 · 全部开源 · 共 {count} 个",
        "cols": ["#", "项目", "说明", "语言", "版本", "最近更新"],
    },
    "zh-tw": {
        "title": "專案合集",
        "tagline": "自製工具與實驗專案 · 全部開源 · 共 {count} 個",
        "cols": ["#", "專案", "說明", "語言", "版本", "最近更新"],
    },
    "en": {
        "title": "Projects",
        "tagline": "Self-built tools and experiments · All open source · {count} in total",
        "cols": ["#", "Project", "Description", "Language", "Version", "Updated"],
    },
    "ja": {
        "title": "プロジェクト",
        "tagline": "自作ツールと実験プロジェクト · すべてオープンソース · 全 {count} 件",
        "cols": ["#", "プロジェクト", "説明", "言語", "バージョン", "更新日"],
    },
}
