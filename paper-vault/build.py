#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""paper-vault 生成器引擎。

把 <vault>/papers/*/paper.json 渲染成本地静态、翻页式、中英对照的三遍法阅读库：
  L1 论文库首页 index.html
  L2 单篇门户 papers/<slug>/index.html （鸟瞰/理解/吃透 三模式 + L3 翻页阅读器）

用法：
  python3 build.py --vault <dir>     # 默认当前目录

一份引擎、三种入口（Claude Code skill / Codex AGENTS.md / 手动直跑）。
共享静态资源 app.css / library.js / reader.js 以字符串常量内嵌，每次 build 覆盖写出。
"""

import argparse
import html
import json
import sys
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# §6.1 主题 + 全局样式（app.css）
# ─────────────────────────────────────────────────────────────────────────────
APP_CSS = r"""
/* paper-vault app.css —— 由 build.py 写出，勿手改 */

/* ── 三套主题（html[data-theme] 切换） ── */
html[data-theme="warm"]{
  --paper:#f4ece0; --page:#f7f0e6; --ink:#2b2620; --soft:#6f6456;
  --accent:#c0613a; --accent2:#3f7a6d; --card:#fffaf2; --line:#e0d5c4; --gold:#b8860b;
}
html[data-theme="paperwhite"]{
  --paper:#e9e9e9; --page:#ffffff; --ink:#1a1a1a; --soft:#666b70;
  --accent:#0a66c2; --accent2:#0a7d6b; --card:#ffffff; --line:#e3e3e3; --gold:#a07c00;
}
html[data-theme="slate"]{
  --paper:#0f141b; --page:#161d27; --ink:#e9edf2; --soft:#9aa6b2;
  --accent:#5aa9e6; --accent2:#5ad1b0; --card:#1c2530; --line:#2a3542; --gold:#d4af37;
}

:root{
  --font-zh:"Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif;
  --font-en:"Newsreader",Georgia,"Times New Roman",serif;
  --font-display:"Noto Serif SC","Songti SC",serif;
  --read:1;
}

*{box-sizing:border-box;}
html,body{margin:0;padding:0;}
body{
  background:var(--paper); color:var(--ink);
  font-family:var(--font-zh);
  -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility;
}
a{color:var(--accent); text-decoration:none;}
a:hover{text-decoration:underline;}

/* 语言显隐（对照/原文/中文） */
.en{font-family:var(--font-en);}
.zh{color:var(--soft); font-family:var(--font-zh);}
/* 语言隐藏必须绝对优先（用 !important 压过各内容块的 display:block，
   否则 list/标题等更高优先级规则会让 .zh 在原文模式下漏出中文） */
body.lang-en .zh{display:none !important;}
body.lang-zh .en{display:none !important;}
body.lang-zh .zh{color:var(--ink);}           /* zh-only 时把 zh 提为主色 */

/* ─────────────────── L1 论文库首页 ─────────────────── */
.l1{background:var(--paper);}
.l1 header.libhead{
  max-width:1180px; margin:0 auto; padding:54px 40px 18px;
  display:flex; align-items:baseline; gap:16px; flex-wrap:wrap;
}
.l1 .libtitle{
  font-family:var(--font-display); font-weight:700;
  font-size:calc(34px*var(--read)); margin:0; color:var(--ink);
}
.l1 .libcount{color:var(--soft); font-size:calc(16px*var(--read));}
.l1 .spacer{flex:1;}
.iconbtn{
  background:var(--card); border:1px solid var(--line); color:var(--ink);
  border-radius:10px; padding:7px 12px; cursor:pointer; font-size:16px; line-height:1;
}
.iconbtn:hover{border-color:var(--accent);}

