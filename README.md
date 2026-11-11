# bookpage

把一本书的一个主题，编译成**一张离线可开的交互教学页**。

模型只写结构化 IR（JSON），渲染器负责把它变成 HTML —— 因此同一份 IR 两次构建**字节级相同**，
不需要模板抄写、不需要浏览器、不需要任何第三方包。

- 设计稿：[output/2026-11-10/bookpage-design.md](../../output/2026-11-10/bookpage-design.md)
- 逆向对象：book-to-webpage（见 [output/2026-11-10/book-to-webpage-reverse-engineering.md](../../output/2026-11-10/book-to-webpage-reverse-engineering.md)）
- 代码：单文件 `bookpage.py`（约 1000 行，纯 Python 标准库）

## 作为 skill 安装

本目录同时是一个 DSH skill：`SKILL.md` 是模型侧说明（触发条件、IR 契约、错误码、流程），
`bookpage.py` 是它调用的渲染器。安装即把整目录放进技能目录：

```bash
cp -r projects/bookpage ~/.dsh/skills/bookpage    # 或推到私有仓库后用 git URL 安装
```

安装后 skill 目录里出现 `bookpage` 条目；模型负责产 IR，渲染器负责落盘，
`out/` 与 `contracts.txt` 这类工作产物不必带过去。

与 `book-to-webpage` 的分工：那个是一次性交付的“手工拼版”路径，这个是可复现的“IR + 渲染”路径，
两者可共存；概览（overview）与速读（reader）两种单页形态只有 bookpage 支持。

## 用法

```bash
# 校验 IR：结构与字段约束，错误带错误码与字段路径
python bookpage.py lint demo.json

# 渲染：<ir.json> <out.html>
python bookpage.py build demo.json out/demo.html

# 全书概览模式（mode=overview，单页滚动、无 tab）：框架 / 章节地图 / 概念地图 / 决策规则
python bookpage.py build demo-overview.json out/demo-overview.html

# 速读模式（mode=reader）：全书判断卡 + 概念网格 + 目录 + 章节卡 + 搜索 + 原文折叠
python bookpage.py build demo-reader.json out/demo-reader.html

# 拆书：按章切成 ch-01.md … + index.json（去页眉/许可证/章末注释，无标题时按 6,000 字等分）
python bookpage.py split 书.txt -o chapters/

# 模板校验失败但仍想看效果：把出错的 section 降级成 prose，并留 <!-- degraded -->
python bookpage.py build demo.json out/demo.html --degrade

# 中文感知的 token 估算（对比上游按空格切词的实现）
python bookpage.py tokens tests/sample-book.md

# 中文章节计数：第N章 / 第N回 / Chapter N
python bookpage.py chapters tests/sample-book.md

# 书源 → 纯文本：docx/epub 零依赖；pdf 需 pypdf；mobi/azw3 需 calibre
python bookpage.py extract 某本书.epub -o full_text.txt
```

退出码：`0` 成功、`1` IR 校验失败、`2` 参数或读文件错误。

## 自检

```bash
python tests/selftest.py
```

九条断言全部可复跑，不依赖浏览器与 pip（A1–A7、A9 跑 `tests/selftest.py`，A8 跑 `tests/test_golden.py`）：

| 编号 | 断言 | 现状 |
| --- | --- | --- |
| A1 | 同一 IR 两次构建 sha256 相同 | PASS（`42a8d1400d5bb007…`，27,221 bytes） |
| A2 | 未知 signature → 退出码 1，报 E101 且指出 `sections[i].signature` | PASS |
| A3 | 缺必需键 → 退出码 1，报 E102 且指出键名 | PASS |
| A4 | 中文样书章节计数 = 8 | PASS 8/8 |
| A5 | 中文 token 估算 ≥ 上游算法的 8 倍 | PASS：3,379 vs 202（约 17 倍） |
| A6 | 产物无 `{{`、tab↔panel 与 section 一一对齐、无外部引用（离线可开） | PASS |
| A7 | 剥离 PYTHON* 变量 + `-I` 隔离下仍能构建 | PASS（27,221 bytes） |
| A8 | 金标准回归：五份样例 IR（demo / all / overview / reader / 庄子 reader）哈希钉死 + 12 个组件标记齐备 | PASS（demo `b318941435…` / all `e1dfcc06e2…` / overview `db273747f0…` / reader `6c34affdea…` / zhuangzi `7ce9155c25…`，12/12） |
| A9 | 书源提取：epub（按 spine 顺序）/docx（zipfile+XML）/纯文本，章节计数正确；pdf、mobi 缺依赖或解析失败时 rc=2 并说明原因；本机同时有 pypdf+reportlab 时再跑一份真 PDF | PASS（公版书 epub 46,157 字符 / 9 章；真 PDF 3 章） |
| A10 | overview 模式：四区块渲染、两次构建同哈希、无 tab/panel、无外部引用；空区块报 E102、误写 sections 报 E100、非法 relation 被拒 | PASS（`29e816814f31e5a2…`，三条拒绝路径） |
| A11 | reader 模式 + split：样书切出 8 章（文件数与 index 一致、每文件有标题行)、reader 两次构建同哈希、无 tab、有目录与搜索框、digest 卡与概念卡数量与 IR 一致、digest 的章号引用数与 IR 一致且不指向空锚点、无外部引用；无标题书回退到等分切 | PASS（8 章 / `35f69bba96…` / 等分回退） |

