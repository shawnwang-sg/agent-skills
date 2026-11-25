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
import re
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
  max-width:1480px; margin:0 auto; padding:40px 40px 6px;
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

/* 左侧分类文件夹栏（类似 Zotero 的集合），右侧只显示选中分类的论文 */
.libwrap{max-width:1480px; margin:0 auto; padding:0 40px; display:flex; gap:28px; align-items:flex-start;}
.folders{
  flex:0 0 240px; position:sticky; top:16px; margin-top:22px;
  max-height:calc(100vh - 32px); overflow:auto;
  background:var(--card); border:1px solid var(--line); border-radius:12px; padding:8px;
}
.fbar{display:flex; align-items:center; gap:6px; padding:4px 6px 8px;}
.fbar .ftitle{flex:1; color:var(--soft); font-size:12px; letter-spacing:.08em;}
.fbtn{background:var(--paper); border:1px solid var(--line); color:var(--ink); border-radius:7px;
  padding:2px 9px; font-size:12px; cursor:pointer;}
.fbtn:hover{border-color:var(--accent);}
.folder{
  display:flex; align-items:center; gap:6px; width:100%; box-sizing:border-box;
  border-radius:8px; padding:6px 10px; cursor:pointer; user-select:none;
  color:var(--ink); font-size:calc(14px*var(--read)); font-family:var(--font-zh);
}
.folder:hover{background:var(--paper);}
.folder .twist{flex:0 0 12px; color:var(--soft); font-size:11px;}
.folder .fname{flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
.folder .fcount{color:var(--soft); font-size:12px;}
.folder .fop{background:transparent; border:0; color:var(--soft); cursor:pointer; padding:0 3px; font-size:13px;}
.folder .fop:hover{color:var(--accent);}
.folder:not(:hover):not(.on) .fop{display:none;}   /* 编辑按钮只在悬停 / 选中的分类上出现，不挤名字 */
.folder.on{background:var(--accent); color:#fff;}
.folder.on .twist,.folder.on .fcount,.folder.on .fop{color:#fff;}
.folder.drop{outline:2px dashed var(--accent); outline-offset:-2px;}
.folder.fav{color:var(--accent); font-weight:600;}
.folder.fav.on{color:#fff;}
.libsearch{
  width:min(360px, 42vw); box-sizing:border-box; padding:7px 12px; border-radius:10px;
  border:1px solid var(--line); background:var(--card); color:var(--ink);
  font-size:calc(14px*var(--read)); font-family:var(--font-zh);
}
.libsearch:focus{outline:none; border-color:var(--accent);}
.pcard .star{
  flex:0 0 auto; background:transparent; border:0; cursor:pointer; padding:0 2px;
  font-size:22px; line-height:1.2; color:var(--soft);
}
.pcard .star:hover,.pcard .star.on{color:var(--gold, #c9a227);}
.pcard .readtag{
  flex:0 0 auto; align-self:flex-start; margin-top:4px; cursor:pointer;
  background:transparent; border:1px solid var(--line); color:var(--soft);
  border-radius:999px; padding:1px 9px; font-size:12px; font-family:var(--font-zh);
}
.pcard .readtag:hover{border-color:var(--accent2); color:var(--accent2);}
.pcard .readtag.on{background:var(--accent2); border-color:var(--accent2); color:#fff;}
@media(max-width:760px){ .libsearch{width:100%; order:5;} }
.folder.all{font-weight:600; border-bottom:1px solid var(--line); border-radius:8px 8px 0 0; margin-bottom:4px;}
.fhint{color:var(--soft); font-size:12px; padding:6px 8px 2px; line-height:1.6;}
.fhint:empty{display:none;}
.fhint.bad{color:var(--accent);}
.subhead{font-family:var(--font-zh); font-weight:600; color:var(--soft); font-size:calc(15px*var(--read)); margin:22px 0 6px;}
.fempty{color:var(--soft);}
body.fediting .pcard{cursor:grab;}
/* 左栏视图切换：内容 / 会议 / 作者 */
.fview{display:flex; gap:4px; margin:8px 4px 6px; padding:3px; background:var(--paper); border-radius:9px;}
.fview button{flex:1; border:0; background:transparent; color:var(--soft); border-radius:7px; padding:4px 0;
  font-size:13px; font-family:var(--font-zh); cursor:pointer;}
.fview button.on{background:var(--card); color:var(--ink); font-weight:600; box-shadow:0 1px 2px rgba(0,0,0,.08);}
.fgroup{color:var(--soft); font-size:11px; letter-spacing:.06em; padding:10px 10px 2px;}
body.fview-venue .fbar .fbtn, body.fview-author .fbar .fbtn{display:none;}
.flinks{margin:14px 4px 4px; padding-top:10px; border-top:1px solid var(--line); font-size:12px; line-height:1.7;}
.flinks b{display:block; color:var(--soft); font-weight:600; margin-bottom:2px;}
.flinks a{display:block; color:var(--accent2); text-decoration:none; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
.flinks a:hover{text-decoration:underline;}
/* 会议 / 作者介绍卡 */
.vcard{background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px 20px; margin:0 0 14px;
  font-family:var(--font-zh); font-size:calc(14px*var(--read)); line-height:1.75;}
.vcard .vfull{color:var(--soft); margin-bottom:8px;}
.vcard .vscore{float:right; margin:-4px 0 6px 16px; text-align:right;}
.vcard .vscore b{font-size:34px; color:var(--accent); font-family:var(--font-display);}
.vcard .vscore small{color:var(--soft); font-size:12px;}
.vcard .vtags span{display:inline-block; border:1px solid var(--line); border-radius:999px; padding:0 9px; margin:0 6px 6px 0; font-size:12px; color:var(--soft);}
.vcard .vtags span.ccf{border-color:var(--accent); color:var(--accent); font-weight:600;}
.vcard h4{margin:12px 0 4px; font-size:13px; color:var(--accent2);}
.vcard p{margin:0;}
.vcard table{border-collapse:collapse; margin-top:2px;}
.vcard td{padding:2px 16px 2px 0; vertical-align:top;}
.vcard .vlinks a{display:inline-block; margin:4px 8px 0 0; padding:3px 12px; border:1px solid var(--line); border-radius:8px;
  color:var(--ink); text-decoration:none; background:var(--paper);}
.vcard .vlinks a:hover{border-color:var(--accent);}
.uibtn{font-size:12px; font-weight:600; letter-spacing:.02em; min-width:34px;}
.libmotto{font-family:var(--font-zh); color:var(--accent); font-size:14px; letter-spacing:.04em;}
@media(max-width:760px){ .libmotto{display:none;} }
@media(max-width:760px){
  .libwrap{flex-direction:column; padding:0 16px; gap:0;}
  .folders{position:static; flex:none; width:100%; max-height:none; display:flex; flex-wrap:wrap; gap:4px;}
  .folder{width:auto;}
  .folder.all{border:0;}
}

main.lib{flex:1; min-width:0; padding:10px 0 60px;}
.libfoot{max-width:1480px; margin:0 auto; padding:0 40px 40px;}
@media(max-width:760px){ .libfoot{padding:0 16px 24px;} }
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

/* ── 我的概括（理解每一节末尾 / 鸟瞰的一句话结论）── */
.mysum{margin:0; padding:14px 16px; border:1px dashed var(--accent2); border-radius:12px; background:var(--card);
  font-family:var(--font-zh); font-size:calc(14px*var(--read)); line-height:1.7;}
.mysum .ms-head{font-weight:700; color:var(--accent2);}
.mysum .ms-sub{font-weight:400; color:var(--soft); font-size:12px; margin-left:8px;}
.mysum textarea{width:100%; box-sizing:border-box; margin:8px 0; padding:8px 10px; border:1px solid var(--line); border-radius:8px;
  background:var(--page); color:var(--ink); font:inherit; resize:vertical; min-height:84px;}
.mysum textarea:focus{outline:none; border-color:var(--accent2);}
.mysum .ms-bar{display:flex; gap:8px; align-items:center; flex-wrap:wrap;}
.mysum button{border:1px solid var(--line); background:var(--paper); color:var(--ink); border-radius:8px; padding:5px 14px; cursor:pointer; font:inherit; font-size:13px;}
.mysum button.primary{background:var(--accent2); border-color:var(--accent2); color:#fff; font-weight:600;}
.mysum button:disabled{opacity:.55; cursor:wait;}
.mysum .ms-st{color:var(--soft); font-size:12px;}
.mysum .ms-res{margin-top:10px;}
.mysum .ms-score{font-size:28px; font-weight:700; color:var(--accent); margin-right:8px;}
.mysum .ms-score small{font-size:14px; color:var(--soft); font-weight:400;}
.mysum .ms-res h5{margin:10px 0 2px; font-size:13px; color:var(--accent2);}
.mysum .ms-res ul{margin:2px 0; padding-left:20px;}
.mysum .ms-res q{display:block; color:var(--soft); font-style:italic; font-family:var(--font-en, serif); quotes:none;}
.mysum details summary{cursor:pointer; color:var(--accent2); margin-top:8px;}
.mysum-wrap{margin:18px 0 6px; text-align:right;}
.mysum-wrap .mysum{text-align:left; margin-top:8px;}
.ms-toggle{border:1px solid var(--line); background:transparent; color:var(--accent2); border-radius:999px; padding:3px 12px;
  font:13px var(--font-zh); cursor:pointer; opacity:.8;}
.ms-toggle:hover,.ms-toggle.on{opacity:1; border-color:var(--accent2);}
/* ── 划词收藏 → 雅言堂 ── */
.pick{position:fixed; z-index:50; display:flex; gap:4px; padding:4px; border-radius:9px; background:var(--ink); box-shadow:0 4px 14px rgba(0,0,0,.25);}
.pick button{border:0; background:transparent; color:var(--page); font:13px var(--font-zh); padding:4px 10px; border-radius:6px; cursor:pointer;}
.pick button:hover{background:rgba(255,255,255,.15);}
.toast{position:fixed; z-index:60; left:50%; bottom:70px; transform:translateX(-50%); max-width:min(560px,90vw);
  background:var(--ink); color:var(--page); padding:8px 16px; border-radius:10px; font:13px/1.6 var(--font-zh); box-shadow:0 4px 14px rgba(0,0,0,.25);}
"""

# ─────────────────────────────────────────────────────────────────────────────
# §6.3 L1 行为（library.js）
# ─────────────────────────────────────────────────────────────────────────────
FAVICON_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect x="4" y="4" width="92" height="92" rx="22" fill="#A62B26"/><g fill="none" stroke="#fff" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 31 Q35 25 50 33 Q65 25 80 31 V73 Q65 67 50 75 Q35 67 20 73 Z"/><path d="M50 33 V75"/></g></svg>'

LIBRARY_JS = r"""
/* paper-vault library.js —— L1 行为 */
(function(){
  // ── 界面语言（中 / EN）：存在 localStorage.pv_ui，切换后刷新页面 ──
  var UI = (function(){ try { return localStorage.getItem("pv_ui") === "en" ? "en" : "zh"; } catch(e) { return "zh"; } })();
  function T(zh, en){ return UI === "en" ? en : zh; }
  function X(o, k){ return UI === "en" && o && o[k + "_en"] != null ? o[k + "_en"] : (o || {})[k]; }   // 数据里的 *_en 字段
  document.documentElement.setAttribute("data-ui", UI);
  if (UI === "en") {
    document.documentElement.lang = "en";
    document.querySelectorAll("[data-en]").forEach(function(el){ el.textContent = el.getAttribute("data-en"); });
    document.querySelectorAll("[data-en-ph]").forEach(function(el){ el.placeholder = el.getAttribute("data-en-ph"); });
    document.querySelectorAll("[data-en-title]").forEach(function(el){ el.title = el.getAttribute("data-en-title"); });
    document.querySelectorAll(".pv-use-notice").forEach(function(n){
      var a = n.querySelector("a"), href = a ? a.getAttribute("href") : "";
      var full = !!n.querySelector("strong");
      n.innerHTML = (full ? "<div><strong>Personal study notice</strong> · " : "<span>") +
        "Personal study and research only · non-commercial · not for distribution" +
        (full ? "<p>Copyright in the papers, figures and other materials belongs to their authors and rights holders. Translations and notes are unofficial study aids; the original text prevails.</p></div>" : "</span>") +
        (href ? '<a href="' + href + '">Full statement</a>' : "");
    });
  }
  (function(){
    var host = document.querySelector(".libhead") || document.querySelector(".topbar");
    if (!host || document.getElementById("uiBtn")) return;
    var b = document.createElement("button");
    b.id = "uiBtn"; b.className = "iconbtn uibtn"; b.textContent = UI === "en" ? "中" : "EN";
    b.title = UI === "en" ? "切换到中文界面" : "Switch to English interface";
    b.addEventListener("click", function(){ try { localStorage.setItem("pv_ui", UI === "en" ? "zh" : "en"); } catch(e) {} location.reload(); });
    var theme = host.querySelector("#themeBtn");
    if (theme) host.insertBefore(b, theme); else host.appendChild(b);
  })();

  // 右下角「i」：打开本库的规划页 roadmap.html（以后要做的事）
  (function(href, bottom){
    if (document.getElementById("roadmap-i")) return;
    var a = document.createElement("a");
    a.id = "roadmap-i"; a.href = href; a.target = "_blank"; a.rel = "noopener"; a.title = T("以后要做的事", "Roadmap"); a.textContent = "i";
    a.style.cssText = "position:fixed;right:16px;bottom:" + bottom + "px;z-index:2147483000;width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#A62B26;color:#fff;text-decoration:none;font:italic 700 16px/1 Georgia,serif;box-shadow:0 2px 8px rgba(0,0,0,.25);opacity:.85";
    document.body.appendChild(a);
  })("roadmap.html", 16);

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

  // ── 分类树（类似 Zotero 的文件夹）──────────────────────────────────────
  // 数据：{tree:[{id,name,papers:[slug],children:[...]}]}，一篇论文只属于一个分类。
  // 点分类 → 右侧显示它和子分类里的论文。编辑模式下可新建子分类 / 改名 / 删除；
  // 拖论文到分类上 = 移过去；拖分类到分类上 = 变成它的子分类，拖到「全部论文」= 回到顶层。
  // 保存：用 serve.py 打开时写回 folders.json；直接双击打开时只存在本浏览器里。
  var treeBox = document.getElementById("ftree");
  if (!treeBox) return;
  var pool = document.getElementById("pool"), cardsBox = document.getElementById("cards");
  var titleEl = document.getElementById("fTitle"), hint = document.getElementById("fHint");
  var cardOf = {};
  pool.querySelectorAll(".pcard").forEach(function(c){ cardOf[c.getAttribute("data-slug")] = c; });
  var ALL = "__all__", NONE = "__none__", FAV = "__fav__", READ = "__reading__";
  var LS = function(k, v){ try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch(e) { return null; } };
  var embedded = JSON.parse(document.getElementById("pv-folders").textContent);
  var tree = embedded.tree, favs = embedded.favorites || [], reading = embedded.reading || [], editing = false, current = LS("pv_folder") || "";
  var query = "", searchBox = document.getElementById("q");
  // 会议 / 作者视图（venues.json 存在时才有）
  var VEN = embedded.venues, facets = embedded.facets || {}, venOf = {};
  if (VEN) VEN.venues.forEach(function(v){ venOf[v.key] = v; });
  var view = VEN ? (LS("pv_view") || "content") : "content";
  var lastOf = {}; try { lastOf = JSON.parse(LS("pv_view_last") || "{}"); } catch(e) {}
  function E(tag, cls, text){ var x = document.createElement(tag); if (cls) x.className = cls; if (text != null) x.textContent = text; return x; }
  function papersOfVenue(k){ return Object.keys(cardOf).filter(function(s){ return (facets[s] || {}).v === k; }); }
  function papersOfAuthor(a){ return Object.keys(cardOf).filter(function(s){ return ((facets[s] || {}).a || []).indexOf(a) >= 0; }); }
  function authorCounts(){
    var c = {}; Object.keys(cardOf).forEach(function(s){ ((facets[s] || {}).a || []).forEach(function(a){ c[a] = (c[a] || 0) + 1; }); });
    return c;
  }
  function byYear(slugs){ return slugs.slice().sort(function(a, b){ return ((facets[b] || {}).y || 0) - ((facets[a] || {}).y || 0); }); }
  var closed = {}; try { closed = JSON.parse(LS("pv_fold_closed") || "{}"); } catch(e) {}
  var served = /^https?:$/.test(location.protocol);

  function walk(nodes, fn, parent){ nodes.forEach(function(n){ n.papers = n.papers || []; fn(n, parent, nodes); walk(n.children || (n.children = []), fn, n); }); }
  function find(id){ var hit = null; walk(tree, function(n, p, list){ if (n.id === id) hit = {node:n, list:list}; }); return hit; }
  function newId(){ return "f" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }
  function unassigned(){
    var seen = {}; walk(tree, function(n){ (n.papers || (n.papers = [])).forEach(function(s){ seen[s] = 1; }); });
    return Object.keys(cardOf).filter(function(s){ return !seen[s]; });
  }
  function count(n){ var k = (n.papers || []).filter(function(s){ return cardOf[s]; }).length; (n.children || []).forEach(function(c){ k += count(c); }); return k; }
  function contains(a, b){ if (a === b) return true; return (a.children || []).some(function(c){ return contains(c, b); }); }

  function setHint(msg, bad){ hint.textContent = msg || ""; hint.classList.toggle("bad", !!bad); }
  function save(){
    var body = JSON.stringify({version:1, favorites:favs, reading:reading, tree:tree}, null, 2);
    LS("pv_folders_local", body);
    if (!served) { setHint(T("只存在这个浏览器里。用 python serve.py 打开才会存进 folders.json。", "Saved in this browser only. Open with python serve.py to save to folders.json."), true); return; }
    fetch("api/folders", {method:"POST", headers:{"Content-Type":"application/json"}, body:body})
      .then(function(r){ if (!r.ok) throw r.status; LS("pv_folders_local", ""); setHint(T("已保存", "Saved")); })
      .catch(function(){ setHint(T("保存失败：本地服务没开？已先存在浏览器里。", "Save failed: is the local server running? Kept in this browser for now."), true); });
  }

  function row(id, name, n, depth, hasKids, node){
    var r = document.createElement("div");
    r.className = "folder" + (id === ALL && view === "content" ? " all" : "") + (id === FAV || id === READ ? " fav" : "") + (id === current && !query ? " on" : "");
    r.style.paddingLeft = (8 + depth * 16) + "px";
    r.setAttribute("data-id", id);
    var tw = document.createElement("span"); tw.className = "twist";
    tw.textContent = hasKids ? (closed[id] ? "▸" : "▾") : "";
    tw.addEventListener("click", function(e){ e.stopPropagation(); closed[id] = !closed[id]; LS("pv_fold_closed", JSON.stringify(closed)); paintTree(); });
    var nm = document.createElement("span"); nm.className = "fname"; nm.textContent = name;
    var ct = document.createElement("span"); ct.className = "fcount"; ct.textContent = n;
    r.appendChild(tw); r.appendChild(nm); r.appendChild(ct);
    if (editing && node) {
      [["＋", T("新建子分类", "New subfolder"), function(){ var s = prompt(T("子分类名称", "Subfolder name")); if (s && s.trim()) { node.children.push({id:newId(), name:s.trim(), papers:[], children:[]}); closed[node.id] = false; changed(); } }],
       ["✎", T("改名", "Rename"), function(){ var s = prompt(T("新名称", "New name"), node.name); if (s && s.trim()) { node.name = s.trim(); changed(); } }],
       ["✕", T("删除（论文和子分类并到上一级）", "Delete (papers and subfolders move up a level)"), function(){ removeNode(node); }]].forEach(function(b){
        var x = document.createElement("button"); x.className = "fop"; x.textContent = b[0]; x.title = b[1];
        x.addEventListener("click", function(e){ e.stopPropagation(); b[2](); });
        r.appendChild(x);
      });
      r.draggable = true;
      r.addEventListener("dragstart", function(e){ e.dataTransfer.setData("text/plain", "folder:" + id); });
    }
    r.addEventListener("click", function(){ open(id); window.scrollTo(0, 0); });
    r.addEventListener("dragover", function(e){ if (id !== NONE && id !== FAV && id !== READ) { e.preventDefault(); r.classList.add("drop"); } });
    r.addEventListener("dragleave", function(){ r.classList.remove("drop"); });
    r.addEventListener("drop", function(e){ e.preventDefault(); r.classList.remove("drop"); dropOn(id, e.dataTransfer.getData("text/plain")); });
    return r;
  }

  function removeNode(node){
    var hit = find(node.id); if (!hit) return;
    if (!confirm(T("删除分类「" + node.name + "」？里面的论文和子分类会并到上一级。", "Delete folder \"" + node.name + "\"? Its papers and subfolders move up a level."))) return;
    var parent = null; walk(tree, function(n){ if (n.children.indexOf(node) >= 0) parent = n; });
    var i = hit.list.indexOf(node);
    hit.list.splice.apply(hit.list, [i, 1].concat(node.children));
    if (parent) parent.papers = parent.papers.concat(node.papers);   // 顶层的论文变成「未归类」
    if (current === node.id) current = parent ? parent.id : ALL;
    changed();
  }

  function dropOn(id, data){
    if (!data) return;
    var kind = data.split(":")[0], val = data.slice(kind.length + 1);
    if (kind === "paper") {
      if (id === ALL) return;
      walk(tree, function(n){ n.papers = n.papers.filter(function(s){ return s !== val; }); });
      var t = find(id); if (t) t.node.papers.push(val);
      changed(); return;
    }
    if (kind === "folder") {
      var src = find(val); if (!src || val === id) return;
      var dst = id === ALL ? null : find(id);
      if (id !== ALL && (!dst || contains(src.node, dst.node))) return;   // 不能拖进自己的子分类
      src.list.splice(src.list.indexOf(src.node), 1);
      (dst ? dst.node.children : tree).push(src.node);
      if (dst) closed[dst.node.id] = false;
      changed();
    }
  }

  function paintTree(){
    treeBox.innerHTML = "";
    treeBox.appendChild(row(FAV, T("★ 收藏", "★ Starred"), favs.filter(function(s){ return cardOf[s]; }).length, 0, false, null));
    treeBox.appendChild(row(READ, T("◔ 正在读", "◔ Reading"), reading.filter(function(s){ return cardOf[s]; }).length, 0, false, null));
    if (VEN) {
      var seg = E("div", "fview");
      [["content", T("内容", "Topics")], ["venue", T("会议", "Venues")], ["author", T("作者", "Authors")]].forEach(function(o){
        var b = E("button", view === o[0] ? "on" : "", o[1]);
        b.addEventListener("click", function(){ setView(o[0]); });
        seg.appendChild(b);
      });
      treeBox.appendChild(seg);
    }
    if (view === "venue") {
      VEN.groups.forEach(function(g){
        var vs = VEN.venues.filter(function(v){ return v.group === g && papersOfVenue(v.key).length; })
          .sort(function(a, b){ return (b.score || 0) - (a.score || 0); });
        if (!vs.length) return;
        treeBox.appendChild(E("div", "fgroup", UI === "en" && VEN.groups_en ? (VEN.groups_en[g] || g) : g));
        vs.forEach(function(v){ treeBox.appendChild(row("v:" + v.key, X(v, "name") + (v.score ? "  ·  " + v.score + T(" 分", "/10") : ""), papersOfVenue(v.key).length, 0, false, null)); });
      });
    } else if (view === "author") {
      var ac = authorCounts(), names = Object.keys(ac).filter(function(a){ return ac[a] >= 2; });
      names.sort(function(a, b){ return ac[b] - ac[a] || a.localeCompare(b); });
      treeBox.appendChild(E("div", "fgroup", T("库里有 2 篇以上的作者", "Authors with 2+ papers here")));
      names.forEach(function(a){ treeBox.appendChild(row("a:" + a, a, ac[a], 0, false, null)); });
      treeBox.appendChild(E("div", "fhint", T("其余 " + (Object.keys(ac).length - names.length) + " 位作者只有 1 篇，可用右上角搜索。", (Object.keys(ac).length - names.length) + " more authors have 1 paper each; use search at the top right.")));
    } else {
      treeBox.appendChild(row(ALL, T("全部论文", "All papers"), Object.keys(cardOf).length, 0, false, null));
      (function draw(nodes, depth){
        nodes.forEach(function(n){
          treeBox.appendChild(row(n.id, n.name, count(n), depth, n.children.length > 0, n));
          if (!closed[n.id]) draw(n.children, depth + 1);
        });
      })(tree, 0);
      var loose = unassigned();
      if (loose.length) treeBox.appendChild(row(NONE, T("未归类", "Unfiled"), loose.length, 0, false, null));
    }
    if (VEN && VEN.friend_links && VEN.friend_links.length) {
      var fl = E("div", "flinks"); fl.appendChild(E("b", "", T("友情链接 · 找新论文", "Links · find new papers")));
      VEN.friend_links.forEach(function(l){ var a = E("a", "", X(l, "name")); a.href = l.url; a.target = "_blank"; a.rel = "noopener"; a.title = X(l, "note") || ""; fl.appendChild(a); });
      treeBox.appendChild(fl);
    }
    document.body.classList.toggle("fediting", editing);
    document.body.classList.remove("fview-content", "fview-venue", "fview-author");
    document.body.classList.add("fview-" + view);
  }

  function setView(v){
    if (v === view) return;
    lastOf[view] = current; view = v; LS("pv_view", v); LS("pv_view_last", JSON.stringify(lastOf));
    var go = lastOf[v];
    if (!go || go === FAV || go === READ) {
      if (v === "venue") go = "v:" + ((VEN.venues.filter(function(x){ return papersOfVenue(x.key).length; })[0] || {}).key);
      else if (v === "author") { var ac = authorCounts(); go = "a:" + Object.keys(ac).sort(function(a, b){ return ac[b] - ac[a]; })[0]; }
      else go = ALL;
    }
    open(go);
  }

  function venueCard(v, n){
    var c = E("div", "vcard");
    if (v.score) {
      var sc = E("div", "vscore"); sc.appendChild(E("b", "", String(v.score))); sc.appendChild(E("small", "", T(" / 10 综合评分", " / 10 overall")));
      if (VEN.score_note) sc.title = X(VEN, "score_note");
      c.appendChild(sc);
    }
    c.appendChild(E("div", "vfull", X(v, "full")));
    var tags = E("div", "vtags");
    [X(v, "kind"), X(v, "group")].concat(v.ccf ? ["CCF " + v.ccf] : []).concat(v.time ? [X(v, "time")] : []).forEach(function(t){
      tags.appendChild(E("span", t.indexOf("CCF") === 0 ? "ccf" : "", t));
    });
    tags.appendChild(E("span", "", T("库里 " + n + " 篇", n + " in library")));
    c.appendChild(tags);
    c.appendChild(E("h4", "", T("介绍", "About"))); c.appendChild(E("p", "", X(v, "intro")));
    if (v.influence) { c.appendChild(E("h4", "", T("分量与影响力", "Standing and influence"))); c.appendChild(E("p", "", X(v, "influence"))); }
    if (v.editions && v.editions.length) {
      c.appendChild(E("h4", "", T("时间地点", "When and where")));
      var t = E("table");
      v.editions.forEach(function(ed){ var tr = E("tr"); tr.appendChild(E("td", "", String(ed.year))); tr.appendChild(E("td", "", X(ed, "place"))); tr.appendChild(E("td", "", X(ed, "dates") || "")); t.appendChild(tr); });
      c.appendChild(t);
    }
    var LK = X(v, "links") || {}, links = Object.keys(LK);
    if (links.length) {
      var lk = E("div", "vlinks");
      links.forEach(function(k){ var a = E("a", "", k + " ↗"); a.href = LK[k]; a.target = "_blank"; a.rel = "noopener"; lk.appendChild(a); });
      c.appendChild(lk);
    }
    if (VEN.checked && v.editions && v.editions.length) c.appendChild(E("div", "fhint", T("时间地点核对于 " + VEN.checked + "，以官网为准。", "Dates checked on " + VEN.checked + "; the official site prevails.")));
    if (v.score && VEN.score_note) c.appendChild(E("div", "fhint", X(VEN, "score_note")));
    return c;
  }

  function authorCard(a, slugs){
    var c = E("div", "vcard"), co = {};
    slugs.forEach(function(s){ (facets[s].a || []).forEach(function(x){ if (x !== a) co[x] = (co[x] || 0) + 1; }); });
    var vs = {}; slugs.forEach(function(s){ var k = facets[s].v; if (k) vs[k] = (vs[k] || 0) + 1; });
    var tags = E("div", "vtags"); tags.appendChild(E("span", "", T("库里 " + slugs.length + " 篇", slugs.length + " in library")));
    Object.keys(vs).forEach(function(k){ tags.appendChild(E("span", "", X(venOf[k], "name") + " × " + vs[k])); });
    c.appendChild(tags);
    var top = Object.keys(co).sort(function(x, y){ return co[y] - co[x]; }).slice(0, 12);
    if (top.length) { c.appendChild(E("h4", "", T("库里的合作者", "Co-authors here"))); c.appendChild(E("p", "", top.join(T("、", ", ")))); }
    var lk = E("div", "vlinks"), q = encodeURIComponent(a);
    [["DBLP", "https://dblp.org/search?q=" + q], ["Google Scholar", "https://scholar.google.com/scholar?q=author%3A%22" + q + "%22"], ["Semantic Scholar", "https://www.semanticscholar.org/search?q=" + q]].forEach(function(x){
      var l = E("a", "", x[0] + " ↗"); l.href = x[1]; l.target = "_blank"; l.rel = "noopener"; lk.appendChild(l);
    });
    c.appendChild(lk);
    return c;
  }

  function putByYear(slugs){
    var last = null;
    byYear(slugs).forEach(function(s){
      var y = (facets[s] || {}).y || T("年份不详", "Year unknown");
      if (y !== last) { cardsBox.appendChild(E("h3", "subhead", String(y))); last = y; }
      cardsBox.appendChild(cardOf[s]);
    });
  }

  function open(id){
    id = id || ALL;
    if (/^v:/.test(id) && !(VEN && venOf[id.slice(2)])) id = ALL;
    if (/^a:/.test(id) && !(VEN && papersOfAuthor(id.slice(2)).length)) id = ALL;
    if (/^v:/.test(id)) view = "venue"; else if (/^a:/.test(id)) view = "author";
    else if (id !== FAV && id !== READ) view = "content";
    if (VEN) LS("pv_view", view);
    if (!/^[va]:/.test(id) && id !== ALL && id !== NONE && id !== FAV && id !== READ && !find(id)) id = tree.length ? tree[0].id : ALL;
    current = id; LS("pv_folder", id);
    if (query && searchBox) { query = ""; searchBox.value = ""; }
    Object.keys(cardOf).forEach(function(s){ pool.appendChild(cardOf[s]); });
    cardsBox.innerHTML = "";
    function put(slugs, box){ slugs.forEach(function(s){ if (cardOf[s]) box.appendChild(cardOf[s]); }); }
    function section(n, path){
      if (n.papers.some(function(s){ return cardOf[s]; }) && path) {
        var h = document.createElement("h3"); h.className = "subhead"; h.textContent = path;
        cardsBox.appendChild(h);
      }
      put(n.papers, cardsBox);
      n.children.forEach(function(c){ section(c, (path ? path + " / " : "") + c.name); });
    }
    if (id === FAV) { titleEl.textContent = T("★ 收藏", "★ Starred"); put(favs, cardsBox); }
    else if (id === READ) { titleEl.textContent = T("◔ 正在读", "◔ Reading"); put(reading, cardsBox); }
    else if (id === ALL) { titleEl.textContent = T("全部论文", "All papers"); tree.forEach(function(n){ section(n, n.name); }); put(unassigned(), cardsBox); }
    else if (id === NONE) { titleEl.textContent = T("未归类", "Unfiled"); put(unassigned(), cardsBox); }
    else if (/^v:/.test(id)) { var v = venOf[id.slice(2)], vs = papersOfVenue(v.key); titleEl.textContent = X(v, "name"); cardsBox.appendChild(venueCard(v, vs.length)); putByYear(vs); }
    else if (/^a:/.test(id)) { var an = id.slice(2), as = papersOfAuthor(an); titleEl.textContent = an; cardsBox.appendChild(authorCard(an, as)); putByYear(as); }
    else { var n = find(id).node; titleEl.textContent = n.name; section(n, ""); }
    if (!cardsBox.children.length) cardsBox.innerHTML = '<p class="fempty">' + (id === FAV ? T("还没有收藏。点论文标题右边的 ☆ 就能收藏。", "Nothing starred yet. Click ☆ next to a paper title.") : id === READ ? T("还没有在读的论文。点论文标题右边的「在读」就能加进来。", "Nothing in Reading yet. Click \"Reading\" next to a paper title.") : T("这个分类还没有论文。", "No papers in this folder yet.") + (editing ? T("把右边的论文拖到左边分类上即可移动。", " Drag a paper onto a folder to move it.") : "")) + "</p>";
    paintStars();
    paintTree();
  }

  function changed(){ save(); open(current); }

  // 拖论文 + 星标收藏（收藏不影响论文所在的分类）
  function paintStars(){
    Object.keys(cardOf).forEach(function(s){
      var b = cardOf[s].querySelector(".star"), on = favs.indexOf(s) >= 0;
      if (b) { b.textContent = on ? "★" : "☆"; b.classList.toggle("on", on); b.title = on ? T("取消收藏", "Unstar") : T("收藏", "Star"); }
      var r = cardOf[s].querySelector(".readtag"), rd = reading.indexOf(s) >= 0;
      if (r) { r.classList.toggle("on", rd); r.title = rd ? T("移出「正在读」", "Remove from Reading") : T("标为正在读", "Mark as reading"); r.textContent = T("在读", "Reading"); }
    });
  }
  Object.keys(cardOf).forEach(function(s){
    cardOf[s].addEventListener("dragstart", function(e){ e.dataTransfer.setData("text/plain", "paper:" + s); });
    var b = cardOf[s].querySelector(".star");
    if (b) b.addEventListener("click", function(e){
      e.stopPropagation();
      var i = favs.indexOf(s);
      if (i >= 0) favs.splice(i, 1); else favs.unshift(s);
      save();
      if (query) { paintStars(); paintTree(); } else open(current);
    });
    var r = cardOf[s].querySelector(".readtag");
    if (r) r.addEventListener("click", function(e){
      e.stopPropagation();
      var i = reading.indexOf(s);
      if (i >= 0) reading.splice(i, 1); else reading.unshift(s);
      save();
      if (query) { paintStars(); paintTree(); } else open(current);
    });
  });

  // 搜索：标题、作者、出处、编号、概述；多个词要同时命中。清空后回到原来的分类。
  var textOf = {};
  Object.keys(cardOf).forEach(function(s){ textOf[s] = (s + " " + cardOf[s].textContent).toLowerCase(); });
  function search(q){
    query = q.trim();
    if (!query) { open(current); return; }
    var terms = query.toLowerCase().split(/\s+/);
    var hits = Object.keys(cardOf).filter(function(s){ return terms.every(function(w){ return textOf[s].indexOf(w) >= 0; }); });
    Object.keys(cardOf).forEach(function(s){ pool.appendChild(cardOf[s]); });
    cardsBox.innerHTML = "";
    hits.forEach(function(s){ cardsBox.appendChild(cardOf[s]); });
    titleEl.textContent = T("搜索「" + query + "」· " + hits.length + " 篇", "Search \"" + query + "\" · " + hits.length);
    if (!hits.length) cardsBox.innerHTML = '<p class="fempty">' + T("没有找到。可以试试英文关键词、作者名或编号（如 L26）。", "Nothing found. Try English keywords, an author or an ID such as L26.") + '</p>';
    paintStars(); paintTree();
  }
  if (searchBox) {
    searchBox.addEventListener("input", function(){ search(searchBox.value); });
    searchBox.addEventListener("keydown", function(e){ if (e.key === "Escape") { searchBox.value = ""; search(""); searchBox.blur(); } });
    document.addEventListener("keydown", function(e){
      var tag = (document.activeElement || {}).tagName || "";
      if (e.key === "/" && !/INPUT|TEXTAREA/.test(tag)) { e.preventDefault(); searchBox.focus(); }
    });
  }
  document.getElementById("fEdit").addEventListener("click", function(e){
    editing = !editing; e.target.textContent = editing ? T("完成", "Done") : T("编辑", "Edit");
    if (editing) setHint(T("拖论文到分类上 = 移动；拖分类到分类上 = 变成子分类，拖到「全部论文」= 回顶层。", "Drag a paper onto a folder to move it; drag a folder onto another to nest it, onto All papers to move it to the top."));
    else setHint("");
    open(current);
  });
  document.getElementById("fAdd").addEventListener("click", function(){
    var s = prompt(T("新分类名称", "New folder name")); if (!s || !s.trim()) return;
    var n = {id:newId(), name:s.trim(), papers:[], children:[]}; tree.push(n); current = n.id; changed();
  });

  // 启动：优先读 folders.json（用 serve.py 打开时），其次是本浏览器里没存进文件的编辑，最后用生成时内嵌的树
  function start(d){
    if (d && Array.isArray(d.tree)) {
      tree = d.tree;
      favs = Array.isArray(d.favorites) ? d.favorites : [];
      reading = Array.isArray(d.reading) ? d.reading : [];
    }
    walk(tree, function(){}); open(current);
  }
  var local = null; try { local = JSON.parse(LS("pv_folders_local") || "null"); } catch(e) {}
  if (local && local.tree) { start(local); if (served) save(); }
  else if (served) fetch("folders.json", {cache:"no-store"}).then(function(r){ return r.ok ? r.json() : null; })
    .then(function(d){ start(d); }).catch(function(){ start(); });
  else start();
})();
"""

# ─────────────────────────────────────────────────────────────────────────────
# §6.4 L2/L3 行为（reader.js）
# ─────────────────────────────────────────────────────────────────────────────
READER_JS = r"""
/* paper-vault reader.js —— L2 翻页阅读器行为 */
(function(){
  // ── 界面语言（中 / EN）：存在 localStorage.pv_ui，切换后刷新页面 ──
  var UI = (function(){ try { return localStorage.getItem("pv_ui") === "en" ? "en" : "zh"; } catch(e) { return "zh"; } })();
  function T(zh, en){ return UI === "en" ? en : zh; }
  function X(o, k){ return UI === "en" && o && o[k + "_en"] != null ? o[k + "_en"] : (o || {})[k]; }   // 数据里的 *_en 字段
  document.documentElement.setAttribute("data-ui", UI);
  if (UI === "en") {
    document.documentElement.lang = "en";
    document.querySelectorAll("[data-en]").forEach(function(el){ el.textContent = el.getAttribute("data-en"); });
    document.querySelectorAll("[data-en-ph]").forEach(function(el){ el.placeholder = el.getAttribute("data-en-ph"); });
    document.querySelectorAll("[data-en-title]").forEach(function(el){ el.title = el.getAttribute("data-en-title"); });
    document.querySelectorAll(".pv-use-notice").forEach(function(n){
      var a = n.querySelector("a"), href = a ? a.getAttribute("href") : "";
      var full = !!n.querySelector("strong");
      n.innerHTML = (full ? "<div><strong>Personal study notice</strong> · " : "<span>") +
        "Personal study and research only · non-commercial · not for distribution" +
        (full ? "<p>Copyright in the papers, figures and other materials belongs to their authors and rights holders. Translations and notes are unofficial study aids; the original text prevails.</p></div>" : "</span>") +
        (href ? '<a href="' + href + '">Full statement</a>' : "");
    });
  }
  (function(){
    var host = document.querySelector(".libhead") || document.querySelector(".topbar");
    if (!host || document.getElementById("uiBtn")) return;
    var b = document.createElement("button");
    b.id = "uiBtn"; b.className = "iconbtn uibtn"; b.textContent = UI === "en" ? "中" : "EN";
    b.title = UI === "en" ? "切换到中文界面" : "Switch to English interface";
    b.addEventListener("click", function(){ try { localStorage.setItem("pv_ui", UI === "en" ? "zh" : "en"); } catch(e) {} location.reload(); });
    var theme = host.querySelector("#themeBtn");
    if (theme) host.insertBefore(b, theme); else host.appendChild(b);
  })();


  // 右下角「i」：打开本库的规划页 roadmap.html（以后要做的事）
  (function(href, bottom){
    if (document.getElementById("roadmap-i")) return;
    var a = document.createElement("a");
    a.id = "roadmap-i"; a.href = href; a.target = "_blank"; a.rel = "noopener"; a.title = T("以后要做的事", "Roadmap"); a.textContent = "i";
    a.style.cssText = "position:fixed;right:16px;bottom:" + bottom + "px;z-index:2147483000;width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#A62B26;color:#fff;text-decoration:none;font:italic 700 16px/1 Georgia,serif;box-shadow:0 2px 8px rgba(0,0,0,.25);opacity:.85";
    document.body.appendChild(a);
  })("../../roadmap.html", 44);
  // 标签页图标：已生成的阅读页没有 <link rel=icon>，这里补上
  if (!document.querySelector("link[rel=icon]")) {
    var ic = document.createElement("link"); ic.rel = "icon"; ic.type = "image/svg+xml"; ic.href = "../../assets/favicon.svg";
    document.head.appendChild(ic);
  }
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
    if (/INPUT|TEXTAREA|SELECT/.test((e.target || {}).tagName || "")) return;   // 在概括框里打字不翻页
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


  // ── 我的概括：理解模式每一节末尾一个框，鸟瞰「一句话结论」页先写再看 ──
  // 保存进 vault/notes.json；「提交并评分」由 serve.py 调本机 claude 打 1–10 分并点评。
  var served = /^https?:$/.test(location.protocol);
  var slugM = location.pathname.match(/papers\/([^\/]+)\//), SLUG = slugM ? decodeURIComponent(slugM[1]) : "";
  var NOTES = {};
  function E(tag, cls, text){ var x = document.createElement(tag); if (cls) x.className = cls; if (text != null) x.textContent = text; return x; }
  function sections(mk){
    // 一节分成多页时，目录标题带「(i/n)」；i > 1 的页接在上一节后面。顺序和 paper.json 的 sections 一致
    var out = [], last = null;
    (modes[mk] ? modes[mk].pages : []).forEach(function(pg){
      var raw = pg.getAttribute("data-toc-en") || "", m = raw.match(/\s*\((\d+)\/\d+\)$/);
      if (last && m && +m[1] > 1) { last.pages.push(pg); return; }
      last = {title: raw.replace(/\s*\(\d+\/\d+\)$/, ""), pages:[pg], idx:out.length}; out.push(last);
    });
    return out;
  }
  function renderResult(box, entry){
    var res = box.querySelector(".ms-res"); res.innerHTML = "";
    var r = entry && entry.result; if (!r) return;
    var head = E("div"); var sc = E("span", "ms-score", String(r.score)); sc.appendChild(E("small", "", " / 10"));
    head.appendChild(sc); head.appendChild(document.createTextNode(r.verdict || "")); res.appendChild(head);
    function list(title, items, fn){
      if (!items || !items.length) return;
      res.appendChild(E("h5", "", title)); var ul = E("ul");
      items.forEach(function(it){ var li = E("li"); fn(li, it); ul.appendChild(li); }); res.appendChild(ul);
    }
    list(T("✓ 说对了", "✓ Got right"), r.right, function(li, it){ li.textContent = it; });
    list(T("△ 漏掉的关键点", "△ Missed points"), r.missed, function(li, it){ li.appendChild(document.createTextNode(it.point || it)); if (it.quote) li.appendChild(E("q", "", it.quote)); });
    list(T("✗ 不对的地方", "✗ Not quite right"), r.wrong, function(li, it){ li.appendChild(document.createTextNode("「" + (it.claim || "") + "」 " + (it.why || ""))); });
    list(T("英文表达", "English wording"), r.english, function(li, it){ li.appendChild(document.createTextNode(it.original + " → " + it.better + (it.why ? "（" + it.why + "）" : ""))); });
    if (r.reference) { var d = E("details"); d.appendChild(E("summary", "", T("看参考概括", "Show a reference summary"))); d.appendChild(E("p", "", r.reference)); res.appendChild(d); }
  }
  function sumBox(mk, sec, opts){
    var key = mk + ":" + sec.idx, hist = ((NOTES[SLUG] || {})[key]) || [], last = hist[hist.length - 1];
    var wrap = E("div", "mysum-wrap"), tg = E("button", "ms-toggle");
    var box = E("div", "mysum"); box.hidden = true;
    function label(){
      var l = hist[hist.length - 1], r = l && l.result;
      tg.textContent = "✍ " + (l ? opts.head + (r ? " · " + r.score + "/10" : T(" · 已写", " · written")) : opts.btn);
    }
    label();
    tg.addEventListener("click", function(){ box.hidden = !box.hidden; tg.classList.toggle("on", !box.hidden); if (!box.hidden) ta.focus(); });
    wrap.appendChild(tg); wrap.appendChild(box);
    var h = E("div", "ms-head", opts.head); h.appendChild(E("span", "ms-sub", opts.sub)); box.appendChild(h);
    var ta = E("textarea"); ta.placeholder = opts.ph; if (last) ta.value = last.text; box.appendChild(ta);
    var bar = E("div", "ms-bar"), bj = E("button", "primary", T("提交并评分", "Submit for a score")), bs = E("button", "", T("只保存", "Save only")), st = E("span", "ms-st");
    bar.appendChild(bj); bar.appendChild(bs);
    var bc = E("button", "", T("收起", "Close")); bc.addEventListener("click", function(){ box.hidden = true; tg.classList.remove("on"); }); bar.appendChild(bc);
    bar.appendChild(st); box.appendChild(bar); box.appendChild(E("div", "ms-res"));
    if (hist.length) st.textContent = T("已写过 " + hist.length + " 次，最近 " + last.at, "Written " + hist.length + "×, last " + last.at);
    if (!served) { st.textContent = T("用 python serve.py 打开才能保存和评分", "Open with python serve.py to save and score"); bj.disabled = bs.disabled = true; }
    renderResult(box, last);
    function send(api){
      var text = ta.value.trim(); if (!text) { st.textContent = T("先写几句再提交", "Write something first"); return; }
      bj.disabled = bs.disabled = true; st.textContent = api === "judge" ? T("评分中，约 20–60 秒…", "Scoring, about 20–60 s…") : T("保存中…", "Saving…");
      fetch("../../api/" + api, {method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({slug:SLUG, mode:mk, sec:sec.idx, title:sec.title, text:text})})
        .then(function(r){ return r.json().then(function(d){ if (!r.ok) throw new Error(d.error || r.status); return d; }); })
        .then(function(d){
          (NOTES[SLUG] = NOTES[SLUG] || {})[key] = hist.concat([d.entry]); hist = NOTES[SLUG][key];
          st.textContent = (api === "judge" ? T("已评分", "Scored") : T("已保存", "Saved")) + " · " + d.entry.at;
          if (d.entry.result) renderResult(box, d.entry);
          label();
        })
        .catch(function(e){ st.textContent = T("失败：", "Failed: ") + e.message; })
        .then(function(){ bj.disabled = bs.disabled = false; });
    }
    bj.addEventListener("click", function(){ send("judge"); });
    bs.addEventListener("click", function(){ send("notes"); });
    return wrap;
  }
  function addSummaryBoxes(){
    if (!SLUG) return;
    sections("grasp").forEach(function(sec){
      var col = sec.pages[sec.pages.length - 1].querySelector(".col"); if (!col) return;
      col.appendChild(sumBox("grasp", sec, {btn:T("写这一节的概括", "Summarize this section"), head:T("我的概括", "My summary"), sub:T("用自己的话写：这一节在说什么、靠什么证据。中英文都行。", "In your own words: what this section says and what backs it up. Chinese or English."), ph:T("这一节说的是……", "This section says…")}));
    });
    sections("skim").forEach(function(sec){
      var pg = sec.pages[0]; if (!pg.classList.contains("page--conclusion")) return;
      pg.querySelector(".col").appendChild(sumBox("skim", sec, {btn:T("写我的一句话", "Write my one-liner"), head:T("我的一句话", "My one-liner"), sub:T("用一句话说：这篇论文解决了什么、靠什么、结果如何。", "One sentence: what the paper solves, how, and with what result."), ph:T("这篇论文……", "This paper…")}));
    });
  }

  // ── 划词收藏 → 雅言堂（serve.py 转发到 lang-coach 的 /api/collect）──
  var pick = null;
  function hidePick(){ if (pick) { pick.remove(); pick = null; } }
  function toast(msg){
    var t = E("div", "toast", msg); document.body.appendChild(t);
    setTimeout(function(){ t.remove(); }, 3500);
  }
  function sentenceOf(full, frag){
    var parts = full.match(/[^.!?。！？]+[.!?。！？]*["')\]]*\s*/g) || [full];
    for (var i = 0; i < parts.length; i++) if (parts[i].indexOf(frag) >= 0) return parts[i].trim();
    return full.trim().slice(0, 600);
  }
  function collect(kind, text, sentence){
    hidePick();
    var page = document.querySelector(".mode.active .page.active"), sec = page ? (page.getAttribute("data-toc-en") || "") : "";
    fetch("../../api/coach/collect", {method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({kind:kind, text:text, sentence:sentence,
        source:{app:"paper-vault", slug:SLUG, title:(document.querySelector(".tb-title") || {}).textContent || document.title, section:sec, url:location.href}})})
      .then(function(r){ return r.json().then(function(d){ if (!r.ok) throw new Error(d.error || r.status); return d; }); })
      .then(function(d){
        if (kind === "word") { var w = d.word || {}; toast(T("已收进雅言堂 · 学术英语：", "Saved to Calliope Hall · academic words: ") + (w.display || text) + (w.ipa ? "  /" + w.ipa.replace(/^\/|\/$/g, "") + "/" : "") + (w.zh ? "  " + w.zh : "")); }
        else toast(T("已收进雅言堂的难句本，打开雅言堂可看主干拆解。", "Saved to Calliope Hall's hard sentences; open it there for a breakdown."));
      })
      .catch(function(e){ toast(T("没收成：", "Not saved: ") + e.message); });
  }
  if (served) document.addEventListener("mouseup", function(e){
    if (e.target.closest && (e.target.closest(".pick") || e.target.closest(".mysum"))) return;
    setTimeout(function(){
      hidePick();
      var sel = window.getSelection(), text = sel ? sel.toString().replace(/\s+/g, " ").trim() : "";
      if (!text || text.length > 500 || !/[A-Za-z]/.test(text)) return;
      var node = sel.anchorNode && (sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentNode);
      var host = node && node.closest && node.closest(".page .en"); if (!host || node.closest(".mysum")) return;
      var rect = sel.getRangeAt(0).getBoundingClientRect(), words = text.split(" ").length;
      pick = E("div", "pick");
      var sentence = sentenceOf(host.textContent, text);
      if (words <= 4) { var bw = E("button", "", T("＋ 收藏词", "＋ Save word")); bw.addEventListener("click", function(){ collect("word", text, sentence); }); pick.appendChild(bw); }
      var bsn = E("button", "", T("＋ 收藏句", "＋ Save sentence")); bsn.addEventListener("click", function(){ collect("sentence", words > 4 ? text : sentence, sentence); }); pick.appendChild(bsn);
      document.body.appendChild(pick);
      pick.style.left = Math.max(8, Math.min(window.innerWidth - pick.offsetWidth - 8, rect.left + rect.width / 2 - pick.offsetWidth / 2)) + "px";
      pick.style.top = Math.max(8, rect.top - pick.offsetHeight - 8) + "px";
    }, 0);
  });
  document.addEventListener("scroll", hidePick, true);

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
  // 概括框：先读 notes.json（用 serve.py 打开时），再插框
  if (served) fetch("../../api/notes", {cache:"no-store"}).then(function(r){ return r.ok ? r.json() : null; })
    .then(function(d){ NOTES = (d && d.summaries) || {}; addSummaryBoxes(); }).catch(function(){ addSummaryBoxes(); });
  else addSummaryBoxes();
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
    mode_en = {"skim": "Skim", "grasp": "Grasp", "master": "Master"}
    modeseg = "".join(
        '<button data-mode="%s"%s data-en="%s">%s</button>' % (k, (" class=\"on\"" if i == 0 else ""), mode_en[k], lbl)
        for i, (k, lbl) in enumerate(mode_order) if k in modes
    )
    langseg = ('<button data-lang="both" class="on" data-en="Both">对照</button>'
               '<button data-lang="en" data-en="Original">原文</button>'
               '<button data-lang="zh" data-en="Chinese">中文</button>')

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
  <a class="home" href="../../index.html" title="返回潜研堂" data-en-title="Back to Lyceum Hall">📚</a>
  <span class="tb-title">%(title)s</span>
  <span class="tb-meta">%(tbmeta)s</span>
  %(urllink)s
  <span class="tb-spacer"></span>
  <span class="seg modeseg">%(modeseg)s</span>
  <span class="seg langseg">%(langseg)s</span>
  <button class="iconbtn" id="tocBtn" title="目录 (T)" data-en-title="Contents (T)">☰</button>
  <button class="iconbtn" id="cardBtn" title="卡片模式 (C)：折叠答案，先猜后翻" data-en-title="Card mode (C): hide answers, guess first" data-en="Q">卡</button>
  <button class="iconbtn" id="aMinus" title="缩小" data-en-title="Smaller">A−</button>
  <button class="iconbtn" id="aPlus" title="放大" data-en-title="Larger">A+</button>
  <button class="iconbtn" id="themeBtn" title="主题" data-en-title="Theme">◐</button>
  <button class="iconbtn" id="fullBtn" title="全屏 (F)" data-en-title="Full screen (F)">⤢</button>
</div>
<div id="progress"></div>
<nav class="toc"></nav>
<button class="toc-fab" id="tocFab" title="展开目录" data-en-title="Show contents">☰</button>
<div class="modewrap">%(modes)s</div>
<div class="nav">
  <button class="prev" title="上一页 (←)" data-en-title="Previous (←)">‹</button>
  <span class="pageno">1 / 1</span>
  <button class="next" title="下一页 (→)" data-en-title="Next (→)">›</button>
</div>
<div class="hint" data-en="← → page · 1/2/3 mode · L language · T contents · F full screen">← → 翻页 · 1/2/3 模式 · L 语言 · T 目录 · F 全屏</div>
<script src="%(reader)s"></script>
</body>
</html>""" % {
        "title": title, "fonts": GOOGLE_FONTS, "css": css_href,
        "tbmeta": tb_meta, "urllink": url_link,
        "modeseg": modeseg, "langseg": langseg,
        "modes": modes_html, "reader": reader_href,
    }


FOLDERS_FILE = "folders.json"


def default_tree(papers):
    """按 meta.category 生成一层分类树（第一次没有 folders.json 时用）。"""
    cats = {}
    for p in papers:
        c = (p["meta"].get("category") or "未分类").strip()
        cats.setdefault(c, []).append(p["slug"])
    return [{"id": "c%02d" % i, "name": c, "papers": cats[c], "children": []}
            for i, c in enumerate(sorted(cats), 1)]


def load_tree(vault, papers):
    """读 vault/folders.json（用户在首页编辑过的分类树）；没有就按 category 生成。"""
    f = Path(vault) / FOLDERS_FILE
    if f.exists():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data.get("tree"), list):
                return data["tree"]
        except Exception as e:
            print("  ! %s 解析失败，改用默认分类：%s" % (f, e), file=sys.stderr)
    return default_tree(papers)


def load_favorites(vault, key="favorites"):
    """folders.json 里的收藏（favorites）或正在读（reading）列表，都是 slug。"""
    try:
        fav = json.loads((Path(vault) / FOLDERS_FILE).read_text(encoding="utf-8")).get(key, [])
        return [s for s in fav if isinstance(s, str)]
    except Exception:
        return []


VENUES_FILE = "venues.json"


def load_venues(vault):
    """vault/venues.json：会议 / 期刊资料（介绍、分级、时间地点、链接）和友情链接。没有就返回 None。"""
    f = Path(vault) / VENUES_FILE
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    except Exception as e:
        print("  ! %s 解析失败，首页不显示会议：%s" % (f, e), file=sys.stderr)
        return None


def paper_facets(papers, venues):
    """每篇论文的会议（按 venues.json 里的 match 正则，先匹配先得）、年份、作者列表。"""
    out = {}
    rules = [(v["key"], re.compile(v["match"], re.I)) for v in (venues or {}).get("venues", []) if v.get("match")]
    for p in papers:
        m = p["meta"]
        src = m.get("source") or ""
        key = next((k for k, rx in rules if rx.search(src)), "")
        yr = re.search(r"\b(19|20)\d{2}\b", src)
        authors = [re.sub(r"\s*\(.*?\)\s*", "", a).strip() for a in re.split(r";|；", m.get("authors") or "")]
        out[p["slug"]] = {"v": key, "y": int(yr.group(0)) if yr else 0, "a": [a for a in authors if a]}
    # 同一人的不同写法（Reynold Xin / Reynold S. Xin）合并：去掉中间名缩写后相同就算一人，显示最长的写法
    canon = lambda a: " ".join(t for t in a.split() if not re.fullmatch(r"[A-Z]\.", t)).lower()
    best = {}
    for f in out.values():
        for a in f["a"]:
            k = canon(a)
            if len(a) > len(best.get(k, "")):
                best[k] = a
    for f in out.values():
        f["a"] = list(dict.fromkeys(best[canon(a)] for a in f["a"]))
    return out


def render_l1(papers, css_href, library_href, tree=None, favorites=None, reading=None, venues=None):
    # papers: list of dict {slug, meta}；tree: 分类树（见 load_tree），树和交互都由 library.js 渲染
    # venues: load_venues() 的结果；有它时左栏多出「会议」「作者」两种视图和友情链接
    if tree is None:
        tree = default_tree(papers)

    cards = ""
    for p in papers:
        m = p["meta"]
        href = "papers/%s/index.html" % p["slug"]
        pmeta = " · ".join([x for x in [esc(m.get("authors")), esc(m.get("source"))] if x])
        cards += ("""<div class="pcard" data-slug="%(slug)s" draggable="true">
  <div class="pcardtop">
    <span class="caret">▶</span>
    <div style="flex:1">
      <a class="ptitle" href="%(href)s">%(title)s</a>
      <div class="pmeta">%(pmeta)s</div>
    </div>
    <button class="readtag" title="标为正在读" data-en="Reading" data-en-title="Mark as reading">在读</button>
    <button class="star" title="收藏" data-en-title="Star">☆</button>
  </div>
  <div class="poverview">%(overview)s</div>
</div>""") % {
            "slug": esc(p["slug"]), "href": esc(href), "title": esc(m.get("title")),
            "pmeta": pmeta, "overview": esc(m.get("overview")),
        }
    tree_json = json.dumps({"tree": tree, "favorites": favorites or [], "reading": reading or [],
                            "venues": venues, "facets": paper_facets(papers, venues) if venues else {}},
                           ensure_ascii=False).replace("</", "<\\/")
    chips = ('<div class="fbar"><span class="ftitle" data-en="Library">分类</span>'
             '<button class="fbtn" id="fAdd" title="新建分类" data-en-title="New folder">＋</button>'
             '<button class="fbtn" id="fEdit" title="编辑分类树" data-en="Edit" data-en-title="Edit folders">编辑</button></div>'
             '<div id="ftree"></div><div class="fhint" id="fHint"></div>')
    groups_html = ('<h2 class="cathead" id="fTitle"></h2><div id="cards"></div>'
                   '<div id="pool" hidden>%s</div>'
                   '<script type="application/json" id="pv-folders">%s</script>') % (cards, tree_json)

    return """<!doctype html>
<html lang="zh" data-theme="warm">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>潜研堂 · Lyceum Hall</title>
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
<link rel="stylesheet" href="%(css)s">
</head>
<body class="l1">
<header class="libhead">
  <h1 class="libtitle" title="Lyceum Hall" data-en="Lyceum Hall" data-en-title="潜研堂">潜研堂</h1>
  <span class="libmotto" data-en="The sun's rays do not burn until brought to a focus.">心无旁骛，专心致志；沉潜往复，钩深致远</span>
  <span class="libcount" data-en="%(count)d papers · bilingual">%(count)d 篇 · 中英对照</span>
  <span class="spacer"></span>
  <input class="libsearch" id="q" type="search" placeholder="搜索论文、作者、编号（按 / ）" data-en-ph="Search papers, authors, IDs (press /)" autocomplete="off">
  <button class="iconbtn" id="themeBtn" title="主题">◐</button>
</header>
<div class="libwrap">
<nav class="folders" aria-label="分类">%(chips)s</nav>
<main class="lib">%(groups)s</main>
</div>
<footer class="libfoot"></footer>
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
    (assets / "favicon.svg").write_text(FAVICON_SVG, encoding="utf-8")

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

    l1 = render_l1(papers, "assets/app.css", "assets/library.js", load_tree(vault, papers),
                   load_favorites(vault), load_favorites(vault, "reading"), load_venues(vault))
    (vault / "index.html").write_text(l1, encoding="utf-8")
    # 本地服务：打开首页并把分类树的编辑保存回 folders.json
    serve_src = Path(__file__).with_name("serve.py")
    if serve_src.exists() and serve_src.resolve() != (vault / "serve.py").resolve():
        (vault / "serve.py").write_text(serve_src.read_text(encoding="utf-8"), encoding="utf-8")

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
    vault = Path(args.vault).expanduser().resolve()
    result = build(vault)
    # 对照缺失始终视为硬错误；--strict 下再跑三遍法质量门（validate.py），有不合格即退出码 1
    if result["pairing"]:
        sys.exit(1)
    if args.strict:
        import subprocess
        rc = subprocess.call([sys.executable, str(Path(__file__).with_name("validate.py")),
                              "--vault", str(vault), "--all"])
        if rc:
            sys.exit(1)


if __name__ == "__main__":
    main()
