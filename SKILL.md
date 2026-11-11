---
name: bookpage
description: 把书的一个主题编成一张离线可开的交互教学页：模型只写结构化 IR（JSON），由确定性渲染器产出单文件 HTML，同一份 IR 两次构建字节级相同。当用户要把某本书/某章/某主题做成可点击的学习页、且希望结果稳定可复现（不靠每次手工拼 DOM）时使用。
---

# bookpage

一句话：**你写 IR，渲染器写 HTML。**

模型不产 DOM、不产 CSS、不产 JS —— 只产一份受 schema 约束的 JSON。渲染器（`bookpage.py`，约 1000 行，纯标准库）负责把 IR 变成单文件 HTML，因此：

- 同一份 IR 两次 `build` → **sha256 相同**
- `lint` 在落盘前就把结构错误挡住（带错误码 + 字段路径）
- 不需要浏览器、不需要 pip、不需要模板抄写

## 什么时候用这个，什么时候用 book-to-webpage

| 情况 | 用哪个 |
| --- | --- |
| 一次性交付、只求好看，不要求可复现 | book-to-webpage（组件资产丰富，但每次结果不同） |
| 要可回归、要能只改一处再重渲、要在 CI 里验 | **bookpage（本 skill）** |
| 需要全书概览（框架网格/章节地图/概念地图/决策规则） | **bookpage 的 `mode: overview`**（见下节） |

## 流程

```
① 拆书 → ② 只读当前章 → ③ 写 IR.json → ④ lint → ⑤ 按错误码改 → ⑥ build → ⑦ 自检
```

1. **拆书**：优先用本项目的 `python bookpage.py extract <书> -o full_text.txt`，再 `python bookpage.py split full_text.txt -o chapters/` 按章切开（docx/epub 零依赖、按 epub 内置顺序拼接、末尾打印字符数/章节数/token 估算），也可复用 `book-to-webpage` 的 `scripts/extract.py`（多产一份 `metadata.json`，但中文章节识别为 0）。全书超 5 万 token 时**不要整本读**：先 `chapters` 数章节，再 grep 标题定位边界，只切当前章。
2. **选题**：一个页面讲一个主题，选 4–7 节；每节一个组件；主题散布全书时先把相关章节列出来，再统一取用。
3. **写 IR**：严格按下面的骨架。`signature` 只能取白名单值；字数上限先看契约表，别写完再被 lint 打回。
4. **lint**：`python bookpage.py lint ir.json` —— 退出码 1 即失败，输出形如 `E102 sections[0].data.steps: 缺失或不是 list`。
5. **修**：只按错误码改对应字段，不重写整份 IR。
6. **build**：`python bookpage.py build ir.json out.html`。
7. **自检**：产物里不该有 `{{` 残留；`section.id` 数 = `tab` 数 = `panel` 数。

## IR 骨架

```json
{
  "schema": "bookpage/1",
  "meta": {"book": "书名", "author": "作者", "mode": "theme", "theme": "paper",
           "topic": "本节主题", "sources": ["第 N 章 …"]},
  "hero": {"eyebrow": "第 N 章 · 副题", "title": "一句钩子", "lede": "60–110 字导语",
           "thesis": "一句判断，20–60 字"},
  "sections": [
    {"id": "s1", "label": "3–8 字小标题", "lead": "一句话引入",
     "source": "第 N 章", "signature": "causal_chain",
     "data": {"steps": [{"title": "≤10 字", "text": "≤120 字", "detail": "≤160 字（可选）"}]}}
  ],
  "questions": [{"q": "≤40 字", "hint": "≤60 字（可选）"}]
}
```

硬规则：

- `id` 必须匹配 `^[a-z][a-z0-9_-]{0,15}$`，且在整份 IR 内唯一
- `theme` 只能是 `paper` / `minimal` / `dark`
- `sections` 4–7 个；`questions` 2–6 个
- 全部字符串走同一套转义，**不要在字段里写 HTML**（写 `<b>` 会被原样转义显示）