## 视觉验证

本机没有 playwright，改用系统自带的 Edge 无头模式截图，命令可复跑：

```bash
msedge --headless=new --disable-gpu --hide-scrollbars \
  --screenshot=out/shot.png --window-size=1280,1600 \
  "file:///<绝对路径>/out/demo.html"
```

已核对四个视角（截图在 `out/` 与 `../../output/2026-11-10/`）：

| 视角 | 结果 |
| A12 | 论证主线 + 已读标记：`thread` 环数与 IR 一致、主线章号锚点不悬空、`class="mark"` 按钮数 == 章节数、`id="rRead"` 计数器存在、内联 JS 含 localStorage 且无箭头函数、两次构建同哈希 | PASS（5 环 / 9 个按钮 / `7f44eb9f9b…`） |
| --- | --- |
| 首屏（因果链面板） | 标题衬线、hero 判断条、7 个 tab 一行排开、四步卡片等宽 |
| 矩阵面板（tab 2） | 表头「模式 / 启动资金 / 回款方式 / 主要风险」与 4 行数据对齐，首列底色区分 |
| 前后对比（tab 5） | 双栏等宽、左侧税收财政 / 右侧土地财政，竖线分隔 |
| 深色主题（`theme: dark`，同一份 IR） | 底色、正文、卡片边框、tab 选中态均正确反相，无对比度塌陷 |

矩阵与深色两张截图是“把 active 面板换到第 N 个”后的同一份产物 —— 顺带验证了 tab 选中态与面板内容在运行时保持一致。
## IR 最小样例

```json
{
  "schema": "bookpage/1",
  "meta": {"book": "置身事内", "author": "兰小欢", "mode": "theme",
           "theme": "paper", "topic": "房地产与地方财政", "sources": ["第 4 章 土地财政"]},
  "hero": {"eyebrow": "第三章 · 土地与财政", "title": "土地财政是怎么转起来的",
           "lede": "（60–140 字，钩子）", "thesis": "（≤60 字，核心判断）"},
  "sections": [
    {"id": "s1", "label": "钱从哪来", "signature": "causal_chain", "lead": "段首引语",
     "source": "第 1 章", "data": {"steps": [{"title": "分税制", "text": "…", "detail": "…"}]}}
  ],
  "questions": [{"q": "（≤40 字）", "hint": "（≤60 字）"}]
}
```

`signature` 是枚举白名单，拼错即被 lint 拒绝 —— 这正是上游“让模型直接拼 DOM”的失败面。

书源侧补了 `extract`：`docx`、`epub` 用标准库直读（epub 按 OPF spine 顺序，不是按文件名字典序），
`pdf` 需 `pypdf`、`mobi/azw3` 需 calibre —— 缺依赖时以退出码 2 明确说缺什么，不产出空文本。
同一本公版书走 `.epub` 与 `.txt` 两条路径，字符数 46,157 vs 46,497、章节数均为 9。

## 三种模式

| mode | 页面形态 | 结构 | 什么时候用 |
| --- | --- | --- | --- |
| `theme`（默认） | 顶部 sticky tab + 分节面板，每节一个组件 | `sections[]` 4–7 节 | 讲透某个主题、某个机制 |
| `overview` | 单页滚动，无 tab、无 JS 依赖 | `frameworks` / `chapterMap` / `conceptMap` / `decisionRules` 至少其一 | 先看全书骨架再决定读哪 |
| `reader` | 单页滚动：全书判断卡 + 概念网格 + 论证主线 + 左侧 sticky 目录 + 章节卡 + 搜索框 + 滚动进度 + 已读标记 | `digest[]` 3–5 条（每条可带 `refs` 章号）、`concepts[]` 2–6 组、`thread[]` 3–6 环（可选）、`chapters[]` 3–40 章（role/gist/points/quote/text） | **快速理解一本书**：先看全书在说什么，再按章扫读、点开原文核对 |

