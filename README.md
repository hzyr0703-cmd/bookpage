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
两者可共存；全书概览模式仍只有前者支持。

## 用法

```bash
# 校验 IR：结构与字段约束，错误带错误码与字段路径
python bookpage.py lint demo.json

# 渲染：<ir.json> <out.html>
python bookpage.py build demo.json out/demo.html

# 模板校验失败但仍想看效果：把出错的 section 降级成 prose，并留 <!-- degraded -->
python bookpage.py build demo.json out/demo.html --degrade

# 中文感知的 token 估算（对比上游按空格切词的实现）
python bookpage.py tokens tests/sample-book.md

# 中文章节计数：第N章 / 第N回 / Chapter N
python bookpage.py chapters tests/sample-book.md
```

退出码：`0` 成功、`1` IR 校验失败、`2` 参数或读文件错误。

## 自检

```bash
python tests/selftest.py
```

八条断言全部可复跑，不依赖浏览器与 pip（A1–A7 跑 `tests/selftest.py`，A8 跑 `tests/test_golden.py`）：

| 编号 | 断言 | 现状 |
| --- | --- | --- |
| A1 | 同一 IR 两次构建 sha256 相同 | PASS（`65767738fb8b1f53…`，24,872 bytes） |
| A2 | 未知 signature → 退出码 1，报 E101 且指出 `sections[i].signature` | PASS |
| A3 | 缺必需键 → 退出码 1，报 E102 且指出键名 | PASS |
| A4 | 中文样书章节计数 = 8 | PASS 8/8 |
| A5 | 中文 token 估算 ≥ 上游算法的 8 倍 | PASS：3,379 vs 202（约 17 倍） |
| A6 | 产物无 `{{`、tab↔panel 与 section 一一对齐、无外部引用（离线可开） | PASS |
| A7 | 剥离 PYTHON* 变量 + `-I` 隔离下仍能构建 | PASS（24,872 bytes） |
| A8 | 金标准回归：两份样例 IR 产物哈希钉死 + 11 个组件标记齐备 | PASS（demo `65767738…` / all `6d435f03…`，11/11） |

## 视觉验证

本机没有 playwright，改用系统自带的 Edge 无头模式截图，命令可复跑：

```bash
msedge --headless=new --disable-gpu --hide-scrollbars \
  --screenshot=out/shot.png --window-size=1280,1600 \
  "file:///<绝对路径>/out/demo.html"
```

已核对四个视角（截图在 `out/` 与 `../../output/2026-11-10/`）：

| 视角 | 结果 |
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

## 组件（10 个 + 1 个逃生口）

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

未做：全书 overview 模式（frameworks / chapterMap / conceptMap / decisionRules）、PDF/EPUB 提取
（复用 book-to-skill）、浏览器端 DOM 校验（改为对 IR 与产物做纯函数断言，因而不引入 playwright）。

## 目录

```
bookpage/
├── bookpage.py            # 渲染器 + lint + tokens + chapters（单文件）
├── demo.json              # 7 节示例 IR（《置身事内》房地产与地方财政）
├── out/demo.html          # 示例产物（离线单文件）
├── tests/
│   ├── selftest.py        # A1–A7
│   ├── test_golden.py     # A8 金标准回归（哈希锁死 + 组件标记）
│   ├── golden.sha         # A8 钉住的哈希（改版后 --update 重钉）
│   ├── all-components.json# prose / decision_tree / story_card / questions 补测
│   └── sample-book.md     # 八章中文夹具
└── README.md
```
