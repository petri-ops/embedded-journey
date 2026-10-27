# -*- coding: utf-8 -*-
"""课程文档构建器：把本目录的 Markdown 源文件生成为可分享的单文件 HTML。

用法（在本目录下运行）：
    python build_html.py

特点：
- 生成的 .html 无任何外部依赖（CSS 内嵌），双击即可在浏览器打开，适合直接分享
- 导航栏按「篇」分组（见 GROUPS；当前页高亮；窄屏自动折叠为顶部下拉）
- 首页 index.html 为按篇分区的门户卡片页，课程状态构建时从 00-课程总览.md 解析
- 自动把文档里的 .md 链接改写为 .html 链接
- 自动处理 <details> 折叠答案块
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
  .nav-group-title {
    margin: 16px 0 4px; padding: 0 12px;
    font-size: 12.5px; color: #9aa3b2; letter-spacing: 2px;
  }
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
  /* ===== 门户首页（按篇分区） ===== */
  .portal-sub { color: #9aa3b2; margin: -6px 0 10px; font-size: 15px; }
  .portal-section { margin: 34px 0; }
  .portal-section > h2 { margin-top: 0; }
  .portal-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 14px;
  }
  .portal-card {
    display: block; background: #fff; border: 1px solid #dfe4ec;
    border-radius: 12px; padding: 14px 16px; text-decoration: none;
    color: inherit; transition: border-color .15s, box-shadow .15s;
  }
  .portal-card:hover {
    border-color: #8aa4f0; box-shadow: 0 4px 14px rgba(26,43,74,.10);
    text-decoration: none;
  }
  .portal-card .t { font-weight: 600; color: #1a2b4a; font-size: 15.5px; }
  .portal-card .d { color: #6b7690; font-size: 13.5px; margin-top: 6px; line-height: 1.6; }
  .portal-card .s {
    display: inline-block; margin-top: 10px; font-size: 12.5px;
    padding: 2px 10px; border-radius: 999px;
    background: #eef1f6; color: #6b7690;
  }
  .portal-card .s.ok { background: #e7f6ec; color: #1d7a43; }
  .portal-card .s.wip { background: #fdf3e0; color: #a8681c; }
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
    .sidebar nav .nav-group-title { margin: 10px 12px 2px; padding: 0; }
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


# ===== 站点结构：按「篇」分组。新增课程或新开一篇时，改这里即可 =====
TOP_PAGE = "00-课程总览"  # 置顶入口，不归组
GROUPS = [
    ("课程篇", [
        "01-电子电路基础",
        "02-GPIO输入-按键与中断",
        "03-ADC与PWM进阶",
        "04-通信协议-UART-I2C-SPI",
        "05-MQTT与asyncio",
        "06-结业项目",
    ]),
    ("方向篇", ["07-产品形态与产品化路线"]),
    ("记录篇", ["成长档案"]),
    ("工具箱", ["词汇表", "配件清单"]),
]
# 门户首页卡片的静态一句话描述。进度状态不在这里维护——唯一事实源是 00-课程总览.md
CARD_DESC = {
    "00-课程总览": "课程表、学习日志、踩坑记录、常用命令——进度的唯一事实源",
    "01-电子电路基础": "欧姆定律、LED 限流、上拉电阻、分压器，实战翻车点复盘",
    "02-GPIO输入-按键与中断": "轮询 vs 中断、消抖、ISR 三纪律，按键+网页双通道控灯",
    "03-ADC与PWM进阶": "模拟量采集、滞回光控灯、舵机、蜂鸣器、步进电机",
    "04-通信协议-UART-I2C-SPI": "UART 回环、I2C 扫总线、OLED、SPI 彩屏、矩阵键盘",
    "05-MQTT与asyncio": "发布/订阅、公共 broker 安全、并发任务，跨互联网监控",
    "06-结业项目": "阶段 0 毕业考试，独立交付一个完整系统",
    "07-产品形态与产品化路线": "从开发板到工业级产品：形态谱系与成长路线落点",
    "成长档案": "概念追踪、提问日志、错题本、能力雷达——跨会话长期记忆",
    "词汇表": "中英对照领域术语速查，讲义术语可点击弹出解释",
    "配件清单": "进阶版套件 36 项清单与兼容矩阵",
}


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


def nav_link(by_stem: dict, stem: str, current, fixed_label: str = "") -> str:
    """生成单个导航链接；current 为 None 或不匹配时不高亮。"""
    f = by_stem[stem]
    label = fixed_label or (extract_title(f.read_text(encoding="utf-8")) or f.stem)
    active = ' class="active"' if current is not None and f == current else ""
    return f'    <a href="{stem}.html"{active}>{label}</a>'


def build_nav(files: list, current) -> str:
    """按「篇」分组生成导航栏 HTML：总览置顶 + GROUPS 分组 + 未登记文件兜底。"""
    by_stem = {f.stem: f for f in files}
    listed = {TOP_PAGE}
    for _, stems in GROUPS:
        listed.update(stems)

    items = [nav_link(by_stem, TOP_PAGE, current, "📚 课程总览")]
    for group, stems in GROUPS:
        missing = [s for s in stems if s not in by_stem]
        if missing:
            print(f"提醒: 「{group}」登记的文件不存在: {', '.join(missing)}")
        present = [s for s in stems if s in by_stem]
        if not present:
            continue
        items.append(f'    <div class="nav-group-title">{group}</div>')
        items.extend(nav_link(by_stem, s, current) for s in present)

    unlisted = [f.stem for f in files if f.stem not in listed]
    if unlisted:
        print("提醒: 以下文件未登记进 GROUPS，已自动归入「其他」组: " + ", ".join(unlisted))
        items.append('    <div class="nav-group-title">其他</div>')
        items.extend(nav_link(by_stem, s, current) for s in unlisted)
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


def parse_course_table(course_dir: Path) -> dict:
    """从 00-课程总览.md 的「课程路线」表解析课程状态与核心内容（唯一进度事实源）。

    返回 {课程文件stem: {stat: 状态文字, brief: 核心内容}}；表格缺失或格式变化时返回空，
    构建自动降级为无状态卡片，不阻塞。
    """
    try:
        text = (course_dir / "00-课程总览.md").read_text(encoding="utf-8")
    except OSError:
        return {}
    table = {}
    row = re.compile(
        r"^\|\s*(\d+)\s*\|\s*\[([^\]]+)\]\(([^)]+\.md)\)\s*\|"
        r"\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|",
        re.MULTILINE,
    )
    for m in row.finditer(text):
        table[Path(m.group(3)).stem] = {"stat": m.group(4), "brief": m.group(5)}
    return table


def status_class(stat: str) -> str:
    if stat.startswith("✅"):
        return "s ok"
    if stat.startswith("🚧"):
        return "s wip"
    return "s"


def build_index(course_dir: Path, files: list) -> None:
    """生成按篇分区的门户首页 index.html（课程卡片状态取自 00-课程总览.md）。"""
    by_stem = {f.stem: f for f in files}
    course_status = parse_course_table(course_dir)

    def card(stem: str, stat: str = "", desc: str = "") -> str:
        f = by_stem.get(stem)
        if not f:
            return ""
        title = extract_title(f.read_text(encoding="utf-8")) or f.stem
        badge = f'<span class="{status_class(stat)}">{stat}</span>' if stat else ""
        return (
            f'<a class="portal-card" href="{stem}.html">'
            f'<div class="t">{title}</div>'
            f'<div class="d">{desc}</div>'
            f'{badge}</a>'
        )

    blocks = []
    for group, stems in GROUPS:
        cards = []
        for stem in stems:
            if stem not in by_stem:
                continue
            if group == "课程篇":
                info = course_status.get(stem, {})
                cards.append(card(stem, stat=info.get("stat", ""),
                                  desc=info.get("brief") or CARD_DESC.get(stem, "")))
            else:
                cards.append(card(stem, desc=CARD_DESC.get(stem, "")))
        cards = [c for c in cards if c]
        if cards:
            blocks.append(
                f'<section class="portal-section">\n<h2>{group}</h2>\n'
                f'<div class="portal-grid">\n' + "\n".join(cards) + "\n</div>\n</section>"
            )

    content = (
        "<h1>ESP32 + MicroPython 学习课程</h1>\n"
        '<p class="portal-sub">讲义自学 → 实操验证 → 交作业批改 → 归档自动更新；'
        "进度只记录在课程总览。</p>\n" + "\n".join(blocks)
    )

    html = (
        TEMPLATE.replace("{{TITLE}}", "课程首页")
        .replace("{{NAV}}", build_nav(files, None))
        .replace("{{CONTENT}}", content)
        .replace("{{GLOSSARY_DATA}}", json.dumps(GLOSSARY, ensure_ascii=False))
    )
    (course_dir / "index.html").write_text(html, encoding="utf-8")
    print("生成: index.html（门户首页，按篇分区）")


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
    build_index(course_dir, files)
    print(f"完成，共生成 {len(files)} 个课程页 + 门户首页（单文件、无依赖、可直接分享）")


if __name__ == "__main__":
    main()
