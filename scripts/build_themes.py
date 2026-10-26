# -*- coding: utf-8 -*-
"""构建 Typora 纯黑系列主题（唯一真源）。

从内置 night.css 派生两个主题：
  pure-black.css       纯黑背景 + night 原始文字亮度（较亮，适合白天/大屏）
  pure-black-soft.css  纯黑背景 + 文字压一档（主文字 11.31:1 -> 10.49:1，适合长时间写作）

两个版本共享全部非亮度修复：
  · 灰面 -> 纯黑/近黑（含 CSS 命名色 gray 的转换）
  · mark 黄底补深字（night 原主题缺 color，导致浅灰字压黄底不可读）
  · 选区 / 快速打开面板 / 取消固定按钮 / 搜索命中 的饱和蓝压暗
  · 标题层级角标恢复可见（#888 在纯黑上只剩 2.16:1）
  · 代码块补 1px 边框（#0f0f0f 底在纯黑上会融进背景）
  · @import "pdf-white.css" —— 导出 PDF 自动转白底黑字，无需手动切主题
  · @media print 补充：暗色代码高亮的 token 色在白底上几乎看不见，逐类改深色

用法：python build_themes.py
"""
import re, os, sys, shutil, argparse, platform


def guess_themes_dir():
    """探测 Typora 的主题目录。"""
    if os.name == 'nt':
        return os.path.join(os.environ.get('APPDATA', ''), 'Typora', 'themes')
    if platform.system() == 'Darwin':
        return os.path.expanduser('~/Library/Application Support/abnerworks.Typora/themes')
    return os.path.expanduser('~/.config/Typora/themes')


THEMES = guess_themes_dir()   # 读取 night.css 的来源目录
BASE = os.path.join(THEMES, 'night.css')
OUT_DIR = THEMES              # 写出目录，可由 --out 覆盖


def replace_ci(s, old, new):
    """大小写不敏感替换（night.css 里 hex 大小写混用）。"""
    return re.sub(re.escape(old), new, s, flags=re.I)


# ---------- 灰面 -> 纯黑 / 近黑 ----------
BG_MAP = {
    '#363b40': '#000000',   # 主体 / 正文背景
    '#2e3033': '#0a0a0a',   # 侧边栏
    '#2d3033': '#0a0a0a',
    '#2f353a': '#0a0a0a',
    '#333333': '#0f0f0f',   # 代码块 / 提示气泡
    '#333':    '#0f0f0f',
    '#42464a': '#1a1a1a',
    '#474d54': '#1f1f1f',   # 表格 / 引用边框
    '#525c65': '#2a2a2a',
    '#57616b': '#2e2e2e',
    '#555':    '#242424',   # 分隔线
    '#656565': '#2a2a2a',
    '#686868': '#2a2a2a',
    '#70717d': '#1f1f1f',   # 悬停底（原值过亮）
    '#777777': '#333333',
    '#888':    '#757575',   # 标题层级角标：直接给到 4.6:1，别再压
    '#9b9b9b': '#555555',   # checkbox 灰块
}

BG_RGBA_MAP = {
    'rgb(34, 34, 34)':        'rgb(15, 15, 15)',
    'rgba(50, 54, 59, 0.93)': 'rgba(0, 0, 0, 0.93)',
    'rgba(26, 21, 21, 0.51)': 'rgba(0, 0, 0, 0.51)',
    'rgba(174, 174, 174, 0.7)': 'rgba(0, 0, 0, 0.7)',   # 模态遮罩：浅灰在纯黑上刺眼
    'rgba(0, 0, 0, 0.05)':    'rgba(255, 255, 255, 0.05)',  # 纯黑上的浅色遮罩
    'rgba(77, 139, 219, 0.8)':  'rgba(70, 126, 200, 0.6)',
    'rgba(199, 140, 60, 0.81)': 'rgba(165, 115, 48, 0.62)',
    'rgba(230, 230, 230, 0.30)': 'rgba(195, 200, 205, 0.20)',
    'rgba(230, 230, 230, 0.50)': 'rgba(195, 200, 205, 0.32)',
    'rgba(250, 250, 250, 0.3)':  'rgba(195, 200, 205, 0.20)',
    'rgba(250, 250, 250, 0.5)':  'rgba(195, 200, 205, 0.32)',
}