#chips{max-width:1180px; margin:0 auto; padding:6px 40px 10px; display:flex; gap:8px; flex-wrap:wrap;}
.chip{
  background:var(--card); border:1px solid var(--line); color:var(--soft);
  border-radius:999px; padding:5px 14px; cursor:pointer; font-size:calc(14px*var(--read));
}
.chip.on{background:var(--accent); border-color:var(--accent); color:#fff;}

main.lib{max-width:1180px; margin:0 auto; padding:10px 40px 120px;}
.catgroup{margin:22px 0 8px;}
.cathead{
  font-family:var(--font-display); font-weight:600; color:var(--accent2);
  font-size:calc(20px*var(--read)); margin:18px 0 10px;
  border-bottom:2px solid var(--line); padding-bottom:6px;
}
.pcard{
  background:var(--card); border:1px solid var(--line); border-radius:14px;
  padding:16px 18px; margin:10px 0;
}
.pcard .pcardtop{display:flex; align-items:flex-start; gap:10px;}
.pcard .caret{
  cursor:pointer; user-select:none; color:var(--soft);
  transition:transform .2s ease; font-size:14px; line-height:1.7; flex:0 0 auto;
}
.pcard.open .caret{transform:rotate(90deg);}
.pcard .ptitle{
  font-family:var(--font-en); font-weight:600;
  font-size:calc(23px*var(--read)); color:var(--ink); line-height:1.35;
}
.pcard .pmeta{color:var(--soft); font-size:calc(13px*var(--read)); margin-top:4px;}
.pcard .pmeta .cat{color:var(--accent2);}
.pcard .poverview{
  max-height:0; overflow:hidden; transition:max-height .3s ease;
  color:var(--ink); font-size:calc(15px*var(--read)); line-height:1.85; margin-top:0;
}
.pcard.open .poverview{max-height:1200px; margin-top:12px;}

/* ─────────────────── L2 / L3 阅读器 ─────────────────── */
body.l2{height:100vh; overflow:hidden; background:var(--paper);}
.topbar{
  position:fixed; top:0; left:0; right:0; height:54px; z-index:30;
  display:flex; align-items:center; gap:12px; padding:0 18px;
  background:var(--card); border-bottom:1px solid var(--line);
}
.topbar .home{font-size:18px; flex:0 0 auto;}
.topbar .tb-title{
  font-family:var(--font-en); font-weight:600; font-size:16px; color:var(--ink);
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:34vw;
}
.topbar .tb-meta{color:var(--soft); font-size:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:18vw;}
.topbar .tb-spacer{flex:1;}
.seg{display:inline-flex; background:var(--paper); border:1px solid var(--line); border-radius:10px; overflow:hidden;}
.seg button{
  background:transparent; border:0; color:var(--soft); cursor:pointer;
  padding:6px 12px; font-size:13px; font-family:var(--font-zh);
}
.seg button.on{background:var(--accent); color:#fff;}

#progress{position:fixed; top:54px; left:0; height:3px; background:var(--accent); width:0; z-index:31; transition:width .2s ease;}

.modewrap{position:fixed; inset:54px 0 0 0; background:var(--paper);}
.mode{position:absolute; inset:0; display:none;}
.mode.active{display:block;}
.page{position:absolute; inset:0; overflow-y:auto; opacity:0; visibility:hidden;}
.page.active{opacity:1; visibility:visible;}

.col{max-width:1180px; margin:0 auto; padding:70px 88px 160px;}
.col h2.pagetitle{
  font-family:var(--font-display); font-weight:700;
  font-size:calc(41px*var(--read)); line-height:1.25; margin:0 0 6px; color:var(--ink);
}
.col h2.pagetitle .zh{display:block; font-size:calc(22px*var(--read)); color:var(--soft); margin-top:4px;}

/* 内容块 */
.blk-p{font-size:calc(23px*var(--read)); line-height:1.9; margin:18px 0;}
.blk-p .en{display:block;}
.blk-p .zh{display:block; margin-top:6px; font-size:calc(20px*var(--read)); line-height:1.85;}
.blk-h3{font-family:var(--font-display); font-size:calc(28px*var(--read)); margin:30px 0 10px; color:var(--ink);}
.blk-h3 .zh{display:block; font-size:calc(18px*var(--read)); color:var(--soft);}
.blk-list{font-size:calc(22px*var(--read)); line-height:1.85; margin:14px 0; padding-left:0; list-style:none;}
.blk-list li{position:relative; padding-left:26px; margin:8px 0;}
.blk-list li::before{content:"\25C6"; position:absolute; left:0; color:var(--accent2); font-size:.7em; top:.45em;}
.blk-list li .en{display:block;}
.blk-list li .zh{display:block; font-size:calc(19px*var(--read));}
.blk-quote{
  border-left:4px solid var(--accent); background:var(--card);
  padding:14px 20px; margin:20px 0; border-radius:0 10px 10px 0;
  font-size:calc(21px*var(--read)); line-height:1.85;
}
.blk-quote .en{display:block; font-style:italic;}
.blk-quote .zh{display:block; margin-top:6px;}

/* 5C 等术语：竖向叠放（每张卡占整行） */
.blk-terms{display:flex; flex-direction:column; gap:12px; margin:20px 0;}
.term{background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 18px;}
.term-w,.term-zh{display:inline-block;}
.term-zh{margin-left:8px; color:var(--soft);}
.term-w{font-family:var(--font-en); font-weight:600; font-size:calc(21px*var(--read)); color:var(--accent);}
.term-zh{font-size:calc(18px*var(--read)); color:var(--ink); margin-top:2px;}
.term-m{font-size:calc(18px*var(--read)); color:var(--soft); margin-top:6px; line-height:1.7;}

.blk-qa{background:var(--card); border:1px solid var(--line); border-radius:14px; padding:16px 18px; margin:16px 0;}
.qa-row{display:flex; gap:12px; align-items:flex-start;}
.qa-row+.qa-row{margin-top:12px; padding-top:12px; border-top:1px dashed var(--line);}
.qa-badge{
  flex:0 0 auto; width:28px; height:28px; border-radius:8px; color:#fff;
  display:flex; align-items:center; justify-content:center; font-weight:700; font-size:15px;
}
.qa-q .qa-badge{background:var(--accent);}
.qa-a .qa-badge{background:var(--accent2);}
.qa-body{font-size:calc(20px*var(--read)); line-height:1.8;}
.qa-body .en{display:block;}
.qa-body .zh{display:block; margin-top:4px; font-size:calc(18px*var(--read));}

.blk-figure{margin:24px 0; text-align:center;}
.blk-figure img,.blk-figure svg{max-width:100%; height:auto; border-radius:10px; background:var(--card); border:1px solid var(--line);}
.blk-figure figcaption{font-size:calc(18px*var(--read)); color:var(--soft); margin-top:8px; line-height:1.7;}
.blk-figure figcaption .en{display:block;}
.blk-figure figcaption .zh{display:block;}

.blk-math{font-size:calc(20px*var(--read)); margin:20px 0; overflow-x:auto;}
.blk-code{
  background:var(--card); border:1px solid var(--line); border-radius:10px;
  padding:14px 16px; margin:18px 0; overflow-x:auto;
  font-size:calc(18px*var(--read)); line-height:1.6;
}
.blk-code code{font-family:"SF Mono",Menlo,Consolas,monospace; white-space:pre;}

/* 底部导航 / 侧栏目录 / 提示 */
.nav{
  position:fixed; bottom:18px; left:50%; transform:translateX(-50%); z-index:25;
  display:flex; align-items:center; gap:14px;
  background:var(--card); border:1px solid var(--line); border-radius:999px;
  padding:8px 16px; box-shadow:0 4px 18px rgba(0,0,0,.12);
}
.nav button{background:transparent; border:0; color:var(--ink); cursor:pointer; font-size:18px;}
.nav .pageno{color:var(--soft); font-size:14px; min-width:54px; text-align:center;}
.hint{position:fixed; bottom:18px; right:18px; color:var(--soft); font-size:12px; z-index:24; opacity:.7;}

/* 左侧常驻目录：默认展开，可完全收起为悬浮按钮（pv_toc） */
.toc{
  position:fixed; top:54px; bottom:0; left:0; width:280px; z-index:40;
  background:var(--card); border-right:1px solid var(--line);
  transform:translateX(0); transition:transform .25s ease; overflow-y:auto; padding:16px 14px;
}
body.toc-collapsed .toc{transform:translateX(-100%);}
.toc .toc-head{display:flex; align-items:center; justify-content:space-between; margin:0 0 10px;}
.toc h4{font-family:var(--font-display); color:var(--accent2); margin:0; font-size:16px;}
.toc .toc-collapse{background:transparent; border:0; color:var(--soft); cursor:pointer; font-size:18px; line-height:1;}
.toc a{display:block; padding:7px 10px; border-radius:8px; color:var(--ink); font-size:14px; line-height:1.4;}
.toc a:hover{background:var(--paper); text-decoration:none;}
.toc a.cur{background:var(--accent); color:#fff;}
/* 目录条目双语：对照模式英文在上、中文在下；原文/中文各显一种 */
.toc a .en{display:block;}
.toc a .zh{display:block; color:var(--soft); font-size:12px;}
.toc a.cur .zh{color:#fff; opacity:.85;}
.toc h4 .en,.toc h4 .zh{display:inline;}
.toc h4 .zh{margin-left:6px; color:var(--soft); font-weight:400; font-size:13px;}
/* 分组标题（一级）与组内（二级缩进） */
.toc a.toc-group{font-weight:700; color:var(--accent2); margin-top:8px;}
.toc a.toc-group .zh{color:var(--accent2); opacity:.8;}
.toc a.toc-sub{padding-left:24px; font-size:13px;}
.toc a.toc-sub .zh{font-size:11px;}
/* 悬浮重开按钮：仅收起时出现 */
.toc-fab{
  position:fixed; left:14px; top:70px; z-index:39; display:none;
  width:40px; height:40px; border-radius:10px; align-items:center; justify-content:center;
  background:var(--card); border:1px solid var(--line); color:var(--ink); cursor:pointer;
  font-size:18px; box-shadow:0 3px 12px rgba(0,0,0,.12);
}
body.toc-collapsed .toc-fab{display:flex;}
/* 阅读区随目录展开右移；收起时占满 */
.modewrap{left:280px;}
body.toc-collapsed .modewrap{left:0;}

/* 章节标题树（鸟瞰导览页） */
.blk-headings{list-style:none; padding-left:0; margin:16px 0; font-size:calc(20px*var(--read)); line-height:1.7;}
.blk-headings li{padding:5px 0; border-bottom:1px dashed var(--line);}
.blk-headings .hd-l1{padding-left:0;}
.blk-headings .hd-l2{padding-left:26px;}
.blk-headings .hd-l3{padding-left:52px;}
.blk-headings .hd-title{font-weight:600;}
.blk-headings .hd-l3 .hd-title{font-weight:500; color:var(--soft);}
.blk-headings .hd-title .en{margin-right:8px;}
.blk-headings .hd-title .zh{color:var(--soft); font-weight:400;}
/* 每节开头第一小截原文 */
.blk-headings .hd-lead{font-size:calc(16px*var(--read)); line-height:1.65; margin-top:4px; color:var(--soft); border-left:2px solid var(--line); padding-left:12px;}
.blk-headings .hd-lead .en{display:block; font-family:var(--font-en);}
.blk-headings .hd-lead .zh{display:block;}

/* 参考文献 */
.blk-refs{margin:16px 0; padding-left:26px; font-size:calc(17px*var(--read)); line-height:1.7;}
.blk-refs li{margin:8px 0;}
.ref-link{color:var(--accent); font-weight:600;}
.ref-note{color:var(--soft);}
.ref-note .en{display:block;} .ref-note .zh{display:block;}

/* 幻灯页（鸟瞰速览，frontend-slides 风格） */
.page--slide .col{max-width:980px; padding:90px 80px 160px; display:flex; flex-direction:column; justify-content:center; min-height:100%;}
.page--slide .pagetitle{font-size:calc(52px*var(--read)); border-left:6px solid var(--accent); padding-left:22px; margin-bottom:28px;}
.page--slide .pagetitle .zh{font-size:calc(26px*var(--read));}
.page--slide .blk-list{font-size:calc(27px*var(--read)); line-height:2;}
.page--slide .blk-list li{margin:16px 0;}
.page--slide .blk-list li .zh{font-size:calc(22px*var(--read));}
.page--slide .blk-p{font-size:calc(27px*var(--read)); line-height:1.9;}

/* 假设卡徽标 */
.blk-assume .qa-q .qa-badge{background:var(--gold);}
.blk-assume .qa-a .qa-badge{background:var(--accent2);}

/* 卡片模式：全局折叠答案，点卡片翻开 */
.qa-reveal{display:none; color:var(--accent); font-size:calc(15px*var(--read)); margin-top:10px; user-select:none;}
body.cards-hidden .blk-qa{cursor:pointer;}
body.cards-hidden .blk-qa .qa-a{display:none;}
body.cards-hidden .blk-qa .qa-reveal{display:block;}
body.cards-hidden .blk-qa.revealed .qa-a{display:flex;}
body.cards-hidden .blk-qa.revealed .qa-reveal{display:none;}
.iconbtn.on{background:var(--accent); color:#fff; border-color:var(--accent);}

@media (max-width:900px){
  /* 窄屏：目录改为覆盖式抽屉，不挤压阅读区 */
  .modewrap{left:0;}
  .toc{transform:translateX(-100%); box-shadow:0 0 24px rgba(0,0,0,.18);}
  body:not(.toc-collapsed) .toc{transform:translateX(0);}
}
@media (max-width:760px){
  .col{padding:40px 22px 140px;}
  .page--slide .col{padding:60px 28px 140px;}
  .topbar .tb-title{max-width:40vw;}
  .topbar .tb-meta{display:none;}
}
"""

# ─────────────────────────────────────────────────────────────────────────────
# §6.3 L1 行为（library.js）
# ─────────────────────────────────────────────────────────────────────────────
LIBRARY_JS = r"""
/* paper-vault library.js —— L1 行为 */
(function(){
  var THEMES = ["warm","paperwhite","slate"];
  function applyTheme(t){ document.documentElement.setAttribute("data-theme", t); }

  // 主题：localStorage.pv_theme，◐ 在 warm→paperwhite→slate 循环
  var saved = localStorage.getItem("pv_theme");
  if (saved && THEMES.indexOf(saved) >= 0) applyTheme(saved);
  var tbtn = document.getElementById("themeBtn");
  if (tbtn) tbtn.addEventListener("click", function(){
    var cur = document.documentElement.getAttribute("data-theme") || "warm";
    var next = THEMES[(THEMES.indexOf(cur)+1) % THEMES.length];
    applyTheme(next); localStorage.setItem("pv_theme", next);
  });

  // 折叠：点 .caret 切 .pcard.open（CSS 用 max-height 过渡展开 .poverview）
  document.querySelectorAll(".pcard").forEach(function(card){
    var head = card.querySelector(".pcardtop");
    if (head) head.addEventListener("click", function(e){
      if (e.target.closest("a")) return;          // 点标题链接不折叠
      card.classList.toggle("open");
    });
  });

  // 分类筛选：点 chip 高亮、显示对应 .catgroup、隐藏其余（「全部」显示所有）
  var chips = document.querySelectorAll(".chip");
  chips.forEach(function(chip){
    chip.addEventListener("click", function(){
      chips.forEach(function(c){ c.classList.remove("on"); });
      chip.classList.add("on");
      var cat = chip.getAttribute("data-cat");
      document.querySelectorAll(".catgroup").forEach(function(g){
        g.style.display = (cat === "__all__" || g.getAttribute("data-cat") === cat) ? "" : "none";
      });
    });
  });
})();
"""

# ─────────────────────────────────────────────────────────────────────────────
# §6.4 L2/L3 行为（reader.js）
# ─────────────────────────────────────────────────────────────────────────────
READER_JS = r"""
/* paper-vault reader.js —— L2 翻页阅读器行为 */
(function(){
  var THEMES = ["warm","paperwhite","slate"];
  var LANGS  = ["both","en","zh"];

  // 收集 3 个 .mode → {mode:{el,pages[],idx}}
  var modes = {};
  document.querySelectorAll(".mode").forEach(function(m){
    var key = m.getAttribute("data-mode");
    modes[key] = { el:m, pages: Array.prototype.slice.call(m.querySelectorAll(".page")), idx:0 };
  });
  var cur = document.querySelector(".mode.active");
  var curKey = cur ? cur.getAttribute("data-mode") : Object.keys(modes)[0];

  var progress = document.getElementById("progress");
  var pageno   = document.querySelector(".nav .pageno");
  var tocEl    = document.querySelector(".toc");

  function curMode(){ return modes[curKey]; }

  function showPage(n){
    var M = curMode(); if (!M || !M.pages.length) return;
    n = Math.max(0, Math.min(n, M.pages.length-1));
    M.idx = n;
    M.pages.forEach(function(p,i){
      p.classList.toggle("active", i===n);
      if (i===n) p.scrollTop = 0;
    });
    if (pageno) pageno.textContent = (n+1) + " / " + M.pages.length;
    if (progress) progress.style.width = ((n+1)/M.pages.length*100) + "%";
    if (tocEl) tocEl.querySelectorAll("a").forEach(function(a,i){ a.classList.toggle("cur", i===n); });
  }

  function buildTOC(){
    if (!tocEl) return;
    var M = curMode(); if (!M) return;
    // 标签同时给 en/zh 两个 span，由语言显隐 CSS 控制：对照模式双语、原文/中文各显一种
    function lbl(en, zh){
      return '<span class="en">'+(en||"")+'</span><span class="zh">'+(zh||"")+'</span>';
    }
    var html = '<div class="toc-head"><h4>'
             + lbl("Contents","目录")
             + '</h4><button class="toc-collapse" title="收起目录 · collapse">‹</button></div>';
    var lastGroup = null;
    M.pages.forEach(function(p,i){
      var en = p.getAttribute("data-toc-en"), zh = p.getAttribute("data-toc-zh");
      var gen = p.getAttribute("data-tocgrp-en")||"", gzh = p.getAttribute("data-tocgrp-zh")||"";
      var grpKey = gen || gzh;
      if (grpKey){
        if (grpKey !== lastGroup){   // 分组标题（一级），如 PPT 速览
          html += '<a href="#" class="toc-group" data-i="'+i+'">'+ lbl(gen,gzh) +'</a>';
          lastGroup = grpKey;
        }
        html += '<a href="#" class="toc-sub" data-i="'+i+'">'+ lbl(en,zh) +'</a>';  // 组内（二级）
      } else {
        lastGroup = null;
        html += '<a href="#" data-i="'+i+'">'+ lbl(en,zh) +'</a>';
      }
    });
    tocEl.innerHTML = html;
    tocEl.querySelectorAll("a").forEach(function(a){
      a.addEventListener("click", function(e){
        e.preventDefault();
        showPage(parseInt(a.getAttribute("data-i"),10));
        if (window.matchMedia("(max-width:900px)").matches) setToc(true); // 窄屏点目录后自动收起
      });
    });
    var cb = tocEl.querySelector(".toc-collapse");
    if (cb) cb.addEventListener("click", function(){ setToc(true); });
  }

  // 目录收起/展开（完全收起 + 悬浮按钮）
  function setToc(collapsed){
    document.body.classList.toggle("toc-collapsed", collapsed);
    localStorage.setItem("pv_toc", collapsed ? "1" : "0");
  }
  function toggleToc(){ setToc(!document.body.classList.contains("toc-collapsed")); }

  // 卡片模式：折叠所有答案，点卡片翻开
  function setCards(on){
    document.body.classList.toggle("cards-hidden", on);
    localStorage.setItem("pv_cards", on ? "1" : "0");
    var b = document.getElementById("cardBtn"); if (b) b.classList.toggle("on", on);
    if (!on) document.querySelectorAll(".blk-qa.revealed").forEach(function(c){ c.classList.remove("revealed"); });
  }
  function toggleCards(){ setCards(!document.body.classList.contains("cards-hidden")); }

  function showMode(mk){
    if (!modes[mk]) return;
    curKey = mk;
    Object.keys(modes).forEach(function(k){ modes[k].el.classList.toggle("active", k===mk); });
    document.querySelectorAll(".seg.modeseg button").forEach(function(b){
      b.classList.toggle("on", b.getAttribute("data-mode")===mk);
    });
    buildTOC();
    showPage(modes[mk].idx);   // 显示该模式记忆的页码
  }

  // 语言：pv_lang ∈ both/en/zh
  function setLang(m){
    document.body.className = "l2 lang-" + m;
    localStorage.setItem("pv_lang", m);
    document.querySelectorAll(".seg.langseg button").forEach(function(b){
      b.classList.toggle("on", b.getAttribute("data-lang")===m);
    });
    buildTOC();   // 目录跟随语言切换（原文/中文）重建
  }
  function cycleLang(){
    var c = localStorage.getItem("pv_lang") || "both";
    setLang(LANGS[(LANGS.indexOf(c)+1) % LANGS.length]);
  }

  // 字号：pv_read，A+/A- 改 --read（范围 0.7–1.6）
  function setRead(v){
    v = Math.max(0.7, Math.min(1.6, v));
    document.documentElement.style.setProperty("--read", v);
    localStorage.setItem("pv_read", v);
  }

  // 主题：◐ 循环
  function applyTheme(t){ document.documentElement.setAttribute("data-theme", t); }
  function cycleTheme(){
    var c = document.documentElement.getAttribute("data-theme") || "warm";
    var n = THEMES[(THEMES.indexOf(c)+1) % THEMES.length];
    applyTheme(n); localStorage.setItem("pv_theme", n);
  }

  // 全屏
  function toggleFull(){
    if (!document.fullscreenElement) { (document.documentElement.requestFullscreen||function(){})(); }
    else { (document.exitFullscreen||function(){})(); }
  }

  // ── 绑定 topbar 控件 ──
  document.querySelectorAll(".seg.modeseg button").forEach(function(b){
    b.addEventListener("click", function(){ showMode(b.getAttribute("data-mode")); });
  });
  document.querySelectorAll(".seg.langseg button").forEach(function(b){
    b.addEventListener("click", function(){ setLang(b.getAttribute("data-lang")); });
  });
  var prev=document.querySelector(".nav .prev"), next=document.querySelector(".nav .next");
  if (prev) prev.addEventListener("click", function(){ showPage(curMode().idx-1); });
  if (next) next.addEventListener("click", function(){ showPage(curMode().idx+1); });
  var tocBtn=document.getElementById("tocBtn");
  if (tocBtn) tocBtn.addEventListener("click", toggleToc);
  var tocFab=document.getElementById("tocFab");
  if (tocFab) tocFab.addEventListener("click", function(){ setToc(false); });
  var cardBtn=document.getElementById("cardBtn");
  if (cardBtn) cardBtn.addEventListener("click", toggleCards);
  // 卡片翻开：卡片模式下点 .blk-qa 切换 revealed
  document.addEventListener("click", function(e){
    if (!document.body.classList.contains("cards-hidden")) return;
    var card = e.target.closest(".blk-qa");
    if (card) card.classList.toggle("revealed");
  });
  var aMinus=document.getElementById("aMinus"), aPlus=document.getElementById("aPlus");
  if (aMinus) aMinus.addEventListener("click", function(){ setRead((parseFloat(localStorage.getItem("pv_read"))||1)-0.1); });
  if (aPlus)  aPlus.addEventListener("click",  function(){ setRead((parseFloat(localStorage.getItem("pv_read"))||1)+0.1); });
  var themeBtn=document.getElementById("themeBtn");
  if (themeBtn) themeBtn.addEventListener("click", cycleTheme);
  var fullBtn=document.getElementById("fullBtn");
  if (fullBtn) fullBtn.addEventListener("click", toggleFull);

  // ── 键盘 ──
  document.addEventListener("keydown", function(e){
    if (e.key==="ArrowLeft"||e.key==="PageUp"){ showPage(curMode().idx-1); }
    else if (e.key==="ArrowRight"||e.key==="PageDown"){ showPage(curMode().idx+1); }
    else if (e.key==="Home"){ showPage(0); }
    else if (e.key==="End"){ showPage(curMode().pages.length-1); }
    else if (e.key==="1"){ showMode("skim"); }
    else if (e.key==="2"){ showMode("grasp"); }
    else if (e.key==="3"){ showMode("master"); }
    else if (e.key==="l"||e.key==="L"){ cycleLang(); }
    else if (e.key==="t"||e.key==="T"){ toggleToc(); }
    else if (e.key==="c"||e.key==="C"){ toggleCards(); }
    else if (e.key==="f"||e.key==="F"){ toggleFull(); }
    else if (e.key==="Escape"){ setToc(true); }
  });

  // ── 触摸：横滑翻页（纵向留给页内滚动） ──
  var tx=0, ty=0;
  document.addEventListener("touchstart", function(e){ tx=e.touches[0].clientX; ty=e.touches[0].clientY; }, {passive:true});
  document.addEventListener("touchend", function(e){
    var dx=e.changedTouches[0].clientX-tx, dy=e.changedTouches[0].clientY-ty;
    if (Math.abs(dx)>60 && Math.abs(dx)>Math.abs(dy)){ showPage(curMode().idx + (dx<0?1:-1)); }
  }, {passive:true});

  // ── 含 .math 块则联网注入 MathJax CDN ──
  if (document.querySelector(".blk-math")){
    window.MathJax = { tex:{ inlineMath:[["\\(","\\)"]], displayMath:[["\\[","\\]"]] } };
    var s=document.createElement("script");
    s.src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js";
    s.async=true; document.head.appendChild(s);
  }

  // ── 初始化 ──
  var st=localStorage.getItem("pv_theme"); if (st && THEMES.indexOf(st)>=0) applyTheme(st);
  setLang(localStorage.getItem("pv_lang") || "both");
  setRead(parseFloat(localStorage.getItem("pv_read")) || 1);
  // 目录默认展开（窄屏默认收起）；卡片模式默认关闭
  var tocPref = localStorage.getItem("pv_toc");
  if (tocPref === null) tocPref = window.matchMedia("(max-width:900px)").matches ? "1" : "0";
  setToc(tocPref === "1");
  setCards(localStorage.getItem("pv_cards") === "1");
  showMode(curKey);
})();
"""


# ─────────────────────────────────────────────────────────────────────────────
# 渲染辅助
# ─────────────────────────────────────────────────────────────────────────────
def esc(s):
    return html.escape(s if s is not None else "", quote=True)


def lang_spans(en, zh):
    out = ""
    if en:
        out += '<span class="en">%s</span>' % esc(en)
    if zh:
        out += '<span class="zh">%s</span>' % esc(zh)
    return out


def render_block(b):
    t = b.get("type")
    if t == "p":
        return '<p class="blk-p">%s</p>' % lang_spans(b.get("en"), b.get("zh"))
    if t == "h3":
        return '<h3 class="blk-h3">%s</h3>' % lang_spans(b.get("en"), b.get("zh"))
    if t == "list":
        lis = "".join('<li>%s</li>' % lang_spans(it.get("en"), it.get("zh"))
                      for it in b.get("items", []))
        return '<ul class="blk-list">%s</ul>' % lis
    if t == "quote":
        return '<blockquote class="blk-quote">%s</blockquote>' % lang_spans(b.get("en"), b.get("zh"))
    if t == "terms":
        cards = ""
        for it in b.get("items", []):
            inner = ('<div class="term-w en">%s</div>'
                     '<div class="term-zh zh">%s</div>') % (esc(it.get("w")), esc(it.get("zh")))
            # 解释行：英文 m_en 与中文 m 各自成对（供严格中英对照）
            if it.get("m_en"):
                inner += '<div class="term-m en">%s</div>' % esc(it.get("m_en"))
            if it.get("m"):
                inner += '<div class="term-m zh">%s</div>' % esc(it.get("m"))
            cards += '<div class="term">%s</div>' % inner
        return '<div class="blk-terms">%s</div>' % cards
    if t == "qa":
        # 假设卡用 kind=assume 区分徽标，但结构与 qa 一致（卡片模式统一作用）
        is_assume = b.get("kind") == "assume"
        qbadge = "H" if is_assume else "Q"   # H=Hypothesis 假设
        abadge = "T" if is_assume else "A"   # T=Test 确认/挑战
        cls = "blk-qa" + (" blk-assume" if is_assume else "")
        return ('<div class="%s">'
                '<div class="qa-row qa-q"><span class="qa-badge">%s</span>'
                '<div class="qa-body">%s</div></div>'
                '<div class="qa-reveal">▸ 点击翻开 · tap to reveal</div>'
                '<div class="qa-row qa-a"><span class="qa-badge">%s</span>'
                '<div class="qa-body">%s</div></div>'
                '</div>') % (cls, qbadge, lang_spans(b.get("q_en"), b.get("q_zh")),
                             abadge, lang_spans(b.get("a_en"), b.get("a_zh")))
    if t == "headings":
        # 章节/小节标题树；leads=[{en,zh},...] 该节每个分段的开头小截（可多行）。
        # 兼容旧的单条 lead_en/lead_zh。
        lis = ""
        for it in b.get("items", []):
            lvl = min(max(int(it.get("level", 1)), 1), 3)
            head = '<div class="hd-title">%s</div>' % lang_spans(it.get("en"), it.get("zh"))
            leads = it.get("leads")
            if not leads and (it.get("lead_en") or it.get("lead_zh")):
                leads = [{"en": it.get("lead_en"), "zh": it.get("lead_zh")}]
            leads_html = ""
            for ld in (leads or []):
                leads_html += '<div class="hd-lead">%s</div>' % lang_spans(ld.get("en"), ld.get("zh"))
            lis += '<li class="hd-l%d">%s%s</li>' % (lvl, head, leads_html)
        return '<ul class="blk-headings">%s</ul>' % lis
    if t == "refs":
        # 参考文献；slug 命中库内论文则加跳转链接
        items = ""
        for it in b.get("items", []):
            cite = esc(it.get("cite"))
            note = ""
            if it.get("note_en") or it.get("note_zh"):
                note = ' <span class="ref-note">%s</span>' % lang_spans(it.get("note_en"), it.get("note_zh"))
            if it.get("slug"):
                cite = '<a class="ref-link" href="../%s/index.html">%s ↗</a>' % (esc(it.get("slug")), cite)
            items += '<li class="ref-item">%s%s</li>' % (cite, note)
        return '<ol class="blk-refs">%s</ol>' % items
    if t == "figure":
        # 优先原图 src，否则内联 svg（svg 是可信自产，不转义）
        if b.get("svg"):
            inner = b.get("svg")
        elif b.get("src"):
            inner = '<img src="%s" alt="">' % esc(b.get("src"))
        else:
            inner = ""
        cap = ""
        if b.get("caption_en") or b.get("caption_zh"):
            cap = '<figcaption>%s</figcaption>' % lang_spans(b.get("caption_en"), b.get("caption_zh"))
        return '<figure class="blk-figure">%s%s</figure>' % (inner, cap)
    if t == "math":
        return '<div class="blk-math">\\[%s\\]</div>' % esc(b.get("tex"))
    if t == "code":
        return '<pre class="blk-code"><code>%s</code></pre>' % esc(b.get("text"))
    if t == "pagebreak":
        return ""  # 在分页阶段处理
    return ""


def paginate(section):
    """一个 section = 一页；遇 pagebreak 把 blocks 切成多页。"""
    pages = [[]]
    for b in section.get("blocks", []):
        if b.get("type") == "pagebreak":
            pages.append([])
        else:
            pages[-1].append(b)
    pages = [p for p in pages if p]
    return pages or [[]]


def render_mode(mode_key, mode):
    """渲染一个 .mode（含若干 .page）。返回 html 字符串。"""
    pages_html = []
    for section in mode.get("sections", []):
        chunks = paginate(section)
        n = len(chunks)
        kind = section.get("kind", "") or ""
        page_cls = "page" + ((" page--" + kind) if kind else "")
        # 可选目录分组（如「PPT速览」），组内各页标题在目录里作二级
        grp_en = esc(section.get("toc_group_en", "") or "")
        grp_zh = esc(section.get("toc_group_zh", "") or "")
        grp_attr = (' data-tocgrp-en="%s" data-tocgrp-zh="%s"' % (grp_en, grp_zh)) if (grp_en or grp_zh) else ""
        for i, blocks in enumerate(chunks):
            title_en = section.get("title", "") or ""
            title_zh = section.get("title_zh", "") or ""
            part = " (%d/%d)" % (i + 1, n) if n > 1 else ""
            toc_en = esc((title_en or title_zh) + part)
            toc_zh = esc((title_zh or title_en) + part)
            title_html = '<h2 class="pagetitle"><span class="en">%s%s</span>' % (esc(title_en), esc(part))
            if title_zh:
                title_html += '<span class="zh">%s</span>' % esc(title_zh)
            title_html += "</h2>"
            body = "".join(render_block(b) for b in blocks)
            pages_html.append(
                '<section class="%s" data-toc="%s" data-toc-en="%s" data-toc-zh="%s"%s>'
                '<div class="col">%s%s</div></section>'
                % (page_cls, toc_zh, toc_en, toc_zh, grp_attr, title_html, body)
            )
    return '<div class="mode" data-mode="%s">%s</div>' % (mode_key, "".join(pages_html))


GOOGLE_FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
                '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
                '<link href="https://fonts.googleapis.com/css2?'
                'family=Noto+Sans+SC:wght@400;500;700&'
                'family=Noto+Serif+SC:wght@400;600;700&'
                'family=Newsreader:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">')


def render_l2(meta, modes, css_href, reader_href):
    title = esc(meta.get("title"))
    authors = esc(meta.get("authors"))
    source = esc(meta.get("source"))
    url = meta.get("url") or ""
    tb_meta = " · ".join([x for x in [authors, source] if x])

    mode_order = [("skim", "鸟瞰"), ("grasp", "理解"), ("master", "吃透")]
    modeseg = "".join(
        '<button data-mode="%s"%s>%s</button>' % (k, (" class=\"on\"" if i == 0 else ""), lbl)
        for i, (k, lbl) in enumerate(mode_order) if k in modes
    )
    langseg = ('<button data-lang="both" class="on">对照</button>'
               '<button data-lang="en">原文</button>'
               '<button data-lang="zh">中文</button>')

    modes_html = ""
    first = True
    for k, _lbl in mode_order:
        if k not in modes:
            continue
        m = render_mode(k, modes[k])
        if first:
            m = m.replace('<div class="mode"', '<div class="mode active"', 1)
            first = False
        modes_html += m

    url_link = ('<a class="home" href="%s" target="_blank" title="原文">🔗</a>' % esc(url)) if url else ""

    return """<!doctype html>
<html lang="zh" data-theme="warm">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s</title>
%(fonts)s
<link rel="stylesheet" href="%(css)s">
</head>
<body class="l2 lang-both">
<div class="topbar">
  <a class="home" href="../../index.html" title="返回论文库">📚</a>
  <span class="tb-title">%(title)s</span>
  <span class="tb-meta">%(tbmeta)s</span>
  %(urllink)s
  <span class="tb-spacer"></span>
  <span class="seg modeseg">%(modeseg)s</span>
  <span class="seg langseg">%(langseg)s</span>
  <button class="iconbtn" id="tocBtn" title="目录 (T)">☰</button>
  <button class="iconbtn" id="cardBtn" title="卡片模式 (C)：折叠答案，先猜后翻">卡</button>
  <button class="iconbtn" id="aMinus" title="缩小">A−</button>
  <button class="iconbtn" id="aPlus" title="放大">A+</button>
  <button class="iconbtn" id="themeBtn" title="主题">◐</button>
  <button class="iconbtn" id="fullBtn" title="全屏 (F)">⤢</button>
</div>
<div id="progress"></div>
<nav class="toc"></nav>
<button class="toc-fab" id="tocFab" title="展开目录">☰</button>
<div class="modewrap">%(modes)s</div>
<div class="nav">
  <button class="prev" title="上一页 (←)">‹</button>
  <span class="pageno">1 / 1</span>
  <button class="next" title="下一页 (→)">›</button>
</div>
<div class="hint">← → 翻页 · 1/2/3 模式 · L 语言 · T 目录 · F 全屏</div>
<script src="%(reader)s"></script>
</body>
</html>""" % {
        "title": title, "fonts": GOOGLE_FONTS, "css": css_href,
        "tbmeta": tb_meta, "urllink": url_link,
        "modeseg": modeseg, "langseg": langseg,
        "modes": modes_html, "reader": reader_href,
    }


def render_l1(papers, css_href, library_href):
    # papers: list of dict {slug, meta}
    cats = []
    for p in papers:
        c = (p["meta"].get("category") or "未分类").strip()
        if c not in cats:
            cats.append(c)
    cats.sort()

    chips = '<button class="chip on" data-cat="__all__">全部</button>'
    chips += "".join('<button class="chip" data-cat="%s">%s</button>' % (esc(c), esc(c)) for c in cats)

    groups_html = ""
    for c in cats:
        cards = ""
        for p in papers:
            if (p["meta"].get("category") or "未分类").strip() != c:
                continue
            m = p["meta"]
            href = "papers/%s/index.html" % p["slug"]
            pmeta = " · ".join([x for x in [esc(m.get("authors")), esc(m.get("source"))] if x])
            cards += ("""<div class="pcard">
  <div class="pcardtop">
    <span class="caret">▶</span>
    <div style="flex:1">
      <a class="ptitle" href="%(href)s">%(title)s</a>
      <div class="pmeta">%(pmeta)s · <span class="cat">%(cat)s</span></div>
    </div>
  </div>
  <div class="poverview">%(overview)s</div>
</div>""") % {
                "href": esc(href), "title": esc(m.get("title")),
                "pmeta": pmeta, "cat": esc(c), "overview": esc(m.get("overview")),
            }
        groups_html += ('<section class="catgroup" data-cat="%s">'
                        '<h3 class="cathead">%s</h3>%s</section>') % (esc(c), esc(c), cards)

    return """<!doctype html>
<html lang="zh" data-theme="warm">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>论文阅读库</title>
<link rel="stylesheet" href="%(css)s">
</head>
<body class="l1">
<header class="libhead">
  <h1 class="libtitle">论文阅读库</h1>
  <span class="libcount">%(count)d 篇 · 三遍法 · 中英对照</span>
  <span class="spacer"></span>
  <button class="iconbtn" id="themeBtn" title="主题">◐</button>
</header>
<div id="chips">%(chips)s</div>
<main class="lib">%(groups)s</main>
<script src="%(library)s"></script>
</body>
</html>""" % {
        "css": css_href, "count": len(papers),
        "chips": chips, "groups": groups_html, "library": library_href,
    }


# ─────────────────────────────────────────────────────────────────────────────
# §3 三模式原文比例自检
# 目标：skim≈1/5、grasp≈1/3、master≈1/2（en 词数 ÷ 全文词数）。
# 软硬度：允许 ±20% 误差（相对目标）。加工流程据此最多重跑 2 次。
# 需要 paper.json 的 meta.source_words 提供全文英文词数；缺失则跳过自检。
# ─────────────────────────────────────────────────────────────────────────────
RATIO_TOL = 0.20      # ±20%，相对目标
GRASP_TARGET = 0.50   # 理解：保留 ≥50% 原文关键内容
REPRO_MIN = 0.20      # 吃透「论文重现」段 ≥ 全文 20%


def _section_en_words(sec):
    n = 0
    for b in sec.get("blocks", []):
        for k in ("en", "q_en", "a_en", "caption_en"):
            v = b.get(k)
            if v:
                n += len(v.split())
        for it in b.get("items", []):
            for k in ("en", "w"):
                v = it.get(k)
                if v:
                    n += len(v.split())
    return n


def count_en_words(mode):
    """统计一个 mode 内所有 en 散文字段的英文词数（不计 code/math/tex）。"""
    return sum(_section_en_words(s) for s in mode.get("sections", []))


def check_ratios(meta, modes):
    """v2 校验：鸟瞰=结构化(不卡比例)；理解≥50%(±20%)；吃透只校验「论文重现」段≥20%全文。
    返回 (report_lines, violations)。"""
    try:
        source_words = int(meta.get("source_words") or 0)
    except (TypeError, ValueError):
        source_words = 0
    if source_words <= 0:
        return (["    （未提供 meta.source_words，跳过比例自检）"], [])

    lines, violations = [], []
    # 鸟瞰：结构化导览 + 幻灯，不设比例目标，仅报词数
    if "skim" in modes:
        w = count_en_words(modes["skim"])
        lines.append("    skim    %5d 词  比例 %.3f  （结构化导览+幻灯，不卡比例）"
                     % (w, w / source_words))
    # 理解：≥50%，±20% → [0.40, 0.60]
    if "grasp" in modes:
        lo, hi = GRASP_TARGET * (1 - RATIO_TOL), GRASP_TARGET * (1 + RATIO_TOL)
        w = count_en_words(modes["grasp"]); r = w / source_words
        status = "OK" if lo <= r <= hi else ("LOW" if r < lo else "HIGH")
        if status != "OK":
            violations.append(("grasp", r, GRASP_TARGET))
        lines.append("    grasp   %5d 词  比例 %.3f  目标 %.2f [%.2f,%.2f]  %s"
                     % (w, r, GRASP_TARGET, lo, hi, status))
    # 吃透：深度优先，不卡总量；只要求「论文重现」段(kind=reproduction) ≥20% 全文（允许 -20% 容差）
    if "master" in modes:
        repro = [s for s in modes["master"].get("sections", []) if s.get("kind") == "reproduction"]
        w = sum(_section_en_words(s) for s in repro); r = w / source_words
        floor = REPRO_MIN * (1 - RATIO_TOL)   # 0.16
        status = "OK" if r >= floor else "LOW"
        if status != "OK":
            violations.append(("master-repro", r, REPRO_MIN))
        total = count_en_words(modes["master"])
        lines.append("    master  重现段 %5d 词  比例 %.3f  目标 ≥%.2f  %s  （全模式 %d 词，深度优先）"
                     % (w, r, REPRO_MIN, status, total))
    return (lines, violations)


# ─────────────────────────────────────────────────────────────────────────────
# 严格中英对照校验：每个内容块必须同时给 en 与 zh（缺一即不合格）
# 例外：code/math（无译文）、terms.m（中文大白话，无英文对应，设计上仅中文）。
# ─────────────────────────────────────────────────────────────────────────────
def _has(v):
    return bool(v and str(v).strip())


def check_pairing(modes):
    """返回缺失对照的块列表 [(mode, section, idx, type, 说明)]。"""
    bad = []
    for mk in ("skim", "grasp", "master"):
        if mk not in modes:
            continue
        for sec in modes[mk].get("sections", []):
            st = sec.get("title_zh") or sec.get("title") or "?"
            for bi, b in enumerate(sec.get("blocks", [])):
                t = b.get("type")
                if t in ("p", "h3", "quote"):
                    if _has(b.get("en")) != _has(b.get("zh")):
                        bad.append((mk, st, bi, t, "en/zh 缺一"))
                elif t == "qa":
                    for a, z in (("q_en", "q_zh"), ("a_en", "a_zh")):
                        if _has(b.get(a)) != _has(b.get(z)):
                            bad.append((mk, st, bi, t, "%s/%s 缺一" % (a, z)))
                elif t == "figure":
                    if _has(b.get("caption_en")) != _has(b.get("caption_zh")):
                        bad.append((mk, st, bi, t, "caption en/zh 缺一"))
                elif t == "list":
                    for ii, it in enumerate(b.get("items", [])):
                        if _has(it.get("en")) != _has(it.get("zh")):
                            bad.append((mk, st, bi, t, "item %d en/zh 缺一" % ii))
                elif t == "terms":
                    for ii, it in enumerate(b.get("items", [])):
                        if _has(it.get("w")) != _has(it.get("zh")):
                            bad.append((mk, st, bi, t, "term %d w/zh 缺一" % ii))
                        if _has(it.get("m")) != _has(it.get("m_en")):
                            bad.append((mk, st, bi, t, "term %d m/m_en 缺一（解释需中英成对）" % ii))
                elif t == "headings":
                    for ii, it in enumerate(b.get("items", [])):
                        if _has(it.get("en")) != _has(it.get("zh")):
                            bad.append((mk, st, bi, t, "heading %d en/zh 缺一" % ii))
                        if _has(it.get("lead_en")) != _has(it.get("lead_zh")):
                            bad.append((mk, st, bi, t, "heading %d lead en/zh 缺一" % ii))
                        for li, ld in enumerate(it.get("leads", []) or []):
                            if _has(ld.get("en")) != _has(ld.get("zh")):
                                bad.append((mk, st, bi, t, "heading %d lead %d en/zh 缺一" % (ii, li)))
                # refs：引文为语言中立，note 若给则须成对
                elif t == "refs":
                    for ii, it in enumerate(b.get("items", [])):
                        if _has(it.get("note_en")) != _has(it.get("note_zh")):
                            bad.append((mk, st, bi, t, "ref %d note en/zh 缺一" % ii))
    return bad


# ─────────────────────────────────────────────────────────────────────────────
# §4 主流程
# ─────────────────────────────────────────────────────────────────────────────
def build(vault: Path):
    assets = vault / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "app.css").write_text(APP_CSS, encoding="utf-8")
    (assets / "library.js").write_text(LIBRARY_JS, encoding="utf-8")
    (assets / "reader.js").write_text(READER_JS, encoding="utf-8")

    papers = []
    all_violations = {}   # slug -> [(mode, ratio, target), ...]
    pairing_bad = {}      # slug -> [缺对照的块...]
    report = []
    papers_dir = vault / "papers"
    for pj in sorted(papers_dir.glob("*/paper.json")) if papers_dir.exists() else []:
        slug = pj.parent.name
        try:
            data = json.loads(pj.read_text(encoding="utf-8"))
        except Exception as e:
            print("  ! 跳过 %s：JSON 解析失败 %s" % (slug, e), file=sys.stderr)
            continue
        meta = data.get("meta", {})
        modes = data.get("modes", {})
        # L2 在 papers/<slug>/，资源回退两级
        out = render_l2(meta, modes, "../../assets/app.css", "../../assets/reader.js")
        (pj.parent / "index.html").write_text(out, encoding="utf-8")
        papers.append({"slug": slug, "meta": meta})
        # §3 比例自检
        lines, violations = check_ratios(meta, modes)
        report.append("  %s" % slug)
        report.extend(lines)
        if violations:
            all_violations[slug] = violations
        # 严格中英对照校验
        bad = check_pairing(modes)
        if bad:
            pairing_bad[slug] = bad

    l1 = render_l1(papers, "assets/app.css", "assets/library.js")
    (vault / "index.html").write_text(l1, encoding="utf-8")

    print("OK  %d 篇论文 -> %s" % (len(papers), (vault / "index.html").resolve()))
    print("原文比例自检（目标 ±%d%%）:" % int(RATIO_TOL * 100))
    print("\n".join(report))
    if all_violations:
        n = sum(len(v) for v in all_violations.values())
        print("⚠ %d 个模式超出 ±%d%% 目标比例（见上 LOW/HIGH）。"
              "加工流程应修订对应模式重跑，最多 2 次。" % (n, int(RATIO_TOL * 100)))
    # 中英对照校验报告
    if pairing_bad:
        n = sum(len(v) for v in pairing_bad.values())
        print("⚠ 中英对照校验：%d 个块缺少对照（每个内容块须同时给 en 与 zh）：" % n)
        for slug, items in pairing_bad.items():
            for mk, st, bi, t, why in items[:30]:
                print("    %s  %s/%s #%d %s — %s" % (slug, mk, st, bi, t, why))
    else:
        print("中英对照校验：全部内容块 en/zh 成对 ✓")
    return {"ratio": all_violations, "pairing": pairing_bad}


def main():
    ap = argparse.ArgumentParser(description="paper-vault 阅读库生成器")
    ap.add_argument("--vault", default=".", help="vault 目录（默认当前目录）")
    ap.add_argument("--strict", action="store_true",
                    help="比例超界或存在缺对照的块则以退出码 1 结束（供加工流程/CI 判定重跑）")
    args = ap.parse_args()
    result = build(Path(args.vault).expanduser().resolve())
    # 对照缺失始终视为硬错误；比例超界仅在 --strict 下视为错误
    if result["pairing"] or (args.strict and result["ratio"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
