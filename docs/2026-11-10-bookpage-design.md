# bookpage 设计稿 v2 · 一个比 book-to-webpage 更可交付的「书 → 网页」项目

> 状态：设计（未开工）。v2 在 v1 基础上补齐**组件契约、CLI 与错误码、确定性工程规则、提示词修复环、可访问性、可执行的验收命令**，并附一页视觉样张。
> 上游：[crayon-ai/book-to-webpage](https://github.com/crayon-ai/book-to-webpage)（已安装、已用 REA 逆向，见 `book-to-webpage-reverse-engineering.md`）
> 视觉样张：`bookpage-mockup.html`（人写，仅定义组件外观与交互，**不是**渲染器产出）
> 日期：2026-11-10

---

## 0. 结论

**能做，但“book-to-skill + TiddlyWiki5 / Pandoc”这个配方不成立** —— 两个候选解决的都是「能出 HTML」，而逆向证明 book-to-webpage 的短板是「没有渲染器」：977 行骨架 + 356 行组件范式交给模型每次手工填，所以不可复现、每页重读约 34 KB 模板、中文与 Windows 三处硬伤。

正确配方是三层，第三方只当可选零件：

| 层 | 用什么 | 为什么 |
| --- | --- | --- |
| 内容层 | book-to-skill 的提取器 + `.kb/`（章节/索引/术语表） | 它是 book-to-webpage 提取器的原始来源，成熟、跨格式 |
| 契约层 | 结构化 IR（JSON，schema `bookpage/1`） | 模型只产内容与组件名，不产 DOM；可 lint、可 diff、可重渲 |
| 渲染层 | 自研确定性渲染器（组件库 + 主题变量） | 同输入 → 字节级相同输出；零外部依赖 |

Pandoc 仅作**可选**的 md→HTML 后端（需要 md 语义保真时接 [Lua filter](https://pandoc.org/lua-filters.html)），TiddlyWiki 仅作**另一种成品形态**（可检索知识库）的导出目标，二者都不是主干。

---

## 1. 为什么不是现成的几个「书 → 站点」工具

| 工具 | 它是什么 | 拿它做教学页会缺什么 |
| --- | --- | --- |
| [Quarto](https://quarto.org/) | 多格式出版系统（HTML/PDF/Word/ePub、书籍项目、`quarto render`） | 排版强、组件弱：分栏/Tab/点选反馈/因果链要自己写 div + 自备 JS；中文教学页的交互层没有现成范式 |
| [Jupyter Book（经 myst）](https://jupyterbook.org/stable/build-and-publish/website) | markdown + notebook → 可交互网站/PDF | 偏技术文档与 notebook 场景；教学页要的“概念对照/矩阵/追问卡”仍要自建 |
| mdBook（Rust） | markdown → 带搜索的书籍站点 | 输出是“翻页阅读器”，单主题多章节结构，不适合单页多模块 |
| docsify | 客户端渲染的文档站，无构建 | 同上，且依赖浏览器端 JS 运行时，离线单文件不成立 |
| TiddlyWiki5 | 单 HTML 维基，tiddler/标签/检索 | 非线性浏览强，**版式与组件几乎为零**，要复刻组件得写插件 |
| Pandoc | 通用文档转换 + 模板/Lua filter | 输出是“正确排版的静态页”，交互为零 |

共同结论：**它们都提供「输出载体」，不提供「教学页的组件语义 + 版式 + 交互」**。而这层恰好是 book-to-webpage 用资产库提供、却用“模型手填”交付的东西 —— 所以要做的是**把资产换成渲染器**，不是换一个输出工具。

---

## 2. 逆向得到的可测基线（新项目必须全过）

| 指标 | book-to-webpage 实测 | bookpage 目标 | 验法 |
| --- | --- | --- | --- |
| 同输入两次生成 | 不一致（模型拼 DOM） | **字节级一致** | 两次 build 比对 sha256 |
| 中文 token 估算 | 4,266 字 → 146 token（约 20× 低估） | 误差 ≤ ±20% | 单测断言 |
| 中文章节识别 | 8 章 → 0 章 | **8/8** | 对同一本样例书跑 `chapters` |
| 外部依赖 | poppler/calibre/playwright/pip 包 | **0**（纯 Python 标准库） | 干净环境直跑 |
| 每页 token 成本 | 每次重读约 34 KB 模板 | 组件库固化，模型只产 IR（< ~4 KB/页） | 统计 IR 字节 |

环境实测：本机 **没有** jinja2、pandoc、jsdom、playwright —— “零依赖”必须是真零依赖。

---

## 3. 架构与数据流

```
书（pdf/epub/docx/md）
   │ ① 提取（复用 book-to-skill 提取器）→ full_text.txt + metadata.json
   ▼
.kb/（INDEX.md / chapters/ / glossary.md / patterns.md）
   │ ② 编译：模型只产结构化 IR（schema 约束，不产 DOM）
   ▼
IR.json ─► ③ lint（纯函数，结构/取值/命名）─► ④ build（组件库 + 主题 + 内联 JS/CSS）─► 单文件 HTML
                │ 失败 → 回传错误码与字段路径 → 模型修一轮（最多 2 轮）→ 仍失败则降级 prose
                └ ⑤ 自检：两次 build 哈希一致 / 无 {{}} 残留 / section↔tab↔panel 对齐
```

---

## 4. IR 契约（schema `bookpage/1`）

```json
{
  "schema": "bookpage/1",
  "meta": {"book": "置身事内", "author": "兰小欢", "mode": "theme",
           "theme": "paper", "topic": "房地产与地方财政",
           "sources": ["第 1 章 地方政府的权力与事务", "第 4 章 土地财政"]},
  "hero": {"eyebrow": "第三章 · 土地与财政", "title": "土地财政是怎么转起来的",
           "lede": "一句话钩子", "thesis": "本节要证明的判断"},
  "sections": [
    {"id": "s1", "label": "钱从哪来", "signature": "causal_chain",
     "lead": "段首引语", "source": "第 1 章",
     "data": {"steps": [{"title": "分税制", "text": "1994 年之后，地方…", "detail": "展开一句"}]}}
  ],
  "questions": [{"q": "产业升级为什么不能只靠补贴？", "hint": "从地方竞争角度"}]
}
```

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `schema` | string | ✓ | 恒为 `bookpage/1` |
| `meta.theme` | string | ✓ | 枚举：`paper` / `minimal` / `dark` |
| `meta.mode` | string | ✓ | `theme`（本章/主题）；`overview` 留位，v1 不渲染 |
| `meta.sources` | string[] | ✗ | ≤ 8 条，显示在“出处”开关里 |
| `hero.eyebrow` | string | ✓ | ≤ 30 字 |
| `hero.title` | string | ✓ | ≤ 40 字 |
| `hero.lede` | string | ✓ | 60–140 字 |
| `hero.thesis` | string | ✗ | ≤ 60 字 |
| `sections[].id` | string | ✓ | `^[a-z][a-z0-9_-]{0,15}$`，全页唯一 |
| `sections[].label` | string | ✓ | ≤ 14 字（Tab 宽度） |
| `sections[].signature` | string | ✓ | 见 §5 白名单 |
| `sections[].lead` | string | ✗ | ≤ 80 字 |
| `sections[].source` | string | ✗ | 出处标注 |
| `sections[].data` | object | ✓ | 按 signature 的契约校验（§5） |
| `questions[]` | object[] | ✗ | ≤ 6 条；`q` ≤ 40 字 |

---

## 5. 组件契约（10 个 + prose 逃生口）

每个组件 = 一个渲染函数 + 一个校验函数（均为纯函数，无副作用），所以渲染结果可哈希。

| signature | `data` 必需键 | 取值约束 | 页面交互 |
| --- | --- | --- | --- |
| `causal_chain` | `steps[]` | 2–6 步；每步 `title`(≤10 字) + `text`(≤120 字)，`detail` 可选 | 点击步骤 → 高亮 + 展开 detail；键盘可操作 |
| `type_selector` | `types[]` | 2–5 项；`name`(≤8 字) + `tagline`(≤20 字) + `text`(≤120 字) | 按钮组切换右侧描述，单选 |
| `matrix` | `cols[]` `rows[]` | 2–4 列；2–6 行；单元格 ≤ 30 字 | 行悬停高亮（纯 CSS 可见性，无 JS 依赖） |
| `timeline` | `items[]` | 3–8 项；`when`(≤12 字) + `title` + `text`(≤100 字) | 竖向时间轴，当前项强调 |
| `decision_tree` | `root` | 深度 ≤ 3，每层 2–3 选项；叶子节点为结果文案 | 点击选项逐层展开，可回退 |
| `questions` | `items[]` | 2–6 条；`q`(≤40 字) + `hint` 可选 | 卡片翻转显示提示（`prefers-reduced-motion` 时直接切换） |
| `story_card` | `title` `body` | `label` 可选；`body` ≤ 200 字 | 无（阅读块） |
| `before_after` | `left` `right` | 各含 `title` + `points[]`(2–5 条，每条 ≤ 40 字) | 两栏对照，移动端上下堆叠 |
| `accordion` | `items[]` | 2–7 项；`title`(≤16 字) + `body`(≤200 字) | 原生 `<details>`，无需 JS |
| `quote_card` | `text` | ≤ 120 字；`speaker` `source` 可选 | 无 |
| `prose` | `paragraphs[]` | 1–5 段，每段 ≤ 240 字 | 无（组件表达力不足时的逃生口） |

**降级规则**：任一 section 的 `data` 校验失败且修复两轮未过 → 渲染器用 `prose` 承接其 `lead`，页面仍出、不中断。

---

## 6. 主题变量（沿用原项目 21 个变量名，值自写）

| 变量 | 作用 | paper（暖纸） | minimal（极简） | dark（夜读） |
| --- | --- | --- | --- | --- |
| `--paper` | 页面底色 | `#f7f3ea` | `#ffffff` | `#14161a` |
| `--paper-deep` | 次级底 | `#efe8da` | `#f5f6f7` | `#1b1f25` |
| `--ink` | 主文字 | `#2b2622` | `#1a1a1a` | `#e6e3dd` |
| `--ink-soft` / `--ink-soft-2` | 次级/三级文字 | `#5a5049` / `#8a817a` | `#555` / `#888` | `#b9b3aa` / `#8a857e` |
| `--line` | 分隔线 | `rgba(43,38,34,.14)` | `rgba(0,0,0,.12)` | `rgba(255,255,255,.14)` |
| `--red` / `--blue` / `--green` / `--gold` | 强调与语义色 | `#b4462f` / `#3a5c80` / `#4a6f52` / `#a8842c` | 同左降饱和 | 提亮 15% |
| `--tint-accent` / `--tint-accent-strong` | 强调底色 | `rgba(180,70,47,.07)` / `.14` | `rgba(0,0,0,.05)` / `.1` | `rgba(255,255,255,.06)` / `.12` |
| `--surface` / `--surface-strong` | 卡片面 | `#fffdf8` / `#fdf9f1` | `#fff` / `#fafafa` | `#1e2229` / `#242a32` |
| `--bar-bg` | 吸顶 Tab 底 | `rgba(247,243,234,.9)` | `rgba(255,255,255,.9)` | `rgba(20,22,26,.9)` |
| `--shadow` | 阴影 | `0 10px 30px rgba(43,38,34,.08)` | `0 6px 20px rgba(0,0,0,.06)` | `0 10px 30px rgba(0,0,0,.4)` |
| `--font-body` / `--font-display` | 正文字/标题字 | 系统中文宋黑混合栈 | 同 | 同 |
| `--bg` / `--white` | 兼容别名 | 同 paper / `#fff` | 同 | 同 |

新增主题 = 只写一份变量覆盖，不动结构；`meta.theme` 不在枚举内 → `E202`。

---

## 7. 确定性工程规则（A1 的实现基础）

1. **输入规范化**：IR 读入后做 canonical JSON（键按固定顺序、`ensure_ascii=False`、无尾随空格），再进渲染。
2. **禁用非确定性源**：不读时间、不生成 uuid/随机数、不依赖字典遍历顺序、不写 `repr(float)`；所有数值经 `format(x, '.2f')` 统一。
3. **id 派生不新造**：`panel-<section.id>`、`tab-<section.id>`，不生成任何“唯一 id”。
4. **转义固定**：文本一律经同一函数（`& < > " '` 五个实体，其余保留原字符），不许两套路径。
5. **换行与缩进**：统一 `\n`、两空格缩进、行尾去空白；模板字符串不拼接随机空白。
6. **排序稳定**：sections 按 IR 顺序输出，不排序；tab 与 panel 由同一次遍历生成，天然对齐。
7. **CSS/JS 内联固定**：主题 css 与组件 css 以固定顺序拼接，组件 JS 只有一段（开关/切换/复制），不按需拼装。

---

## 8. CLI 与错误码

```
bookpage lint  <ir.json>              # 结构校验，只打印错误
bookpage build <ir.json> <out.html>   # 生成，成功打印 "built: N sections, M bytes"
bookpage tokens <file.md|txt>         # 中文/混合文本 token 估算
bookpage chapters <file.md>           # 章节识别（第X章/章/回）
```

| 退出码 | 含义 |
| --- | --- |
| 0 | 成功 |
| 1 | lint 有错误（已打印 E1xx/E2xx） |
| 2 | 参数/用法错误 |

| 错误码 | 触发 | 输出形态 |
| --- | --- | --- |
| `E100` | `schema` 不是 `bookpage/1` | `E100 schema: 期望 bookpage/1` |
| `E101` | `signature` 不在白名单 | `E101 sections[2].signature: 未知组件 "matrix2"` |
| `E102` | 必需键缺失 | `E102 sections[3].data.steps: 缺失` |
| `E103` | 类型不符 | `E103 meta.sources: 期望 array，得到 string` |
| `E104` | 取值越界（数量/长度） | `E104 sections[0].data.steps: 6 步，上限 6`（越界即报） |
| `E105` | `id` 重复或非法 | `E105 sections[4].id: "s1" 重复` |
| `E201` | 生成串残留 `{{` / `}}` | `E201 输出含未替换占位符` |
| `E202` | 主题不在枚举 | `E202 meta.theme: 未知主题 "midnight"` |

---

## 9. 提示词契约与修复环

对模型（或人工）只有四条硬约束：

1. 只输出一个 JSON 对象，不输出 HTML/解释。
2. `signature` 必须来自 §5 白名单。
3. `data` 的键名与 §5 完全一致，不许多造键。
4. 所有长度上限可越界一次，但 lint 会以 `E104` 回传字段路径。

修复环：`lint` 失败 → 只回传「错误码 + 字段路径 + 期望」，不带整个 IR → 模型只改该段 → 重跑 lint。**最多 2 轮**；仍失败则按 §5 降级 `prose` 保证出页，并在 HTML 注释里留一行 `<!-- degraded: sections[3] -->` 以便排查。

效果：把原项目“45% 的衔接层（写 DOM）”降级为“写字段值”，错误被 lint 挡住、结果可重渲、单页成本从 34 KB 降到 IR 的几 KB。

---

## 10. 可访问性与响应式

- Tab：`role="tab"` + `aria-selected`；panel：`role="tabpanel"` + `aria-labelledby`；键盘 ←/→/Home 切换。
- 组件级交互全部有键盘等价物：`<details>` 原生折叠、按钮组用 `<button>`、因果链步骤用 `<button aria-expanded>`。
- 对比度 ≥ 4.5:1（三套主题各测一遍）；`prefers-reduced-motion: reduce` 时禁用过渡与卡片翻转。
- 断点沿用原项目的 880px / 520px：≥880 三栏网格 → 880 以下单栏；520 以下 Tab 横向滚动、矩阵改为卡片列表。
- 离线可用：无外链字体/CDN，全部内联；单文件可直接双击打开。

---

## 11. 验收（可执行的 A1–A7）

| 编号 | 命令 | 期望 |
| --- | --- | --- |
| A1 | `bookpage build demo.json a.html && bookpage build demo.json b.html && sha256sum a.html b.html` | 两个哈希完全相同 |
| A2 | `bookpage lint bad-sig.json; echo $?` | 打印 `E101 …`，退出码 1 |
| A3 | `bookpage lint bad-key.json; echo $?` | 打印 `E102 …`，退出码 1 |
| A4 | `bookpage chapters sample-book.md` | `chapters: 8` |
| A5 | `bookpage tokens sample-book.md` | 结果 ≥ 原实现的 8 倍，且落在字符量级（约 3,000–4,500） |
| A6 | `bookpage build demo.json c.html && grep -c '{{' c.html` | 计数 0，且 tab 数 = panel 数 = section 数 |
| A7 | 干净 shell（无 venv、无 pip、断网）`python bookpage.py build demo.json d.html` | 成功，无 ImportError |

A1–A7 写成 `tests/selftest.py` 一条命令跑完，打印 PASS/FAIL —— 这是原项目缺的东西（它唯一的自动化脚本把 macOS 路径写死了）。

---

## 12. MVP 范围

**做**
- `bookpage.py` 单文件 CLI：`lint` / `build` / `tokens` / `chapters`
- 10 组件 + `prose`、3 主题、1 份样例 IR（6 节，覆盖 6 种组件）
- `tests/selftest.py`（A1–A7）
- `README.md`（用法 + 为什么确定性）

**不做（v1）**
- 全书 overview 模式（frameworks/chapterMap/conceptMap/decisionRules）：契约留位，v2 补渲染
- PDF/EPUB 提取：复用 book-to-skill，不重写提取器
- 浏览器端 DOM 校验：改为对 IR 与生成串的纯函数断言（不引入 playwright）
- 发布/托管、站内搜索、多页站点

---

## 13. 风险与取舍

| 风险 | 说明 | 应对 |
| --- | --- | --- |
| 确定性 ≠ 质量 | 渲染稳定，但内容取决于模型产 IR 的水平 | lint 保证结构；写作质量靠提示词 + 复用原项目的组合作法 |
| 组件库是人工劳动 | 10 个组件要手写 CSS/JS | 一次写完即成资产，后续页面零边际成本 |
| IR 表达力有限 | 自由排版被 schema 限制 | 保留 `prose` 逃生口与降级路径；复杂页再扩签名 |
| 许可 | 原项目无 LICENSE，资产不可复用 | 代码与 CSS 全自写，只借“签名命名 + 变量名”接口 |
| 纯 stdlib 的 md 上限 | 不如 Pandoc 全 | 需要完整 md 语义时接 Pandoc 作可选后端 |
| 单页上限 | 一页多模块，超长页在移动端难读 | 强制 ≤ 8 个 section；超出拆成第二页（`build --part`，v2） |

---

## 14. 落地顺序

1. `bookpage.py` 骨架 + `prose` + `build` + 主题注入 → 先让 A1/A6/A7 过（证明确定性成立）
2. 逐组件实现（每个组件带校验函数），A2/A3/A4 逐步收紧（顺序：accordion → quote_card → story_card → matrix → timeline → causal_chain → type_selector → before_after → questions → decision_tree）
3. `tokens` / `chapters` 两个纯函数 + A5
4. 样例 IR + demo 页，连跑两次比对哈希，再对照 `bookpage-mockup.html` 调版式
5. README + 差异表（用实测数字，不用形容词）

预计一个下午（约 600–800 行，含 CSS/JS），无新增依赖。
