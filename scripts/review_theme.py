# -*- coding: utf-8 -*-
"""静态审查主题文件：结构完整性 + 漏改的命名色 / 灰色面。

和 audit_computed.py 互补——
  audit_computed  看「浏览器算出来的最终颜色」，管渲染正确性；
  本脚本          看「文件里还剩什么」，管有没有漏改的灰面、命名色、断掉的 @import。

用法:
    python review_theme.py                        # 默认审查 Typora 目录里的 pure-black-soft
    python review_theme.py --css themes/pure-black.css
"""
import argparse
import os
import re
import sys
from theme_dependencies import check_imports, imports

# 这些命名色是 hex 映射的盲区，纯黑主题正文里出现基本等于漏改
NAMED_DANGER = ['white', 'gray', 'grey', 'silver', 'lightgray', 'lightgrey',
                'darkgray', 'darkgrey', 'gainsboro', 'whitesmoke']

# 正文类标签：这些选择器上用浅命名色会直接伤到可读性
TEXT_TAGS = ('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'td', 'th',
             'blockquote', 'em', 'strong', 'b', 'i', 'dt', 'dd', 'figcaption')


def guess_themes_dir():
    import platform
    if os.name == 'nt':
        return os.path.join(os.environ.get('APPDATA', ''), 'Typora', 'themes')
    if platform.system() == 'Darwin':
        return os.path.expanduser('~/Library/Application Support/abnerworks.Typora/themes')
    return os.path.expanduser('~/.config/Typora/themes')


def lum(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def media_spans(src):
    """标出所有 @media 块的字符区间，用于把打印规则排除在屏幕检查之外。"""
    spans = []
    for m in re.finditer(r'@media[^{]*\{', src):
        start = m.end() - 1
        depth, i = 0, start
        while i < len(src):
            if src[i] == '{':
                depth += 1
            elif src[i] == '}':
                depth -= 1
                if depth == 0:
                    spans.append((start, i))
                    break
            i += 1
    return spans


def in_spans(pos, spans):
    return any(a <= pos <= b for a, b in spans)


def is_text_selector(sel):
    """判断选择器是否作用于正文（而非按钮、菜单这类 UI 元素）。

    先排除 UI 关键字——像 `.megamenu-menu-panel tbody td` 虽然含 td，
    但它是设置菜单里的表格，不是正文。
    """
    ui_hints = ('megamenu', 'menu', 'btn', 'modal', 'sidebar', 'dropdown', 'ty-',
                'md-', 'file-', 'outline', 'preferences', 'search', 'quick-open',
                'nav-', 'footer', 'tooltip', 'popover', 'panel', 'toc', 'gutter',
                'code-tooltip', 'input-group')
    low = sel.lower()
    if any(h in low for h in ui_hints):
        return False
    for tag in TEXT_TAGS:
        if re.search(r'(^|[\s,>+~(])' + tag + r'($|[\s,.:#\[>+{~])', sel):
            return True
    return False


def main():
    ap = argparse.ArgumentParser(description='静态审查 Typora 主题文件。')
    ap.add_argument('--css', default=os.path.join(guess_themes_dir(), 'pure-black-soft.css'))
    ap.add_argument('--allow-missing-night', action='store_true',
                    help='仅部分检查：允许缺少 Typora 内置依赖')
    args = ap.parse_args()

    path = args.css
    if not os.path.exists(path):
        sys.exit('找不到 %s' % path)

    with open(path, encoding='utf-8') as stream:
        src = stream.read()
    print('审查文件: %s (%.1f KB)' % (os.path.basename(path), len(src.encode('utf-8')) / 1024))
    print()

    problems = 0
    mspans = media_spans(src)

    # 1. 结构
    print('[结构]')
    ok_brace = src.count('{') == src.count('}')
    print('  大括号平衡   : %s (%d/%d)' % ('OK' if ok_brace else 'FAIL', src.count('{'), src.count('}')))
    problems += 0 if ok_brace else 1
    crlf = '\r' in src
    print('  CRLF 混入    : %s' % ('有' if crlf else '无'))
    problems += 1 if crlf else 0

    # 2. @import
    print('[@import]')
    missing, skipped = check_imports(path, args.allow_missing_night)
    for dependency in missing:
        print('  FAIL missing:', dependency)
    for dependency in skipped:
        print('  PARTIAL unchecked Typora dependency:', dependency)
    problems += len(missing)

    uncommented = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    first_rule = uncommented.find('{')
    if [m.start() for m in re.finditer(r'@import', uncommented) if m.start() > first_rule]:
        print('  ! 有 @import 位于规则之后，浏览器会忽略')
        problems += 1

    # 3. 命名色：只关心正文标签上的浅命名色；UI 上的 white 是有意的
    print('[命名色残留]')
    found_named = False
    for sel, body, pos in [(m.group(1), m.group(2), m.start())
                           for m in re.finditer(r'([^{}]+)\{([^{}]*)\}', src)]:
        if in_spans(pos, mspans):
            continue
        color = re.search(r'(?<![-\w])color\s*:\s*([^;]+)', body)
        if not color:
            continue
        for name in NAMED_DANGER:
            if re.search(r'(?<![\w#-])' + name + r'(?![\w-])', color.group(1), re.I):
                sel_clean = ' '.join(sel.split())[-46:]
                if is_text_selector(sel_clean):
                    print('  ! %-10s 正文选择器  %s' % (name, sel_clean))
                    problems += 1
                    found_named = True
                else:
                    print('  · %-10s UI 选择器，保留  %s' % (name, sel_clean))
                break
    if not found_named:
        print('  正文无残留（UI 上的 white 属有意保留）')

    # 4. 中灰背景：只取 background / background-color 的值，且排除 @media 内
    print('[中灰背景]')
    gray_hits = []
    for m in re.finditer(r'([^{}]+)\{([^{}]*)\}', src):
        sel, body, pos = m.group(1), m.group(2), m.start()
        if in_spans(pos, mspans):
            continue
        decls = dict((k.strip().lower(), v.strip())
                     for k, v in re.findall(r'([\w-]+)\s*:\s*([^;]+)', body))
        val = decls.get('background-color') or decls.get('background') or ''
        for hx in re.findall(r'#[0-9a-fA-F]{6}', val):
            L = lum(hx.lower())
            if 0.08 < L < 0.45:
                gray_hits.append((' '.join(sel.split())[-46:], hx.lower(), L))
    if gray_hits:
        for sel, hx, L in gray_hits[:12]:
            print('  ! %s 亮度 %.3f  %s' % (hx, L, sel))
        problems += 1
    else:
        print('  无')

    # 5. 打印样式
    print('[打印样式]')
    has_print = '@media print' in src
    print('  @media print : %s' % ('存在' if has_print else '缺失'))
    problems += 0 if has_print else 1
    if 'pdf-white.css' not in imports(src):
        print('  ! 未引入 pdf-white.css，导出 PDF 会是黑底')
        problems += 1

    print()
    print('问题数:', problems)
    sys.exit(0 if problems == 0 else 1)


if __name__ == '__main__':
    main()
