# bookpage

把一本书的一个主题，编译成**一张离线可开的交互教学页**。

模型只写结构化 IR（JSON），渲染器负责把它变成 HTML —— 因此同一份 IR 两次构建**字节级相同**，
不需要模板抄写、不需要浏览器、不需要任何第三方包。

- 设计稿：[docs/2026-11-10-bookpage-design.md](docs/2026-11-10-bookpage-design.md)（竞品对比、IR 契约、组件契约、确定性规则）
- 立项起点：先逆向了一个同类 skill（book-to-webpage）再定方案；那份逆向报告属于另一个项目，未随本仓库发布
- 代码：单文件 `bookpage.py`（约 3,500 行，纯 Python 标准库）＋ `tests/` 里 28 项自检

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

# 起草包：每章脉络（章题/字数/首句/末句/按句抽样骨架/书内引号句），全部取自原文
python bookpage.py draft 书.txt -o 起草包.md
python bookpage.py draft 书.txt --chapter 3 -o 第3章.md
python bookpage.py draft 书.txt -o 起草包/ --split 6      # 长书按卷切，每卷一份 part-N.md + index.json
python bookpage.py draft 书.txt -o 第2卷.md --split 6 --part 2   # 只导出某一卷

# 模板校验失败但仍想看效果：把出错的 section 降级成 prose，并留 <!-- degraded -->
python bookpage.py build demo.json out/demo.html --degrade

# 中文感知的 token 估算（对比上游按空格切词的实现）
python bookpage.py tokens tests/sample-book.md

# 中文章节计数：第N章 / 第N回 / Chapter N
python bookpage.py chapters tests/sample-book.md

# 书源 → 纯文本：docx/epub 零依赖；pdf 需 pypdf；mobi/azw3 需 calibre
python bookpage.py extract 某本书.epub -o full_text.txt

# 起草候选：每章首句/末句/书内引号句（只给能过 verify 的句子）
python bookpage.py outline 书.txt -o 候选.md

# 引文核对：引文/原文片段/章题/要点数字与拉丁名/要点里的「」原话（E301–E306）+ 覆盖率
python bookpage.py verify demo-reader.json --source tmp/bookpage-e2e/kb/full_text.txt

# 扫描版 PDF 摸底：抽样判文本层，按页渲 PNG，并报「书版页码 = 物理页 - 前置页数」
python bookpage.py render 书.pdf -o pages/ --pages 1-4 --dpi 180