# ---------- soft 变体专用：文字压一档 ----------
TEXT_MAP_SOFT = {
    '#b8bfc6': '#b2b8be',   # 正文            11.31 -> 10.49
    '#b7b7b7': '#adb1b5',   # 控件文字
    '#dedede': '#d6dade',   # 标题 / strong / 表格链接
    '#eee':    '#e4e8ec',   # hover / 激活
    '#ddd':    '#cfd3d7',   # md-focus 标记
    '#e0e0e0': '#d2d8de',   # 普通链接
    '#bbbbbb': '#a5a9ad',   # 图片元信息
    '#ccc':    '#bfc3c7',
    '#a8c2dc': '#a6bcd2',   # 目录项
    '#81b1db': '#8cabd0',   # 行内公式
    '#9da2a6': '#9ca1a6',   # 引用
    '#8c8e92': '#8e9296',   # md-attr
    '#5a95e3': '#639ce8',   # 注释
    '#f1908e': '#e58886',   # 图表报错
    '#6dc1e7': '#68b6d6',   # --primary-color
    '#a3d5fe': '#9cc4e8',
    '#d3d40e': '#c8c90f',   # mark 底色
}

# ---------- 共享缺陷修复（与亮度无关） ----------
FIXES = [
    ('--select-text-bg-color:#4a89dc;', '--select-text-bg-color: #2b4a6b;'),
    ('background: #4a89dc;',            'background: #2b4a6b;'),   # 行内选中高亮
    ('background-color: #4D8BDB;',      'background-color: #2b4a6b;'),  # 快速打开激活项
    ('background-color: #4182C4;',      'background-color: #2b4a6b;'),  # 取消固定按钮
    ('--search-select-bg-color: #428bca;', '--search-select-bg-color: #2f5d8a;'),
    ('--text-color: #e8f2fb;',          '--text-color: #bccddc;'),  # 表格编辑浮层
    ('background-color: #555555;',      'background-color: #2a2a2a;'),  # TOC 下拉分隔线
    ('border-top: 1px solid gray;',     'border-top: 1px solid #2a2a2a;'),  # 命名色 gray
    # 结构线：原 #474d54 对 #363B40 是 1.29:1，映射到 #1f1f1f 后对纯黑只剩 1.15:1，比原设计更弱
    ('border: solid 1px #1f1f1f;',      'border: solid 1px #2a2a2a;'),      # 表格
    ('border-left: solid 2px #1f1f1f;', 'border-left: solid 2px #2a2a2a;'), # 引用
]

# ---------- 命名色修正（必须是基座原值） ----------
NAMED_FIX = [
    ('border-bottom: 1px solid grey;',  'border-bottom: 1px solid #2a2a2a;'),
    ('border-bottom: 1px dashed grey;', 'border-bottom: 1px dashed #2a2a2a;'),
    ('border: 1px grey solid;',         'border: 1px solid #2a2a2a;'),
]

MARK_FIX_OLD = '''mark {
    background: #c8c90f;
}'''
MARK_FIX_NEW = '''mark {
    background: #c8c90f;
    color: #0f0f0f;   /* 黄底必须配深字，night 原主题缺这一条 */
}'''

# ---------- 屏幕补充 ----------
SCREEN_EXTRA = """

/* ============ 纯黑背景适配（build_themes.py） ============ */

/* 代码块：底色 #0f0f0f 在纯黑上几乎融进背景，补一道极淡边框勾出范围 */
.md-fences {
    border: 1px solid #262626;
}

/* 行内代码：保持 night 原设计（继承正文字色），
   仅把半透明白底从 5% 提到 8%，否则纯黑上看不出边界 */
code, tt, var {
    background: rgba(255, 255, 255, 0.08);
}

/* 分隔线：#1a1a1a 对纯黑只有 1.21:1，等于画了条看不见的线 */
#write hr {
    background-color: #2e2e2e;
}

/* 选区：深蓝底 + 文字可读 */
::selection,
*::selection {
    background: #2b4a6b;
    color: #dee3e8;
}
"""

SCREEN_EXTRA_SOFT = """
/* 表格表头：night 用 #dedede，一整行在纯黑上偏亮，压到比正文高一档 */
#write th {
    color: #c4c8cc;
}

/* 粗体不再额外提亮：暗色下字形变粗本身就会显亮 */
#write strong,
#write b {
    color: #bcc2c8;
}
"""

