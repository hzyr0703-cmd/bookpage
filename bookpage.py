#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bookpage 1.0 — 把结构化 IR 渲染成确定性单文件 HTML。

零第三方依赖（仅 Python 标准库）。四类子命令：
    python bookpage.py lint   <ir.json>
    python bookpage.py build  <ir.json> <out.html> [--degrade]
    python bookpage.py tokens <file>
    python bookpage.py chapters <file>
  python bookpage.py outline  <书稿> [-o 文件]
    python bookpage.py extract <book> [-o out.txt]   # docx/epub 走标准库；pdf 需 pypdf

设计原则：同输入 → 字节级相同输出。不读时间、不生成 uuid、不依赖字典顺序、
所有文本走同一条转义路径、换行与缩进固定。
"""

import json
import io
from html.parser import HTMLParser
import os
import re
import sys
import unicodedata

VERSION = "1.0"
SCHEMA = "bookpage/1"
EXIT_OK = 0
EXIT_LINT = 1
EXIT_USAGE = 2

ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,15}$")
CHAPTER_RE = re.compile(r"第\s*[0-9〇○零一二三四五六七八九十百千两]+\s*[章节回卷篇]")
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
.dt-node summary::before{content:"▸";display:inline-block;color:var(--red);margin-right:9px;font-weight:400}
details.dt-node[open] summary::before{content:"▾"}
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
.qcard{font:inherit;text-align:left;cursor:pointer;padding:18px;border-radius:12px;border:1px solid var(--line);background:var(--surface);min-height:132px;display:flex;flex-direction:column;justify-content:flex-start;align-items:stretch}
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
/* ---- 概览模式（overview）：框架网格 / 章节地图 / 概念地图 / 决策规则 ---- */
.frameworks{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}
.fw{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:18px 20px}
.fw h3{margin:0 0 8px;font-size:17px;line-height:1.4}
.fw .fwthesis{margin:0 0 10px;color:var(--ink-soft);font-size:14.5px;line-height:1.75}
.fw ul{margin:0;padding-left:18px;font-size:14px;line-height:1.9;color:var(--ink)}
.chaptermap{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}
.cm-row{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.cm-n{font-size:12px;letter-spacing:.08em;color:var(--red)}
.cm-title{font-size:16px;font-weight:600;margin:2px 0 4px}
.cm-gist{font-size:14px;color:var(--ink-soft);line-height:1.75}
.cm-mark{display:inline-block;margin-top:7px;font-size:12px;color:var(--muted);border:1px dashed var(--line);border-radius:999px;padding:2px 10px}
.cm-group{margin-bottom:20px}
.cm-rel{display:inline-block;font-size:12px;color:var(--red);border:1px solid var(--red);border-radius:999px;padding:1px 10px;margin-bottom:8px}
.cm-name{font-size:16px;font-weight:600;margin-bottom:8px}
.cm-items{display:flex;flex-wrap:wrap;gap:8px}
.cm-item{font-size:13.5px;background:var(--surface-strong);border:1px solid var(--line);border-radius:8px;padding:6px 11px}
.rules{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}
.rule{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 18px}
.rule div{font-size:14.5px;line-height:1.75}
.rule b{color:var(--red);margin-right:8px}
.ov-block{margin-top:44px}
.ov-block h2{font-size:19px;margin:0 0 6px}
.ov-block .lead{margin:0 0 16px}
@media (max-width:520px){.frameworks{grid-template-columns:1fr}}
/* ---- 速读模式（reader）：目录 + 章节卡 + 搜索 + 进度 ---- */
#rProg{position:fixed;left:0;top:0;height:2px;width:0;background:var(--red);z-index:60}
.rbar{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:12px;padding:10px 0;background:var(--bg);border-bottom:1px solid var(--line)}
#rFilter{flex:1;max-width:320px;font:inherit;font-size:14px;padding:7px 12px;border:1px solid var(--line);border-radius:999px;background:var(--surface);color:var(--ink)}
#rFilter:focus{outline:2px solid var(--red);outline-offset:1px}
#rCount{font-size:12.5px;color:var(--muted)}
.rgrid{display:grid;grid-template-columns:190px minmax(0,1fr);gap:30px;margin-top:22px}
.toc{position:sticky;top:60px;align-self:start;max-height:calc(100vh - 90px);overflow:auto;font-size:13.5px;line-height:1.85}
.toc a{display:block;color:var(--ink-soft);text-decoration:none;padding:2px 0}
.toc a:hover{color:var(--ink);text-decoration:underline}
.toc .tp{font-weight:600;color:var(--ink);margin-top:10px;border-bottom:1px solid var(--line)}
.toc .toc-ch{padding-left:10px}
.part{margin:0 0 26px}
.part .ptitle{font-size:13px;letter-spacing:.08em;color:var(--muted);margin:22px 0 10px;padding-top:16px;border-top:1px solid var(--line)}
.part .pgist{font-size:13.5px;color:var(--ink-soft);margin:-4px 0 14px}
.chap{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:20px 22px;margin-bottom:16px;scroll-margin-top:70px}
.chap .n{font-size:12px;letter-spacing:.08em;color:var(--red)}
.chap h2{margin:2px 0 6px;font-size:18px;line-height:1.45}
.chap .gist{margin:6px 0 10px;font-size:15px;line-height:1.85;color:var(--ink)}
.chap ul{margin:0;padding-left:18px;font-size:14px;line-height:1.9;color:var(--ink)}
.chap blockquote{margin:10px 0 0;padding:8px 14px;border-left:2px solid var(--gold);background:var(--surface-strong);font-size:14px;line-height:1.85}
.chap cite{display:block;margin-top:4px;font-size:12px;color:var(--muted);font-style:normal}
.chap details{margin-top:10px}
.chap details summary{cursor:pointer;font-size:13px;color:var(--red)}
.chap details p{margin:8px 0 0;font-size:14.5px;line-height:1.95;color:var(--ink);text-indent:2em;max-width:38em}
.thread{margin:30px 0 6px}
.thread h2{font-size:18px;margin:0 0 12px}
.tchain{display:flex;flex-wrap:wrap;gap:10px;list-style:none;padding:0;margin:0}
.tstep{flex:1 1 190px;min-width:168px;padding:14px 14px 12px;border:1px solid var(--line);border-radius:12px;background:var(--surface)}
.tstep .tn{font-size:11px;letter-spacing:.1em;color:var(--red)}
.tstep b{display:block;margin:2px 0 4px;font-size:14.5px}
.tstep p{margin:0;font-size:13px;line-height:1.8;color:var(--ink-soft)}
.tstep .tref{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;font-size:11.5px}
.tstep .tref a{color:var(--red);text-decoration:none;border-bottom:1px dotted var(--red)}
.chap .mark{float:right;font:inherit;font-size:11.5px;padding:2px 9px;margin:-2px 0 6px 8px;border:1px solid var(--line);border-radius:999px;background:var(--surface-strong);color:var(--muted);cursor:pointer}
.chap .mark[aria-pressed="true"]{border-color:var(--red);color:var(--red)}
.chap.chap-read{background:var(--surface-strong);border-color:var(--red)}
#rRead{font-size:12.5px;color:var(--muted)}
.digest{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;margin:26px 0 6px}
.dg{padding:16px 18px;border:1px solid var(--line);border-radius:12px;background:var(--surface)}
.dg .k{font-size:11.5px;letter-spacing:.1em;color:var(--red);display:block;margin-bottom:6px}
.dg p{margin:0;font-size:14.5px;line-height:1.85;color:var(--ink)}
.dg .ref{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px;font-size:12px}
.dg .ref a{color:var(--red);text-decoration:none;border-bottom:1px dotted var(--red)}
.chap .gist,.chap ul,.chap details p{max-width:38em}
.concepts{margin:20px 0 4px}
.concepts h2{font-family:var(--font-display);font-size:19px;margin:0 0 8px}
.cg{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}
.cc{padding:12px 14px;border:1px solid var(--line);border-radius:10px;background:var(--surface-strong);text-decoration:none;display:block}
.cc b{display:block;font-size:14.5px;color:var(--ink)}
.cc span{display:block;margin-top:4px;font-size:12.5px;line-height:1.65;color:var(--ink-soft)}
.cc em{display:block;margin-top:7px;font-size:11.5px;font-style:normal;color:var(--red)}
.chap .role{font-size:13px;color:var(--ink-soft-2);margin:0 0 8px}
@media (max-width:880px){.rgrid{grid-template-columns:1fr}.toc{position:static;max-height:none;display:flex;flex-wrap:wrap;gap:6px;padding-bottom:8px}.toc a{border:1px solid var(--line);border-radius:8px;padding:3px 10px}}
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


# ---------------------------------------------------------------- 概览模式校验
RELATIONS = ("因果", "对立", "组成", "递进")


def _v_overview(errs, ir):
    """overview 模式不用 sections，改校验四个可选区块（至少一个非空）。"""
    blocks = 0
    fw = ir.get("frameworks")
    if fw is not None:
        blocks += 1
        if not isinstance(fw, list):
            errs.append(("E103", "frameworks", "期望 array，得到 %s" % _typename(fw)))
        elif not (3 <= len(fw) <= 6):
            errs.append(("E104", "frameworks", "%d 个，期望 3–6" % len(fw)))
        else:
            for i, f in enumerate(fw):
                p = "frameworks[%d]" % i
                if not isinstance(f, dict):
                    errs.append(("E103", p, "期望 object，得到 %s" % _typename(f)))
                    continue
                fv_str(errs, p, f, "title", 1, 14)
                fv_str(errs, p, f, "thesis", 1, 40)
                pts = fv_list(errs, p, f, "points", 2, 4)
                if pts:
                    for j, t in enumerate(pts):
                        if not isinstance(t, str):
                            errs.append(("E103", "%s.points[%d]" % (p, j), "期望 string，得到 %s" % _typename(t)))
                        elif not (1 <= len(t) <= 30):
                            errs.append(("E104", "%s.points[%d]" % (p, j), "%d 字，期望 1–30" % len(t)))

    cm = ir.get("chapterMap")
    if cm is not None:
        blocks += 1
        if not isinstance(cm, list):
            errs.append(("E103", "chapterMap", "期望 array，得到 %s" % _typename(cm)))
        elif not (3 <= len(cm) <= 12):
            errs.append(("E104", "chapterMap", "%d 个，期望 3–12" % len(cm)))
        else:
            for i, row in enumerate(cm):
                p = "chapterMap[%d]" % i
                if not isinstance(row, dict):
                    errs.append(("E103", p, "期望 object，得到 %s" % _typename(row)))
                    continue
                fw_u = row.get("n")
                if not isinstance(fw_u, int) or isinstance(fw_u, bool) or not (1 <= fw_u <= 99):
                    errs.append(("E103", p + ".n", "期望 1–99 的整数，得到 %s" % _typename(fw_u)))
                fv_str(errs, p, row, "title", 1, 20)
                fv_str(errs, p, row, "gist", 1, 40)
                fv_str(errs, p, row, "mark", 0, 10, required=False)

    cg = ir.get("conceptMap")
    if cg is not None:
        blocks += 1
        if not isinstance(cg, list):
            errs.append(("E103", "conceptMap", "期望 array，得到 %s" % _typename(cg)))
        elif not (2 <= len(cg) <= 6):
            errs.append(("E104", "conceptMap", "%d 组，期望 2–6" % len(cg)))
        else:
            for i, g in enumerate(cg):
                p = "conceptMap[%d]" % i
                if not isinstance(g, dict):
                    errs.append(("E103", p, "期望 object，得到 %s" % _typename(g)))
                    continue
                fv_str(errs, p, g, "name", 1, 14)
                rel = fv_str(errs, p, g, "relation", 1, 6)
                if rel and rel not in RELATIONS:
                    errs.append(("E100", p + ".relation", "未知关系 %r（可选 %s）" % (rel, "/".join(RELATIONS))))
                items = fv_list(errs, p, g, "items", 2, 5)
                if items:
                    for j, t in enumerate(items):
                        if not isinstance(t, str):
                            errs.append(("E103", "%s.items[%d]" % (p, j), "期望 string，得到 %s" % _typename(t)))
                        elif not (1 <= len(t) <= 30):
                            errs.append(("E104", "%s.items[%d]" % (p, j), "%d 字，期望 1–30" % len(t)))

    dr = ir.get("decisionRules")
    if dr is not None:
        blocks += 1
        if not isinstance(dr, list):
            errs.append(("E103", "decisionRules", "期望 array，得到 %s" % _typename(dr)))
        elif not (2 <= len(dr) <= 5):
            errs.append(("E104", "decisionRules", "%d 条，期望 2–5" % len(dr)))
        else:
            for i, r in enumerate(dr):
                p = "decisionRules[%d]" % i
                if not isinstance(r, dict):
                    errs.append(("E103", p, "期望 object，得到 %s" % _typename(r)))
                    continue
                fv_str(errs, p, r, "if", 1, 40)
                fv_str(errs, p, r, "then", 1, 40)
                fv_str(errs, p, r, "else", 0, 40, required=False)

    if blocks == 0:
        errs.append(("E102", "frameworks", "overview 模式至少要有 frameworks/chapterMap/conceptMap/decisionRules 之一"))


# ---------------------------------------------------------------- 速读模式校验
def _v_reader(errs, ir):
    """reader 模式：按章排列的速读卡，章号必须递增且连续可读。"""
    dg = ir.get("digest")
    if dg is not None:
        if not isinstance(dg, list):
            errs.append(("E103", "digest", "期望 array，得到 %s" % _typename(dg)))
        elif not (3 <= len(dg) <= 5):
            errs.append(("E104", "digest", "%d 条，期望 3–5" % len(dg)))
        else:
            for j, t in enumerate(dg):
                txt = t if isinstance(t, str) else (t.get("t") if isinstance(t, dict) else None)
                if not isinstance(txt, str):
                    errs.append(("E103", "digest[%d]" % j,
                                 "期望 string 或 {t, refs}，得到 %s" % _typename(t)))
                    continue
                if not (10 <= len(txt) <= 60):
                    errs.append(("E104", "digest[%d]" % j, "%d 字，期望 10–60" % len(txt)))
                if isinstance(t, dict):
                    refs = t.get("refs")
                    if refs is not None:
                        if not isinstance(refs, list):
                            errs.append(("E103", "digest[%d].refs" % j,
                                         "期望 array，得到 %s" % _typename(refs)))
                        elif not (1 <= len(refs) <= 3):
                            errs.append(("E104", "digest[%d].refs" % j,
                                         "%d 个，期望 1–3" % len(refs)))
                        elif not all(isinstance(x, int) and 1 <= x <= 120 for x in refs):
                            errs.append(("E104", "digest[%d].refs" % j,
                                         "章号须为 1–120 的整数"))
    cs = ir.get("concepts")
    if cs is not None:
        if not isinstance(cs, list):
            errs.append(("E103", "concepts", "期望 array，得到 %s" % _typename(cs)))
        elif not (2 <= len(cs) <= 6):
            errs.append(("E104", "concepts", "%d 组，期望 2–6" % len(cs)))
        else:
            for j, c in enumerate(cs):
                cp = "concepts[%d]" % j
                if not isinstance(c, dict):
                    errs.append(("E103", cp, "期望 object，得到 %s" % _typename(c)))
                    continue
                fv_str(errs, cp, c, "name", 1, 14)
                fv_str(errs, cp, c, "gist", 10, 60)
                ch = fv_list(errs, cp, c, "chapters", 1, 3)
                if ch:
                    for k, v in enumerate(ch):
                        if not isinstance(v, int) or isinstance(v, bool) or not (1 <= v <= 120):
                            errs.append(("E103", "%s.chapters[%d]" % (cp, k),
                                         "期望 1–120 的整数，得到 %s" % _typename(v)))
    th = ir.get("thread")
    if th is not None:
        if not isinstance(th, list):
            errs.append(("E103", "thread", "期望 array，得到 %s" % _typename(th)))
        elif not (3 <= len(th) <= 6):
            errs.append(("E104", "thread", "%d 环，期望 3–6" % len(th)))
        else:
            for j, st in enumerate(th):
                sp = "thread[%d]" % j
                if not isinstance(st, dict):
                    errs.append(("E103", sp, "期望 object，得到 %s" % _typename(st)))
                    continue
                fv_str(errs, sp, st, "step", 2, 12)
                fv_str(errs, sp, st, "what", 10, 44)
                ch = fv_list(errs, sp, st, "chapters", 1, 2)
                if ch:
                    for k, v in enumerate(ch):
                        if not isinstance(v, int) or isinstance(v, bool) or not (1 <= v <= 120):
                            errs.append(("E103", "%s.chapters[%d]" % (sp, k),
                                         "期望 1–120 的整数，得到 %s" % _typename(v)))
    chs = ir.get("chapters")
    if not isinstance(chs, list):
        errs.append(("E103", "chapters", "期望 array，得到 %s" % _typename(chs)))
        return
    if not (3 <= len(chs) <= 120):
        errs.append(("E104", "chapters", "%d 章，期望 3–120" % len(chs)))
        return
    prev = 0
    for i, c in enumerate(chs):
        p = "chapters[%d]" % i
        if not isinstance(c, dict):
            errs.append(("E103", p, "期望 object，得到 %s" % _typename(c)))
            continue
        n = c.get("n")
        if not isinstance(n, int) or isinstance(n, bool) or not (1 <= n <= 120):
            errs.append(("E103", p + ".n", "期望 1–120 的整数，得到 %s" % _typename(n)))
        elif n <= prev:
            errs.append(("E104", p + ".n", "章号需递增（前一个是 %d）" % prev))
        else:
            prev = n
        fv_str(errs, p, c, "title", 1, 24)
        fv_str(errs, p, c, "gist", 10, 70)
        pts = fv_list(errs, p, c, "points", 2, 4)
        if pts:
            for j, t in enumerate(pts):
                if not isinstance(t, str):
                    errs.append(("E103", "%s.points[%d]" % (p, j), "期望 string，得到 %s" % _typename(t)))
                elif not (1 <= len(t) <= 40):
                    errs.append(("E104", "%s.points[%d]" % (p, j), "%d 字，期望 1–40" % len(t)))
        fv_str(errs, p, c, "role", 0, 34, required=False)
        fv_str(errs, p, c, "quote", 0, 90, required=False)
        fv_str(errs, p, c, "quote_from", 0, 12, required=False)
        fv_str(errs, p, c, "srcTitle", 0, 40, required=False)
        tx = c.get("text")
        if tx is not None:
            if not isinstance(tx, list):
                errs.append(("E103", p + ".text", "期望 array，得到 %s" % _typename(tx)))
            elif not (1 <= len(tx) <= 4):
                errs.append(("E104", p + ".text", "%d 段，期望 1–4" % len(tx)))
            else:
                for j, t in enumerate(tx):
                    if not isinstance(t, str):
                        errs.append(("E103", "%s.text[%d]" % (p, j), "期望 string，得到 %s" % _typename(t)))
                    elif not (1 <= len(t) <= 400):
                        errs.append(("E104", "%s.text[%d]" % (p, j), "%d 字，期望 1–400" % len(t)))

    parts = ir.get("parts")
    if parts is not None:
        if not isinstance(parts, list):
            errs.append(("E103", "parts", "期望 array，得到 %s" % _typename(parts)))
        elif not (2 <= len(parts) <= 12):
            errs.append(("E104", "parts", "%d 组，期望 2–12" % len(parts)))
        else:
            seq = []
            for j, pt in enumerate(parts):
                pp = "parts[%d]" % j
                if not isinstance(pt, dict):
                    errs.append(("E103", pp, "期望 object，得到 %s" % _typename(pt)))
                    continue
                fv_str(errs, pp, pt, "title", 1, 14)
                fv_str(errs, pp, pt, "gist", 0, 40, required=False)
                pl = fv_list(errs, pp, pt, "chapters", 1, 30)
                if pl:
                    for k, v in enumerate(pl):
                        if not isinstance(v, int) or isinstance(v, bool) or not (1 <= v <= 120):
                            errs.append(("E103", "%s.chapters[%d]" % (pp, k),
                                         "期望 1–120 的整数，得到 %s" % _typename(v)))
                        else:
                            seq.append(v)
            nums = [c.get("n") for c in chs if isinstance(c.get("n"), int)]
            if seq and nums and seq != nums:
                errs.append(("E104", "parts", "分组须按章号顺序完整覆盖全书，且章号不重复"))
    elif len(chs) > 40:
        errs.append(("E104", "chapters", "%d 章超过 40，长书需用 parts[] 分组（2–12 组）" % len(chs)))



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
    if mode and mode not in ("theme", "overview", "reader"):
        errs.append(("E100", "meta.mode", "只支持 theme / overview / reader，收到 %r" % mode))
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

    if mode in ("overview", "reader"):
        if "sections" in ir:
            huge = "overview 模式不用 sections，改用 frameworks/chapterMap/conceptMap/decisionRules" if mode == "overview" else "reader 模式不用 sections，改用 chapters[]"
            errs.append(("E100", "sections", huge))
        if mode == "overview":
            _v_overview(errs, ir)
        else:
            _v_reader(errs, ir)
    secs = ir.get("sections") if mode not in ("overview", "reader") else []
    if not isinstance(secs, list):
        errs.append(("E103", "sections", "期望 array，得到 %s" % _typename(secs)))
        secs = []
    elif secs and not (1 <= len(secs) <= 8):
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


def render_overview(ir):
    meta = ir.get("meta") or {}
    hero = ir.get("hero") or {}
    book = meta.get("book") or ""
    theme = meta.get("theme") if meta.get("theme") in THEMES else "paper"
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
    out.append('<div class="topbar"><span class="crumb">%s</span></div>' % esc(crumb))
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

    fw = [x for x in (ir.get("frameworks") or []) if isinstance(x, dict)]
    if fw:
        out.append('<section class="ov-block">')
        out.append("<h2>全书骨架</h2>")
        out.append('<p class="lead">先看四个框架，再看它们怎么互相支撑。</p>')
        out.append('<div class="frameworks">')
        for f in fw:
            out.append('<div class="fw"><h3>%s</h3>' % esc(f.get("title") or ""))
            out.append('<p class="fwthesis">%s</p>' % esc(f.get("thesis") or ""))
            pts = [x for x in (f.get("points") or []) if isinstance(x, str)]
            if pts:
                out.append("<ul>")
                for t in pts:
                    out.append("<li>%s</li>" % esc(t))
                out.append("</ul>")
            out.append("</div>")
        out.append("</div>")
        out.append("</section>")

    cm = [x for x in (ir.get("chapterMap") or []) if isinstance(x, dict)]
    if cm:
        out.append('<section class="ov-block">')
        out.append("<h2>章节地图</h2>")
        out.append('<p class="lead">每一章在全书里的位置与作用。</p>')
        out.append('<div class="chaptermap">')
        for row in cm:
            out.append('<div class="cm-row">')
            out.append('<div class="cm-n">第 %s 章</div>' % esc(str(row.get("n", ""))))
            out.append('<div class="cm-title">%s</div>' % esc(row.get("title") or ""))
            out.append('<div class="cm-gist">%s</div>' % esc(row.get("gist") or ""))
            if row.get("mark"):
                out.append('<span class="cm-mark">%s</span>' % esc(row["mark"]))
            out.append("</div>")
        out.append("</div>")
        out.append("</section>")

    cg = [x for x in (ir.get("conceptMap") or []) if isinstance(x, dict)]
    if cg:
        out.append('<section class="ov-block">')
        out.append("<h2>概念地图</h2>")
        out.append('<p class="lead">概念之间的关系，比单点定义更好记。</p>')
        for g in cg:
            out.append('<div class="cm-group">')
            out.append('<span class="cm-rel">%s</span>' % esc(g.get("relation") or ""))
            out.append('<div class="cm-name">%s</div>' % esc(g.get("name") or ""))
            items = [x for x in (g.get("items") or []) if isinstance(x, str)]
            if items:
                out.append('<div class="cm-items">')
                for t in items:
                    out.append('<span class="cm-item">%s</span>' % esc(t))
                out.append("</div>")
            out.append("</div>")
        out.append("</section>")

    dr = [x for x in (ir.get("decisionRules") or []) if isinstance(x, dict)]
    if dr:
        out.append('<section class="ov-block">')
        out.append("<h2>怎么用这本书判断</h2>")
        out.append('<p class="lead">把书里的判断压成几条可以直接套的规则。</p>')
        out.append('<div class="rules">')
        for r in dr:
            out.append('<div class="rule">')
            out.append('<div><b>当</b>%s</div>' % esc(r.get("if") or ""))
            out.append('<div><b>则</b>%s</div>' % esc(r.get("then") or ""))
            if r.get("else"):
                out.append('<div><b>否则</b>%s</div>' % esc(r["else"]))
            out.append("</div>")
        out.append("</div>")
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
    out.append('<footer class="footer">%s%s · 全书概览 · 主题 %s · 由 bookpage %s 生成，无外部依赖</footer>'
               % (esc(foot), "，" if foot else "", theme_name, VERSION))
    out.append("</main>")
    out.append('<div id="toast" role="status" aria-live="polite"></div>')
    out.append("</body>")
    out.append("</html>")
    return "\n".join(out) + "\n"


READER_JS = """(function () {
  var bar = document.getElementById("rProg");
  function onScroll() {
    var h = document.documentElement.scrollHeight - window.innerHeight;
    var pct = h > 0 ? (window.scrollY / h) * 100 : 0;
    if (bar) bar.style.width = Math.min(100, Math.max(0, pct)) + "%";
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
  var box = document.getElementById("rFilter");
  var cnt = document.getElementById("rCount");
  var cards = Array.prototype.slice.call(document.querySelectorAll(".chap"));
  var links = Array.prototype.slice.call(document.querySelectorAll(".toc a"));
  function apply() {
    var q = (box.value || "").trim().toLowerCase();
    var shown = 0;
    cards.forEach(function (c) {
      var hit = !q || (c.getAttribute("data-search") || "").toLowerCase().indexOf(q) >= 0;
      c.style.display = hit ? "" : "none";
      if (hit) shown++;
    });
    links.forEach(function (a) {
      var href = a.getAttribute("href") || "";
      if (href.indexOf("#ch-") !== 0) return;
      var el = document.getElementById(href.slice(1));
      a.style.display = (el && el.style.display === "none") ? "none" : "";
    });
    Array.prototype.slice.call(document.querySelectorAll(".part")).forEach(function (sec) {
      var vis = Array.prototype.slice.call(sec.querySelectorAll(".chap")).some(function (c) {
        return c.style.display !== "none";
      });
      sec.style.display = vis ? "" : "none";
      var head = document.querySelector('.toc a[href="#' + sec.id + '"]');
      if (head && q) head.style.display = vis ? "" : "none";
    });
    if (cnt) cnt.textContent = "显示 " + shown + " / " + cards.length + " 章";
  }
  if (box) { box.addEventListener("input", apply); apply(); }
  var bookTag = (document.body.getAttribute("data-book") || "").trim();
  var readKey = "bp-read:" + (bookTag || document.title || "");
  var readSet = {};
  try {
    var raw = window.localStorage.getItem(readKey);
    if (raw) { JSON.parse(raw).forEach(function (n) { readSet[String(n)] = true; }); }
  } catch (err) { readSet = {}; }
  var marks = Array.prototype.slice.call(document.querySelectorAll(".mark"));
  var rcount = document.getElementById("rRead");
  function paintMarks() {
    var done = 0;
    marks.forEach(function (m) {
      var n = String(m.getAttribute("data-n"));
      var on = !!readSet[n];
      m.setAttribute("aria-pressed", on ? "true" : "false");
      m.textContent = on ? "已读完" : "标为读完";
      var art = document.getElementById("ch-" + n);
      if (art) art.className = on ? "chap chap-read" : "chap";
      if (on) done++;
    });
    if (rcount) rcount.textContent = "已读 " + done + " / " + marks.length;
  }
  function saveMarks() {
    var arr = [];
    for (var k in readSet) { if (readSet[k]) arr.push(k); }
    try { window.localStorage.setItem(readKey, JSON.stringify(arr)); } catch (err) {}
  }
  marks.forEach(function (m) {
    m.addEventListener("click", function () {
      var n = String(m.getAttribute("data-n"));
      if (readSet[n]) { delete readSet[n]; } else { readSet[n] = true; }
      saveMarks();
      paintMarks();
    });
  });
  paintMarks();
})();"""

def render_reader(ir):
    meta = ir.get("meta") or {}
    hero = ir.get("hero") or {}
    book = meta.get("book") or ""
    theme = meta.get("theme") if meta.get("theme") in THEMES else "paper"
    theme_name = {"paper": "暖纸", "minimal": "极简", "dark": "夜读"}.get(theme, "暖纸")
    chs = [c for c in (ir.get("chapters") or []) if isinstance(c, dict)]

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
    out.append('<body data-book="%s">' % esc(book))
    out.append('<div id="rProg"></div>')
    crumb = " · ".join([x for x in (book, meta.get("topic")) if x])
    out.append('<div class="topbar"><span class="crumb">%s</span></div>' % esc(crumb))
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
    dg_items = []
    for t in (ir.get("digest") or []):
        if isinstance(t, str):
            dg_items.append((t, []))
        elif isinstance(t, dict) and isinstance(t.get("t"), str):
            dg_items.append((t["t"], [x for x in (t.get("refs") or []) if isinstance(x, int)]))
    if dg_items:
        out.append('<section class="digest" aria-label="这本书在说什么">')
        for i, (t, refs) in enumerate(dg_items):
            links = "".join('<a href="#ch-%s">第 %s 章</a>' % (r, r) for r in refs)
            ref_html = ('<span class="ref">%s</span>' % links) if links else ""
            out.append('<div class="dg"><span class="k">%02d</span><p>%s</p>%s</div>'
                       % (i + 1, esc(t), ref_html))
        out.append("</section>")
    cs = [c for c in (ir.get("concepts") or []) if isinstance(c, dict)]
    if cs:
        out.append('<section class="concepts" aria-label="关键概念">')
        out.append("<h2>关键概念</h2>")
        out.append('<div class="cg">')
        for c in cs:
            nums = [str(x) for x in (c.get("chapters") or []) if isinstance(x, int)]
            first = nums[0] if nums else "1"
            out.append('<a class="cc" href="#ch-%s"><b>%s</b><span>%s</span><em>第 %s 章</em></a>'
                       % (esc(first), esc(c.get("name") or ""), esc(c.get("gist") or ""),
                          esc("、".join(nums))))
        out.append("</div></section>")
    th = [s for s in (ir.get("thread") or []) if isinstance(s, dict)]
    if th:
        out.append('<section class="thread" aria-label="全书论证主线">')
        out.append("<h2>主线怎么推进</h2>")
        out.append('<ol class="tchain">')
        for i, s in enumerate(th):
            links = "".join('<a href="#ch-%s">第 %s 章</a>' % (r, r)
                            for r in (s.get("chapters") or []) if isinstance(r, int))
            out.append('<li class="tstep"><span class="tn">%02d</span><b>%s</b><p>%s</p>'
                       '<span class="tref">%s</span></li>'
                       % (i + 1, esc(s.get("step") or ""), esc(s.get("what") or ""), links))
        out.append("</ol></section>")
    hint = "搜章节 / 关键词"
    if ir.get("concepts"):
        hint = "搜章节 / 关键词，例如：" + str(ir["concepts"][0].get("name") or "")
    out.append('<div class="rbar"><input id="rFilter" type="search" placeholder="%s" aria-label="搜索章节"><span id="rCount"></span><span id="rRead"></span></div>' % esc(hint))
    parts = [x for x in (ir.get("parts") or []) if isinstance(x, dict)]
    by_n = {}
    for c in chs:
        if isinstance(c.get("n"), int):
            by_n[c["n"]] = c

    def emit_card(c):
        n = str(c.get("n", ""))
        parts_txt = [c.get("title") or "", c.get("role") or "", c.get("gist") or ""]
        parts_txt.extend([x for x in (c.get("points") or []) if isinstance(x, str)])
        if c.get("quote"):
            parts_txt.append(c["quote"])
        parts_txt.extend([x for x in (c.get("text") or []) if isinstance(x, str)])
        search = esc(" ".join(parts_txt))
        out.append('<article class="chap" id="ch-%s" data-search="%s">' % (esc(n), search))
        out.append('<button class="mark" type="button" data-n="%s" aria-pressed="false">标为读完</button>' % esc(n))
        out.append('<div class="n">%s</div>' % esc(n))
        out.append("<h2>%s</h2>" % esc(c.get("title") or ""))
        if c.get("role"):
            out.append('<p class="role">%s</p>' % esc(c["role"]))
        out.append('<p class="gist">%s</p>' % esc(c.get("gist") or ""))
        pts = [x for x in (c.get("points") or []) if isinstance(x, str)]
        if pts:
            out.append("<ul>")
            for t in pts:
                out.append("<li>%s</li>" % esc(t))
            out.append("</ul>")
        if c.get("quote"):
            out.append("<blockquote>%s" % esc(c["quote"]))
            if c.get("quote_from"):
                out.append("<cite>%s</cite>" % esc(c["quote_from"]))
            out.append("</blockquote>")
        tx = [x for x in (c.get("text") or []) if isinstance(x, str)]
        if tx:
            out.append("<details><summary>读原文（%d 段）</summary>" % len(tx))
            for t in tx:
                out.append("<p>%s</p>" % esc(t))
            out.append("</details>")
        out.append("</article>")

    out.append('<div class="rgrid">')
    out.append('<nav class="toc" aria-label="章节目录">')
    if parts:
        for pi, pt in enumerate(parts):
            out.append('<a class="tp" href="#pt-%d">%s</a>' % (pi + 1, esc(pt.get("title") or "")))
            for n in (pt.get("chapters") or []):
                c = by_n.get(n)
                if c is None:
                    continue
                out.append('<a class="toc-ch" href="#ch-%s">%s · %s</a>'
                           % (esc(str(n)), esc(str(n)), esc(c.get("title") or "")))
    else:
        for c in chs:
            n = c.get("n", "")
            out.append('<a href="#ch-%s">%s · %s</a>' % (esc(str(n)), esc(str(n)), esc(c.get("title") or "")))
    out.append("</nav>")
    out.append("<div>")
    if parts:
        for pi, pt in enumerate(parts):
            out.append('<section class="part" id="pt-%d">' % (pi + 1))
            out.append('<h3 class="ptitle">%s</h3>' % esc(pt.get("title") or ""))
            if pt.get("gist"):
                out.append('<p class="pgist">%s</p>' % esc(pt["gist"]))
            for n in (pt.get("chapters") or []):
                c = by_n.get(n)
                if c is not None:
                    emit_card(c)
            out.append("</section>")
    else:
        for c in chs:
            emit_card(c)
    out.append("</div>")
    out.append("</div>")
    out.append("</div>")
    out.append("</div>")
    foot = " · ".join([x for x in (book, meta.get("author")) if x])
    out.append('<footer class="footer">%s%s · 全书速读 · %d 章 · 主题 %s · 由 bookpage %s 生成</footer>'
               % (esc(foot), "，" if foot else "", len(chs), theme_name, VERSION))
    out.append("</main>")
    out.append("<script>")
    out.append(READER_JS)
    out.append("</script>")
    out.append("</body>")
    out.append("</html>")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- 页面组装
def render_page(ir, degraded=()):
    mode = (ir.get("meta") or {}).get("mode")
    if mode == "overview":
        return render_overview(ir)
    if mode == "reader":
        return render_reader(ir)
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


BOILER_START = re.compile(r"^\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG.*$", re.M | re.I)
BOILER_END = re.compile(r"^\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG.*$", re.M | re.I)
CJK_SPACE = re.compile(r"(?<=[\u4e00-\u9fff])[ \u3000]+(?=[\u4e00-\u9fff])")


def strip_boilerplate(text):
    """去掉公版书站点的页眉/许可证尾巴，避免最后一章被版权文本撑大。"""
    m = BOILER_START.search(text)
    if m:
        text = text[m.end():]
    m = BOILER_END.search(text)
    if m:
        text = text[:m.start()]
    return text.strip("\n")


def clean_chapter_body(body):
    """去掉章内的站点署名行与章末人工注释块（〔1〕〔2〕…连续三条以上视为注释）。"""
    lines = [l for l in body.splitlines() if not re.match(r"\s*Produced by", l)]
    first, count = None, 0
    for i, l in enumerate(lines):
        if re.match(r"\s*〔\s*[０-９0-9]+\s*〕", l):
            count += 1
            if first is None:
                first = i
    if count >= 3 and first is not None:
        lines = lines[:first]
    return "\n".join(lines).strip()


FRONT_HINTS = ("版权信息", "版权页", "ISBN", "书名：", "书名:", "Copyright", "图书在版编目")
TOC_STUB_MAX = 60  # 目录页里每卷只占一行，正文为空


def _looks_front_matter(text):
    if len(text) > 2000:
        return False
    return any(h in text for h in FRONT_HINTS)


def _drop_toc_stubs(chapters):
    """目录页会给每卷留一个空章，正文里再出现一次同名标题。

    规则：正文不足 60 字且后面还有同名章 → 视为目录条目丢弃；正文保留下来的那份才是真章。
    """
    keys = [re.sub(r"[ \u3000]+", " ", t).strip() for t, _b in chapters]
    keep = []
    for i, (title, body) in enumerate(chapters):
        bare = re.sub(r"[ \u3000]+", " ", body).strip()
        if len(bare) < TOC_STUB_MAX and keys[i] in keys[i + 1:]:
            continue
        keep.append((title, body))
    return keep


def _is_chapter_heading(s):
    """章标题判定：章节标记后面必须跟空白，且标题本身不超过 34 字。

    正文里常出现「第四回中既将薛家母子…」这类以回次开头的普通句子，
    只凭 CHAPTER_RE 会把它们当成章标题，切出一堆假章。
    """
    m = CHAPTER_RE.match(s) or EN_CHAPTER_RE.match(s)
    if not m:
        return False
    rest = s[m.end():]
    # 标题只写「第一卷」、书名另起一行的书：光杆标题也算章标题
    if not rest.strip():
        return True
    # 「第十七回至十八回 …」这种合并回目：把「至十八回」并进标题再判定
    if rest[:1] in ("至", "～", "-", "—"):
        m2 = re.match(r"[^\s\u3000]{1,8}[回]", rest)
        if m2:
            rest = rest[m2.end():]
    if not rest or rest[0] not in " \u3000":
        return False
    return len(rest.strip()) <= 34


def _drop_toc_runs(chapters, min_run=8, min_repeat=0.6):
    """整块目录：连续 ≥8 个空章，且其中多数章题后面还会再出现一次。

    有些 epub 先把整本书的回目列一遍，再逐回放正文；这些行会被认成章标题，切出一串 0 字章。
    只按「空」判断会误伤真正很短的章节，所以再加一条：这些标题必须后面重复出现。
    """
    def key(t):
        return re.sub(r"[ \u3000]+", " ", t).strip()

    dup = []
    for i, (t, _b) in enumerate(chapters):
        k = key(t)
        dup.append(any(k and (k in key(t2) or key(t2) in k) for t2, _b2 in chapters[i + 1:]))

    keep, run = [], []
    for i, item in enumerate(chapters):
        bare = re.sub(r"[ \u3000]+", " ", item[1]).strip()
        if len(bare) < TOC_STUB_MAX:
            run.append((i, item))
            continue
        if len(run) >= min_run:
            hits = sum(1 for j, _it in run if dup[j])
            if hits < min_repeat * len(run):
                keep.extend(it for _j, it in run)
        else:
            keep.extend(it for _j, it in run)
        run = []
        keep.append(item)
    if run:
        hits = sum(1 for j, _it in run if dup[j])
        if len(run) < min_run or hits < min_repeat * len(run):
            keep.extend(it for _j, it in run)
    return keep


def clean_heading(title):
    """去掉回目里的校注标记：〔一〕、[1]、(2)。人文社版本的回目里夹着校勘序号，直接显示像乱码。"""
    t = re.sub(r"〔[^〕]{1,6}〕", "", title)
    t = re.sub(r"\[[0-9,，\-]{1,8}\]", "", t)
    t = re.sub(r"[(（][0-9一二三四五]{1,3}[)）]", "", t)
    t = re.sub(r"[ \u3000]+", " ", t).strip()
    return t


def _merge_duplicate_titles(chapters):
    """同名相邻章只留正文最长的一份。

    前置页（版权、凡例、序）若被首章的标题吸进去，会和真正的第一回同名；
    目录里残留的单词条也会和正文里的同名章并存。同名只留长的那份即可。
    """
    out = []
    for title, body in chapters:
        if out and out[-1][0] == title:
            if len(body) > len(out[-1][1]):
                out[-1] = (title, body)
            continue
        out.append((title, body))
    return out


def split_chapters(text, max_chars=6000):
    """按章节标题切分正文；找不到标题时按字数等分。返回 ([(title, body)], method)。"""
    text = strip_boilerplate(text)
    lines = text.splitlines()
    starts = []
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or len(s) > 40:
            continue
        s = re.sub(r"^[#>*\-\s]+", "", s)
        if not s or len(s) > 40:
            continue
        if _is_chapter_heading(s):
            starts.append((i, clean_heading(s)))
    if not starts:
        blocks, buf, total = [], [], 0
        for line in lines:
            buf.append(line)
            total += len(line)
            if total >= max_chars:
                body = "\n".join(buf).strip()
                if body:
                    blocks.append(body)
                buf, total = [], 0
        body = "\n".join(buf).strip()
        if body:
            blocks.append(body)
        return [("第 %d 段" % (i + 1), b) for i, b in enumerate(blocks)], "equal-split"
    out = []
    for k, (idx, title) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        body = "\n".join(lines[idx:end])
        if k == 0:
            head = "\n".join(lines[:idx]).strip()
            if head and not _looks_front_matter(head):
                body = head + "\n\n" + body
        body = clean_chapter_body(body)
        # 正文里常把章题再印一遍，去掉与标题重复的行
        norm = re.sub(r"[ \u3000]+", " ", title).strip()
        keep = [l for l in body.splitlines()
                if re.sub(r"[ \u3000]+", " ", l.strip()) != norm]
        out.append((title, "\n".join(keep).strip()))
    out = _merge_duplicate_titles(_drop_toc_stubs(_drop_toc_runs(out)))
    return out, "headings"


def read_text(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("无法解码为 UTF-8 或 GB18030：%s" % path)


# ---------------------------------------------------------------- 书源提取
TEXT_BOOK_EXT = {".txt", ".md", ".markdown", ".rst", ".adoc"}


class MissingExtractor(Exception):
    """缺少能解析该格式的依赖，或该格式不在支持列表内。"""


def _normalize(text):
    t = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip() + "\n"


class _HTMLText(HTMLParser):
    SKIP = ("script", "style", "head", "nav")

    def __init__(self):
        HTMLParser.__init__(self)
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        if tag in ("p", "div", "li", "tr"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)

    def text(self):
        return "".join(self.parts)


def _html_to_text(raw):
    p = _HTMLText()
    p.feed(raw)
    p.close()
    return p.text()


def _extract_docx(path):
    import zipfile
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(path) as zf:
        if "word/document.xml" not in zf.namelist():
            raise ValueError("docx 里没有 word/document.xml")
        root = ET.fromstring(zf.read("word/document.xml"))
    parts = []
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag == "p":
            parts.append("\n")
        elif tag == "t" and el.text:
            parts.append(el.text)
        elif tag == "tab":
            parts.append(" ")
        elif tag in ("br", "tr"):
            parts.append("\n")
    return "".join(parts)


def _extract_epub(path):
    import zipfile
    import xml.etree.ElementTree as ET
    from urllib.parse import unquote
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        opf = None
        if "META-INF/container.xml" in names:
            root = ET.fromstring(zf.read("META-INF/container.xml"))
            for el in root.iter():
                if el.tag.split("}")[-1] == "rootfile" and el.get("full-path"):
                    opf = el.get("full-path")
                    break
        if not opf:
            cands = [n for n in names if n.lower().endswith(".opf")]
            opf = cands[0] if cands else None
        docs = []
        if opf:
            base = opf.rsplit("/", 1)[0] + "/" if "/" in opf else ""
            oroot = ET.fromstring(zf.read(opf))
            manifest = {}
            spine = []
            for el in oroot.iter():
                tag = el.tag.split("}")[-1]
                if tag == "item" and el.get("id") and el.get("href"):
                    manifest[el.get("id")] = el.get("href")
                elif tag == "itemref" and el.get("idref"):
                    spine.append(el.get("idref"))
            for idref in spine:
                href = manifest.get(idref)
                if not href:
                    continue
                name = base + unquote(href.split("#")[0])
                if name in names and name.lower().endswith((".xhtml", ".html", ".htm", ".xml")):
                    docs.append(name)
        if not docs:
            docs = sorted(n for n in names
                          if n.lower().endswith((".xhtml", ".html", ".htm")))
        chunks = []
        for name in docs:
            chunks.append(_html_to_text(zf.read(name).decode("utf-8", "replace")))
    return "\n\n".join(chunks)


def _extract_pdf(path):
    PdfReader = None
    for mod in ("pypdf", "PyPDF2"):
        try:
            PdfReader = __import__(mod, fromlist=["PdfReader"]).PdfReader
            break
        except Exception:
            PdfReader = None
    if PdfReader is None:
        raise MissingExtractor(
            "pdf 需要 pypdf（pip install pypdf），或装 poppler 后用 pdftotext；"
            "bookpage 本身仍是零依赖，pdf 解析不属于零依赖路径")
    reader = PdfReader(path)
    return "\n\n".join((p.extract_text() or "") for p in reader.pages)


def _extract_rtf(path):
    raw = read_text(path)
    t = re.sub(r"\\'([0-9a-fA-F]{2})",
               lambda m: bytes([int(m.group(1), 16)]).decode("latin-1"), raw)
    t = re.sub(r"\\u(-?[0-9]+)[?]?",
               lambda m: chr(int(m.group(1)) % 65536), t)
    t = re.sub(r"\{\\\*.*?\}", "", t, flags=re.S)
    t = re.sub(r"\\[a-zA-Z]+(-?[0-9]+)?[ ]?", " ", t)
    return t.replace("{", "").replace("}", "")


def extract_book(path):
    """返回 (纯文本, 格式名)。缺依赖时抛 MissingExtractor。"""
    ext = os.path.splitext(path)[1].lower()
    if ext in TEXT_BOOK_EXT or ext == "":
        return _normalize(read_text(path)), "text"
    if ext == ".docx":
        return _normalize(_extract_docx(path)), "docx"
    if ext == ".epub":
        return _normalize(_extract_epub(path)), "epub"
    if ext == ".pdf":
        return _normalize(_extract_pdf(path)), "pdf"
    if ext == ".rtf":
        return _normalize(_extract_rtf(path)), "rtf"
    if ext in (".mobi", ".azw", ".azw3"):
        raise MissingExtractor("mobi/azw3 需要 calibre 的 ebook-convert，本机未安装")
    raise MissingExtractor("不支持的格式 %r（支持 txt/md/rst/adoc/docx/epub/rtf/pdf）" % ext)



# ---------------------------------------------------------------- 校验 / 渲染 / 书架
MATCH_MAP = str.maketrans({
    "“": "\"", "”": "\"", "‘": "'", "’": "'",
    "「": "\"", "」": "\"", "『": "\"", "』": "\"",
    "…": "...", "　": " ", " ": " ",
})


def _match_key(text):
    """比对用的归一化：NFKC（全角→半角）、统一引号/省略号、去掉所有空白。"""
    return "".join(unicodedata.normalize("NFKC", str(text)).translate(MATCH_MAP).split())


def _title_key(text):
    return re.sub(r"[ \u3000]+", " ", str(text)).strip()


POINT_QUOTE_RE = re.compile(r"[「『“]([^「」『』“”]{2,40})[」』”]")
POINT_BOOK_RE = re.compile(r"《([^》]{2,30})》")
POINT_NUM_RE = re.compile(r"([0-9]{1,4}(?:年|月|日|卷|章|个|次|倍|%|％)?)")
POINT_LATIN_RE = re.compile(r"[A-Za-z]{2,12}")


def _point_refs(point):
    """要点里"可被机器核对"的字面量：数字与拉丁名（NFKC 归一，全角/半角等价）。

    只查这两类，是有意为之：它们写错就是幻觉，且不受简体/繁体改写影响。
    普通叙述不做比对：按 2 字窗口算重合度时真要点 0.14、假要点 0.00，没有区分度。
    """
    out = []
    for m in POINT_NUM_RE.finditer(point):
        out.append(m.group(1))
    for m in POINT_LATIN_RE.finditer(point):
        out.append(m.group(0))
    return [x for x in out if len(x) >= 2]


_FOLD = None
_FOLD_TRIED = False


def _fold_fn():
    """繁→简折叠函数；zhconv 不在时装不上就返回 None（这条检查跳过，不新增硬依赖）。"""
    global _FOLD, _FOLD_TRIED
    if _FOLD_TRIED:
        return _FOLD
    _FOLD_TRIED = True
    try:
        import zhconv
        _FOLD = lambda t: zhconv.convert(str(t), "zh-cn")
    except Exception:
        _FOLD = None
    return _FOLD


def _point_names(point):
    """要点里的引号短语与书名（含汉字的），交给折叠后的比对。"""
    out = []
    for m in POINT_QUOTE_RE.finditer(point):
        out.append(m.group(1))
    for m in POINT_BOOK_RE.finditer(point):
        out.append(m.group(1))
    return [x for x in out if CJK_RE.search(x) and len(x) >= 2]


def verify_ir(ir, source_text):
    """核对 IR 里的引文与原文片段是否真的落在书稿里。返回 (errs, stats)。"""
    errs = []
    chapters, method = split_chapters(source_text)
    mode = (ir.get("meta") or {}).get("mode") or "theme"
    stats = {"mode": mode, "chapters": 0, "quotes": 0, "params": 0, "coverage": []}
    if mode == "reader":
        by_title = dict((_title_key(t), b) for t, b in chapters)
        for i, c in enumerate(ir.get("chapters") or []):
            title = _title_key(c.get("srcTitle") or c.get("title") or "")
            body = by_title.get(title)
            if body is None and title:
                cand = [b for t, b in chapters if title in t or t in title]
                body = cand[0] if len(cand) == 1 else None
            if body is None:
                errs.append(("E303", "chapters[%d].title" % i,
                             "书里找不到这个章节标题（切章方式 %s）" % method))
                continue
            stats["chapters"] += 1
            body_key = _match_key(body)
            quote = c.get("quote")
            if quote:
                stats["quotes"] += 1
                if _match_key(quote) not in body_key:
                    errs.append(("E301", "chapters[%d].quote" % i, "引文不在该章正文里"))
            covered = 0
            for k, seg in enumerate(c.get("text") or []):
                stats["params"] += 1
                if _match_key(seg) in body_key:
                    covered += len(seg)
                else:
                    errs.append(("E302", "chapters[%d].text[%d]" % (i, k),
                                 "原文片段不在该章正文里"))
            stats["coverage"].append(covered / float(max(1, len(body))))
            # E304：要点里的数字与拉丁名，必须能在这章正文里找到
            for pk, point in enumerate(c.get("points") or []):
                for ref in _point_refs(point):
                    stats["point_refs"] = stats.get("point_refs", 0) + 1
                    if _match_key(ref) not in body_key:
                        errs.append(("E304", "chapters[%d].points[%d]" % (i, pk),
                                     "要点里的「%s」在该章正文里找不到（疑似凭记忆补的）" % ref))
                # E306：要点里的引号短语/书名，繁简折叠后再比对（需 zhconv，缺则跳过）
                fold = _fold_fn()
                if fold is None:
                    continue
                fbody = _match_key(fold(body))
                fbody_np = re.sub(r"[，。、；：！？…\"'（）()《》「」『』]", "", fbody)
                for name in _point_names(point):
                    stats["point_names"] = stats.get("point_names", 0) + 1
                    k1 = _match_key(fold(name))
                    k2 = re.sub(r"[，。、；：！？…\"'（）()《》「」『』]", "", k1)
                    if k1 not in fbody and k2 not in fbody_np:
                        errs.append(("E306", "chapters[%d].points[%d]" % (i, pk),
                                     "要点里的「%s」在该章正文里找不到（繁简已折叠，疑似凭记忆补的）" % name))
            # E305：可选的证据片段 ev[]，必须逐字出自本章正文
            for ek, seg in enumerate(c.get("ev") or []):
                stats["ev"] = stats.get("ev", 0) + 1
                if _match_key(seg) not in body_key:
                    errs.append(("E305", "chapters[%d].ev[%d]" % (i, ek),
                                 "证据片段不在该章正文里"))
    else:
        book_key = _match_key(source_text)
        for i, sec in enumerate(ir.get("sections") or []):
            if sec.get("signature") != "quote_card":
                continue
            q = (sec.get("data") or {}).get("text")
            src_note = str((sec.get("data") or {}).get("source") or "") + str((sec.get("data") or {}).get("speaker") or "")
            if q:
                if "非原文" in src_note or "转述" in src_note:
                    stats["quotes_skipped"] = stats.get("quotes_skipped", 0) + 1
                    continue
                stats["quotes"] += 1
                if _match_key(q) not in book_key:
                    errs.append(("E301", "sections[%d].data.text" % i, "引文不在书稿里"))
    return errs, stats


def cmd_verify(argv):
    src = None
    if "--source" in argv:
        i = argv.index("--source")
        if i + 1 >= len(argv):
            return _fail_usage("--source 后面要跟书稿路径")
        src = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if len(argv) != 1 or not src:
        return _fail_usage("verify 用法：<ir.json> --source <书稿>")
    try:
        ir = _read_json(argv[0])
    except (IOError, OSError) as exc:
        return _fail_usage("读不到 %s（%s）" % (argv[0], exc))
    except ValueError as exc:
        sys.stdout.write("E100 root: JSON 解析失败：%s\n" % exc)
        return EXIT_LINT
    try:
        text = _normalize(read_text(src))
    except (IOError, OSError) as exc:
        return _fail_usage("读不到 %s（%s）" % (src, exc))
    errs, stats = verify_ir(ir, text)
    for e in errs:
        sys.stdout.write(format_error(e) + "\n")
    if errs:
        sys.stdout.write("verify: %d 个错误（核对 %d 章 / 引文 %d 条 / 原文段 %d 段）\n"
                         % (len(errs), stats["chapters"], stats["quotes"], stats["params"]))
        return EXIT_LINT
    avg = sum(stats["coverage"]) / len(stats["coverage"]) if stats["coverage"] else 0.0
    sys.stdout.write("verify: OK（核对 %d 章 / 引文 %d 条 / 原文段 %d 段 / 平均覆盖 %.1f%%）\n"
                     % (stats["chapters"], stats["quotes"], stats["params"], avg * 100.0))
    return EXIT_OK


def cmd_render(argv):
    out_dir = None
    dpi = 180
    pages = None
    rest = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "-o" and i + 1 < len(argv):
            out_dir = argv[i + 1]
            i += 2
            continue
        if a == "--dpi" and i + 1 < len(argv):
            try:
                dpi = int(argv[i + 1])
            except ValueError:
                return _fail_usage("--dpi 需要整数")
            i += 2
            continue
        if a == "--pages" and i + 1 < len(argv):
            spec = argv[i + 1]
            try:
                if "-" in spec:
                    lo, hi = spec.split("-", 1)
                    pages = (int(lo), int(hi))
                else:
                    pages = (int(spec), int(spec))
            except ValueError:
                return _fail_usage("--pages 形如 1-8 或 3")
            i += 2
            continue
        rest.append(a)
        i += 1
    if len(rest) != 1:
        return _fail_usage("render 用法：<file.pdf> [-o dir] [--dpi 180] [--pages 1-8]")
    src = rest[0]
    try:
        import fitz
    except ImportError:
        return _fail_usage("渲染 PDF 需要 pymupdf：python -m pip install pymupdf")
    try:
        doc = fitz.open(src)
    except Exception as exc:
        return _fail_usage("打不开 %s（%s）" % (src, exc))
    total = doc.page_count
    if total <= 0:
        doc.close()
        return _fail_usage("%s 没有任何页面" % src)
    sample = sorted(set([0, total // 4, total // 2, (3 * total) // 4, total - 1]))
    sample = [p for p in sample if 0 <= p < total]
    hit, chars = 0, 0
    for p in sample:
        t = doc[p].get_text().strip()
        if t:
            hit += 1
            chars += len(t)
    if out_dir is None:
        out_dir = os.path.splitext(src)[0] + "-pages"
    if pages is None:
        lo, hi = 1, min(total, 8)
    else:
        lo, hi = max(1, pages[0]), min(total, pages[1])
    if hi < lo:
        lo, hi = 1, min(total, 1)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    for n in range(lo, hi + 1):
        pix = doc[n - 1].get_pixmap(dpi=dpi)
        pix.save(os.path.join(out_dir, "p%03d.png" % n))
    doc.close()
    sys.stdout.write("render: %d 页 -> %s（%d dpi，本次 %d 页）\n"
                     % (total, out_dir, dpi, hi - lo + 1))
    if hit:
        sys.stdout.write("  文本层：有（抽样 %d 页，%d 页抽到 %d 字）→ 可直接 extract\n"
                         % (len(sample), hit, chars))
    else:
        sys.stdout.write("  文本层：无（抽样 %d 页全 0 字）→ 扫描件，走视觉转录\n" % len(sample))
    sys.stdout.write("  页码：书版页码 = PDF 物理页 - 前置页数（先用目录页核对一次）\n")
    return EXIT_OK


SHELF_CSS = """
body{margin:0;background:#f7f3ea;color:#2b2b2b;font-family:"Noto Serif SC","Source Han Serif SC",Georgia,serif}
.page{max-width:1000px;margin:0 auto;padding:56px 24px 80px}
h1{font-size:34px;margin:0 0 10px}
.lead{color:#6b6257;margin:0 0 28px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}
.card{display:block;background:#fffdf8;border:1px solid #e6ddcc;border-radius:12px;padding:18px 18px 16px;text-decoration:none;color:inherit}
.card:hover{border-color:#c9b899;transform:translateY(-1px)}
.b{font-size:19px;font-weight:600;margin:0 0 6px}
.a{color:#8a7f70;font-size:13px;margin:0 0 12px}
.m{font-size:12px;color:#9a8f80;border-top:1px dashed #e6ddcc;padding-top:10px;display:flex;justify-content:space-between}
.empty{color:#9a8f80}
.bk{margin:0 0 26px;padding-bottom:20px;border-bottom:1px solid #efe6d6}
.bk h2{font-size:22px;margin:0 0 4px}
.bk .au{color:#8a7f70;font-size:13px;margin:0 0 12px}
.row{display:flex;flex-wrap:wrap;gap:8px}
.chip{display:inline-block;font-size:13px;padding:6px 12px;border:1px solid #e6ddcc;border-radius:99px;background:#fffdf8;color:#2b2b2b;text-decoration:none}
.chip:hover{border-color:#c9b899}
.chip.off{color:#b5aa99;background:#fbf7ef}
footer{margin-top:36px;color:#a39785;font-size:12px;border-top:1px solid #e6ddcc;padding-top:14px}
"""

SHELF_LABEL = {"theme": "主题页", "overview": "全书骨架", "reader": "速读页"}


def cmd_shelf(argv):
    out = "index.html"
    dirs = []
    i = 0
    while i < len(argv):
        if argv[i] == "-o" and i + 1 < len(argv):
            out = argv[i + 1]
            i += 2
            continue
        dirs.append(argv[i])
        i += 1
    if not dirs:
        dirs = ["."]
    rows = []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if not name.endswith(".json"):
                continue
            p = os.path.join(d, name)
            try:
                ir = _read_json(p)
            except Exception:
                continue
            if not isinstance(ir, dict) or ir.get("schema") != SCHEMA:
                continue
            meta = ir.get("meta") or {}
            mode = meta.get("mode") or "theme"
            stem = os.path.splitext(name)[0]
            html = None
            for cand in (os.path.join(d, stem + ".html"),
                         os.path.join(d, "out", stem + ".html")):
                if os.path.isfile(cand):
                    html = cand
                    break
            if mode == "reader":
                count, unit = len(ir.get("chapters") or []), "章"
            elif mode == "overview":
                count, unit = len(ir.get("chapterMap") or []), "章"
            else:
                count, unit = len(ir.get("sections") or []), "节"
            rows.append({"book": meta.get("book") or stem, "author": meta.get("author") or "",
                         "mode": mode, "theme": meta.get("theme") or "paper",
                         "count": count, "unit": unit, "html": html})
    seen, uniq = set(), []
    for r in rows:
        key = (r["book"], r["mode"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    order = {"reader": 0, "overview": 1, "theme": 2}
    uniq.sort(key=lambda r: (order.get(r["mode"], 9), r["book"]))
    out_dir = os.path.dirname(os.path.abspath(out))
    groups = {}
    for r in uniq:
        groups.setdefault(r["book"], []).append(r)
    books = [(bk, sorted(items, key=lambda r: order.get(r["mode"], 9))) for bk, items in groups.items()]
    books.sort(key=lambda x: x[0])
    parts = []
    for bk, items in books:
        author = next((r["author"] for r in items if r["author"]), "")
        parts.append('<section class="bk">')
        parts.append("<h2>%s</h2>" % esc(bk))
        parts.append('<p class="au">%s</p>'
                     % ((esc(author) + " · 共 %d 页" % len(items)) if author
                        else "共 %d 页" % len(items)))
        parts.append('<div class="row">')
        for r in items:
            if r["html"]:
                href = os.path.relpath(os.path.abspath(r["html"]), out_dir).replace("\\", "/")
                parts.append('<a class="chip" href="%s">%s · %d %s</a>'
                             % (esc(href), SHELF_LABEL.get(r["mode"], r["mode"]), r["count"], r["unit"]))
            else:
                parts.append('<span class="chip off">%s · 未构建</span>'
                             % SHELF_LABEL.get(r["mode"], r["mode"]))
        parts.append("</div></section>")
    body = "\n".join(parts) if parts else '<p class="empty">这些目录里没有找到 bookpage IR。</p>'
    doc = ("<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n"
           "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
           "<title>bookpage 书房</title>\n<style>%s</style>\n</head>\n<body>\n"
           "<div class=\"page\">\n<h1>书房</h1>\n<p class=\"lead\">共 %d 本、%d 页，断网也能打开；一本书的三种页排在同一行。</p>\n"
           "%s\n"
           "<footer>bookpage 生成 · 同目录下的 IR 会被自动收进来</footer>\n</div>\n</body>\n</html>\n"
           % (SHELF_CSS, len(books), len(uniq), body))
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(doc)
    missing = sum(1 for r in uniq if not r["html"])
    sys.stdout.write("shelf: %d 本 -> %s（缺构建 %d 本）\n" % (len(uniq), out, missing))
    for r in uniq:
        sys.stdout.write("  %-4s %s（%d %s）\n" % (SHELF_LABEL.get(r["mode"], r["mode"]),
                                                  r["book"], r["count"], r["unit"]))
    return EXIT_OK

# ---------------------------------------------------------------- 命令
USAGE = """bookpage %s — 确定性书页渲染器（零依赖）

用法：
  python bookpage.py lint   <ir.json>
  python bookpage.py build  <ir.json> <out.html> [--degrade]
  python bookpage.py verify <ir.json> --source <书稿>
  python bookpage.py tokens <file>
  python bookpage.py chapters <file>
  python bookpage.py extract <book> [-o out.txt]
  python bookpage.py split   <book> [-o dir]
  python bookpage.py render  <file.pdf> [-o dir] [--dpi 180] [--pages 1-8]
  python bookpage.py shelf   [dir ...] [-o index.html]
  python bookpage.py outline <书稿> [-o 文件] [--per 4]
  python bookpage.py draft   <书稿> [-o 包.md] [--per 6] [--chapter N]

退出码：0 成功 / 1 校验有错 / 2 用法错误
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
    mode = (ir.get("meta") or {}).get("mode") or "theme"
    if mode == "overview":
        sys.stdout.write("lint: OK（overview：%d 框架 / %d 章 / %d 组概念 / %d 条规则 / %d 个问题）\n"
                         % (len(ir.get("frameworks") or []), len(ir.get("chapterMap") or []),
                            len(ir.get("conceptMap") or []), len(ir.get("decisionRules") or []),
                            len(ir.get("questions") or [])))
    elif mode == "reader":
        sys.stdout.write("lint: OK（reader：%d 章 / %d 条判断 / %d 组概念 / %d 个问题）\n"
                         % (len(ir.get("chapters") or []), len(ir.get("digest") or []),
                            len(ir.get("concepts") or []), len(ir.get("questions") or [])))
    else:
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
    mode = (ir.get("meta") or {}).get("mode") or "theme"
    if mode == "overview":
        desc = "overview（%d 框架 / %d 章 / %d 组概念 / %d 条规则）" % (
            len(ir.get("frameworks") or []), len(ir.get("chapterMap") or []),
            len(ir.get("conceptMap") or []), len(ir.get("decisionRules") or []))
    elif mode == "reader":
        desc = "reader（%d 章）" % len(ir.get("chapters") or [])
    else:
        n = len([s for s in (ir.get("sections") or []) if isinstance(s, dict)])
        desc = "%d sections" % n
    sys.stdout.write("built: %s, %d bytes -> %s\n"
                     % (desc, len(html.encode("utf-8")), dst))
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


def isdir_hint(path):
    """-o 给的是目录（已存在或带结尾斜杠）时，把全文写进该目录的 full_text.txt。"""
    return os.path.isdir(path) or path.endswith(("/", os.sep))


def cmd_extract(argv):
    out = None
    if "-o" in argv:
        i = argv.index("-o")
        if i + 1 >= len(argv):
            return _fail_usage("-o 后面要跟输出路径")
        out = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if len(argv) != 1:
        return _fail_usage("extract 需要 1 个参数：<书文件> [-o out.txt]")
    src = argv[0]
    try:
        text, method = extract_book(src)
    except MissingExtractor as exc:
        return _fail_usage(str(exc))
    except (IOError, OSError) as exc:
        return _fail_usage("读不到 %s（%s）" % (src, exc))
    except Exception as exc:  # 损坏的 docx/epub/pdf
        return _fail_usage("解析 %s 失败（%s）" % (src, exc))
    if out is None:
        out = os.path.splitext(src)[0] + ".txt"
    elif isdir_hint(out):
        out = os.path.join(out, "full_text.txt")
    parent = os.path.dirname(os.path.abspath(out))
    if not os.path.isdir(parent):
        os.makedirs(parent)
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    sys.stdout.write("extracted: %s（%s）-> %s\n" % (src, method, out))
    sys.stdout.write("  字符 %d / 章节 %d / 估算 tokens %d\n"
                     % (len(text), count_chapters(text), estimate_tokens(text)))
    return EXIT_OK


def cmd_split(argv):
    out = None
    if "-o" in argv:
        i = argv.index("-o")
        if i + 1 >= len(argv):
            return _fail_usage("-o 后面要跟输出目录")
        out = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if len(argv) != 1:
        return _fail_usage("split 需要 1 个参数：<书文件> [-o 输出目录]")
    src = argv[0]
    try:
        text, method = extract_book(src)
    except MissingExtractor as exc:
        return _fail_usage(str(exc))
    except (IOError, OSError) as exc:
        return _fail_usage("读不到 %s（%s）" % (src, exc))
    except Exception as exc:
        return _fail_usage("解析 %s 失败（%s）" % (src, exc))
    chapters, split_method = split_chapters(text)
    if out is None:
        out = os.path.splitext(src)[0] + ".chapters"
    if not os.path.isdir(out):
        os.makedirs(out)
    # 清掉上一次切分留下的 ch-*.md：章节数变化时旧文件会残留，读章程序会按文件名读到错位的章。
    for stale in os.listdir(out):
        if re.match(r"ch-[0-9]+.md$", stale):
            os.unlink(os.path.join(out, stale))
    index = []
    for i, (title, body) in enumerate(chapters, 1):
        name = "ch-%02d.md" % i
        path = os.path.join(out, name)
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# %s\n\n%s\n" % (title, body))
        index.append({"n": i, "title": title, "chars": len(body), "file": name})
    meta = {"source": os.path.abspath(src), "method": split_method,
            "extract": method, "chars": len(text), "chapters": index}
    with io.open(os.path.join(out, "index.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    sys.stdout.write("split: %d 章（%s）-> %s\n" % (len(chapters), split_method, out))
    for row in index:
        sys.stdout.write("  %s  %s（%d 字）\n" % (row["file"], row["title"], row["chars"]))
    return EXIT_OK


def _cjk_runs(text):
    """把文本切成连续 CJK 片段（标点、空白、拉丁字母都算断点）。"""
    return re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]{2,}", text)


STOP_CHARS = set("之乎者也而其所以於于與不為是有無知曰言乃則故若且焉耳夫矣哉皆亦則若雖然故曰")


def _is_function_word(w):
    """虚词拼接出来的窗口（而不 / 者也 / 以為）不该当成专名候选。"""
    return all(ch in STOP_CHARS for ch in w)


def _terms(text, chapters, limit=40, min_count=3):
    """高频专名候选：2–4 字窗口计数，长词优先覆盖短词，按 覆盖章数→次数 排序。"""
    counts = {}
    where = {}
    for idx, (title, body) in enumerate(chapters, 1):
        for run in _cjk_runs(body):
            for size in (2, 3, 4):
                for i in range(len(run) - size + 1):
                    w = run[i:i + size]
                    counts[w] = counts.get(w, 0) + 1
                    where.setdefault(w, set()).add(idx)
    cand = [w for w, c in counts.items() if c >= min_count and not _is_function_word(w)]
    cand.sort(key=lambda w: (-counts[w], -len(w), w))
    keep = []
    for w in cand:
        if any(w != k and w in k and counts[k] >= counts[w] * 0.9 for k in keep):
            continue
        keep.append(w)
    keep.sort(key=lambda w: (-len(where[w]), -counts[w], w))
    return [(w, counts[w], sorted(where[w])) for w in keep[:limit]]


def _sentence_split(body):
    return [x.strip() for x in re.split(r"[。！？；\n]+", body) if x.strip()]


QUOTE_MARK = re.compile(r"[「『][^」』]{6,90}[」』]|“[^”]{6,90}”")


def _candidates(body, terms, per=4):
    """章节候选引文：带引号的句子 > 含高频专名的短句 > 章首句。"""
    out = []
    for m in QUOTE_MARK.findall(body):
        out.append(("引号句", m))
    for sent in _sentence_split(body):
        if not (14 <= len(sent) <= 90):
            continue
        if [t for t, _, _ in terms if t in sent]:
            out.append(("含专名", sent))
    if body.strip():
        out.append(("首句", _sentence_split(body)[0]))
    seen = []
    for kind, text in out:
        if text in [t for _, t in seen]:
            continue
        seen.append((kind, text))
        if len(seen) >= per:
            break
    return seen


def outline_book(text, chapters, per=4):
    """只输出可被机器验证的信号：章结构、首/末句、书里自带引号的句子。

    刻意不做分词与专名提取 —— 试过两条都失败（见 README「outline 没做什么」）：
    2–4 字窗口在文言里全是「而不 / 者也」，对话标记正则在白话里抓出「誰知」这类副词。
    """
    lines = ["# 起草候选（给写 IR 用，不含全文）", "",
             "共 %d 章 / %d 字。" % (len(chapters), len(text)), ""]
    for idx, (title, body) in enumerate(chapters, 1):
        body = "\n".join(x for x in body.split("\n")
                         if x.strip() and not x.strip().startswith("#"))
        paras = [p for p in body.split("\n") if p.strip()]
        lines.append("## 第 %d 章 %s（%d 字 / %d 段）" % (idx, title, len(body), len(paras)))
        sents = [x for x in _sentence_split(body) if len(x) >= 8]
        if sents:
            lines.append("- 首句：%s" % sents[0])
            if len(sents) > 1:
                lines.append("- 末句：%s" % sents[-1])
        quotes = QUOTE_MARK.findall(body)[:per]
        for q in quotes:
            lines.append("- 书内引号句：%s" % q)
        if not quotes:
            lines.append("- 书内引号句：无（这章没有引号包起来的原话）")
        lines.append("")
    return "\n".join(lines) + "\n"


def _clip(text, n):
    """按句读边界截断，不把句子砍半（砍半的引文会被 verify 之外的读者当成残句）。"""
    if len(text) <= n:
        return text
    cut = text[:n]
    m = list(re.finditer(r"[，。；！？：、」』”]", cut))
    if m and m[-1].end() > n // 2:
        return cut[:m[-1].end()]
    return cut


def draft_pack(text, chapters, per=6, head=70, lead=14):
    """给"模型写 IR"用的上下文包：每章只留脉络，不留全文。

    每条目都设计成能被 verify 认账：章题、段首、引号句都直接取自原文片段，
    模型若照抄不会失真；若自己改写，verify 会报 E301/E302。
    """
    lines = ["# 起草包（只含脉络，不含全文）", "",
             "共 %d 章 / %d 字。写 IR 时只用本文件，不要回读全文。" % (len(chapters), len(text)),
             "纪律：quote 与 text 必须逐字取自原文（本包里的句子可直接用），改写会被 verify 报错。",
             ""]
    for idx, (title, body) in enumerate(chapters, 1):
        body = "\n".join(x for x in body.split("\n")
                         if x.strip() and not x.strip().startswith("#"))
        paras = [p.strip() for p in body.split("\n") if p.strip()]
        lines.append("## 第 %d 章 %s（%d 字 / %d 段）" % (idx, title, len(body), len(paras)))
        sents = [x for x in _sentence_split(body) if len(x) >= 8]
        if sents:
            lines.append("- 首句：%s" % _clip(sents[0], head))
            if len(sents) > 1:
                lines.append("- 末句：%s" % _clip(sents[-1], head))
        if len(paras) >= 4:
            lines.append("- 骨架（每段起头）：")
            for p in paras:
                g = re.sub(r"[ \u3000]+", " ", p).strip()
                lines.append("  · %s…" % g[:lead])
        else:
            lines.append("- 骨架（无分段，按句抽样）：")
            ss = [x for x in _sentence_split(body) if len(x) >= 6]
            if ss:
                step = max(1, len(ss) // 8)
                for k in range(0, len(ss), step):
                    lines.append("  · %s…" % _clip(re.sub(r"[ \u3000]+", " ", ss[k]).strip(), lead + 6))
        quotes = QUOTE_MARK.findall(body)[:per]
        if quotes:
            for q in quotes:
                lines.append("- 书内引号句：%s" % _clip(q, head * 2))
        else:
            lines.append("- 书内引号句：无（未加引号的书，quote 请从首/末句或骨架句里取连续的原文片段）")
        lines.append("")
    return "\n".join(lines) + "\n"


def cmd_draft(argv):
    """draft <书稿> [-o 文件名] [--per N] [--chapter N]"""
    out = None
    per = 6
    only = None
    src = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "-o":
            i += 1
            out = argv[i]
        elif a == "--per":
            i += 1
            per = int(argv[i])
        elif a == "--chapter":
            i += 1
            only = int(argv[i])
        elif a in ("--help", "-h"):
            print("用法：draft <书稿> [-o 文件名] [--per 6] [--chapter N]", file=sys.stderr)
            return EXIT_USAGE
        elif not a.startswith("-") and src is None:
            src = a
        i += 1
    if not src:
        print("ERROR: draft 需要一份书稿。用法：draft <书稿> [-o 文件名]", file=sys.stderr)
        return EXIT_USAGE
    text = strip_boilerplate(read_text(src))
    chapters, method = split_chapters(text, max_chars=6000)
    if only is not None:
        if only < 1 or only > len(chapters):
            print("ERROR: --chapter 超出范围（共 %d 章）" % len(chapters), file=sys.stderr)
            return EXIT_USAGE
        chapters = [chapters[only - 1]]
    md = draft_pack(text, chapters, per=per)
    if out:
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(md)
        print("draft: %d 章 / 切分方式 %s / %d 字 -> %s"
              % (len(chapters), method, len(md), out))
    else:
        sys.stdout.write(md)
    return EXIT_OK


def cmd_outline(argv):
    """outline <书稿> [-o 文件名] [--top N] [--per N]"""
    out = None
    per = 4
    src = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "-o":
            i += 1
            out = argv[i]
        elif a == "--top":
            i += 1
            argv[i] = argv[i]  # 兼容旧调用：词频统计已移除，参数被忽略
        elif a == "--per":
            i += 1
            per = int(argv[i])
        elif a in ("--help", "-h"):
            print("用法：outline <书稿> [-o 文件名] [--per 4]", file=sys.stderr)
            return EXIT_USAGE
        elif not a.startswith("-") and src is None:
            src = a
        i += 1
    if not src:
        print("ERROR: outline 需要一份书稿。用法：outline <书稿> [-o 文件名]", file=sys.stderr)
        return EXIT_USAGE
    text = strip_boilerplate(read_text(src))
    chapters, method = split_chapters(text, max_chars=6000)
    md = outline_book(text, chapters, per=per)
    if out:
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(md)
        print("outline: %d 章 / 切分方式 %s -> %s" % (len(chapters), method, out))
    else:
        sys.stdout.write(md)
    return EXIT_OK


COMMANDS = {"lint": cmd_lint, "build": cmd_build, "tokens": cmd_tokens, "chapters": cmd_chapters, "outline": cmd_outline, "draft": cmd_draft,
            "extract": cmd_extract, "split": cmd_split, "verify": cmd_verify, "render": cmd_render,
            "shelf": cmd_shelf}


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