# 书房：把若干目录里的 IR 收成一页，按书分组；已构建的给链接，没构建的标灰
python bookpage.py shelf 交付目录/ -o 交付目录/index.html
```

退出码：`0` 成功、`1` IR 校验失败、`2` 参数或读文件错误。

## 自检

```bash
python tests/selftest.py
```

十五条断言全部可复跑，不依赖浏览器与 pip（A1–A7、A9–A16 跑 `tests/selftest.py`，A8 跑 `tests/test_golden.py`）：

| 编号 | 断言 | 现状 |
| --- | --- | --- |
| A1 | 同一 IR 两次构建 sha256 相同 | PASS（`b318941435c43bc5…`，31,548 bytes） |
| A2 | 未知 signature → 退出码 1，报 E101 且指出 `sections[i].signature` | PASS |
| A3 | 缺必需键 → 退出码 1，报 E102 且指出键名 | PASS |
| A4 | 中文样书章节计数 = 8 | PASS 8/8 |
| A5 | 中文 token 估算 ≥ 上游算法的 8 倍 | PASS：3,379 vs 202（约 17 倍） |
| A6 | 产物无 `{{`、tab↔panel 与 section 一一对齐、无外部引用（离线可开） | PASS |
| A7 | 剥离 PYTHON* 变量 + `-I` 隔离下仍能构建 | PASS（31,548 bytes） |
| A8 | 金标准回归：五份样例 IR（demo / all / overview / reader / 庄子 reader）哈希钉死 + 12 个组件标记齐备 | PASS（demo `b318941435…` / all `e1dfcc06e2…` / overview `db273747f0…` / reader `691841ff92…` / zhuangzi `7ce9155c25…`，12/12） |
| A9 | 书源提取：epub（按 spine 顺序）/docx（zipfile+XML）/纯文本，章节计数正确；pdf、mobi 缺依赖或解析失败时 rc=2 并说明原因；本机同时有 pypdf+reportlab 时再跑一份真 PDF | PASS（公版书 epub 46,157 字符 / 9 章；真 PDF 3 章） |
| A10 | overview 模式：四区块渲染、两次构建同哈希、无 tab/panel、无外部引用；空区块报 E102、误写 sections 报 E100、非法 relation 被拒 | PASS（`29e816814f31e5a2…`，三条拒绝路径） |
| A11 | reader 模式 + split：样书切出 8 章（文件数与 index 一致、每文件有标题行)、reader 两次构建同哈希、无 tab、有目录与搜索框、digest 卡与概念卡数量与 IR 一致、digest 的章号引用数与 IR 一致且不指向空锚点、无外部引用；无标题书回退到等分切 | PASS（8 章 / `35f69bba96…` / 等分回退） |
| A13 | verify：引文、原文片段、章题三类错误都能定位到具体字段（E301/E302/E303），正常 IR 必须通过 | PASS（3 章样本，三类错误各自命中） |
| A18 | split 丢掉目录空条目、版权页不并入首章；verify 抓编造的数字（E304）与编造证据（E305），正常 IR 不误报 | PASS（3 卷夹具 / 1874 年触发 E304 / 伪造 ev 触发 E305） |
| A20 | verify 抓要点里带引号的编造原话（E306），繁体写法折叠后不误报；未装 zhconv 则跳过 | PASS（编造「壬辰条例」触发 E306 / 「行動」折叠通过） |
| A21 | 长书分卷：120 章 + 6 组 `parts` 构建、组锚点与目录对齐、两次同哈希；乱序/缺组/未分组一律 E104 | PASS |
| A19 | 像素基线：三张页（theme / reader / 七组件主题页）× 两个宽度（1280、900）渲染后的 PNG 哈希不变 | PASS（6 张，msedge；换机器或换浏览器版本需 `python tests/visual.py --update` 重钉） |
| A14 | render：有文本层的 PDF 判「文本层：有」并按页区间渲 PNG；没装 pymupdf 时退化为校验缺依赖报错 rc=2 | PASS（3 页样本 → 只渲 1-2 页） |
| A15 | shelf 书房页：同目录 2 本 2 页（1 已构建 / 1 未构建）按书分组，链接可点、未构建标灰、两次输出同哈希、无占位符与外部引用 | PASS（2 个书组 / 2 枚页签，两次同哈希） |
| A16 | outline：8 章候选、两次同哈希、长度短于原文、无虚词噪声、无占位符 | PASS（1,233 / 4,596 字节） |
| A17 | draft：8 章起草包、两次同哈希、包内每句都能在原文逐字找到、长度显著短于原文、无占位符 | PASS（97 句全部命中，3,497 / 4,596 字节） |
| A26 | draft 分卷：章号连续不重排、每卷都远小于整本、`--part K` 与落盘逐字一致、两次分卷同哈希、缺目录/裸 `--part`/卷号越界全报用法错误 | PASS（8 章切 3 卷，二次一致） |
| A27 | 互链只走站内相对路径（外链 / 绝对路径 / 非 html 一律拒，超 3 条拒）；`verify --stamp` 写回数字后两次构建仍同哈希，页脚出现核对信息 | PASS（相对链接放行 / 三类坏链拒绝 / stamp 后同哈希） |
| A28 | 窄屏版面：477px 下 `scrollWidth == clientWidth`（无横向溢出），且 viewport 与 880/520 两个断点都在 | PASS（3 页全部无溢出） |
| A29 | `build` / `shelf` 的 `-o` 指向不存在的目录时自建目录，不抛栈、退出码正确 | PASS（三级嵌套目录 + 多层书房目录） |
| A23 | guide 模式：五段齐全（premise/机制/场景/边界/证据）、自测条数与 IR 一致、无 tab、两次构建同哈希 | PASS（6 概念 / 3 自测 / `b7ddaea9…`） |
| A24 | guide verify：证据逐字核对；编造引文、章号越界（E301）、答案悬空（E105）都被拦 | PASS（3 类错误各自命中） |
| A25 | guide 边界：缺 `limits` → E102、概念超 12 个 → E104、无证据过半 → E104 | PASS |

## draft 起草包（把"写 IR"交给模型的接口）

`draft` 产出的不是摘要，是**脉络 + 可逐字引用的原句**：每章给章题、字数、首句、末句、按句抽样骨架（无分段的书退化为按句抽样）、书内引号句。

实测体积与验证（同一份 IR 只用起草包写、不回读全文）：

| 书 | 原文 | 起草包 | 占比 | 包里句子能否被 verify 认账 |
| --- | --- | --- | --- | --- |
| 《莊子·內篇》 | 16,971 字 | 3,778 字 | 22% | 3 章试跑 IR 全部通过（引文 3/3、原文段 6/6） |
| 《阿Q正傳》 | 27,769 字 | 7,876 字 | 28% | 阿Q 原页数据重写后 9 章全部通过 |

这条路线要成立的前提是：**起草包里的句子 100% 是原文片段**，模型照抄不会失真；一旦它自己"润色"，`verify` 会立刻报 E301/E302。所以 `draft` 有意不给自由摘要——摘要由模型写判断层时自己生成。

局限：判断卡（digest）与主线（thread）仍需模型自己判断，起草包只提供材料，不提供结论。

### 长书必须分卷（`--split`）

小书的 22%–28% 比例没问题，但比例乘上大书就炸了。《红楼梦》1,092,390 字符的整包实测 **193,469 字 / 143,580 tokens**——模型一次读不完，"只读起草包"这条 SOP 在长书上直接失效。

`--split N` 按字数把章均衡切成 N 卷（章不拆开、不重排，每卷章号沿用全书章号），另写一份 `index.json` 记录每卷的章号区间、字数、token 估算：

| 卷 | 章 | 起草包 | 约 tokens |
| --- | --- | --- | --- |
| 1 | 1–18 | 25,780 字 | 19,197 |
| 2 | 19–38 | 24,733 字 | 18,630 |
| 3 | 39–56 | 24,112 字 | 18,031 |
| 4 | 57–75 | 25,703 字 | 19,364 |
| 5 | 76–96 | 20,451 字 | 15,515 |
| 6 | 97–119 | 16,077 字 | 12,358 |

合计 136,856 字（原文 13%），最大一卷 19,364 tokens，是单次上下文能整读的量级。顺带修掉一处噪声：本书 epub 把词条注释（`踹窝：路面上践踏成的坑窝`）拼在每回正文末尾，`_strip_tail_notes` 从章尾连续剥离这类行，否则"末句"会取到注释而不是正文（全包因此少了约 5.7 万字符）。

`--part K` 单独导出第 K 卷，方便一次只把一个文件交给模型。

## outline 没做什么（两次失败记录）

最初想让 `outline` 顺手给出「跨章高频专名」，帮选题更快，两种做法都没站住：

1. **2–4 字窗口计数**：文言里最高频的窗口是「而不（80 次）/ 不知（44 次）/ 以為（39 次）」，全是虚词；加了虚词字符表过滤后仍留下「子曰 / 夫子 / 人之 / 而後」这类语法组合。白文本上同样跑偏（阿Q 前十二名是「沒有 / 一個 / 知道 / 自己」，只有一个「未莊」是真专名）。
2. **对话标记正则**（`某某曰/说/道/问` 抓说话人）：文言抓出「敢 / 名之 / 謂之」这类误命中，白话抓出「誰知 / 我不知」，真名（庄子、阿Q、赵太爷）反而漏掉。

结论：没有分词就无法可靠抽专名，与其给出一份看着像分析、实则要人工逐条否掉的清单，不如只给**能被校验的部分**——章结构、首句、末句、书里自带引号的句子。这三样都能被 `verify` 认账，也不骗人。若以后要回到专名提取，需要引入词性标注或专名词典，属于另一个量级的工作。

## 视觉验证

本机没有 playwright，改用系统自带的 Edge 无头模式截图，命令可复跑：

```bash
msedge --headless=new --disable-gpu --hide-scrollbars \
  --screenshot=out/shot.png --window-size=1280,1600 \
  "file:///<绝对路径>/out/demo.html"
```

已核对四个视角（截图放在工作区 `out/`，不入库）：

| 视角 | 结果 |
| A12 | 论证主线 + 已读标记：`thread` 环数与 IR 一致、主线章号锚点不悬空、`class="mark"` 按钮数 == 章节数、`id="rRead"` 计数器存在、内联 JS 含 localStorage 且无箭头函数、两次构建同哈希 | PASS（5 环 / 9 个按钮 / `7f44eb9f9b…`） |
| --- | --- |
| 首屏（因果链面板） | 标题衬线、hero 判断条、7 个 tab 一行排开、四步卡片等宽 |
| 矩阵面板（tab 2） | 表头「模式 / 启动资金 / 回款方式 / 主要风险」与 4 行数据对齐，首列底色区分 |
| 前后对比（tab 5） | 双栏等宽、左侧税收财政 / 右侧土地财政，竖线分隔 |
| 深色主题（`theme: dark`，同一份 IR） | 底色、正文、卡片边框、tab 选中态均正确反相，无对比度塌陷 |

矩阵与深色两张截图是“把 active 面板换到第 N 个”后的同一份产物 —— 顺带验证了 tab 选中态与面板内容在运行时保持一致。
## 弱语义提示（`lint --strict`）

结构正确但读起来是空话的地方，`lint` 会打「提示 W4xx」，默认**不算失败**（判定表达质量，误报宁可漏）：

| 码 | 抓什么 | 为什么加 |
| --- | --- | --- |
| W401 | `oneliner` 把 `name` 的字重复了一遍 | 概念卡最容易犯的错：标题换个说法，读者什么都没多知道 |
| W403 | `scenes[].when` 里没有触发条件（当/如果/遇到/正在…） | 场景段写成"人生难免起伏"就失去对照价值 |
| W404 | `limits[]` 写「视情况而定 / 因人而异 / 不一定」 | 等于没写边界，还给人一种写过的错觉 |

`lint --strict` 把提示也按失败计（退出码 1），适合收尾前一刀切。

**试过但撤掉的规则（W402）**：原本想抓"机制各步里一个因果词都没有"，理由是机制该讲为什么。实测在《沉思录》讲解页 8 个概念里报了 6 个——那本书的机制是用"判断起情绪：焦虑都是判断的副产品"这种"部位 + 后果"写法推进的，本来就不必带"因为/所以"。76% 的误报率说明规则错了，不是文章错了，于是删掉，只在文档里留痕。

## 窄屏断言

`tests/visual.py` 除了像素基线，还做两件事：

1. **477px 实测无横向溢出**：注入脚本读 `documentElement.scrollWidth / clientWidth`，不等就是排版溢出。
2. **静态审计**：viewport 在、`@media (max-width:880px)` 与 `(max-width:520px)` 两个断点都在、没有写死 `width:Npx`（>340px 一律判失败）。

已知限制：Edge 无头最小视口就是 477px，`--window-size=375` 会被顶回 477（实测 `innerWidth=492`），所以 375/390 的真机窄屏**本机测不了**。520px 断点以下走的是同一套规则，477 能覆盖；比 477 更窄的情况只能靠静态审计里"不写死宽度"这条兜。

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

## 四种模式

| mode | 页面形态 | 结构 | 什么时候用 |
| --- | --- | --- | --- |
| `theme`（默认） | 顶部 sticky tab + 分节面板，每节一个组件 | `sections[]` 4–7 节 | 讲透某个主题、某个机制 |
| `overview` | 单页滚动，无 tab、无 JS 依赖 | `frameworks` / `chapterMap` / `conceptMap` / `decisionRules` 至少其一 | 先看全书骨架再决定读哪 |
| `reader` | 单页滚动：全书判断卡 + 概念网格 + 论证主线 + 左侧 sticky 目录 + 章节卡 + 搜索框 + 滚动进度 + 已读标记 | `digest[]` 3–5 条（每条可带 `refs` 章号）、`concepts[]` 2–6 组、`thread[]` 3–6 环（可选）、`chapters[]` 3–120 章（role/gist/points/quote/text）、`parts[]` 2–12 组（可选；**超过 40 章必须分组**，各组章号拼接后须与全书章号一致） | **快速理解一本书**：先看全书在说什么，再按章扫读、点开原文核对 |
| `guide` | 单页滚动：hero + 左侧常驻索引（premise/概念名/自测锚）+ 每个概念一块（机制链 / 场景卡 / 边界条 / 证据「第 N 章」）+ 分栏支撑表 + 自测折叠题；无 tab、无 JS | `premise` 10–40 字、`ideas[]` 6–12 个（oneliner 10–40、mechanism 3–5、scenes 2–3、limits 1–3、evidence 0–3 且无证据者 ≤1/3）、`checks[]` 3–6（answer 为 idea id 或 `none`）、`support[]` 0–2 组 | **让读者带走可调用的方法**：全书只留 6–12 个概念，写清机制、用法、边界与原文证据 |

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

4. **`.qcard` 一律顶对齐**：按钮默认把单行内容垂直居中，多行内容顶对齐，导致"三张问题卡里只有短问题那张字位偏移"。
   改成 `display:flex;flex-direction:column` 后三种主题下卡内文字基线一致（三主题真书实战时发现）。

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
