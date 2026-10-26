# -*- coding: utf-8 -*-
"""课程文档构建器：把本目录的 Markdown 源文件生成为可分享的单文件 HTML。

用法（在本目录下运行）：
    python build_html.py

特点：
- 生成的 .html 无任何外部依赖（CSS 内嵌），双击即可在浏览器打开，适合直接分享
- 自动生成左侧课程导航栏（当前页高亮；窄屏自动折叠为顶部横条）
- 自动把文档里的 .md 链接改写为 .html 链接
- 自动处理 <details> 折叠答案块
- 新增课程 .md 文件后重新运行，导航栏自动收录
"""
import json
import re
from pathlib import Path

import markdown

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{TITLE}}</title>
<style>
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
    color: #2c3e50; background: #fafbfc; line-height: 1.75;
    margin: 0; display: flex; min-height: 100vh; font-size: 16px;
  }
  /* ===== 左侧导航栏 ===== */
  .sidebar {
    width: 252px; flex-shrink: 0; position: sticky; top: 0;
    height: 100vh; overflow-y: auto;
    background: #ffffff; border-right: 1px solid #e6eaf0;
    padding: 22px 14px 18px;
  }
  .side-bar { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
  .nav-toggle {
    display: inline-block; flex-shrink: 0;
    font-size: 13.5px; color: #3a5bd9; background: #f0f5ff;
    border: 1px solid #cfd9f5; border-radius: 8px;
    padding: 6px 12px; cursor: pointer;
  }
  .nav-toggle:hover { background: #e2eafc; }
  .nav-float {
    display: none; position: fixed; top: 12px; left: 12px; z-index: 200;
    font-size: 13.5px; color: #3a5bd9; background: #fff;
    border: 1px solid #cfd9f5; border-radius: 8px;
    padding: 6px 12px; cursor: pointer; box-shadow: 0 2px 8px rgba(26,43,74,.14);
  }
  @media (min-width: 821px) {
    body.nav-collapsed .sidebar { display: none; }
    body.nav-collapsed .nav-float { display: inline-block; }
  }
  .sidebar nav a {
    display: block; padding: 9px 12px; margin-bottom: 3px;
    border-radius: 8px; color: #45506b; text-decoration: none; font-size: 14.5px;
  }
  .sidebar nav a:hover { background: #f0f5ff; color: #3a5bd9; }
  .sidebar nav a.active { background: #5a7dee; color: #fff; font-weight: 600; }
  .side-foot {
    margin-top: 18px; padding: 10px 12px 0; border-top: 1px solid #eef1f6;
    font-size: 12px; color: #9aa3b2;
  }
  /* ===== 主内容区 ===== */
  main { flex: 1; min-width: 0; }
  .content { max-width: 880px; margin: 0 auto; padding: 30px 30px 60px; }
  h1 {
    font-size: 30px; color: #1a2b4a; margin: 10px 0 18px;
    padding-bottom: 12px; border-bottom: 3px solid #5a7dee;
  }
  h2 {
    font-size: 22px; color: #1a2b4a; margin-top: 38px;
    padding-left: 10px; border-left: 4px solid #5a7dee;
  }
  h3 { font-size: 18px; color: #2c3e50; margin-top: 26px; }
  code {
    font-family: Consolas, "Courier New", monospace;
    background: #eef1f6; color: #c7254e;
    padding: 2px 6px; border-radius: 4px; font-size: 0.9em;
  }
  pre {
    background: #282c34; border-radius: 10px; padding: 16px 18px;
    overflow-x: auto; line-height: 1.5; margin: 14px 0;
  }
  pre code {
    background: none; color: #abb2bf; padding: 0;
    font-size: 14px; border-radius: 0;
  }
  table { border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 15px; }
  th, td { border: 1px solid #dfe4ec; padding: 8px 12px; text-align: left; }
  th { background: #eef2fa; color: #1a2b4a; }
  tr:nth-child(even) td { background: #f5f7fb; }
  blockquote {
    margin: 14px 0; padding: 10px 16px; background: #f0f5ff;
    border-left: 4px solid #8aa4f0; color: #45506b; border-radius: 0 8px 8px 0;
  }
  details {
    margin: 14px 0; border: 1px solid #dfe4ec; border-radius: 10px;
    padding: 12px 16px; background: #fff;
  }
  summary { cursor: pointer; font-weight: bold; color: #5a7dee; }
  details[open] { border-color: #8aa4f0; }
  hr { border: none; border-top: 1px dashed #cfd6e2; margin: 30px 0; }
  a { color: #5a7dee; }
  /* ===== 术语悬浮解释 ===== */
  .gloss { border-bottom: 1px dashed #5a7dee; cursor: help; }
  .gloss:hover { background: #f0f5ff; }
  .gloss-pop {
    position: fixed; z-index: 999; max-width: 340px;
    background: #fff; border: 1px solid #cfd6e2; border-radius: 10px;
    box-shadow: 0 8px 24px rgba(26,43,74,.18); padding: 12px 14px;
    font-size: 14px; line-height: 1.7; color: #2c3e50;
  }
  .gloss-pop .t { font-weight: 700; color: #1a2b4a; margin-bottom: 4px; }
  .gloss-pop .more { display: block; margin-top: 8px; font-size: 12.5px; }
  .footer { margin-top: 44px; font-size: 13px; color: #9aa3b2; text-align: center; }
  /* ===== 窄屏：导航折叠为顶栏，点开下拉目录 ===== */
  @media (max-width: 820px) {
    body { display: block; }
    .sidebar {
      position: sticky; top: 0; z-index: 100;
      width: auto; height: auto; overflow: visible; padding: 10px 14px;
      border-right: none; border-bottom: 1px solid #e6eaf0;
      box-shadow: 0 1px 6px rgba(26,43,74,.06);
    }
    .side-bar { align-items: center; }
    .nav-toggle { display: inline-block; }
    .sidebar nav {
      display: none; position: absolute; left: 0; right: 0; top: 100%;
      background: #fff; border-bottom: 1px solid #e6eaf0;
      padding: 8px 12px; box-shadow: 0 10px 18px rgba(26,43,74,.14);
    }
    .sidebar nav.open { display: block; }
    .sidebar nav a { display: block; margin: 2px 0; padding: 10px 12px; }
    .side-foot { display: none; }
    .content { padding: 20px 16px 50px; }
    h1 { font-size: 24px; }
    table { display: block; overflow-x: auto; }
  }
  @media print {
    .sidebar, .footer { display: none; }
    body { display: block; background: #fff; }
  }
</style>
</head>
<body>
<button class="nav-float" id="navFloat" type="button" aria-label="显示目录">☰ 目录</button>
<aside class="sidebar">
  <div class="side-bar">
    <button class="nav-toggle" id="navToggle" type="button" aria-label="展开或收起目录">☰ 目录</button>
  </div>
  <nav id="courseNav">
{{NAV}}
  </nav>
  <div class="side-foot">单文件 · 无依赖 · 可直接分享</div>
</aside>
<main><div class="content">
{{CONTENT}}
<div class="footer">— ESP32 + MicroPython 学习课程 —</div>
</div></main>
<script>
(function () {
  var G = {{GLOSSARY_DATA}};
  var pop = null;
  function close() { if (pop) { pop.remove(); pop = null; } }
  function show(el) {
    close();
    var d = G[el.getAttribute('data-term')];
    if (!d) return;
    pop = document.createElement('div');
    pop.className = 'gloss-pop';
    pop.innerHTML = '<div class="t">' + d.t + '</div>' + d.d +
      '<a class="more" href="词汇表.html">查看完整词汇表 →</a>';
    document.body.appendChild(pop);
    var r = el.getBoundingClientRect();
    var top = r.bottom + 8;
    var left = Math.min(r.left, window.innerWidth - pop.offsetWidth - 12);
    if (top + pop.offsetHeight > window.innerHeight - 12) {
      top = Math.max(12, r.top - pop.offsetHeight - 8);
    }
    pop.style.top = top + 'px';
    pop.style.left = Math.max(12, left) + 'px';
  }
  document.addEventListener('click', function (e) {
    var el = e.target.closest ? e.target.closest('.gloss') : null;
    if (el) { e.preventDefault(); show(el); return; }
    if (pop && !pop.contains(e.target)) close();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') close();
  });
})();
(function () {
  var btn = document.getElementById('navToggle');
  var nav = document.getElementById('courseNav');
  var float = document.getElementById('navFloat');
  var mq = window.matchMedia('(max-width: 820px)');
  function store(v) {
    try { v ? localStorage.setItem('navCollapsed', '1') : localStorage.removeItem('navCollapsed'); } catch (err) {}
  }
  function collapse() { document.body.classList.add('nav-collapsed'); store(true); }
  function expand() { document.body.classList.remove('nav-collapsed'); store(false); }
  if (btn && nav) {
    btn.addEventListener('click', function () {
      if (mq.matches) { nav.classList.toggle('open'); } else { collapse(); }
    });
  }
  if (float) float.addEventListener('click', expand);
  try {
    if (localStorage.getItem('navCollapsed') === '1' && !mq.matches) {
      document.body.classList.add('nav-collapsed');
    }
  } catch (err) {}
  document.addEventListener('click', function (e) {
    if (mq.matches && nav.classList.contains('open') && !nav.contains(e.target) && !btn.contains(e.target)) {
      nav.classList.remove('open');
    }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') nav.classList.remove('open');
  });
})();
</script>
</body>
</html>
"""


def extract_title(text: str) -> str:
    m = re.search(r"^# (.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def load_glossary(course_dir: Path) -> dict:
    """从 词汇表.md 解析词条：id -> {t: 术语名, d: 解释}，供悬浮解释使用。"""
    path = course_dir / "词汇表.md"
    glossary = {}
    if not path.exists():
        return glossary
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r'^- <a id="([^"]+)"></a>\*\*(.+?)\*\* —— (.+)$', line.strip())
        if m:
            glossary[m.group(1)] = {"t": m.group(2), "d": m.group(3)}
    return glossary


def build_nav(files: list, current: Path) -> str:
    """由课程文件列表生成导航栏 HTML，当前页高亮。"""
    items = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        # 总览页标题与侧栏大标题重复，改用固定短标签
        label = "📚 课程总览" if f.stem.startswith("00") else (extract_title(text) or f.stem)
        active = " class=\"active\"" if f == current else ""
        items.append(f'    <a href="{f.stem}.html"{active}>{label}</a>')
    return "\n".join(items)


def build_file(md_path: Path, files: list) -> Path:
    text = md_path.read_text(encoding="utf-8")

    # 让 <details> 内的 Markdown 也被渲染
    text = text.replace("<details>", '<details markdown="1">')

    html_body = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "md_in_html", "sane_lists"],
    )

    # 站内 .md 链接改写为 .html（保留 #锚点）
    html_body = re.sub(
        r'href="([^"]+?)\.md(#[^"]*)?"',
        lambda m: 'href="' + m.group(1) + '.html' + (m.group(2) or '') + '"',
        html_body,
    )

    # 词汇表锚点链接 → 可点击的悬浮解释术语（GLOSSARY 由 main 注入）
    html_body = re.sub(
        r'<a href="词汇表\.html#([^"]+)">(.*?)</a>',
        lambda m: '<span class="gloss" data-term="%s">%s</span>'
        % (m.group(1), m.group(2)),
        html_body,
    )

    title = extract_title(text) or md_path.stem

    html = (
        TEMPLATE.replace("{{TITLE}}", title)
        .replace("{{NAV}}", build_nav(files, md_path))
        .replace("{{CONTENT}}", html_body)
        .replace("{{GLOSSARY_DATA}}", json.dumps(GLOSSARY, ensure_ascii=False))
    )

    out = md_path.with_suffix(".html")
    out.write_text(html, encoding="utf-8")
    print("生成:", out.name)
    return out


def main():
    global GLOSSARY
    course_dir = Path(__file__).parent
    GLOSSARY = load_glossary(course_dir)
    files = sorted(course_dir.glob("*.md"))
    if not files:
        print("未找到 Markdown 文件")
        return
    print(f"课程目录: {course_dir}  词汇表词条: {len(GLOSSARY)}")
    for f in files:
        build_file(f, files)
    # GitHub Pages 首页：用第一个页面（课程总览）作为 index.html
    first_html = files[0].with_suffix(".html")
    if first_html.exists():
        (course_dir / "index.html").write_text(
            first_html.read_text(encoding="utf-8"), encoding="utf-8"
        )
        print("生成: index.html（站点首页）")
    print(f"完成，共生成 {len(files)} 个 HTML 文件（单文件、无依赖、可直接分享）")


if __name__ == "__main__":
    main()