## 组件契约（`signature` 白名单，共 12 个）

| signature | data 必需键 | 数量 | 字数上限 | 交互 |
| --- | --- | --- | --- | --- |
| `causal_chain` | `steps[{title,text,detail?}]` | 2–6 | title 10 / text 120 / detail 160 | 点任一步展开该步在循环中的位置 |
| `type_selector` | `types[{name,text,tagline?}]` | 2–5 | name 8 / text 120 / tagline 20 | 按钮切换右侧说明 |
| `matrix` | `label_header?`、`cols[2–4]`、`rows[{label,cells}]` | rows 2–6 | cols 16 / label 16 / cell 40 | 行悬停整行高亮 |
| `timeline` | `items[{when,title,text?}]` | 3–8 | when 12 / title 16 / text 100 | 静态时间轴 |
| `decision_tree` | `root{q,options[{label,result\|next}]}` | 每层 2–3 | q 60 / label 16 / result 120 | 嵌套折叠，深度 ≤3 |
| `questions` | `items[{q,hint?}]` | 2–6 | q 40 / hint 60 | 点击翻出提示 |
| `story_card` | `title`、`body`、`label?` | 1 张 | title 20 / body 200 / label 12 | 静态卡片 |
| `before_after` | `left/right{title,points[]}` | 每侧 2–5 | title 10 / point 40 | 双栏对照 |
| `accordion` | `items[{title,body}]` | 2–7 | title 16 / body 200 | 原生折叠（无 JS 也能用） |
| `quote_card` | `text`、`speaker?`、`source?` | 1 张 | text 120 / speaker 20 / source 40 | 静态引语 |
| `key_figures` | `items[{value,label,note?}]` | 2–6 | value 10 / label 14 / note 60 | 数字卡网格，静态 |
| `prose` | `paragraphs[]` | 1–5 | 每段 240 | 无交互，逃生口 |

`matrix` 的 `cells` 数量必须**恰好等于** `cols` 数量；`decision_tree` 的每个选项必须且只能有 `result` 或 `next` 之一。


## 概览模式（`meta.mode = "overview"`）

一个页面讲透**整本书的骨架**，不用 tab，单页滚动。此时**不要写 `sections`**（写了会报 E100），改从下面四个区块里挑一个或几个（至少一个非空，否则 E102）：

```json
{
  "schema": "bookpage/1",
  "meta": {"book": "书名", "author": "作者", "mode": "overview", "theme": "paper",
           "topic": "全书概览", "sources": ["版本 / 译本 / 年份"]},
  "hero": {"eyebrow": "作者 · 年份", "title": "一句书名级的钩子", "lede": "60–110 字全书导语",
           "thesis": "20–60 字的全书判断"},
  "frameworks":  [{"title": "≤14 字", "thesis": "≤40 字", "points": ["≤30 字", "…2–4 条"]}],
  "chapterMap":  [{"n": 1, "title": "≤20 字", "gist": "≤40 字", "mark": "≤10 字（可选）"}],
  "conceptMap":  [{"name": "≤14 字", "relation": "因果|对立|组成|递进", "items": ["≤30 字", "…2–5 条"]}],
  "decisionRules": [{"if": "≤40 字", "then": "≤40 字", "else": "≤40 字（可选）"}],
  "questions": [{"q": "≤40 字", "hint": "≤60 字（可选）"}]
}
```

| 区块 | 数量 | 渲染形态 |
| --- | --- | --- |
| `frameworks` | 3–6 张 | 卡片网格：标题 + 一句论点 + 2–4 个要点 |
| `chapterMap` | 3–12 行 | 数字卡网格：第 N 章 / 标题 / 一句话内容 / 可选标记（如“换算起点”） |
| `conceptMap` | 2–6 组 | 关系徽章 + 概念名 + 2–5 个词条 |
| `decisionRules` | 2–5 条 | 当…则…否则… 三行式规则卡 |

