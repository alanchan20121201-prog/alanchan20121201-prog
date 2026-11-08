"""四语言界面文案与仓库描述翻译。

新增仓库不需要改这个文件：未收录的仓库会自动回落到 GitHub 上的原始描述。
想给它配四语言描述时，在 DESCRIPTIONS 里加一項即可。
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
        "cols": ["#", "项目", "说明", "语言", "⭐", "最近更新"],
    },
    "zh-tw": {
        "title": "專案合集",
        "tagline": "自製工具與實驗專案 · 全部開源 · 共 {count} 個",
        "cols": ["#", "專案", "說明", "語言", "⭐", "最近更新"],
    },
    "en": {
        "title": "Projects",
        "tagline": "Self-built tools and experiments · All open source · {count} in total",
        "cols": ["#", "Project", "Description", "Language", "⭐", "Updated"],
    },
    "ja": {
        "title": "プロジェクト",
        "tagline": "自作ツールと実験プロジェクト · すべてオープンソース · 全 {count} 件",
        "cols": ["#", "プロジェクト", "説明", "言語", "⭐", "更新日"],
    },
}

# 仓库名 -> 四语言描述。未收录的仓库回落到 GitHub 上的原始描述。
DESCRIPTIONS = {
    "GhostNote": {
        "zh-cn": "把一句话像水印一样刻在桌面上，永远置顶、鼠标穿透的 Windows 小工具（.NET 8 + WPF）",
        "zh-tw": "把一句話像浮水印般刻在桌面上，永遠置頂、滑鼠穿透的 Windows 小工具（.NET 8 + WPF）",
        "en": "Etch a line of text onto your desktop like a watermark — always on top, click-through (.NET 8 + WPF)",
        "ja": "テキストを透かしのようにデスクトップに刻む Windows ツール。常に最前面、マウス貫通（.NET 8 + WPF）",
    },
    "TopMostPin": {
        "zh-cn": "Windows 托盘小工具：Ctrl+Alt+L 一键把指定窗口锁定置顶，带高亮边框",
        "zh-tw": "Windows 托盤小工具：Ctrl+Alt+L 一鍵把指定視窗鎖定置頂，帶高亮邊框",
        "en": "Tray utility — press Ctrl+Alt+L to pin any window on top, with a highlight border",
        "ja": "常駐ツール。Ctrl+Alt+L で任意のウィンドウを最前面に固定、ハイライト枠付き",
    },
    "nanotimer": {
        "zh-cn": "无边框透明悬浮的倒计时／秒表／番茄钟，四种显示模式、四语言、内置更新",
        "zh-tw": "無邊框透明懸浮的倒數計時／碼錶／番茄鐘，四種顯示模式、四語言、內建更新",
        "en": "Frameless transparent floating countdown / stopwatch / Pomodoro timer. Four display modes, four languages, in-app updates",
        "ja": "枠なし・透明のフローティング式カウントダウン／ストップウォッチ／ポモドーロ。4 表示モード、4 言語、アプリ内更新",
    },
    "CoreFactory": {
        "zh-cn": "用 AI 制作的游戏",
        "zh-tw": "用 AI 製作的遊戲",
        "en": "A game built with AI",
        "ja": "AI を使って制作したゲーム",
    },
    "Toolbox": {
        "zh-cn": "多功能工具箱",
        "zh-tw": "多功能工具箱",
        "en": "A versatile toolbox",
        "ja": "多機能ツールボックス",
    },
    "File-Transfer": {
        "zh-cn": "免登录、免云端的局域网互传工具，同一 Wi-Fi 下电脑与手机互传文字和任意文件",
        "zh-tw": "免登入、免雲端的區域網路互傳工具，同一 Wi-Fi 下電腦與手機互傳文字和任意檔案",
        "en": "Share text and files between PCs and phones on the same Wi-Fi — no login, no cloud, no install",
        "ja": "同じ Wi-Fi 内で PC とスマホ間のテキスト・ファイル転送。ログイン不要、クラウド不要",
    },
    "Password-Generator": {
        "zh-cn": "纯本地运行的密码生成器、强度分析与密码保险库，中英双语界面，数据完全不上传",
        "zh-tw": "純本機執行的密碼產生器、強度分析與密碼保險庫，中英雙語介面，資料完全不上傳",
        "en": "Local-only password generator, strength analyzer and secure vault. Bilingual UI, zero uploads",
        "ja": "完全ローカル動作のパスワード生成・強度分析・保管庫。多言語 UI、データ送信なし",
    },
    "Note-app": {
        "zh-cn": "极简、本地优先的桌面笔记软件（Electron），内置回收站与便携版 exe",
        "zh-tw": "極簡、本地優先的桌面筆記軟體（Electron），內建回收筒與可攜版 exe",
        "en": "Minimalist local-first desktop note-taking app (Electron) with built-in trash bin and portable exe",
        "ja": "ミニマルなローカル優先デスクトップメモ帳（Electron）。ゴミ箱機能とポータブル exe 付き",
    },
    "Chinese-English-bilingual-translation": {
        "zh-cn": "极简风格的单文件中英双向翻译网页，支持界面切换、一键复制与快速清空",
        "zh-tw": "極簡風格的單檔案中英雙向翻譯網頁，支援介面切換、一鍵複製與快速清空",
        "en": "Minimalist single-file Chinese–English bidirectional translation page with one-click copy and quick clear",
        "ja": "ミニマルな単一ファイルの中英双方向翻訳ページ。ワンクリックコピー、クイッククリア対応",
    },
}
