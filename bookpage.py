#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bookpage 1.0 — 把结构化 IR 渲染成确定性单文件 HTML。

零第三方依赖（仅 Python 标准库）。四个子命令：
    python bookpage.py lint  <ir.json>
    python bookpage.py build <ir.json> <out.html> [--degrade]
    python bookpage.py tokens <file>
    python bookpage.py chapters <file>

设计原则：同输入 → 字节级相同输出。不读时间、不生成 uuid、不依赖字典顺序、
所有文本走同一条转义路径、换行与缩进固定。
"""

import json
import re
import sys

VERSION = "1.0"
SCHEMA = "bookpage/1"
EXIT_OK = 0
EXIT_LINT = 1
EXIT_USAGE = 2

ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,15}$")
CHAPTER_RE = re.compile(r"第\s*[0-9〇零一二三四五六七八九十百千两]+\s*[章节回卷篇]")
EN_CHAPTER_RE = re.compile(r"^(?:chapter|part)\s+[0-9ivxlc]+\b", re.I)
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


# ---------------------------------------------------------------- 主题层
THEMES = {
    "paper": {
        "--paper": "#f7f3ea", "--paper-deep": "#efe8da", "--ink": "#2b2622",
        "--ink-soft": "#5a5049", "--ink-soft-2": "#8a817a",
        "--line": "rgba(43,38,34,.14)",
        "--red": "#b4462f", "--blue": "#3a5c80", "--green": "#4a6f52", "--gold": "#a8842c",
        "--tint-accent": "rgba(180,70,47,.07)", "--tint-accent-strong": "rgba(180,70,47,.14)",
        "--surface": "#fffdf8", "--surface-strong": "#fdf9f1",
        "--bar-bg": "rgba(247,243,234,.9)", "--shadow": "0 10px 30px rgba(43,38,34,.08)",
        "--bg": "#f7f3ea", "--white": "#ffffff",
        "--font-body": '-apple-system,"PingFang SC","Microsoft YaHei",system-ui,sans-serif',
        "--font-display": 'Georgia,"Songti SC","Times New Roman",serif',
    },
    "minimal": {
        "--paper": "#ffffff", "--paper-deep": "#f5f6f7", "--ink": "#1a1a1a",
        "--ink-soft": "#555555", "--ink-soft-2": "#888888",
        "--line": "rgba(0,0,0,.12)",
        "--red": "#9c3a26", "--blue": "#334f6b", "--green": "#415f48", "--gold": "#8f7024",
        "--tint-accent": "rgba(0,0,0,.05)", "--tint-accent-strong": "rgba(0,0,0,.10)",
        "--surface": "#ffffff", "--surface-strong": "#fafafa",
        "--bar-bg": "rgba(255,255,255,.9)", "--shadow": "0 6px 20px rgba(0,0,0,.06)",
        "--bg": "#ffffff", "--white": "#ffffff",
        "--font-body": '-apple-system,"PingFang SC","Microsoft YaHei",system-ui,sans-serif',
        "--font-display": 'Georgia,"Songti SC","Times New Roman",serif',
    },
    "dark": {
        "--paper": "#14161a", "--paper-deep": "#1b1f25", "--ink": "#e6e3dd",
        "--ink-soft": "#b9b3aa", "--ink-soft-2": "#8a857e",
        "--line": "rgba(255,255,255,.14)",
        "--red": "#d0684f", "--blue": "#6b8fb5", "--green": "#7a9c83", "--gold": "#c3a04a",
        "--tint-accent": "rgba(255,255,255,.06)", "--tint-accent-strong": "rgba(255,255,255,.12)",
        "--surface": "#1e2229", "--surface-strong": "#242a32",
        "--bar-bg": "rgba(20,22,26,.9)", "--shadow": "0 10px 30px rgba(0,0,0,.4)",
        "--bg": "#14161a", "--white": "#ffffff",
        "--font-body": '-apple-system,"PingFang SC","Microsoft YaHei",system-ui,sans-serif',
        "--font-display": 'Georgia,"Songti SC","Times New Roman",serif',
    },
}
THEME_NAMES = ("paper", "minimal", "dark")


def theme_block(name):
    """生成 :root 变量块。键顺序固定 = THEMES 字面量顺序。"""
    items = []
    for k, v in THEMES[name].items():
        items.append("  %s:%s;" % (k, v))
    return ":root{\n" + "\n".join(items) + "\n}"


# ---------------------------------------------------------------- 组件层 CSS
BASE_CSS = """
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-family:var(--font-body);line-height:1.75;-webkit-font-smoothing:antialiased}
.page{max-width:1080px;margin:0 auto;padding:0 24px 96px}
.topbar{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:12px;padding:10px 24px;background:var(--bar-bg);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.topbar .crumb{font-size:12px;letter-spacing:.08em;color:var(--ink-soft-2);flex:1}
.btn{font:inherit;font-size:13px;padding:6px 14px;border-radius:999px;cursor:pointer;border:1px solid var(--line);background:var(--surface);color:var(--ink-soft)}
.btn:hover{border-color:var(--red);color:var(--red)}
.btn[aria-pressed="true"]{background:var(--tint-accent-strong);border-color:var(--red);color:var(--red)}
.hero{padding:56px 0 28px;border-bottom:1px solid var(--line)}
.hero .eyebrow{font-size:12px;letter-spacing:.14em;color:var(--red);margin-bottom:14px}
.hero h1{font-family:var(--font-display);font-weight:600;font-size:clamp(30px,4.4vw,46px);line-height:1.28;margin:0 0 18px;letter-spacing:-.01em}
.hero .lede{font-size:17px;color:var(--ink-soft);max-width:46em;margin:0}
.hero .thesis{margin-top:20px;display:inline-block;padding:10px 16px;border-left:3px solid var(--gold);background:var(--surface-strong);font-size:14px;color:var(--ink-soft)}
nav.tabs{position:sticky;top:44px;z-index:15;display:flex;gap:6px;overflow-x:auto;padding:12px 0;background:var(--bar-bg);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.tab{flex:0 0 auto;font:inherit;font-size:14px;padding:8px 16px;border-radius:999px;border:1px solid transparent;background:transparent;color:var(--ink-soft);cursor:pointer;white-space:nowrap}
.tab:hover{color:var(--ink);background:var(--surface)}
.tab[aria-selected="true"]{color:var(--red);background:var(--surface);border-color:var(--red);box-shadow:0 2px 10px rgba(180,70,47,.12)}
.panel{display:none;padding:36px 0 0}
.panel.active{display:block}
.panel h2{font-family:var(--font-display);font-size:24px;margin:0 0 6px;font-weight:600}
.lead{font-size:15px;color:var(--ink-soft);margin:0 0 24px;max-width:44em}
.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:20px 22px;box-shadow:var(--shadow)}
.card h3{font-size:16px;margin:0 0 8px;font-weight:600}
.card p{margin:0;font-size:14.5px;color:var(--ink-soft)}
.meta-line{display:flex;align-items:center;gap:10px;margin-top:22px;padding-top:14px;border-top:1px dashed var(--line);font-size:12.5px;color:var(--ink-soft-2)}
.meta-line .grow{flex:1}
body.show-sources .src{display:inline}
body:not(.show-sources) .src{display:none}
.chain{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px}
.chain-step{font:inherit;text-align:left;cursor:pointer;padding:14px;border-radius:12px;border:1px solid var(--line);background:var(--surface);color:var(--ink);border-top:3px solid var(--blue)}
.chain-step:hover{border-color:var(--blue)}
.chain-step[aria-expanded="true"]{border-color:var(--red);border-top-color:var(--red);background:var(--tint-accent)}
.chain-step .n{font-size:11px;letter-spacing:.1em;color:var(--ink-soft-2)}
.chain-step .t{font-size:15px;font-weight:600;margin:6px 0 4px;display:block}
.chain-step .s{font-size:13px;color:var(--ink-soft);line-height:1.6}
.chain-out{min-height:76px;padding:18px 20px;border-radius:12px;background:var(--surface-strong);border:1px dashed var(--line);font-size:14.5px;color:var(--ink-soft)}
.matrix{width:100%;border-collapse:collapse;background:var(--surface);border-radius:12px;overflow:hidden;border:1px solid var(--line)}
.matrix th,.matrix td{padding:12px 14px;text-align:left;font-size:13.5px;border-bottom:1px solid var(--line);vertical-align:top}
.matrix thead th{background:var(--paper-deep);font-size:12px;letter-spacing:.06em;color:var(--ink-soft)}
.matrix tbody tr:hover td{background:var(--tint-accent)}
.matrix td:first-child{font-weight:600;color:var(--ink)}
.matrix tbody tr:last-child td{border-bottom:0}
.timeline{position:relative;margin:0;padding:0 0 0 26px;list-style:none;border-left:1px solid var(--line)}
.timeline li{position:relative;padding:0 0 22px}
.timeline li::before{content:"";position:absolute;left:-31px;top:8px;width:9px;height:9px;border-radius:50%;background:var(--paper);border:2px solid var(--red)}
.timeline .when{font-size:12px;letter-spacing:.06em;color:var(--red);font-weight:600}
.timeline .what{font-size:15px;font-weight:600;margin:4px 0}
.timeline .why{font-size:13.5px;color:var(--ink-soft)}
details.fold{border:1px solid var(--line);border-radius:12px;margin-bottom:10px;background:var(--surface)}
details.fold summary{cursor:pointer;padding:14px 18px;font-size:14.5px;font-weight:600;list-style:none;display:flex;align-items:center;gap:10px}
details.fold summary::-webkit-details-marker{display:none}
details.fold summary::before{content:"+";display:inline-grid;place-items:center;width:20px;height:20px;border-radius:5px;background:var(--tint-accent);color:var(--red);font-size:14px;flex:0 0 auto}
details.fold[open] summary::before{content:"\\2212"}
details.fold[open]{border-color:var(--red);box-shadow:var(--shadow)}
details.fold .body{padding:0 18px 16px;font-size:14px;color:var(--ink-soft)}
.dt-node{border:1px solid var(--line);border-radius:12px;background:var(--surface);padding:4px 14px;margin:0 0 8px}
.dt-node summary{cursor:pointer;font-size:14.5px;padding:10px 0;list-style:none;font-weight:600}
.dt-node summary::-webkit-details-marker{display:none}
.dt-opts{padding:0 0 8px 8px;border-left:2px solid var(--tint-accent-strong);margin-left:6px}
.dt-result{font-size:14px;color:var(--ink-soft);padding:6px 0 10px}
.ba{display:grid;grid-template-columns:1fr 1fr;border:1px solid var(--line);border-radius:12px;overflow:hidden}
.ba-col{padding:20px 22px;background:var(--surface)}
.ba-col.right{background:var(--surface-strong);border-left:1px solid var(--line)}
.ba-col h4{font-size:14px;letter-spacing:.06em;margin:0 0 12px;color:var(--ink-soft-2);font-weight:600}
.ba-col ul{margin:0;padding-left:18px;font-size:14px;color:var(--ink-soft)}
.ba-col li{margin-bottom:7px}
.selector{display:grid;grid-template-columns:220px 1fr;gap:18px;align-items:start}
.sel-btns{display:flex;flex-direction:column;gap:8px}
.sel-btn{font:inherit;text-align:left;padding:11px 14px;border-radius:10px;cursor:pointer;border:1px solid var(--line);background:var(--surface);color:var(--ink-soft)}
.sel-btn b{display:block;font-size:14.5px;color:var(--ink);font-weight:600}
.sel-btn span{font-size:12.5px}
.sel-btn[aria-pressed="true"]{border-color:var(--blue);background:var(--surface-strong);color:var(--ink)}
.sel-out{padding:18px 20px;border-radius:12px;border:1px dashed var(--line);min-height:150px;background:var(--surface-strong);font-size:14.5px;color:var(--ink-soft)}
.quote{margin:0;padding:26px 28px;border-left:4px solid var(--gold);background:var(--surface);border-radius:0 12px 12px 0;font-family:var(--font-display);font-size:19px;line-height:1.7;color:var(--ink)}
.quote cite{display:block;margin-top:12px;font-family:var(--font-body);font-size:13px;font-style:normal;color:var(--ink-soft-2)}
.figures{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px}
.fig{padding:20px 22px;border:1px solid var(--line);border-radius:14px;background:var(--surface)}
.fig b{display:block;font-family:var(--font-display);font-size:30px;line-height:1.15;color:var(--ink)}
.fig span{display:block;margin-top:6px;font-size:13px;color:var(--ink-soft)}
.fig em{display:block;margin-top:8px;font-size:12px;font-style:normal;color:var(--ink-soft-2)}
.story{position:relative}
.story .label{font-size:11px;letter-spacing:.12em;color:var(--red)}
.prose{font-size:15px;color:var(--ink-soft)}
.prose p{margin:0 0 14px}
.questions{margin-top:56px;padding-top:28px;border-top:1px solid var(--line)}
.questions h2{font-family:var(--font-display);font-size:22px;margin:0 0 4px}
.qgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.qcard{font:inherit;text-align:left;cursor:pointer;padding:18px;border-radius:12px;border:1px solid var(--line);background:var(--surface);min-height:132px}
.qcard:hover{border-color:var(--gold)}
.qcard .q{font-size:14.5px;font-weight:600;display:block;margin-bottom:10px}
.qcard .hint{font-size:13px;color:var(--ink-soft);opacity:0}
.qcard[aria-pressed="true"]{border-color:var(--gold);background:var(--surface-strong)}
.qcard[aria-pressed="true"] .hint{opacity:1}
.footer{margin-top:56px;padding-top:20px;border-top:1px solid var(--line);font-size:12.5px;color:var(--ink-soft-2)}
#toast{position:fixed;left:50%;bottom:28px;transform:translate(-50%,20px);opacity:0;pointer-events:none;background:var(--ink);color:var(--paper);font-size:13px;padding:9px 16px;border-radius:999px;z-index:40}
#toast.on{opacity:1;transform:translate(-50%,0)}
@media (max-width:880px){.selector,.ba,.qgrid{grid-template-columns:1fr}.ba-col.right{border-left:0;border-top:1px solid var(--line)}.chain{grid-template-columns:1fr 1fr}}
@media (max-width:520px){.page{padding:0 16px 72px}.hero{padding:36px 0 20px}.chain{grid-template-columns:1fr}.matrix{display:block;overflow-x:auto}nav.tabs{top:40px}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""

# ---------------------------------------------------------------- 组件层 JS
BASE_JS = """
(function () {
  var body = document.body;
  var toggle = document.getElementById("srcToggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var on = body.classList.toggle("show-sources");
      toggle.setAttribute("aria-pressed", on ? "true" : "false");
      toggle.textContent = on ? "隐藏出处" : "显示出处";
    });
  }
  var tabs = Array.prototype.slice.call(document.querySelectorAll(".tab"));
  function activate(tab) {
    tabs.forEach(function (t) {
      var on = t === tab;
      t.setAttribute("aria-selected", on ? "true" : "false");
      var p = document.getElementById(t.getAttribute("data-target"));
      if (p) { p.classList.toggle("active", on); }
    });
  }
  tabs.forEach(function (t, i) {
    t.addEventListener("click", function () { activate(t); });
    t.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") { return; }
      var n = tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
      activate(n); n.focus();
    });
  });
  // 初始选中：以已经 active 的面板为准，没有则回退第一个 tab，保证 tab 与面板永远一致。
  var shown = document.querySelector(".panel.active");
  var first = shown ? document.querySelector('.tab[data-target="' + shown.id + '"]') : null;
  activate(first || tabs[0]);
  Array.prototype.slice.call(document.querySelectorAll(".chain-step")).forEach(function (s) {
    s.addEventListener("click", function () {
      var out = document.getElementById(s.getAttribute("data-out"));
      if (!out) { return; }
      var open = s.getAttribute("aria-expanded") === "true";
      Array.prototype.slice.call(s.parentNode.querySelectorAll(".chain-step")).forEach(function (o) {
        o.setAttribute("aria-expanded", "false");
      });
      if (open) { out.textContent = out.getAttribute("data-idle"); return; }
      s.setAttribute("aria-expanded", "true");
      out.textContent = s.getAttribute("data-detail");
    });
  });
  Array.prototype.slice.call(document.querySelectorAll(".selector")).forEach(function (box) {
    var out = box.querySelector(".sel-out");
    Array.prototype.slice.call(box.querySelectorAll(".sel-btn")).forEach(function (b) {
      b.addEventListener("click", function () {
        Array.prototype.slice.call(box.querySelectorAll(".sel-btn")).forEach(function (o) {
          o.setAttribute("aria-pressed", "false");
        });
        b.setAttribute("aria-pressed", "true");
        if (out) { out.textContent = b.getAttribute("data-text"); }
      });
    });
  });
  Array.prototype.slice.call(document.querySelectorAll(".qcard")).forEach(function (c) {
    c.addEventListener("click", function () {
      c.setAttribute("aria-pressed", c.getAttribute("aria-pressed") === "true" ? "false" : "true");
    });
  });
  var toast = document.getElementById("toast");
  function showToast(m) {
    if (!toast) { return; }
    toast.textContent = m;
    toast.classList.add("on");
    window.setTimeout(function () { toast.classList.remove("on"); }, 1800);
  }
  Array.prototype.slice.call(document.querySelectorAll(".deep")).forEach(function (b) {
    b.addEventListener("click", function () {
      var book = b.getAttribute("data-book") || "";
      var c = b.getAttribute("data-concept") || "";
      var p = "对《" + book + "》中「" + c + "」，深入追问：请用书里的论证给我一个具体例子，并指出它成立的前提。";
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(p).then(function () { showToast("追问提示词已复制"); },
                                               function () { showToast("复制失败，请手动选择"); });
      } else { showToast("当前环境不支持剪贴板"); }
    });
  });
})();
"""


# ---------------------------------------------------------------- 工具函数
def esc(text):
    """唯一转义路径：五个实体，其余字符原样保留。"""
    if text is None:
        return ""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;"))


def _typename(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    if isinstance(v, (int, float)):
        return "number"
    return type(v).__name__


def _path(base, key):
    return "%s.%s" % (base, key) if base else key


def fv_str(errs, base, data, key, lo, hi, required=True):
    """校验字符串字段：长度按字符计（中文一字算一）。"""
    key_path = _path(base, key)
    if not isinstance(data, dict):
        return None
    if key not in data:
        if required:
            errs.append(("E102", key_path, "缺失"))
        return None
    v = data[key]
    if not isinstance(v, str):
        errs.append(("E103", key_path, "期望 string，得到 %s" % _typename(v)))
        return None
    n = len(v)
    if n < lo:
        errs.append(("E104", key_path, "%d 字，下限 %d" % (n, lo)))
    if hi is not None and n > hi:
        errs.append(("E104", key_path, "%d 字，上限 %d" % (n, hi)))
    return v


def fv_list(errs, base, data, key, lo, hi, required=True):
    key_path = _path(base, key)
    if not isinstance(data, dict):
        return None
    if key not in data:
        if required:
            errs.append(("E102", key_path, "缺失"))
        return None
    v = data[key]
    if not isinstance(v, list):
        errs.append(("E103", key_path, "期望 array，得到 %s" % _typename(v)))
        return None
    n = len(v)
    if n < lo or (hi is not None and n > hi):
        errs.append(("E104", key_path, "%d 项，期望 %d–%d" % (n, lo, hi)))
    return v


# ---------------------------------------------------------------- 各组件校验
def _v_causal_chain(errs, base, data):
    steps = fv_list(errs, base, data, "steps", 2, 6)
    for i, s in enumerate(steps or []):
        p = "%s.steps[%d]" % (base, i)
        if not isinstance(s, dict):
            errs.append(("E103", p, "期望 object，得到 %s" % _typename(s)))
            continue
        fv_str(errs, p, s, "title", 1, 10)
        fv_str(errs, p, s, "text", 1, 120)
        fv_str(errs, p, s, "detail", 0, 160, required=False)


def _v_type_selector(errs, base, data):
    types = fv_list(errs, base, data, "types", 2, 5)
    for i, t in enumerate(types or []):
        p = "%s.types[%d]" % (base, i)
        if not isinstance(t, dict):
            errs.append(("E103", p, "期望 object，得到 %s" % _typename(t)))
            continue
        fv_str(errs, p, t, "name", 1, 8)
        fv_str(errs, p, t, "tagline", 0, 20, required=False)
        fv_str(errs, p, t, "text", 1, 120)


def _v_matrix(errs, base, data):
    fv_str(errs, base, data, "label_header", 0, 8, required=False)
    cols = fv_list(errs, base, data, "cols", 2, 4)
    for i, c in enumerate(cols or []):
        if not isinstance(c, str):
            errs.append(("E103", "%s.cols[%d]" % (base, i), "期望 string，得到 %s" % _typename(c)))
        elif len(c) > 16:
            errs.append(("E104", "%s.cols[%d]" % (base, i), "%d 字，上限 16" % len(c)))
    rows = fv_list(errs, base, data, "rows", 2, 6)
    want = len(cols) if cols else None
    for i, r in enumerate(rows or []):
        p = "%s.rows[%d]" % (base, i)
        if not isinstance(r, dict):
            errs.append(("E103", p, "期望 object，得到 %s" % _typename(r)))
            continue
        fv_str(errs, p, r, "label", 1, 16)
        cells = fv_list(errs, p, r, "cells", want or 1, want or 4)
        for j, cell in enumerate(cells or []):
            if not isinstance(cell, str):
                errs.append(("E103", "%s.cells[%d]" % (p, j), "期望 string，得到 %s" % _typename(cell)))
            elif len(cell) > 40:
                errs.append(("E104", "%s.cells[%d]" % (p, j), "%d 字，上限 40" % len(cell)))


def _v_timeline(errs, base, data):
    items = fv_list(errs, base, data, "items", 3, 8)
    for i, it in enumerate(items or []):
        p = "%s.items[%d]" % (base, i)
        if not isinstance(it, dict):
            errs.append(("E103", p, "期望 object，得到 %s" % _typename(it)))
            continue
        fv_str(errs, p, it, "when", 1, 12)
        fv_str(errs, p, it, "title", 1, 16)
        fv_str(errs, p, it, "text", 0, 100, required=False)


def _v_decision_tree(errs, base, data):
    root = data.get("root") if isinstance(data, dict) else None
    if not isinstance(root, dict):
        errs.append(("E102", base + ".root", "缺失或不是 object"))
        return

    def walk(node, path, depth):
        if depth > 2:
            errs.append(("E104", path, "嵌套深度超过 3 层"))
            return
        fv_str(errs, path, node, "q", 1, 60)
        opts = fv_list(errs, path, node, "options", 2, 3)
        for i, o in enumerate(opts or []):
            op = "%s.options[%d]" % (path, i)
            if not isinstance(o, dict):
                errs.append(("E103", op, "期望 object，得到 %s" % _typename(o)))
                continue
            fv_str(errs, op, o, "label", 1, 16)
            has_result = "result" in o
            has_next = "next" in o
            if has_result == has_next:
                errs.append(("E102", op, "必须且只能有 result 或 next 之一"))
            if has_result:
                fv_str(errs, op, o, "result", 1, 120)
            if has_next:
                if not isinstance(o["next"], dict):
                    errs.append(("E103", op + ".next", "期望 object"))
                else:
                    walk(o["next"], op + ".next", depth + 1)

    walk(root, base + ".root", 0)


def _v_questions(errs, base, data):
    items = fv_list(errs, base, data, "items", 2, 6)
    for i, it in enumerate(items or []):
        p = "%s.items[%d]" % (base, i)
        if not isinstance(it, dict):
            errs.append(("E103", p, "期望 object，得到 %s" % _typename(it)))
            continue
        fv_str(errs, p, it, "q", 1, 40)
        fv_str(errs, p, it, "hint", 0, 60, required=False)


def _v_story_card(errs, base, data):
    fv_str(errs, base, data, "title", 1, 20)
    fv_str(errs, base, data, "body", 1, 200)
    fv_str(errs, base, data, "label", 0, 12, required=False)


def _v_before_after(errs, base, data):
    for side in ("left", "right"):
        p = _path(base, side)
        obj = data.get(side) if isinstance(data, dict) else None
        if not isinstance(obj, dict):
            errs.append(("E102", p, "缺失或不是 object"))
            continue
        fv_str(errs, p, obj, "title", 1, 10)
        pts = fv_list(errs, p, obj, "points", 2, 5)
        for i, pt in enumerate(pts or []):
            if not isinstance(pt, str):
                errs.append(("E103", "%s.points[%d]" % (p, i), "期望 string"))
            elif len(pt) > 40:
                errs.append(("E104", "%s.points[%d]" % (p, i), "%d 字，上限 40" % len(pt)))


def _v_accordion(errs, base, data):
    items = fv_list(errs, base, data, "items", 2, 7)
    for i, it in enumerate(items or []):
        p = "%s.items[%d]" % (base, i)
        if not isinstance(it, dict):
            errs.append(("E103", p, "期望 object，得到 %s" % _typename(it)))
            continue
        fv_str(errs, p, it, "title", 1, 16)
        fv_str(errs, p, it, "body", 1, 200)


def _v_quote_card(errs, base, data):
    fv_str(errs, base, data, "text", 1, 120)
    fv_str(errs, base, data, "speaker", 0, 20, required=False)
    fv_str(errs, base, data, "source", 0, 40, required=False)


def _v_key_figures(errs, base, data):
    items = fv_list(errs, base, data, "items", 2, 6)
    for i, it in enumerate(items or []):
        p = "%s.items[%d]" % (base, i)
        if not isinstance(it, dict):
            errs.append(("E103", p, "期望 object，得到 %s" % _typename(it)))
            continue
        fv_str(errs, p, it, "value", 1, 10)
        fv_str(errs, p, it, "label", 1, 14)
        fv_str(errs, p, it, "note", 0, 60, required=False)


def _v_prose(errs, base, data):
    paras = fv_list(errs, base, data, "paragraphs", 1, 5)
    for i, p in enumerate(paras or []):
        if not isinstance(p, str):
            errs.append(("E103", "%s.paragraphs[%d]" % (base, i), "期望 string"))
        elif len(p) > 240:
            errs.append(("E104", "%s.paragraphs[%d]" % (base, i), "%d 字，上限 240" % len(p)))


# ---------------------------------------------------------------- 各组件渲染
def _r_prose(sec, ctx):
    data = sec.get("data") or {}
    paras = data.get("paragraphs") or []
    return '<div class="prose">' + "".join("<p>%s</p>" % esc(p) for p in paras) + "</div>"


def _r_causal_chain(sec, ctx):
    data = sec.get("data") or {}
    sid = sec["id"]
    out_id = "chainout-" + sid
    steps = data.get("steps") or []
    parts = ['<div class="chain">']
    for i, s in enumerate(steps, 1):
        parts.append(
            '<button class="chain-step" type="button" aria-expanded="false" '
            'data-out="%s" data-detail="%s">'
            '<span class="n">%02d</span><span class="t">%s</span><span class="s">%s</span></button>'
            % (out_id, esc(s.get("detail") or ""), i, esc(s.get("title")), esc(s.get("text")))
        )
    parts.append("</div>")
    idle = "选择任意一步，这里会展开它在整个循环里的位置。"
    parts.append('<div class="chain-out" id="%s" data-idle="%s">%s</div>' % (out_id, esc(idle), esc(idle)))
    return "".join(parts)


def _r_type_selector(sec, ctx):
    data = sec.get("data") or {}
    types = data.get("types") or []
    parts = ['<div class="selector">', '<div class="sel-btns">']
    for i, t in enumerate(types):
        parts.append(
            '<button class="sel-btn" type="button" data-text="%s" aria-pressed="%s">'
            "<b>%s</b><span>%s</span></button>"
            % (esc(t.get("text")), "true" if i == 0 else "false", esc(t.get("name")), esc(t.get("tagline") or "")
               )
        )
    parts.append("</div>")
    parts.append('<div class="sel-out">%s</div>' % esc(types[0].get("text") if types else ""))
    parts.append("</div>")
    return "".join(parts)


def _r_matrix(sec, ctx):
    data = sec.get("data") or {}
    cols = data.get("cols") or []
    rows = data.get("rows") or []
    head = ("<tr>" + '<th class="corner">%s</th>' % esc(data.get("label_header") or "")
            + "".join("<th>%s</th>" % esc(c) for c in cols) + "</tr>")
    body = []
    for r in rows:
        cells = "".join("<td>%s</td>" % esc(c) for c in (r.get("cells") or []))
        body.append("<tr><td>%s</td>%s</tr>" % (esc(r.get("label")), cells))
    return ('<table class="matrix"><thead>%s</thead><tbody>%s</tbody></table>'
            % (head, "".join(body)))


def _r_timeline(sec, ctx):
    data = sec.get("data") or {}
    items = data.get("items") or []
    lis = "".join(
        '<li><div class="when">%s</div><div class="what">%s</div><div class="why">%s</div></li>'
        % (esc(it.get("when")), esc(it.get("title")), esc(it.get("text") or ""))
        for it in items
    )
    return '<ul class="timeline">%s</ul>' % lis


def _r_decision_tree(sec, ctx):
    def node(n):
        opts = []
        for o in n.get("options") or []:
            if "next" in o:
                opts.append('<details class="dt-node"><summary>%s</summary><div class="dt-opts">%s</div></details>'
                            % (esc(o.get("label")), node(o["next"])))
            else:
                opts.append('<details class="dt-node"><summary>%s</summary>'
                            '<div class="dt-result">%s</div></details>'
                            % (esc(o.get("label")), esc(o.get("result")))
                            )
        return ('<div class="dt-node"><div class="dt-q">%s</div><div class="dt-opts">%s</div></div>'
                % (esc(n.get("q")), "".join(opts)))

    root = (sec.get("data") or {}).get("root") or {}
    return node(root)


def _r_questions(sec, ctx):
    data = sec.get("data") or {}
    items = data.get("items") or []
    cards = "".join(
        '<button class="qcard" type="button" aria-pressed="false">'
        '<span class="q">%s</span><span class="hint">%s</span></button>'
        % (esc(it.get("q")), esc(it.get("hint") or "先自己答一遍，再对照书里的论证。"))
        for it in items
    )
    return '<div class="qgrid">%s</div>' % cards


def _r_story_card(sec, ctx):
    data = sec.get("data") or {}
    label = ('<div class="label">%s</div>' % esc(data.get("label"))) if data.get("label") else ""
    body = esc(data.get("body") or "").replace("\n", "<br>")
    return ('<div class="card story">%s<h3>%s</h3><p>%s</p></div>'
            % (label, esc(data.get("title")), body))


def _r_before_after(sec, ctx):
    data = sec.get("data") or {}

    def col(side, klass=""):
        obj = data.get(side) or {}
        pts = "".join("<li>%s</li>" % esc(p) for p in (obj.get("points") or []))
        return ('<div class="ba-col%s"><h4>%s</h4><ul>%s</ul></div>'
                % (klass, esc(obj.get("title")), pts))

    return '<div class="ba">%s%s</div>' % (col("left"), col("right", " right"))


def _r_key_figures(sec, ctx):
    data = sec.get("data") or {}
    cards = "".join(
        '<div class="fig"><b>%s</b><span>%s</span>%s</div>' % (
            esc(it.get("value")),
            esc(it.get("label")),
            ("<em>%s</em>" % esc(it.get("note"))) if it.get("note") else "",
        )
        for it in (data.get("items") or [])
    )
    return '<div class="figures">%s</div>' % cards


def _r_accordion(sec, ctx):
    data = sec.get("data") or {}
    items = data.get("items") or []
    out = "".join(
        '<details class="fold"><summary>%s</summary><div class="body">%s</div></details>'
        % (esc(it.get("title")), esc(it.get("body")))
        for it in items
    )
    return out


def _r_quote_card(sec, ctx):
    data = sec.get("data") or {}
    cite = ""
    if data.get("speaker") or data.get("source"):
        cite = "<cite>—— %s</cite>" % esc(" · ".join(
            [x for x in (data.get("speaker"), data.get("source")) if x]))
    return '<blockquote class="quote">%s%s</blockquote>' % (esc(data.get("text")), cite)


RENDERERS = {
    "causal_chain": _r_causal_chain,
    "type_selector": _r_type_selector,
    "matrix": _r_matrix,
    "timeline": _r_timeline,
    "decision_tree": _r_decision_tree,
    "questions": _r_questions,
    "story_card": _r_story_card,
    "before_after": _r_before_after,
    "accordion": _r_accordion,
    "key_figures": _r_key_figures,
    "quote_card": _r_quote_card,
    "prose": _r_prose,
}

VALIDATORS = {
    "causal_chain": _v_causal_chain,
    "type_selector": _v_type_selector,
    "matrix": _v_matrix,
    "timeline": _v_timeline,
    "decision_tree": _v_decision_tree,
    "questions": _v_questions,
    "story_card": _v_story_card,
    "before_after": _v_before_after,
    "accordion": _v_accordion,
    "key_figures": _v_key_figures,
    "quote_card": _v_quote_card,
    "prose": _v_prose,
}

SIGNATURES = sorted(RENDERERS)


# ---------------------------------------------------------------- 顶层校验
def lint_ir(ir):
    """返回 [(code, path, msg)]，空列表代表通过。"""
    errs = []
    if not isinstance(ir, dict):
        return [("E100", "", "期望 object，得到 %s" % _typename(ir))]
    if ir.get("schema") != SCHEMA:
        got = ir.get("schema")
        shown = str(got) if isinstance(got, str) else _typename(got)
        errs.append(("E100", "schema", "期望 %s，得到 %s" % (SCHEMA, shown)))

    meta = ir.get("meta")
    if not isinstance(meta, dict):
        errs.append(("E103", "meta", "期望 object，得到 %s" % _typename(meta)))
        meta = {}
    fv_str(errs, "meta", meta, "book", 1, 30)
    fv_str(errs, "meta", meta, "author", 0, 30, required=False)
    fv_str(errs, "meta", meta, "topic", 0, 30, required=False)
    mode = fv_str(errs, "meta", meta, "mode", 1, 12)
    if mode and mode != "theme":
        errs.append(("E100", "meta.mode", "v1 只支持 theme，收到 %r" % mode))
    theme = fv_str(errs, "meta", meta, "theme", 1, 12)
    if theme and theme not in THEMES:
        errs.append(("E202", "meta.theme", "未知主题 %r（可选 %s）" % (theme, "/".join(THEME_NAMES))))
    sources = meta.get("sources")
    if sources is not None:
        if not isinstance(sources, list):
            errs.append(("E103", "meta.sources", "期望 array，得到 %s" % _typename(sources)))
        elif len(sources) > 8:
            errs.append(("E104", "meta.sources", "%d 条，上限 8" % len(sources)))
        else:
            for i, s in enumerate(sources):
                if not isinstance(s, str):
                    errs.append(("E103", "meta.sources[%d]" % i, "期望 string"))

    hero = ir.get("hero")
    if not isinstance(hero, dict):
        errs.append(("E103", "hero", "期望 object，得到 %s" % _typename(hero)))
        hero = {}
    fv_str(errs, "hero", hero, "eyebrow", 0, 30, required=False)
    fv_str(errs, "hero", hero, "title", 1, 40)
    fv_str(errs, "hero", hero, "lede", 60, 140)
    fv_str(errs, "hero", hero, "thesis", 0, 60, required=False)

    secs = ir.get("sections")
    if not isinstance(secs, list):
        errs.append(("E103", "sections", "期望 array，得到 %s" % _typename(secs)))
        secs = []
    elif not (1 <= len(secs) <= 8):
        errs.append(("E104", "sections", "%d 个，期望 1–8" % len(secs)))

    seen = set()
    for i, s in enumerate(secs):
        p = "sections[%d]" % i
        if not isinstance(s, dict):
            errs.append(("E103", p, "期望 object，得到 %s" % _typename(s)))
            continue
        sid = s.get("id")
        if not isinstance(sid, str) or not ID_RE.match(sid):
            errs.append(("E105", p + ".id", "非法或缺失：%s" % ("null" if sid is None else str(sid))))
        elif sid in seen:
            errs.append(("E105", p + ".id", "%r 重复" % sid))
        else:
            seen.add(sid)
        fv_str(errs, p, s, "label", 1, 14)
        sig = s.get("signature")
        if not isinstance(sig, str) or sig not in RENDERERS:
            errs.append(("E101", p + ".signature",
                         "未知组件 %s" % (("%r" % sig) if isinstance(sig, str) else _typename(sig))))
        else:
            data = s.get("data")
            if not isinstance(data, dict):
                errs.append(("E103", p + ".data", "期望 object，得到 %s" % _typename(data)))
            else:
                VALIDATORS[sig](errs, p + ".data", data)
        fv_str(errs, p, s, "lead", 0, 80, required=False)
        fv_str(errs, p, s, "source", 0, 40, required=False)

    qs = ir.get("questions")
    if qs is not None:
        if not isinstance(qs, list):
            errs.append(("E103", "questions", "期望 array，得到 %s" % _typename(qs)))
        else:
            if len(qs) > 6:
                errs.append(("E104", "questions", "%d 条，上限 6" % len(qs)))
            for i, q in enumerate(qs):
                p = "questions[%d]" % i
                if not isinstance(q, dict):
                    errs.append(("E103", p, "期望 object，得到 %s" % _typename(q)))
                    continue
                fv_str(errs, p, q, "q", 1, 40)
                fv_str(errs, p, q, "hint", 0, 60, required=False)
    return errs


def format_error(e):
    code, path, msg = e
    return "%s %s: %s" % (code, path, msg) if path else "%s: %s" % (code, msg)


# ---------------------------------------------------------------- 页面组装
def render_page(ir, degraded=()):
    meta = ir.get("meta") or {}
    hero = ir.get("hero") or {}
    book = meta.get("book") or ""
    theme = meta.get("theme") if meta.get("theme") in THEMES else "paper"
    secs = ir.get("sections") or []
    sections = [s for s in secs if isinstance(s, dict)]
    theme_name = {"paper": "暖纸", "minimal": "极简", "dark": "夜读"}.get(theme, "暖纸")

    out = []
    out.append("<!DOCTYPE html>")
    out.append('<html lang="zh-CN" data-theme="%s">' % theme)
    out.append("<head>")
    out.append('<meta charset="utf-8">')
    out.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    title = "《%s》" % book if book else ""
    if hero.get("title"):
        title = (title + " · " + hero["title"]) if title else hero["title"]
    out.append("<title>%s</title>" % esc(title))
    out.append('<meta name="generator" content="bookpage %s">' % VERSION)
    out.append("<style>")
    out.append(theme_block(theme))
    out.append(BASE_CSS)
    out.append("</style>")
    out.append("</head>")
    out.append("<body>")

    crumb = " · ".join([x for x in (book, meta.get("topic")) if x])
    out.append('<div class="topbar"><span class="crumb">%s</span>'
               '<button class="btn" id="srcToggle" type="button" aria-pressed="false">显示出处</button></div>'
               % esc(crumb))

    out.append('<main class="page">')
    out.append('<header class="hero">')
    if hero.get("eyebrow"):
        out.append('<div class="eyebrow">%s</div>' % esc(hero["eyebrow"]))
    out.append("<h1>%s</h1>" % esc(hero.get("title") or ""))
    if hero.get("lede"):
        out.append('<p class="lede">%s</p>' % esc(hero["lede"]))
    if hero.get("thesis"):
        out.append('<div class="thesis">%s</div>' % esc(hero["thesis"]))
    out.append("</header>")

    out.append('<nav class="tabs" role="tablist" aria-label="学习模块">')
    for i, s in enumerate(sections):
        sid = s.get("id") or ("s%d" % i)
        out.append('<button class="tab" type="button" role="tab" id="tab-%s" aria-controls="panel-%s" '
                   'aria-selected="%s" data-target="panel-%s">%s</button>'
                   % (sid, sid, "true" if i == 0 else "false", sid, esc(s.get("label") or sid)))
    out.append("</nav>")

    for i, s in enumerate(sections):
        sid = s.get("id") or ("s%d" % i)
        sig = s.get("signature")
        active = " active" if i == 0 else ""
        out.append('<section class="panel%s" id="panel-%s" role="tabpanel" aria-labelledby="tab-%s">'
                   % (active, sid, sid))
        out.append("<h2>%s</h2>" % esc(s.get("label") or ""))
        if s.get("lead"):
            out.append('<p class="lead">%s</p>' % esc(s["lead"]))
        if i in degraded or sig not in RENDERERS:
            out.append(_r_prose({"data": {"paragraphs": [s.get("lead") or s.get("label") or ""]}}, None))
        else:
            out.append(RENDERERS[sig](s, None))
        src = ('<span class="src">出处：%s</span>' % esc(s["source"])) if s.get("source") else ""
        out.append('<div class="meta-line">%s<span class="grow"></span>'
                   '<button class="btn deep" type="button" data-book="%s" data-concept="%s">深入追问</button></div>'
                   % (src, esc(book), esc(s.get("label") or "")))
        out.append("</section>")

    qs = [q for q in (ir.get("questions") or []) if isinstance(q, dict)]
    if qs:
        out.append('<section class="questions">')
        out.append("<h2>留下来想一想</h2>")
        out.append('<p class="lead">点开卡片看提示，先自己答一遍再对照。</p>')
        out.append('<div class="qgrid">')
        for q in qs:
            out.append('<button class="qcard" type="button" aria-pressed="false">'
                       '<span class="q">%s</span><span class="hint">%s</span></button>'
                       % (esc(q.get("q") or ""), esc(q.get("hint") or "先自己答一遍，再对照书里的论证。")))
        out.append("</div>")
        out.append("</section>")

    foot = " · ".join([x for x in (book, meta.get("author")) if x])
    out.append('<footer class="footer">%s%s · 主题 %s · 由 bookpage %s 生成，无外部依赖</footer>'
               % (esc(foot), "，" if foot else "", theme_name, VERSION))
    out.append("</main>")
    out.append('<div id="toast" role="status" aria-live="polite"></div>')
    out.append("<script>")
    out.append(BASE_JS)
    out.append("</script>")
    out.append("</body>")
    out.append("</html>")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- 文本工具
def estimate_tokens(text):
    """中文感知的 token 估算：CJK 一字约 0.75 token，拉丁词约 1.35，其余非空白字符约 0.35。"""
    cjk = len(CJK_RE.findall(text))
    rest = CJK_RE.sub(" ", text)
    words = [w for w in rest.split() if w]
    others = sum(1 for ch in rest if not ch.isspace() and not ch.isalpha())
    return int(round(cjk * 0.75 + len(words) * 1.35 + others * 0.35))


def count_chapters(text):
    """按行识别章节标题：行首“第X章/节/回”或英文 Chapter N，且整行不超过 40 字。"""
    n = 0
    for line in text.splitlines():
        s = line.strip()
        if not s or len(s) > 40:
            continue
        s = re.sub(r"^[#>*\-\s]+", "", s)
        if not s or len(s) > 40:
            continue
        if CHAPTER_RE.match(s) or EN_CHAPTER_RE.match(s):
            n += 1
    return n


def read_text(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("无法解码为 UTF-8 或 GB18030：%s" % path)


# ---------------------------------------------------------------- 命令
USAGE = """bookpage %s — 确定性书页渲染器（零依赖）

用法：
  python bookpage.py lint  <ir.json>
  python bookpage.py build <ir.json> <out.html> [--degrade]
  python bookpage.py tokens <file>
  python bookpage.py chapters <file>

退出码：0 成功 / 1 lint 有错 / 2 用法错误
组件：%s
""" % (VERSION, "、".join(SIGNATURES))


def _fail_usage(msg):
    sys.stderr.write("用法错误：%s\n\n" % msg)
    sys.stderr.write(USAGE)
    return EXIT_USAGE


def _read_json(path):
    return json.loads(read_text(path))


def cmd_lint(argv):
    if len(argv) != 1:
        return _fail_usage("lint 需要 1 个参数：<ir.json>")
    try:
        ir = _read_json(argv[0])
    except (IOError, OSError) as exc:
        return _fail_usage("读不到 %s（%s）" % (argv[0], exc))
    except ValueError as exc:
        sys.stdout.write("E100 root: JSON 解析失败：%s\n" % exc)
        return EXIT_LINT
    errs = lint_ir(ir)
    for e in errs:
        sys.stdout.write(format_error(e) + "\n")
    if errs:
        sys.stdout.write("lint: %d 个错误\n" % len(errs))
        return EXIT_LINT
    sys.stdout.write("lint: OK（%d 个 section）\n" % len(ir.get("sections") or []))
    return EXIT_OK


def cmd_build(argv):
    degrade = False
    if "--degrade" in argv:
        degrade = True
        argv = [a for a in argv if a != "--degrade"]
    if len(argv) != 2:
        return _fail_usage("build 需要 2 个参数：<ir.json> <out.html>")
    src, dst = argv
    try:
        ir = _read_json(src)
    except (IOError, OSError) as exc:
        return _fail_usage("读不到 %s（%s）" % (src, exc))
    except ValueError as exc:
        sys.stdout.write("E100 root: JSON 解析失败：%s\n" % exc)
        return EXIT_LINT

    errs = lint_ir(ir)
    degraded_index = set()
    if errs:
        for e in errs:
            line = format_error(e)
            if degrade:
                sys.stderr.write("degraded: %s\n" % line)
            else:
                sys.stdout.write(line + "\n")
        if not degrade:
            sys.stdout.write("build: 中止，%d 个 lint 错误（可用 --degrade 降级出页）\n" % len(errs))
            return EXIT_LINT
        for e in errs:
            m = re.match(r"^sections\[(\d+)\]", e[1] or "")
            if m:
                degraded_index.add(int(m.group(1)))

    html = render_page(ir, degraded_index)
    with open(dst, "wb") as fh:
        fh.write(html.encode("utf-8"))
    n = len([s for s in (ir.get("sections") or []) if isinstance(s, dict)])
    sys.stdout.write("built: %d sections, %d bytes -> %s\n"
                     % (n, len(html.encode("utf-8")), dst))
    if degraded_index:
        sys.stdout.write("built: %d 个 section 降级为 prose\n" % len(degraded_index))
    return EXIT_OK


def cmd_tokens(argv):
    if len(argv) != 1:
        return _fail_usage("tokens 需要 1 个参数：<file>")
    try:
        text = read_text(argv[0])
    except (IOError, OSError) as exc:
        return _fail_usage("读不到 %s（%s）" % (argv[0], exc))
    cjk = len(CJK_RE.findall(text))
    sys.stdout.write("tokens: %d\n" % estimate_tokens(text))
    sys.stdout.write("chars: %d\n" % len(text))
    sys.stdout.write("cjk: %d\n" % cjk)
    return EXIT_OK


def cmd_chapters(argv):
    if len(argv) != 1:
        return _fail_usage("chapters 需要 1 个参数：<file>")
    try:
        text = read_text(argv[0])
    except (IOError, OSError) as exc:
        return _fail_usage("读不到 %s（%s）" % (argv[0], exc))
    sys.stdout.write("chapters: %d\n" % count_chapters(text))
    return EXIT_OK


COMMANDS = {"lint": cmd_lint, "build": cmd_build, "tokens": cmd_tokens, "chapters": cmd_chapters}


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help", "help"):
        sys.stdout.write(USAGE)
        return EXIT_OK if len(argv) >= 2 else EXIT_USAGE
    cmd = argv[1]
    if cmd not in COMMANDS:
        return _fail_usage("未知子命令 %r" % cmd)
    return COMMANDS[cmd](argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