# ---------- 打印补充（叠加在 pdf-white.css 之上） ----------
PRINT_EXTRA = """

/* ============ 导出 PDF / 打印补充（build_themes.py） ============
   pdf-white.css 已把页面转成白底黑字，但它不认识暗色主题里的
   代码高亮 token 和几处浅色前景，这里逐条补齐，否则导出后看不见。 */

@media print {

    /* 兜底：万一某个 Typora 版本的导出 DOM 不带 #write，也不至于出黑页 */
    html, body, .typora-export, .typora-export-content, #write {
        background: #ffffff !important;
        color: #333333 !important;
    }

    /* 代码块语法高亮：暗色主题的亮色 token 在白底上几乎不可见 */
    #write .md-fences *,
    #write .md-fences {
        color: #333333 !important;
    }

    #write .cm-s-inner .cm-keyword,
    #write .cm-keyword        { color: #7b2d8e !important; }
    #write .cm-s-inner .cm-string,
    #write .cm-s-inner .cm-string-2,
    #write .cm-string         { color: #b03030 !important; }
    #write .cm-s-inner .cm-comment,
    #write .cm-comment        { color: #8a6d3b !important; }
    #write .cm-s-inner .cm-tag,
    #write .cm-tag            { color: #1f7a1f !important; }
    #write .cm-s-inner .cm-attribute,
    #write .cm-s-inner .cm-def,
    #write .cm-s-inner .cm-header,
    #write .cm-attribute      { color: #4a4abf !important; }
    #write .cm-s-inner .cm-number,
    #write .cm-number         { color: #2e7d6b !important; }
    #write .cm-s-inner .cm-atom,
    #write .cm-s-inner .cm-variable-3,
    #write .cm-atom           { color: #1a6b8a !important; }
    #write .cm-s-inner .cm-builtin { color: #a02090 !important; }
    #write .cm-s-inner .cm-link    { color: #2a5db0 !important; }
    #write .cm-s-inner .cm-meta,
    #write .cm-s-inner .cm-qualifier { color: #666666 !important; }
    #write .cm-s-inner .cm-bracket { color: #665544 !important; }

    /* 行内代码 / 键盘键：屏幕上靠半透明白底，白纸上要换成浅灰底 */
    #write code,
    #write tt,
    #write var {
        background: #f2f2f2 !important;
        color: #333333 !important;
    }

    #write kbd {
        background: #f0f0f0 !important;
        color: #333333 !important;
        border: 1px solid #dddddd !important;
        box-shadow: none !important;
    }

    /* 高亮：黄底降到浅黄，避免整块压黑 */
    #write mark {
        background: #fff3a3 !important;
        color: #333333 !important;
    }

    /* 加粗 / 强调：屏幕上是浅灰 #bcc2c8，白纸上几乎不可见，必须压回深色 */
    #write strong,
    #write b,
    #write dt,
    #write em {
        color: #222222 !important;
    }

    /* 任务列表勾选框：屏幕上是「深底 + 浅灰对勾」，白纸上会变成一个黑方块 */
    #write .md-task-list-item > input:before {
        background: #ffffff !important;
        border: 1px solid #444444 !important;
    }

    #write .md-task-list-item > input:checked:before,
    #write .md-task-list-item > input[checked]:before {
        color: #333333 !important;
        background: #ffffff !important;
        border: 1px solid #444444 !important;
        line-height: 0.875rem !important;  /* night 原值 0.625rem，对勾会偏上 */
    }

    /* 行内公式 / 脚注角标 / YAML 元信息块 */
    #write .md-inline-math svg {
        color: #333333 !important;
    }

    #write sup.md-footnote {
        background: #f0f0f0 !important;
        color: #333333 !important;
    }

    #write pre.md-meta-block {
        background: #f7f7f7 !important;
        color: #666666 !important;
        border-bottom: 1px dashed #dddddd !important;
    }

    /* 引用块：pdf-white.css 里写了 border:none !important + padding:0 !important，
       打印稿中引用与正文完全分不出来。这里恢复一条浅灰左边框和缩进。
       同特异性、同为 !important，靠「后定义」取胜。 */
    #write blockquote {
        border-left: 3px solid #dddddd !important;
        padding-left: 1em !important;
        margin-left: 0 !important;
    }

    /* 评论 / 提示类文字 */
    #write .md-comment {
        color: #6b6b6b !important;
        opacity: 1 !important;
    }

    #write .md-alert-text-note      { color: #1a5fb4 !important; }
    #write .md-alert-text-important { color: #6b2fb5 !important; }
    #write .md-alert-text-warning   { color: #8a5a00 !important; }

    /* 链接：不打论文级别的下划线，但要能看出是链接 */
    #write a {
        color: #1a5fb4 !important;
        text-decoration: underline !important;
    }
}
"""


