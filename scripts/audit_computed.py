# -*- coding: utf-8 -*-
"""用 Playwright + 本机 Chromium 内核浏览器审计主题的实际配色。

不静态解析 CSS，而是让浏览器算完 computed style 再读——
层叠、!important、@import、继承全部由浏览器裁决，避免自己写正则猜。

用法:
    python audit_computed.py                       # 审计 Typora 目录里的 pure-black-soft
    python audit_computed.py --css themes/pure-black.css
    python audit_computed.py --browser chrome      # 默认 msedge

需要: pip install playwright
（用 channel="msedge"/"chrome" 复用系统浏览器，无需 playwright install）
"""
import argparse
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.normpath(os.path.join(HERE, '..', 'tests', 'full.html'))


def guess_themes_dir():
    import platform
    if os.name == 'nt':
        return os.path.join(os.environ.get('APPDATA', ''), 'Typora', 'themes')
    if platform.system() == 'Darwin':
        return os.path.expanduser('~/Library/Application Support/abnerworks.Typora/themes')
    return os.path.expanduser('~/.config/Typora/themes')


# 要审计的元素：选择器 -> 说明
TARGETS = [
    ('#write', '正文容器'),
    ('#write h1', 'H1'),
    ('#write h2', 'H2'),
    ('#write h3', 'H3'),
    ('#write h4', 'H4'),
    ('#write h5', 'H5'),
    ('#write h6', 'H6'),
    ('#write p', '段落'),
    ('#write strong', '加粗'),
    ('#write em', '斜体'),
    ('#write del', '删除线'),
    ('#write a', '链接'),
    ('#write mark', '高亮'),
    ('#write code', '行内代码'),
    ('#write kbd', '键盘键'),
    ('#write var', '变量'),
    ('#write blockquote', '引用'),
    ('#write th', '表头'),
    ('#write td', '单元格'),
    ('#write .md-fences', '代码块'),
    ('#write .cm-keyword', '代码-关键字'),
    ('#write .cm-string', '代码-字符串'),
    ('#write .cm-comment', '代码-注释'),
    ('#write .md-task-list-item', '任务列表项'),
    ('#write .md-alert-text-note', 'alert-NOTE'),
    ('#write .md-alert-text-important', 'alert-IMPORTANT'),
    ('#write .md-alert-text-warning', 'alert-WARNING'),
    ('#write .md-comment', '注释文字'),
    ('#write pre.md-meta-block', 'YAML 元信息'),
    ('#write hr', '分隔线'),
    ('#write ul li', '列表项'),
]

# 这些元素靠线条呈现，可见性要看线色 vs 页面底色，而不是文字色
LINE_ELEMS = {'分隔线'}

JS = """(sels) => {
  const out = [];
  for (const [sel, name] of sels) {
    const el = document.querySelector(sel);
    if (!el) { out.push([sel, name, null, null, null, null]); continue; }
    const cs = getComputedStyle(el);
    out.push([sel, name, cs.color, cs.backgroundColor,
              cs.borderColor, cs.borderTopWidth, cs.borderLeftColor, cs.borderLeftWidth]);
  }
  return out;
}"""

PAGE_BG = {'screen': (0, 0, 0, 1), 'print': (255, 255, 255, 1)}


def parse_rgb(s):
    """'rgb(1,2,3)' / 'rgba(1,2,3,0.5)' -> (r,g,b,a)；无法解析返回 None。"""
    if not s:
        return None
    s = s.strip()
    if not s.startswith('rgb'):
        return None
    body = s[s.index('(') + 1:s.index(')')].replace('/', ',').replace(' ', ',')
    parts = [x for x in body.split(',') if x]
    vals = []
    for n in parts[:4]:
        n = n.strip()
        if not n:
            continue
        if n.endswith('%'):
            vals.append(float(n[:-1]) / 100 * (255 if len(vals) < 3 else 1))
        else:
            try:
                vals.append(float(n))
            except ValueError:
                return None
    if len(vals) < 3:
        return None
    a = vals[3] if len(vals) >= 4 else 1.0
    return (int(round(vals[0])), int(round(vals[1])), int(round(vals[2])), a)


