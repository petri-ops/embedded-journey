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
  .side-title {
    font-size: 17px; font-weight: 700; color: #1a2b4a;
    padding: 0 10px 14px; border-bottom: 1px solid #eef1f6; margin-bottom: 12px;
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
  .footer { margin-top: 44px; font-size: 13px; color: #9aa3b2; text-align: center; }
  /* ===== 窄屏：侧栏折叠为顶部横条 ===== */
  @media (max-width: 820px) {
    body { display: block; }
    .sidebar {
      position: static; width: auto; height: auto; padding: 14px 16px 10px;
      border-right: none; border-bottom: 1px solid #e6eaf0;
    }
    .side-title { padding-bottom: 8px; margin-bottom: 8px; }
    .sidebar nav a { display: inline-block; margin: 0 6px 6px 0; padding: 6px 12px; }
    .side-foot { display: none; }
    .content { padding: 20px 16px 50px; }
  }
  @media print {
    .sidebar, .footer { display: none; }
    body { display: block; background: #fff; }
  }
</style>
</head>
<body>
<aside class="sidebar">
  <div class="side-title">ESP32 + MicroPython<br>学习课程</div>
  <nav>
{{NAV}}
  </nav>
  <div class="side-foot">单文件 · 无依赖 · 可直接分享</div>
</aside>
<main><div class="content">
{{CONTENT}}
<div class="footer">— ESP32 + MicroPython 学习课程 · 由 ZCode 陪伴生成 —</div>
</div></main>
</body>
</html>
"""


def extract_title(text: str) -> str:
    m = re.search(r"^# (.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


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

    # 站内 .md 链接改写为 .html
    html_body = re.sub(
        r'href="([^"]+?)\.md"',
        lambda m: 'href="' + m.group(1) + '.html"',
        html_body,
    )

    title = extract_title(text) or md_path.stem

    html = (
        TEMPLATE.replace("{{TITLE}}", title)
        .replace("{{NAV}}", build_nav(files, md_path))
        .replace("{{CONTENT}}", html_body)
    )

    out = md_path.with_suffix(".html")
    out.write_text(html, encoding="utf-8")
    print("生成:", out.name)
    return out


def main():
    course_dir = Path(__file__).parent
    files = sorted(course_dir.glob("*.md"))
    if not files:
        print("未找到 Markdown 文件")
        return
    print(f"课程目录: {course_dir}")
    for f in files:
        build_file(f, files)
    print(f"完成，共生成 {len(files)} 个 HTML 文件（单文件、无依赖、可直接分享）")


if __name__ == "__main__":
    main()