概览模式的判断标准：读者滚完一页，能说出**这本书由几个框架组成、每章各干什么、概念之间怎么连**。章节地图按原书顺序写全（`n` 连续更易读），不要挑“重要章节”跳跃编号。

## 速读模式（`meta.mode = "reader"`）

目标是**让读者在一页内把整本书过一遍**，不是讲透某一处。此时同样**不要写 `sections`**（写了报 E100），改用 `chapters[]`：

```json
{
  "schema": "bookpage/1",
  "meta": {"book": "书名", "author": "作者", "mode": "reader", "theme": "paper",
           "topic": "全书速读", "sources": ["版本 / 译本 / 年份"]},
  "hero": {"eyebrow": "作者 · 年份", "title": "一句概括全书的主张", "lede": "60–120 字：这本怎么读、页面给什么",
           "thesis": "20–60 字：全书一句话判断"},
  "digest": [{"t": "3–5 条，每条 10–60 字：这本书到底在说什么", "refs": [3, 5]}],
  "concepts": [
    {"name": "≤14 字", "gist": "≤60 字：一句话解释", "chapters": [2, 3]}
  ],
  "thread": [
    {"step": "≤12 字：这一步的名字", "what": "≤44 字：这一步给下一步提供了什么", "chapters": [2, 3]}
  ],
  "chapters": [
    {"n": 1, "title": "原书章题（≤24 字）", "role": "≤34 字：这章在全书里的作用",
     "gist": "≤70 字：这章发生什么", "points": ["≤40 字", "…2–4 条要点"],
     "quote": "≤90 字原文", "quote_from": "≤12 字（第几章）",
     "text": ["原书段落，1–3 段，每段 ≤220 字"]}
  ],
  "questions": [{"q": "≤40 字", "hint": "≤60 字（可选）"}]
}
```

| 字段 | 约束 | 说明 |
| --- | --- | --- |
| `digest` | 3–5 条，每条 10–60 字；可写成 `{t, refs}`，`refs` 1–3 个章号 | 「这本书在说什么」四张卡，先让读者拿到全局判断；带 `refs` 时卡底出现「第 N 章」链接，读者能当场跳去核对证据 |
| `concepts` | 2–6 组 | 关键概念卡：名字 + 一句话解释 + 出现章号（点卡跳章） |
| `thread` | 3–6 环，可选，每环 1–2 个章号 | 论证主线：全书"I 所以 II 所以 III"的推进链，横排在概念之后。每环写**这一步给下一步提供了什么**，不是章节列表——`step` 是这一步的名字（起点/换算/越界/代价），`what` 是它给下一步递过去的条件 |
| `chapters` | 3–40 章，`n` 递增 | 按原书顺序，不跳号；短书就一章一张卡 |
| `role` | ≤34 字，可选 | 这章在全书里的作用（推进/转折/收束），别写成 gist 的同义句 |
| `gist` | 10–70 字 | 一句话：这章发生了什么 |
| `points` | 2–4 条，每条 ≤40 字 | 可扫读的要点，不是复述 gist |
| `quote` | ≤90 字 | 原文金句，尽量照录，不要改写 |
| `text` | 1–3 段，每段 ≤220 字 | 折叠区里的原文片段，让读者能核对 |

页面形态：hero → `digest` 四张判断卡 → `concepts` 概念网格 → `thread` 主线横排（有则出现）→ 搜索框 + 滚动进度条 + 已读计数 → 左侧 sticky 目录 + 章节卡（章号/标题/gist/要点/金句/「读原文」折叠）。每张章节卡右上角有「标为读完」按钮，状态存 `localStorage`（key 含书名），刷新不丢，计数显示"已读 N / M"。搜索框按标题、gist、要点、原文片段过滤章节，目录同步隐藏。

**拆书先行**：先用 `split` 把书按章切开，一章一个 `ch-NN.md`，再逐章写 `gist/points/quote`：

```bash
python bookpage.py split <书> -o chapters/     # 输出 ch-01.md … + index.json（章节数/字数/标题）
```

