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
from theme_dependencies import check_imports

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
    ('#write b', '加粗-b'),
    ('#write i', '斜体-i'),
    ('#write sup.md-footnote', '脚注'),
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
    ('#write .cm-number', '代码-数字'),
    ('#write .cm-tag', '代码-标签'),
    ('#write .cm-attribute', '代码-属性'),
    ('#write .cm-def', '代码-定义'),
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
  // Browser canvas defaults to white; transparent ancestors are composited in order.
  const rgba = value => {
    const m = value.match(/^rgba?\\(([^)]+)\\)$/);
    if (!m) throw new Error('Unsupported color: ' + value);
    const v = m[1].split(',').map(Number);
    return [v[0], v[1], v[2], v.length > 3 ? v[3] : 1];
  };
  const over = (src, dst) => src.slice(0, 3).map((v, i) =>
    v * src[3] + dst[i] * (1 - src[3]));
  const background = el => {
    const chain = [];
    for (let node = el; node; node = node.parentElement) chain.unshift(node);
    return chain.reduce((bg, node) => over(rgba(getComputedStyle(node).backgroundColor), bg), [255,255,255]);
  };
  for (const [sel, name] of sels) {
    const elements = [...document.querySelectorAll(sel)];
    if (!elements.length) { out.push({sel, name, missing: true}); continue; }
    elements.forEach((el, index) => {
      const cs = getComputedStyle(el);
      const bg = background(el);
      out.push({sel, name, index, fg: over(rgba(cs.color), bg), bg,
        parentBg: background(el.parentElement),
        line: parseFloat(cs.borderTopWidth) > 0 && cs.borderTopStyle !== 'none'
          ? over(rgba(cs.borderTopColor), bg) : bg});
    });
  }
  return out;
}"""


def lum(rgb):
    c = [x / 255 for x in rgb[:3]]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def cr(a, b):
    la, lb = lum(a), lum(b)
    la, lb = max(la, lb), min(la, lb)
    return (la + 0.05) / (lb + 0.05)


def run(media, css, browser, allow_missing_night=False):
    missing, skipped = check_imports(css, allow_missing_night)
    if missing:
        raise ValueError('Missing CSS imports: ' + ', '.join(missing))
    if skipped:
        print('PARTIAL: missing Typora dependencies; token styles are not fully verified:')
        print('\n'.join(skipped))
    with sync_playwright() as pw:
        br = pw.chromium.launch(channel=None if browser == 'chromium' else browser, headless=True)
        try:
            pg = br.new_page(viewport={'width': 1000, 'height': 1400})
            pg.emulate_media(media=media)
            pg.goto(Path(HTML).resolve().as_uri())
            pg.add_style_tag(content='*, *::before, *::after { transition: none !important; animation: none !important; }')
            # Wait for actual load/error instead of a fixed delay.
            pg.evaluate("""({url, partial}) => new Promise((resolve, reject) => {
              const link = document.querySelector('link[rel=stylesheet]');
              const timer = setTimeout(() => reject(new Error('Stylesheet load timed out: ' + url)), 10000);
              link.onload = () => { clearTimeout(timer); resolve(); };
              link.onerror = () => {
                clearTimeout(timer);
                // Missing imports also fire error on the parent stylesheet.
                if (partial && link.sheet) resolve();
                else reject(new Error('Stylesheet failed: ' + url));
              };
              link.href = url;
            })""", {'url': Path(css).resolve().as_uri(), 'partial': bool(skipped)})
            pg.evaluate('() => document.fonts.ready')
            return pg.evaluate(JS, TARGETS)
        finally:
            br.close()


def report(media, rows):
    print('Media:', media)
    bad = 0
    for row in rows:
        label = row['name'] + ' [' + str(row.get('index', 0) + 1) + ']'
        if row.get('missing'):
            print('FAIL', label, 'required element missing')
            bad += 1
            continue
        is_line = row['name'] in LINE_ELEMS
        fg = row['line'] if is_line else row['fg']
        bg = row['parentBg'] if is_line else row['bg']
        ratio = cr(fg, bg)
        threshold = 1.35 if is_line else 4.5
        failed = ratio < threshold
        print('%s %-24s %.2f:1' % ('FAIL' if failed else 'OK  ', label, ratio))
        bad += int(failed)
    print('Failures:', bad)
    return bad


def main():
    ap = argparse.ArgumentParser(description='审计 Typora 主题在屏幕与打印两种媒体下的配色对比度。')
    ap.add_argument('--css', default=os.path.join(guess_themes_dir(), 'pure-black-soft.css'),
                    help='待审计的 css 路径')
    ap.add_argument('--browser', default='msedge', choices=['msedge', 'chrome', 'chromium'],
                    help='用哪个浏览器内核，默认 msedge')
    ap.add_argument('--media', default='both', choices=['screen', 'print', 'both'])
    ap.add_argument('--allow-missing-night', action='store_true',
                    help='部分检查：允许缺少 Typora 内置依赖，不能代表完整验证')
    args = ap.parse_args()

    if not os.path.exists(args.css):
        sys.exit('找不到 %s' % args.css)
    print('审计目标:', args.css)

    total = 0
    medias = ('screen', 'print') if args.media == 'both' else (args.media,)
    for m in medias:
        total += report(m, run(m, args.css, args.browser, args.allow_missing_night))
    sys.exit(0 if total == 0 else 1)


if __name__ == '__main__':
    main()