def lum(rgb):
    c = [x / 255 for x in rgb[:3]]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def cr(a, b):
    la, lb = lum(a), lum(b)
    la, lb = max(la, lb), min(la, lb)
    return (la + 0.05) / (lb + 0.05)


def run(media, css, browser):
    # 用 Path.as_uri() 而不是手工拼 file:///，否则 Linux 下会变成 file:////home/...
    css_url = Path(css).resolve().as_uri()
    html_url = Path(HTML).resolve().as_uri()
    with sync_playwright() as pw:
        br = pw.chromium.launch(channel=browser, headless=True)
        pg = br.new_page(viewport={'width': 1000, 'height': 1400})
        pg.emulate_media(media=media)
        pg.goto(html_url)
        # 把测试页的样式表指向待审计主题
        pg.evaluate("u => { document.querySelector('link[rel=stylesheet]').href = u; }", css_url)
        pg.wait_for_timeout(500)
        rows = pg.evaluate(JS, TARGETS)
        br.close()
    return rows


def report(media, rows):
    print('=' * 96)
    print('媒体: %-6s' % media)
    print('=' * 96)
    print('%-18s %-18s %-20s %s' % ('元素', '前景', '背景(合成后)', '对比度'))
    bad = []
    for sel, name, col, bg, bd, bw, blc, blw in rows:
        if col is None:
            print('%-18s %s' % (name, '<元素不存在>'))
            continue
        fg = parse_rgb(col)
        b = parse_rgb(bg)
        base = PAGE_BG[media]

        # 半透明背景：按 alpha 与页面底色合成。否则 rgba(255,255,255,0.08)
        # 会被误读成纯白，行内代码会被误报成 2:1。
        if b is None or b[3] < 0.98:
            a = 0.0 if b is None else b[3]
            src = base if b is None else b
            b = tuple(int(round(src[i] * a + base[i] * (1 - a))) for i in range(3)) + (1.0,)

        if name in LINE_ELEMS:
            # 分隔线有两种画法：屏幕用 background，打印用 border-top
            bw_px = float((bw or '0').replace('px', '') or 0)
            bdc = parse_rgb(bd)
            if bw_px > 0 and bdc is not None:
                line, how = bdc[:3], 'border-top %.0fpx' % bw_px
            else:
                line, how = b[:3], 'background'
            r = cr(line, base[:3])
            flag = '  <-- 线上几乎看不见' if r < 1.35 else ''
            if r < 1.35:
                bad.append((name, '#%02x%02x%02x' % line, r, 'line'))
            print('%-18s %-18s %-20s %6.2f:1  [%s]%s'
                  % (name, '（线色）', '#%02x%02x%02x' % line, r, how, flag))
            continue

        r = cr(fg[:3], b[:3])
        thr = 4.5 if media == 'screen' else 4.0
        flag = ''
        if r < thr:
            flag = '  <-- 对比不足'
            bad.append((name, '#%02x%02x%02x' % fg[:3], r, 'text'))
        print('%-18s %-18s %-20s %6.2f:1%s'
              % (name, '#%02x%02x%02x' % fg[:3], '#%02x%02x%02x' % b[:3], r, flag))
    print()
    print('告警:', len(bad))
    for n, c, r, kind in bad:
        print('   ! [%s] %s %s %.2f:1' % (kind, n, c, r))
    print()
    return len(bad)


def main():
    ap = argparse.ArgumentParser(description='审计 Typora 主题在屏幕与打印两种媒体下的配色对比度。')
    ap.add_argument('--css', default=os.path.join(guess_themes_dir(), 'pure-black-soft.css'),
                    help='待审计的 css 路径')
    ap.add_argument('--browser', default='msedge', choices=['msedge', 'chrome', 'chromium'],
                    help='用哪个浏览器内核，默认 msedge')
    ap.add_argument('--media', default='both', choices=['screen', 'print', 'both'])
    args = ap.parse_args()

    if not os.path.exists(args.css):
        sys.exit('找不到 %s' % args.css)
    print('审计目标:', args.css)

    total = 0
    medias = ('screen', 'print') if args.media == 'both' else (args.media,)
    for m in medias:
        total += report(m, run(m, args.css, args.browser))
    sys.exit(0 if total == 0 else 1)


if __name__ == '__main__':
    main()