## 组件（12 个，含 `prose` 逃生口）

| signature | data 必需键 | 交互 |
| --- | --- | --- |
| `causal_chain` | `steps`（2–6：title ≤10 字、text ≤120、detail ≤160） | 点步骤，右侧展开 detail |
| `type_selector` | `types`（2–5：name ≤8、tagline ≤20、text ≤120） | 点按钮换说明 |
| `matrix` | `cols`（2–4 数据列）+`rows`（2–6，cells 数须与 cols 等长，可选 `label_header`） | 屏读，行悬停高亮 |
| `timeline` | `items`（3–8：when ≤12、title ≤16、text ≤100） | 屏读，左侧竖线 |
| `decision_tree` | `root`（q ≤60，options 2–3，每项 `result` 或 `next`，深度 ≤3） | 点选项走分支 |
| `questions` | `items`（2–6：q ≤40、hint ≤60） | 点开答案 |
| `story_card` | `title` ≤20、`body` ≤200、可选 `label` ≤12 | 屏读卡片 |
| `before_after` | `left`/`right` 各 {title ≤10, points 2–5} | 双栏对照 |
| `accordion` | `items`（2–7：title ≤16、body ≤200） | 原生 `details` 展开 |
| `quote_card` | `text` ≤120、可选 `speaker` ≤20 / `source` ≤40 | 屏读 |
| `key_figures` | `items` 2–6 个，每个 `value` ≤10 / `label` ≤14 / 可选 `note` ≤60 | 数字卡网格 |
| `prose` | `paragraphs`（1–5） | 逃生口，也是降级目标 |

主题三套：`paper`（暖纸）、`minimal`（极简）、`dark`（夜读）。每套只覆盖 21 个 CSS 变量
（`--ink / --paper / --line / --red / --font-body …`），结构层不动。

## 为什么“确定性”在这里是硬指标

上游 book-to-webpage 的做法是：模型每次读 977 行骨架 + 356 行组件范式，然后手工拼 DOM。
后果是同一本书两次生成不一样、没法做回归、没法审 diff、每页要重读约 34 KB 模板。

bookpage 把“拼 DOM”中不变的 90% 固化进渲染器，模型只产 IR：

| 项目 | 上游 | bookpage |
| --- | --- | --- |
| 每次生成的模板开销 | 约 34 KB（977 行 HTML + 356 行 md） | 0（渲染器自带） |
| 同输入可复现 | 否 | 是（sha256 相等） |
| 错误拦截 | 无 schema 校验，靠人眼 | lint 7 个错误码，带字段路径 |
| 中文章节识别 | 8 章识别出 0 章 | 8/8 |
| 中文 token 估算 | 4,596 字 → 202 token（低估约 17 倍） | 3,379 token |
| 运行依赖 | poppler / calibre / playwright / pip 包 | 0（纯标准库） |

## 与设计稿的差异（实现时的两处修正）

1. **matrix 的 `cols` 只表示数据列**：行首的 `label` 是独立字段，可用 `label_header` 给首列表头命名。
   这样 `cells` 数量与 `cols` 严格一一对应，避免“表头比数据多一列”的隐性错位。
2. **decision_tree 用嵌套 `details`**：不依赖 JS，键盘与读屏软件天然可用；深度限 3 层，
   超过即 lint 拒绝（E104）。
3. **tab 选中态以面板为准**：启动时取“已 active 的面板”对应的 tab，取不到才回退第一个。
   否则“面板换了、tab 还指着第一节”这类状态分裂迟早出现（做视觉验证时就撞到过一次）。

未做：mobi/azw3 提取（要 calibre）、浏览器端 DOM 校验（改为对 IR 与产物做纯函数断言，因而不引入 playwright）、
多人协作的 IR 合并与增量重渲染。

## 目录

```
bookpage/
├── bookpage.py            # 渲染器 + lint + tokens + chapters + extract（单文件）
├── demo.json              # 7 节示例 IR（《置身事内》房地产与地方财政）
├── demo-overview.json     # 全书概览 IR（《阿Ｑ正傳》：4 框架 / 9 章 / 4 组概念 / 5 条规则）
├── out/demo.html          # 示例产物（离线单文件）
├── tests/
│   ├── selftest.py        # A1–A7 + A9
│   ├── test_golden.py     # A8 金标准回归（哈希锁死 + 组件标记）
│   ├── test_extract.py    # A9 书源提取回归（运行时生成 epub/docx 夹具）
│   ├── golden.sha         # A8 钉住的哈希（改版后 --update 重钉）
│   ├── all-components.json# prose / decision_tree / story_card / questions 补测
│   └── sample-book.md     # 八章中文夹具
└── README.md
```