def build(variant):
    s = open(BASE, encoding='utf-8').read()

    # 1. 灰面 -> 纯黑
    s = re.sub(r'#[0-9a-fA-F]{3,8}\b',
               lambda m: BG_MAP.get(m.group(0).lower(), m.group(0)), s)
    for old, new in BG_RGBA_MAP.items():
        s = replace_ci(s, old, new)

    # 1b. 命名色（hex 映射抓不到，是最容易漏的一类）
    #     white 共 18 处：只有 h4/h6 是正文标题，其余是按钮/hover 文字，不动。
    #     h4/h6 原本是 white，在纯黑背景上比 h1~h3 的 #dedede 还亮，层级会倒挂。
    s = re.sub(r'(h[46]\s*\{[^{}]*?color:\s*)white\b', r'\1#dedede', s, flags=re.S)
    for old, new in NAMED_FIX:
        s = replace_ci(s, old, new)

    # 2. soft：文字压一档
    if variant == 'soft':
        s = re.sub(r'#[0-9a-fA-F]{6}\b',
                   lambda m: TEXT_MAP_SOFT.get(m.group(0).lower(), m.group(0)), s)

    # 3. 共享缺陷修复
    missed = []
    for old, new in FIXES:
        if re.search(re.escape(old), s, re.I):
            s = replace_ci(s, old, new)
        else:
            missed.append(old)
    s = s.replace(MARK_FIX_OLD, MARK_FIX_NEW)

    # 4. 接入打印样式（@import 必须位于所有规则之前）
    s = s.replace('@import "night/sourcemode.dark.css";',
                  '@import "night/sourcemode.dark.css";\n@import "pdf-white.css";', 1)

    # 5. 屏幕 + 打印补充
    s += SCREEN_EXTRA
    if variant == 'soft':
        s += SCREEN_EXTRA_SOFT
    s += PRINT_EXTRA

    # 6. 头部说明
    if variant == 'soft':
        desc = ('/* pure-black-soft —— OLED 纯黑 + 文字压一档\n'
                ' * 主文字 #b2b8be，对纯黑 10.49:1（night 原版 11.31:1）\n'
                ' * 唯一可调变量：--text-color。改回 #b8bfc6 即等于 pure-black。\n')
    else:
        desc = ('/* pure-black —— OLED 纯黑 + night 原始文字亮度\n'
                ' * 主文字 #b8bfc6，对纯黑 11.31:1。白天/大屏用这个。\n'
                ' * 想把整体压柔一点：把 --text-color 改成 #b2b8be。\n')
    desc += (' * 两版共享全部缺陷修复，并 @import "pdf-white.css"，\n'
             ' * 导出 PDF 会自动转白底黑字，不需要手动切主题。\n'
             ' * 生成脚本：build_themes.py（改配色请改脚本重跑，不要手改本文件）\n'
             ' */\n\n')
    s = desc + s

    out = os.path.join(OUT_DIR, 'pure-black.css' if variant == 'standard' else 'pure-black-soft.css')
    open(out, 'w', encoding='utf-8', newline='\n').write(s)

    key = re.search(r'--text-color:\s*(#[0-9a-f]{6});', s).group(1)
    print('%-20s %5.1f KB  正文 %s  括号 %d/%d %s  未命中修复 %d  打印补丁 %s'
          % (os.path.basename(out), len(s.encode('utf-8')) / 1024, key,
             s.count('{'), s.count('}'), 'OK' if s.count('{') == s.count('}') else 'FAIL',
             len(missed), 'YES' if '@media print' in s else 'NO'))
    return out


def main():
    global OUT_DIR

    ap = argparse.ArgumentParser(
        description='从 Typora 内置 night.css 派生出纯黑主题。')
    ap.add_argument('-t', '--themes', default=None,
                    help='Typora 主题目录（读取 night.css）。默认自动探测。')
    ap.add_argument('-o', '--out', default=None,
                    help='输出目录。默认与 --themes 相同，即直接装回 Typora。')
    args = ap.parse_args()

    global THEMES, BASE
    if args.themes:
        THEMES = args.themes
        BASE = os.path.join(THEMES, 'night.css')
    OUT_DIR = args.out or THEMES

    if not os.path.exists(BASE):
        sys.exit('找不到 %s\n请确认 Typora 已安装，或用 -t 指定主题目录。' % BASE)

    os.makedirs(OUT_DIR, exist_ok=True)

    # 生成的 css 里 @import "pdf-white.css"，该文件必须在输出目录里
    pdfw = os.path.join(OUT_DIR, 'pdf-white.css')
    if not os.path.exists(pdfw):
        here = os.path.dirname(os.path.abspath(__file__))
        for cand in (os.path.join(THEMES, 'pdf-white.css'),
                     os.path.join(here, '..', 'themes', 'pdf-white.css'),
                     os.path.join(here, 'pdf-white.css')):
            if os.path.exists(cand):
                shutil.copyfile(cand, pdfw)
                print('已复制 pdf-white.css -> %s' % OUT_DIR)
                break
        else:
            print('警告: %s 不存在，导出 PDF 的打印样式不会生效。' % pdfw)

    for v in ('standard', 'soft'):
        build(v)


if __name__ == '__main__':
    main()