`split` 会去掉 Gutenberg 页眉与许可证尾巴、章末 `〔N〕` 注释块、重复印的章题；找不到章节标题时按 6,000 字等分。

速读模式的判断标准：读者滚完这一页，能说出**这本书在讲什么（digest）、关键概念之间怎么连（concepts）、全书论证怎么一步步推进（thread）、每章推进在哪（role + gist）**，并且想核对哪句时能点开原文、想停在哪能标"已读完"。

写作纪律：`role` 说"这章在全书里干什么"，`gist` 说"这章发生了什么"，两者不要互相复述；`digest` 不要写成章节列表，要写成判断，并给每条判断挂 1–3 个章号（`refs`），让读者能跳回去核对。

## 错误码 → 改法

| 码 | 含义 | 怎么修 |
| --- | --- | --- |
| `E100` | schema 字段缺失或不是 `bookpage/1` | 补 `"schema": "bookpage/1"` |
| `E101` | 未知 `signature` | 从上面 12 个里选，别自造 |
| `E102` | 必需键缺失 | 按路径补键；`result/next` 二选一的错误也报这个 |
| `E103` | 类型不对（该 list 给了 string 等） | 改成对应容器类型 |
| `E104` | 超出上限（字数/数量/深度） | 压缩文本或拆节 |
| `E105` | `id` 重复 | 换一个唯一 id |
| `E201` | 产物仍有 `{{…}}` 占位符 | 说明 IR 没走到渲染路径，检查是否跳过了 `build` |
| `E202` | 未知主题 | `theme` 改成 `paper/minimal/dark` |

## 命令

```bash
python bookpage.py lint   ir.json                    # 校验，退出码 1 表示失败
python bookpage.py build  ir.json out.html           # 渲染
python bookpage.py build  ir.json out.html --degrade # 出错的节降级为 prose，产物留 <!-- degraded -->
python bookpage.py tokens <文本文件>                 # 中文感知的 token 估算
python bookpage.py chapters <文本文件>               # 中文章节计数（第N章/第N回/Chapter N）
python bookpage.py extract <书> [-o out.txt]         # 书源 → 纯文本（docx/epub 零依赖，pdf 需 pypdf）
python bookpage.py split  <文本文件> -o chapters/    # 按章切开：ch-NN.md + index.json
python bookpage.py build  ir.json out.html           # 三种模式共用同一个 build（按 meta.mode 分派）
python tests/selftest.py                             # A1–A7 + A9（提取）+ A10（overview）+ A11（reader/split）+ A12（主线/已读）
```

退出码：`0` 成功、`1` IR 校验失败、`2` 参数或读文件错误。

提取格式：`txt/md/rst/adoc` 直读；`docx` 走 `zipfile` + `word/document.xml`；`epub` 走 `zipfile` + OPF spine（按书内顺序，不按文件名）；`rtf` 去控制字；`pdf` 需 `pip install pypdf`（bookpage 本体仍零依赖），`mobi/azw3` 需 calibre 的 `ebook-convert`，两者缺依赖时直接以退出码 2 说明缺什么，不静默产出空文本。

## 写作要求（衔接层仍是你的活）

渲染器只管结构与版式，**内容质量仍由你负责**：

- `lead` 写一句“为什么读这一节”，不要复述 `label`
- 每节正文控制在 1–2 句有信息量的话，删掉“本章介绍了…”这类空转
- `thesis` 必须是一个可被反驳的判断，不能是“很重要”
- `questions` 用来留出思考缺口，不要写成复习题
- 出处（`source`）写具体章名，不写“全书”

## 不要做

- 不要手改 `out.html`：下次 `build` 会覆盖，改动要落回 IR
- 不要改主题变量名（21 个 `--` 变量是渲染器与主题的接口）
- 不要在 IR 里塞 HTML/脚本片段
- 不要在 `data` 里加白名单外的键（会被忽略，不会报错，等于白写）
