# -*- coding: utf-8 -*-
"""
通用 eink PPT 生成引擎（主题可配）
================================================
CSS / JS / 动效脚本已**内联固化**进本文件（见 §1 常量），运行时不再读取任何
外部 HTML 底座，彻底消除「参考底座被删就崩」的脆弱性。引擎 = 版式原语 +
强调锚点自动包裹 + 节奏自动分配 + 连续编号。

用法（见文件底部 __main__ 示例）：
    from _eink_template import build, Lecture
    lec = Lecture(title=..., lecture_no=3, series_total=12, slides=[...])
    build(lec, out_dir="<输出目录>/index.html")

数据模型（每页 slide 是一个 dict，type 决定版式）：
    cover      封面：kicker / title(可 title_lines 多行+逐行对齐) / subtitle / meta[]
    hero       分隔/幕封页：label(小字+chrome左) / title(可 title_lines 多行+逐行对齐) / color
    lead       引言：kicker / title / body
    statgrid   数据大字报：kicker / title / stats[{label,nb,unit,note,accent}]
    grid2      左文右图：kicker / title / left(str|list) / img{label,ratio}
    rowline    表格行（生平/年表）：kicker / title / rows[{k,v,m}]
    quote      金句：kicker / text / src
    pillar     支柱卡：kicker / title / items[{ic,t,d}]
    directional 左右对比：kicker / title / left{title,points} / right{title,points}
    callout    引文框：kicker / q / cite
    imgslot    大图占位：kicker / title / label / ratio
    figsvg     L12 手绘示意：kicker / title / svg_inline / cap
    text       通用段落：kicker / title / body
    pipeline   流水线/进程：kicker / title / steps[{title,desc}] / cols
    interactive 互动页：kicker / title / body(提示) / tag
    ziyuan     字源卡：kicker / title / items[{ch,form,mean}]
    chain      链条式：kicker / title / items[{ch,d,blank}]
    raw        自定义HTML：html(直接作为 .frame 内容)

页面级固定元件（任意版式可挂，引擎在 .frame 末尾统一注入）：
    body(M10)   正文/小字：结构化版式(pillar/statgrid/rowline/directional/pipeline/quote/imgslot/figsvg)
                不原生渲染 body，由引擎补挂，根治小字被吞。
    callout(M11) 引文框：非 callout 页可在底部挂引文（引文降级为固定元件）。
    annotation(M13) 注释：页面级小注。
    footnote(M14) 下标/出处：默认右对齐，可用 m14_align 调 左/中/右。
    design      设计占位：「设计:」标记的描述，待按描述生成真实 SVG 后替换。

每页可选字段：
    color       强制 "light"/"dark"（否则自动分配，并打散连续3同色）
    chrome_left 右上角左半（如「核心人物」）；默认按 type 给
    topic       页脚话题名（默认用 lecture.short_title）
    emphasis    本页「强调锚点」列表：内部出现的这些词自动套主题 accent 强调色
                （关键改进：强调锚点在大纲阶段就定好，全系列一贯）

纪律（引擎中立约定，不含任何单一系列的专属规则）：
    · 主题可配（内置 5 套预设：墨水经典/靛蓝瓷/森林墨/牛皮纸/沙丘；ink/paper/accent 三色，双色体系+克制第三色）
    · 默认主题 ink-classic；专用系列的主题/系列名等固化项由调用方通过 `--profile` 或大纲 meta 指定
    · 图标用 Lucide（`<ico=name>`）；是否禁用 emoji 属**风格层**约定，由调用方/专用 profile 决定，引擎层不强制
    · 右下角内页连续 NN / 本讲总页数；封面(L01)不显示页码（「总讲次数」仅作元信息落 ctx，暂不渲染）
    · 页脚只留话题名，不标页码
    · 节奏：无连续3同色
    · ⚠️ 引擎内不得出现任何单一系列的专属值（固定讲数、领域词表、具体选题文案）：
      此类内容一律外置到调用方的 `--profile` 或大纲 meta
"""

import os, re, shutil, html, json, struct, urllib.parse, base64, io

# ---- lucide 图标名白名单（未知 ic 兜底警告数据源；与 lint 同源，由
#      engine/_gen_lucide_list.mjs 从 eink_assets/lucide.umd.min.js 提取。2026-09-18 新增） ----
_LUCIDE_LIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eink_assets", "lucide_icons.txt")
_LUCIDE_ICONS = set()
try:
    with io.open(_LUCIDE_LIST, "r", encoding="utf-8") as _f:
        for _ln in _f:
            _ln = _ln.strip()
            if _ln:
                _LUCIDE_ICONS.add(_ln)
except Exception:
    _LUCIDE_ICONS = set()   # 读不到则不警告（不阻断渲染）

# ----------------------------------------------------------------------------
# 0.5) 主题预设（通用化：配色全部可配，不再写死）
#   每套主题给出 ink/paper/tint/accent（accent-ink 为深底上的亮强调色），
#   以及字体基调 font: serif(衬线主导) / sans(无衬线主导)。
#   默认主题 = ink-classic（墨水经典，最通用安全）。
THEMES = {
  "ink-classic": {  # 墨水经典
    "label": "墨水经典",
    "ink": "#0a0a0b", "ink_rgb": "10,10,11",
    "paper": "#f1efea", "paper_rgb": "241,239,234",
    "paper_tint": "#e8e5de", "ink_tint": "#18181a",
    "accent": "#b23a2e", "accent_ink": "#e0624e",
    "font": "serif",
  },
  "indigo": {  # 靛蓝瓷
    "label": "靛蓝瓷",
    "ink": "#0a1f3d", "ink_rgb": "10,31,61",
    "paper": "#f1f3f5", "paper_rgb": "241,243,245",
    "paper_tint": "#e4e8ec", "ink_tint": "#152a4a",
    "accent": "#d98324", "accent_ink": "#f0a857",
    "font": "sans",
  },
  "forest": {  # 森林墨
    "label": "森林墨",
    "ink": "#1a2e1f", "ink_rgb": "26,46,31",
    "paper": "#f5f1e8", "paper_rgb": "245,241,232",
    "paper_tint": "#ece7da", "ink_tint": "#253d2c",
    "accent": "#b8842f", "accent_ink": "#dcae57",
    "font": "serif",
  },
  "kraft": {  # 牛皮纸（朱砂红 accent，历史厚重感）
    "label": "牛皮纸",
    "ink": "#2a1e13", "ink_rgb": "42,30,19",
    "paper": "#eedfc7", "paper_rgb": "238,223,199",
    "paper_tint": "#e0d0b6", "ink_tint": "#3a2a1d",
    "accent": "#a8331f", "accent_ink": "#d65436",
    "font": "serif",
  },
  "dune": {  # 沙丘
    "label": "沙丘",
    "ink": "#1f1a14", "ink_rgb": "31,26,20",
    "paper": "#f0e6d2", "paper_rgb": "240,230,210",
    "paper_tint": "#e3d7bf", "ink_tint": "#2d2620",
    "accent": "#b5654a", "accent_ink": "#d98c6a",
    "font": "serif",
  },
}

# 默认主题名收编于 _theme_default.py（与 eink2pptx 的 templates.py 同源）
from _theme_default import DEFAULT_THEME  # noqa: E402

def _resolve_theme(name):
    if not name:
        return THEMES[DEFAULT_THEME]
    key = str(name).strip().lower()
    if key in THEMES:
        return THEMES[key]
    for t in THEMES.values():
        if name.strip() in (t["label"], t["label"].split()[-1]):
            return t
    print("  [主题警告] 未找到主题「%s」，回退默认「%s」" % (name, DEFAULT_THEME))
    return THEMES[DEFAULT_THEME]

def _hex2rgb01(hexc):
    h = hexc.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "%.4f,%.4f,%.4f" % (r / 255.0, g / 255.0, b / 255.0)



# ----------------------------------------------------------------------------
# 1) 内联 CSS / JS 底座（已固化进引擎，运行时不再读取任何外部 HTML，
#    彻底消除"参考底座被删就崩"的脆弱性；改视觉只动本文件 _CSS / _CSS_EXTRA 或重建此处常量。
#    注意：_CSS 仅含原始底座 CSS；_CSS_EXTRA（含页面级固定元件样式）为引擎内常量，
#    二者在 build() 中拼接，避免把 _CSS_EXTRA 重复固化进 _CSS。
_THIS = os.path.dirname(os.path.abspath(__file__))
_HEAD = '<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>eink 演示</title>\n<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;0,600;0,700;0,800;0,900;1,400;1,700&family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;0,8..60,500;0,8..60,600;1,8..60,400&family=IBM+Plex+Mono:wght@300;400;500;600&family=Noto+Serif+SC:wght@300;400;500;600;700;900&family=Noto+Sans+SC:wght@300;400;500;700;900&display=swap" rel="stylesheet">'

_CSS = '\n  :root{\n    /* ============ 主题色（此处为兜底默认值；渲染时按 `- 主题:` / --theme 整体覆盖） ============\n       切换主题:改本文件 THEMES 预设,或渲染时 --theme=<名>(build() 会整体覆盖注入 :root)\n       整体替换这几行(--ink / --ink-rgb / --paper / --paper-rgb)\n       其他地方散落的 rgba() 都走 var(--ink-rgb) / var(--paper-rgb),无需逐处改 */\n    --ink:#2a1e13;\n    --ink-rgb:42,30,19;\n    --paper:#eedfc7;\n    --paper-rgb:238,223,199;\n    --paper-tint:#e0d0b6;\n    --ink-tint:#3a2a1d;\n\n    /* ============ 字体(跨主题固定) ============ */\n    --mono:"IBM Plex Mono",ui-monospace,monospace;\n    --serif-en:"Playfair Display","Source Serif 4",Georgia,serif;\n    --serif-body-en:"Source Serif 4",Georgia,serif;\n    --serif-zh:"Noto Serif SC",source-han-serif-sc,serif;\n    --sans-zh:"Noto Sans SC",source-han-sans-sc,sans-serif;\n    /* 中文无衬线（页眉/页脚/小字用，粗体） */\n    --yahei:"Microsoft YaHei","微软雅黑",var(--sans-zh),sans-serif;\n    /* 第三色：accent 点睛强调色（克制使用；色值随主题，非恒定红） */\n    --accent:#a8331f;        /* light 页上的强调色（兜底值，渲染时被主题覆盖） */\n    --accent-ink:#d65436;    /* dark 页上的强调色（更亮保可读；兜底值，被主题覆盖） */\n  }\n  *{box-sizing:border-box;margin:0;padding:0}\n  html,body{width:100%;height:100%;overflow:hidden;background:var(--ink);color:var(--paper);font-family:var(--sans-zh);-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}\n\n  /* ============ WebGL 双背景 ============ */\n  canvas.bg{position:fixed;inset:0;width:100vw;height:100vh;z-index:0;display:block;transition:opacity 1.2s ease}\n  canvas#bg-light{opacity:0}\n  canvas#bg-dark{opacity:1}\n  body.light-bg canvas#bg-light{opacity:1}\n  body.light-bg canvas#bg-dark{opacity:0}\n  body.low-power canvas.bg{display:none!important}\n\n  /* ============ Deck 容器 + 翻页 ============ */\n  /* width: NSLIDES * 100vw，会在 JS 里动态矫正 */\n  #deck{position:fixed;inset:0;width:10000vw;height:100vh;display:flex;flex-wrap:nowrap;transition:transform .9s cubic-bezier(.77,0,.175,1);z-index:10;will-change:transform}\n  .slide{width:100vw;height:100vh;flex:0 0 100vw;position:relative;padding:6vh 6vw 10vh 6vw;display:flex;flex-direction:column;overflow:hidden}\n  .slide.light{color:var(--ink);background:var(--paper)}\n  .slide.dark{color:var(--paper);background:var(--ink)}\n\n  /* 默认页：遮罩较厚，保证文字可读 */\n  .slide::before{content:"";position:absolute;inset:0;z-index:-1;pointer-events:none;transition:background .7s ease}\n  .slide.light::before{background:rgba(var(--paper-rgb),.78);backdrop-filter:blur(3px)}\n  .slide.dark::before{background:rgba(var(--ink-rgb),.78);backdrop-filter:blur(3px)}\n  /* Hero 页：遮罩大幅降低，让 WebGL 背景明显透出 */\n  .slide.hero.light::before{background:rgba(var(--paper-rgb),.16);backdrop-filter:none}\n  .slide.hero.dark::before{background:rgba(var(--ink-rgb),.12);backdrop-filter:none}\n  /* Hero 页顶底微弱渐隐，保证 chrome/foot 区域可读 */\n  .slide.hero::after{content:"";position:absolute;inset:0;z-index:-1;pointer-events:none}\n  .slide.hero.light::after{background:linear-gradient(180deg,rgba(var(--paper-rgb),.28) 0%,rgba(var(--paper-rgb),0) 14%,rgba(var(--paper-rgb),0) 86%,rgba(var(--paper-rgb),.28) 100%)}\n  .slide.hero.dark::after{background:linear-gradient(180deg,rgba(var(--ink-rgb),.32) 0%,rgba(var(--ink-rgb),0) 14%,rgba(var(--ink-rgb),0) 86%,rgba(var(--ink-rgb),.32) 100%)}\n\n  /* ============ Magazine chrome：顶部 meta + 底部 foot ============ */\n  /* 2026-09-04 收敛：原 .chrome 在下文「chrome & foot 补位」段被二次定义（后者胜）。\n     已合并为一条，取层叠后的最终值：font-family/size/letter-spacing/opacity/text-transform 用补位段，\n     布局属性（display/justify-content/align-items/font-weight）用本段。 */\n  .chrome{display:flex;justify-content:space-between;align-items:flex-start;font-family:var(--mono);font-weight:700;font-size:max(11px,.78vw);letter-spacing:.2em;text-transform:uppercase;opacity:.62}\n  .chrome .left,.chrome .right{display:flex;gap:2.4em;align-items:center}\n  .chrome .sep{width:40px;height:1px;background:currentColor;opacity:.4}\n  /* 2026-09-04 收敛：原 .foot 在下文「chrome & foot 补位」段被二次定义（后者胜）。\n     已合并为一条，取层叠后的最终值：字体/字距/opacity 用补位段，布局属性用本段。 */\n  .foot{margin-top:auto;display:flex;justify-content:space-between;align-items:flex-end;font-family:var(--mono);font-weight:700;font-size:max(11px,.78vw);letter-spacing:.18em;text-transform:uppercase;opacity:.5}\n  .foot .title{font-family:var(--yahei);font-weight:700;letter-spacing:.04em;text-transform:none;opacity:.78;font-size:max(13px,1vw)}\n\n  .tag{display:inline-block;font-family:var(--yahei);font-weight:700;font-size:max(12px,.92vw);letter-spacing:.08em;padding:6px 14px;border:1px solid currentColor;opacity:.85}\n  .rule{width:100%;height:1px;background:currentColor;opacity:.25;margin:3vh 0}\n  .rule.v{width:1px;height:100%;margin:0}\n\n  /* ============ 字体规则 ============\n     · 衬线（Noto Serif SC / Playfair）：大标题、重点金句、数字\n     · 非衬线（Noto Sans SC）：正文描述、body、补充说明\n     · 等宽（IBM Plex Mono）：kicker、meta 小标签、foot 右侧\n  */\n  .kicker{font-family:var(--yahei);font-weight:700;font-size:max(14px,1.08vw);letter-spacing:.06em;opacity:.74;margin-bottom:2.6vh}\n  .display{font-family:var(--serif-en);font-weight:700;font-size:11vw;line-height:.92;letter-spacing:-.025em}\n  .display-zh{font-family:var(--serif-zh);font-weight:700;font-size:7.8vw;line-height:1.04;letter-spacing:-.005em}\n  .h1-zh{font-family:var(--serif-zh);font-weight:700;font-size:4.6vw;line-height:1.12;letter-spacing:-.005em}\n  .h2-zh{font-family:var(--serif-zh);font-weight:600;font-size:3.2vw;line-height:1.2;letter-spacing:0}\n  .h3-zh{font-family:var(--serif-zh);font-weight:500;font-size:1.9vw;line-height:1.35}\n  .body-zh{font-family:var(--sans-zh);font-weight:400;font-size:max(15px,1.22vw);line-height:1.75;opacity:.82;letter-spacing:.01em}\n  .body-serif{font-family:var(--serif-zh);font-weight:400;font-size:max(15px,1.3vw);line-height:1.65;opacity:.88}\n  /* 2026-09-04 收敛：.lead 曾在下文「LAYOUTS API · lead 引语」段二次定义（后者胜）。\n     已去重，仅保留最终值（font-size:1.75vw / line-height:1.5 / opacity:.86）。 */\n  .meta{font-family:var(--mono);font-size:max(11px,.88vw);letter-spacing:.16em;text-transform:uppercase;opacity:.6}\n  .big-num{font-family:var(--serif-en);font-weight:800;font-size:10vw;line-height:.85;letter-spacing:-.03em;font-feature-settings:"tnum"}\n  .mid-num{font-family:var(--serif-en);font-weight:700;font-size:5.5vw;line-height:.88;letter-spacing:-.02em;font-feature-settings:"tnum"}\n  .ghost{font-family:var(--serif-en);font-weight:900;font-size:34vw;line-height:.8;opacity:.06;letter-spacing:-.04em;position:absolute;font-feature-settings:"tnum"}\n  em{font-style:italic;font-family:var(--serif-en)}\n  .en{font-family:var(--serif-en);font-style:italic;font-weight:500}\n\n  /* ============ 布局工具 ============ */\n  .col{display:flex;flex-direction:column;gap:2.4vh}\n  .row{display:flex;align-items:center;gap:3vw}\n  .grid-6{display:grid;grid-template-columns:repeat(3,1fr);grid-template-rows:repeat(2,1fr);gap:4vw 6vw;flex:1;align-content:center;padding:2vh 0}\n  .grid-9{display:grid;grid-template-columns:repeat(3,1fr);grid-template-rows:repeat(3,1fr);gap:3vh 4vw;flex:1;align-content:center}\n  .grid-4{display:grid;grid-template-columns:repeat(2,1fr);grid-template-rows:auto;gap:4vh 6vw;flex:1;align-content:center}\n  .grid-3{display:grid;grid-template-columns:repeat(3,1fr);gap:4vw;flex:1;align-content:center}\n  .grid-2{display:grid;grid-template-columns:repeat(2,1fr);gap:4vw 6vw;flex:1;align-content:center}\n  .split{display:grid;grid-template-columns:1fr 1fr;gap:4vw;flex:1;align-items:start}\n  .split-55{display:grid;grid-template-columns:55fr 45fr;gap:5vw;flex:1;align-items:stretch}\n  .fill{flex:1}\n  .center{align-items:center;justify-content:center;text-align:center}\n  .bottom-left{position:absolute;left:6vw;bottom:9vh;max-width:50vw}\n  .bottom-right{position:absolute;right:6vw;bottom:9vh;max-width:50vw;text-align:right}\n  .top-right{position:absolute;right:6vw;top:6vh;text-align:right}\n\n  /* ============ Stat（数字矩阵） ============ */\n  .stat{display:flex;flex-direction:column;gap:1vh;align-items:flex-start}\n  .stat .n{font-family:var(--serif-en);font-weight:800;font-size:8vw;line-height:.88;letter-spacing:-.03em;font-feature-settings:"tnum"}\n  .stat .l{font-family:var(--sans-zh);font-size:max(13px,1.05vw);opacity:.7;margin-top:1vh;font-weight:400;line-height:1.5}\n  .stat .m{font-family:var(--mono);font-size:10px;letter-spacing:.22em;text-transform:uppercase;opacity:.5;margin-bottom:.2vh}\n\n  /* ============ Callout（引用框） ============ */\n  .callout{padding:3vh 2.4vw;border-left:3px solid currentColor;position:relative;font-family:var(--serif-zh);font-size:max(15px,1.2vw);line-height:1.55;opacity:.92}\n  .slide.light .callout{background:rgba(var(--ink-rgb),.05)}\n  .slide.dark .callout{background:rgba(var(--paper-rgb),.06)}\n  .callout .cite{display:block;margin-top:1.6vh;font-family:var(--mono);font-size:11px;letter-spacing:.2em;text-transform:uppercase;opacity:.6}\n  .q-big{font-family:var(--serif-zh);font-weight:700;font-size:max(22px,2.8vw);line-height:1.35;text-align:center}\n  .callout .q-big{font-family:var(--serif-zh);font-weight:600;font-size:max(17px,1.6vw);line-height:1.42}\n\n  /* ============ Platform（平台卡） ============ */\n  .plat{display:flex;flex-direction:column;justify-content:flex-end;padding:2vh 0;border-top:1px solid currentColor;border-color:rgba(127,127,127,.35)}\n  .plat .name{font-family:var(--serif-zh);font-weight:700;font-size:1.8vw;margin-bottom:.6vh}\n  .plat .nb{font-family:var(--serif-en);font-weight:700;font-size:3.2vw;letter-spacing:-.02em;line-height:1;font-feature-settings:"tnum"}\n  .plat .sub{font-family:var(--mono);font-size:10px;letter-spacing:.18em;text-transform:uppercase;opacity:.55;margin-top:.6vh}\n  .plat .fill{font-family:var(--sans-zh);font-weight:300;font-size:2.4vw;opacity:.28;letter-spacing:-.01em;line-height:1}\n\n  /* ============ Rowline（表格行） ============ */\n  .rowline{display:grid;grid-template-columns:1fr 2fr 1fr;gap:2vw;padding:calc(2.2vh * var(--rs,1));border-top:1px solid currentColor;align-items:center;border-color:rgba(127,127,127,.25);min-height:0}\n  .rowline:last-child{border-bottom:1px solid currentColor;border-color:rgba(127,127,127,.25)}\n  .rowline .k{font-family:var(--serif-zh);font-weight:700;font-size:calc(1.7vw * var(--rs,1))}\n  .rowline .v{font-family:var(--sans-zh);font-weight:400;font-size:calc(max(14px,1.2vw) * var(--rs,1));opacity:.85;line-height:1.55}\n  .rowline .m{font-family:var(--mono);font-size:calc(16px * var(--rs,1));letter-spacing:.2em;text-transform:uppercase;opacity:.6;justify-self:end}\n\n  /* ============ Pillar（支柱卡片） ============ */\n  .pillar{display:flex;flex-direction:column;gap:1.8vh}\n  .pillar .ic{font-family:var(--serif-en);font-style:italic;font-size:2.6vw;opacity:.45;font-weight:400}\n  .pillar .ic svg{width:2.8vw;height:2.8vw;stroke-width:1.2;opacity:.7}\n  .pillar .t{font-family:var(--serif-zh);font-weight:700;font-size:2.4vw;line-height:1.1}\n  .pillar .d{font-family:var(--sans-zh);font-weight:400;font-size:max(14px,1.1vw);opacity:.76;line-height:1.6}\n\n  /* ============ Signature / Highlight ============ */\n  .sign{font-family:var(--serif-en);font-style:italic;font-weight:500;font-size:2vw;opacity:.7}\n  .hi{position:relative;display:inline}\n  .slide.dark .hi::after{content:"";position:absolute;left:-.1em;right:-.1em;bottom:-.05em;height:.28em;background:rgba(var(--paper-rgb),.15);z-index:-1}\n  .slide.light .hi::after{content:"";position:absolute;left:-.1em;right:-.1em;bottom:-.05em;height:.28em;background:rgba(var(--ink-rgb),.08);z-index:-1}\n\n  /* ============ 第三色：accent 点睛强调（克制使用，仅强调数字/关键词） ============ */\n  .accent{color:var(--accent)}\n  .slide.dark .accent{color:var(--accent-ink)}\n  .accent-line{position:relative;display:inline}\n  .slide.dark .accent-line::after{content:"";position:absolute;left:-.06em;right:-.06em;bottom:.04em;height:.16em;background:var(--accent-ink);opacity:.34;z-index:-1;border-radius:2px}\n  .slide.light .accent-line::after{content:"";position:absolute;left:-.06em;right:-.06em;bottom:.04em;height:.16em;background:var(--accent);opacity:.22;z-index:-1;border-radius:2px}\n\n  /* ============ Icons（Lucide via CDN） ============ */\n  .ico{width:1em;height:1em;display:inline-block;vertical-align:-.12em;stroke:currentColor;fill:none;stroke-width:1.4;stroke-linecap:round;stroke-linejoin:round;flex-shrink:0}\n  .ico-lg,.ico-md,.ico-sm{fill:none;stroke:currentColor;stroke-linecap:round;stroke-linejoin:round}\n  .ico-lg{width:2.6vw;height:2.6vw;stroke-width:1.2;display:inline-block}\n  .ico-md{width:1.8vw;height:1.8vw;stroke-width:1.3;display:inline-block;vertical-align:-.4em}\n  .ico-sm{width:1.1vw;height:1.1vw;stroke-width:1.4;display:inline-block;vertical-align:-.15em;opacity:.7}\n\n  /* ============ 图片占位（虚线框，提示设计师位置） ============ */\n  .img-slot{border:1.5px dashed rgba(127,127,127,.4);display:flex;align-items:center;justify-content:center;flex-direction:column;gap:1vh;padding:2vh 2vw;font-family:var(--mono);font-size:10px;letter-spacing:.28em;text-transform:uppercase;opacity:.55;position:relative;aspect-ratio:16/9;width:100%;max-height:56vh;margin-inline:auto;box-sizing:border-box}\n  .img-slot::before{content:"";position:absolute;inset:8px;border:1px solid currentColor;opacity:.2}\n  .img-slot .plus{font-size:2vw;font-weight:300;opacity:.5;letter-spacing:0}\n  .img-slot .label{position:relative;z-index:2;text-align:center}\n  .img-slot.r-4x3{aspect-ratio:4/3}\n  .img-slot.r-3x2{aspect-ratio:3/2}\n  .img-slot.r-1x1{aspect-ratio:1/1}\n\n  /* ============ 图片实填框（关键：固定高度 + 只裁底部） ============\n     重要约束：高度用内联 height:Nvh 精确控制，不要用 aspect-ratio（会撑破布局）\n     object-position:top center 保证严禁裁剪顶部和左右，只裁剪底部\n  */\n  .frame-img{overflow:hidden;position:relative;background:rgba(0,0,0,.04);box-sizing:border-box;width:100%;border-radius:4px}\n  .slide.dark .frame-img{background:rgba(255,255,255,.04);border-color:rgba(255,255,255,.12)}\n  .frame-img > img{width:100%;height:100%;object-fit:cover;object-position:top center;display:block}\n  .frame-img.fit-contain > img{object-fit:contain;object-position:center center}\n  .frame-img.r-16x9{aspect-ratio:16/9;max-height:64vh}\n  .frame-img.r-16x10{aspect-ratio:16/10;max-height:56vh}\n  .frame-img.r-4x3{aspect-ratio:4/3;max-height:56vh}\n  .frame-img.r-3x2{aspect-ratio:3/2;max-height:46vh}\n  .frame-img.r-3x4{aspect-ratio:3/4;max-height:60vh}\n  .frame-img.r-1x1{aspect-ratio:1/1;max-height:50vh}\n  .frame-img.h-16{height:16vh}\n  .frame-img.h-18{height:18vh}\n  .frame-img.h-22{height:22vh}\n  .frame-img.h-26{height:26vh}\n  .frame-img.h-28{height:28vh}\n  .frame-cap{display:flex;justify-content:space-between;align-items:baseline;gap:1vw;margin-top:.8vh;font-family:var(--mono);font-size:10px;letter-spacing:.22em;text-transform:uppercase;opacity:.72}\n  .frame-cap .pf{font-family:var(--serif-zh);font-weight:600;font-size:max(13px,1vw);letter-spacing:.04em;text-transform:none;opacity:.94}\n  .frame-cap .nb{font-family:var(--serif-en);font-style:italic;font-size:max(15px,1.2vw);letter-spacing:.02em;text-transform:none;opacity:.88}\n  .frame-cap .idx{font-family:var(--mono);opacity:.5}\n  /* ============ 自制示意图（离线 SVG，示意为主、不画精确边界） ============ */\n  figure.fig-svg{margin:0;display:flex;flex-direction:column;min-width:0}\n  figure.fig-svg > svg{width:100%;height:auto;max-height:58vh;display:block}\n  figure.fig-svg .svg-cap{display:flex;justify-content:space-between;align-items:baseline;gap:1vw;margin-top:.8vh;font-family:var(--yahei);font-weight:700;font-size:max(12px,.95vw);letter-spacing:.04em;opacity:.72}\n  figure.tile{display:flex;flex-direction:column;margin:0;min-width:0}\n  figure.tile > .frame-img{flex:0 0 auto}\n\n  /* ============ 导航 ============ */\n  #nav{position:fixed;left:50%;bottom:2.6vh;transform:translateX(-50%);z-index:30;display:flex;gap:10px;padding:8px 14px;border-radius:999px;background:rgba(0,0,0,.18);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px)}\n  #nav .dot{width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,.3);cursor:pointer;transition:all .3s ease;border:0;padding:0}\n  #nav .dot:hover{background:rgba(255,255,255,.5);transform:scale(1.15)}\n  #nav .dot.active{background:rgba(255,255,255,.95);width:22px;border-radius:999px}\n  body.light-bg #nav{background:rgba(255,255,255,.25)}\n  body.light-bg #nav .dot{background:rgba(var(--ink-rgb),.25)}\n  body.light-bg #nav .dot.active{background:rgba(var(--ink-rgb),.9)}\n  #hint{position:fixed;bottom:3vh;right:3vw;z-index:30;font-family:var(--mono);font-size:10px;letter-spacing:.2em;text-transform:uppercase;opacity:.4;mix-blend-mode:difference;color:#aaa}\n  body.low-power #hint{opacity:.72;color:var(--paper);mix-blend-mode:normal}\n  body.light-bg.low-power #hint{color:var(--ink)}\n\n  /* ============================================================\n     ============ LAYOUTS API · 面向 agent 的类（v2）============\n     所有 layouts.md 中的骨架都基于下面这套命名。\n     如果你在 layouts.md 里看到某个类，它必须在下面有定义。\n     ============================================================ */\n\n  /* ---------- .frame：每页主内容容器 ---------- */\n  .frame{flex:1;display:flex;flex-direction:column;min-height:0;overflow:hidden;justify-content:flex-start;padding-top:3vh}\n  /* 离散纵向开关 - 纵向:顶/中/底；规则线 - 规则线:是（仅居左）；L05图底对齐 img-bottom */\n  .frame.v-top{justify-content:flex-start}\n  .frame.v-mid{justify-content:center}\n  .frame.v-bottom{justify-content:flex-end}\n  .frame.rule-accent::before{content:"";width:6vw;height:3px;background:var(--accent);margin-bottom:3.4vh;flex:0 0 auto;align-self:flex-start}\n  .slide.dark .frame.rule-accent::before{background:var(--accent-ink)}\n  .frame.img-bottom>figure,.frame.img-bottom>.img-slot{align-self:end}\n  /* 当 .frame 同时加了 grid 类时，grid 的 display:grid 覆盖 flex */\n  .frame.grid-2-7-5,\n  .frame.grid-2-6-6,\n  .frame.grid-2-8-4,\n  .frame.grid-3-3,\n  .frame.grid-6{display:grid}\n\n  /* ---------- 标题层级（API 名称，衬线为主） ---------- */\n  .h-hero{\n    font-family:var(--serif-zh);\n    font-weight:900;\n    font-size:10vw;\n    line-height:.96;\n    letter-spacing:-.02em;\n  }\n  .h-xl{\n    font-family:var(--serif-zh);\n    font-weight:700;\n    font-size:6.2vw;\n    line-height:1.08;\n    letter-spacing:-.01em;\n  }\n  .h-sub{\n    font-family:var(--serif-zh);\n    font-weight:500;\n    font-size:3.1vw;\n    line-height:1.25;\n    letter-spacing:0;\n    opacity:.7;\n  }\n  .h-md{\n    font-family:var(--serif-zh);\n    font-weight:600;\n    font-size:2.3vw;\n    line-height:1.3;\n  }\n  /* 英文标题专用（Playfair 衬线） */\n  .h-hero-en,.h-xl-en{font-family:var(--serif-en);letter-spacing:-.025em}\n\n  /* ---------- lead 引语 ---------- */\n  .lead{\n    font-family:var(--serif-zh);\n    font-weight:400;\n    font-size:1.75vw;\n    line-height:1.5;\n    opacity:.86;\n  }\n\n  /* ---------- meta-row 底部元数据 ---------- */\n  .meta-row{\n    display:flex;\n    gap:1.2em;\n    align-items:baseline;\n    flex-wrap:wrap;\n    font-family:var(--yahei);\n    font-weight:700;\n    font-size:max(13px,1vw);\n    letter-spacing:.05em;\n    opacity:.72;\n  }\n\n  /* ---------- stat-card（数据大字报用） ---------- */\n  .stat-card{\n    display:flex;\n    flex-direction:column;\n    gap:.8vh;\n    align-items:flex-start;\n    padding-top:1.6vh;\n    border-top:1px solid currentColor;\n    border-color:rgba(127,127,127,.3);\n    min-height:0;\n  }\n  .stat-card .stat-label{\n    font-family:var(--mono);\n    font-size:max(10px,.78vw);\n    letter-spacing:.24em;\n    text-transform:uppercase;\n    opacity:.55;\n  }\n  .stat-card .stat-nb{\n    font-family:var(--serif-en);\n    font-weight:800;\n    font-size:5.8vw;\n    line-height:.9;\n    letter-spacing:-.03em;\n    font-feature-settings:"tnum";\n    margin-top:.4vh;\n  }\n  .stat-card .stat-nb .stat-unit{\n    font-family:var(--serif-zh);\n    font-weight:500;\n    font-size:.38em;\n    letter-spacing:0;\n    opacity:.72;\n    margin-left:.14em;\n  }\n  .stat-card .stat-note{\n    font-family:var(--sans-zh);\n    font-weight:400;\n    font-size:max(13px,1.05vw);\n    line-height:1.5;\n    opacity:.72;\n    margin-top:.6vh;\n  }\n  /* 当 stat-card 用于 grid-4（2x2），数字适度放大；若页面有标题+引文在上方，可内联 style 覆盖为更小值 */\n  .grid-4 .stat-card .stat-nb{font-size:min(7.5vw,9vh)}\n  /* 当只有 3 个，字也可以稍大 */\n  .grid-3 .stat-card .stat-nb{font-size:min(6.8vw,9.5vh)}\n  .grid-2 .stat-card .stat-nb{font-size:min(7vw,12vh)}\n\n  /* ---------- pipeline（流水线） ---------- */\n  .pipeline-section{\n    margin-top:4.4vh;\n    padding-top:2.8vh;\n    border-top:1px dashed rgba(127,127,127,.32);\n  }\n  .pipeline-section:first-of-type{\n    border-top:0;\n    padding-top:0;\n    margin-top:3vh;\n  }\n  .pipeline-label{\n    font-family:var(--mono);\n    font-size:max(11px,.85vw);\n    letter-spacing:.24em;\n    text-transform:uppercase;\n    opacity:.62;\n    margin-bottom:2.2vh;\n  }\n  .pipeline{\n    display:grid;\n    grid-template-columns:repeat(5,1fr);\n    gap:1.2vw;\n  }\n  .pipeline[data-cols="3"]{grid-template-columns:repeat(3,1fr)}\n  .pipeline[data-cols="4"]{grid-template-columns:repeat(4,1fr)}\n  .pipeline[data-cols="6"]{grid-template-columns:repeat(6,1fr)}\n  .step{\n    display:flex;\n    flex-direction:column;\n    gap:.8vh;\n    padding-top:1.4vh;\n    border-top:1px solid currentColor;\n    border-color:rgba(127,127,127,.35);\n  }\n  .step-nb{\n    font-family:var(--serif-en);\n    font-style:italic;\n    font-weight:500;\n    font-size:1.15vw;\n    opacity:.45;\n  }\n  .step-title{\n    font-family:var(--sans-zh);\n    font-weight:700;\n    font-size:1.55vw;\n    letter-spacing:.01em;\n    line-height:1.2;\n  }\n  .step-desc{\n    font-family:var(--sans-zh);\n    font-weight:400;\n    font-size:max(12px,.95vw);\n    line-height:1.45;\n    opacity:.72;\n  }\n\n  /* ---------- 网格（layouts.md 所用） ---------- */\n  /* 这些类独立挂到任何容器上都能生效，不依赖 .frame 复合选择器 */\n  .grid-2-7-5{display:grid;grid-template-columns:7fr 5fr;gap:3vw 4vh;align-items:start}\n  .grid-2-6-6{display:grid;grid-template-columns:1fr 1fr;gap:3vw 4vh;align-items:start}\n  .grid-2-8-4{display:grid;grid-template-columns:8fr 4fr;gap:3vw 4vh;align-items:start}\n  .grid-3-3{\n    display:grid;\n    grid-template-columns:repeat(3,1fr);\n    grid-auto-rows:minmax(0,1fr);\n    gap:2.4vh 2vw;\n  }\n  /* grid-6 已在旧样式里定义为 3x2，这里仅补 align */\n\n  /* ---------- 图片 frame-img（layouts.md 主命名） ---------- */\n  /* 在旧样式里已定义，这里补 img-cap 命名别名与增强 */\n  figure.frame-img{margin:0;display:flex;flex-direction:column;min-width:0}\n  .img-cap{\n    display:block;\n    margin-top:.8vh;\n    font-family:var(--mono);\n    font-size:max(10px,.8vw);\n    letter-spacing:.22em;\n    text-transform:uppercase;\n    opacity:.6;\n  }\n  /* callout src 命名别名 */\n  .callout-src{\n    display:block;\n    margin-top:1.8vh;\n    font-family:var(--yahei);\n    font-weight:700;\n    font-size:max(13px,1.04vw);\n    letter-spacing:.04em;\n    opacity:.72;\n  }\n\n  /* ---------- chrome & foot 补位（layouts.md 简单写法） ---------- */\n\n\n\n  /* ============ 动效系统(Motion One 驱动) ============\n     所有 [data-anim] 元素默认隐藏,进入页面时由 JS 逐个揭示。\n     - cascade(默认):按 DOM 顺序 stagger 120ms 淡入 + y:16→0\n     - hero(hero 页自动):慢一点的 stagger 180ms\n     - quote(含 [data-anim="line"]):逐行 600ms 淡入\n     - directional(含 [data-anim="left|right"]):左→分隔线→右\n     - pipeline(data-animate="pipeline"):Space/→ 手动推进\n     Motion One 没加载成功时(CDN 断 + 本地丢),所有 [data-anim] 会兜底显示。\n  */\n  [data-anim]{opacity:1}\n  body.motion-ready [data-anim]{opacity:0}\n  body.motion-ready [data-anim="left"]{transform:translateX(-24px)}\n  body.motion-ready [data-anim="right"]{transform:translateX(24px)}\n  body.motion-ready [data-anim="line"]{opacity:0;transform:translateY(10px)}\n  body.motion-ready [data-animate="pipeline"] [data-anim="step"]{opacity:.15}\n  body.low-power #deck{transition:none!important}\n  body.low-power *,\n  body.low-power *::before,\n  body.low-power *::after{animation:none!important;transition:none!important}\n  body.low-power.motion-ready [data-anim],\n  body.low-power [data-anim]{opacity:1!important;transform:none!important}\n\n  /* ---------- 响应式降级 ---------- */\n  @media (max-width:900px){\n    .display{font-size:16vw}\n    .display-zh{font-size:12vw}\n    .h1-zh{font-size:7vw}\n    .h-hero{font-size:14vw}\n    .h-xl{font-size:9vw}\n    .pipeline{grid-template-columns:repeat(2,1fr)}\n    .grid-2-7-5,.grid-2-6-6,.grid-2-8-4{grid-template-columns:1fr}\n  }\n'

_INIT = "\n  (function(){\n    const KEY = 'eink-ppt-low-power'; /* 2026-09-04 去领域残留命名（原 guizang-ppt-low-power） */\n    const OLD_KEY = 'guizang-ppt-low-power';\n    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;\n    let stored = localStorage.getItem(KEY);\n    if (stored === null) { const _old = localStorage.getItem(OLD_KEY); if (_old !== null) { stored = _old; try { localStorage.setItem(KEY, _old); localStorage.removeItem(OLD_KEY); } catch (e) {} } }\n    window.__lowPowerMode = stored === '1' || (stored === null && reduced);\n    function updateHint(){\n      const hint = document.getElementById('hint');\n      if(hint) hint.textContent = `← → 翻页 · B ${window.__lowPowerMode ? '动态' : '静态'} · ESC 索引`;\n    }\n    window.__setLowPowerMode = function(on, opts={}){\n      window.__lowPowerMode = !!on;\n      document.body.classList.toggle('low-power', window.__lowPowerMode);\n      if(opts.persist !== false) localStorage.setItem(KEY, window.__lowPowerMode ? '1' : '0');\n      if(window.__lowPowerMode && document.getAnimations){\n        document.getAnimations().forEach(a=>a.cancel());\n      }\n      updateHint();\n      dispatchEvent(new CustomEvent('ppt-low-power-change', {detail:{on:window.__lowPowerMode}}));\n      if(window.__playSlide) window.__playSlide(window.__currentSlideIndex || 0);\n    };\n    document.body.classList.toggle('low-power', window.__lowPowerMode);\n    addEventListener('DOMContentLoaded', updateHint, {once:true});\n  })();\n"

# ===== M10 分步揭示脚本（2026-08-19）=====
# 前进(右键/滚轮/滑动)的揭示逻辑在 _MOTION 的 __pipeAdvance 导出处（step 优先、回落 pipeline）；
# 本脚本只负责「左键(←/↑/PageUp)回退一段」——capture 监听，先于主 JS 翻页，回退完才允许翻页。
_STEP_JS = r"""
(function(){
  var CACHE=null;
  function slides(){return CACHE||(CACHE=Array.prototype.slice.call(document.querySelectorAll('.slide')));}
  function cur(){var i=window.__currentSlideIndex||0,a=slides();return a[Math.min(i,a.length-1)];}
  function hidePrev(){var c=cur();if(!c)return false;var s=c.querySelectorAll('.step-reveal:not(.hidden)');
    if(s.length){var l=s[s.length-1];l.classList.add('hidden');l.style.display='none';return true;}return false;}
  document.addEventListener('keydown',function(e){
    if(e.key==='ArrowLeft'||e.key==='PageUp'||e.key==='ArrowUp'){if(hidePrev()){e.preventDefault();e.stopPropagation();}}
  },true);
})();
"""


_MOTION = r'''
/* Motion One 由 classic script 加载（<script src="assets/motion.min.js">，见 _MOTION_SRC）。
   2026-09-27 由 ESM 动态 import 改回 classic：file:// 下动态 import 被 CORS 拦掉，
   整段动效初始化（入场 / 数字递增 / M10 分步）会静默失效，只剩静态原值；
   classic script 不受此限，file:// 与 http:// 行为一致。绝不回退任何外部 CDN。
   下面仍留降级分支：assets/ 缺失时静态显示，内容永远可见，不白屏。 */
const motion = window.motion || null;
if(!motion){
  console.warn('[motion] 未加载 motion.min.js（产物缺 assets/ 目录？）——已降级为静态显示');
  document.querySelectorAll('[data-anim]').forEach(el=>{el.style.opacity='1';el.style.transform='none'});
  document.querySelectorAll('[data-animate="pipeline"] [data-anim]').forEach(el=>el.style.opacity='1');
}
if(motion){
  const { animate, stagger } = motion;
  document.body.classList.add('motion-ready');
  const EASE = [.22, 1, .36, 1];
  const slides = [...document.querySelectorAll('.slide')];
  let pipeStep = -1;
  let lastIdx = -1;

  function resetAnims(slide){
    slide.querySelectorAll('[data-anim]').forEach(el=>{
      el.style.opacity='';
      el.style.transform='';
    });
  }

  function revealStatic(slide){
    resetAnims(slide);
    document.getAnimations?.().forEach(a=>a.cancel());
    slide.querySelectorAll('[data-anim]').forEach(el=>{
      el.style.opacity='1';
      el.style.transform='none';
    });
  }

  /* L19 条形图：数字递增。自写 rAF（Motion One 的 onUpdate 不可靠）；
     HTML 里已写终值，低功耗/无 JS 时直接显示正确数字。
     落终值保底（2026-09-27 修复「投屏/切后台时数字冻结成 0万」）：
       递增只是装饰，任何时刻被打断都必须落在终值上，而不是停在 0 或中间值——
       窗口转后台 / 投屏时 rAF 会被节流甚至完全停摆，旧版会永远冻结在那一条 Midnight。
       三重兜底：① 转后台立即落终值；② rAF 停摆时 setTimeout 强制落终值；
                  ③ 递增途中若转后台，下一次回调直接落终值。 */
  const _countUps = new Set();
  function countUp(el, to, delay, dur){
    if(!isFinite(to)) return;
    const dec = (String(to).split('.')[1] || '').length;
    const final = dec ? to.toFixed(dec) : String(to);
    const t0 = performance.now() + delay;
    const rec = { done:false,
      settle:function(){ if(rec.done) return; rec.done=true; el.textContent=final; _countUps.delete(rec); } };
    _countUps.add(rec);
    el.textContent = (0).toFixed(dec);
    function tick(now){
      if(document.hidden){ rec.settle(); return; }
      if(now < t0){ requestAnimationFrame(tick); return; }
      const p = Math.min(1, (now - t0) / dur);
      const e = 1 - Math.pow(1 - p, 3);
      el.textContent = (to * e).toFixed(dec);
      if(p < 1) requestAnimationFrame(tick);
      else rec.settle();
    }
    requestAnimationFrame(tick);
    setTimeout(rec.settle, delay + dur + 400);   // rAF 被节流/停摆时的兜底（delay/dur 单位：毫秒）
  }
  // 切后台：不等下一帧，把还在跑的递增就地落终值
  document.addEventListener('visibilitychange', function(){
    if(!document.hidden) return;
    _countUps.forEach(function(rec){ rec.settle(); });
  });

  /* 入场动画（animate/stagger）的落终值保底（2026-09-27 修复「rAF 停摆时整页永久透明」）。
     countUp 修的是数字，这里修的是文字——同一类故障的另一半：
       CSS 默认态 body.motion-ready [data-anim]{opacity:0}，animate() 靠 rAF 推进；
       rAF 一旦不回调（系统休眠唤醒 / 标签页被浏览器冻结 / 投屏与远程桌面的帧调度异常），
       整页文字就永久停在 opacity 0，内容反而看不见。
     装饰可以丢，内容必须先出来——所以超时强制点亮，不再等动画。
     两重触发：① 翻页后定时器兜底（rAF 停摆时照样会跑）；
               ② 回到前台立刻补一次（被冻结的标签页解冻后不再等满 2.2s）。 */
  function forceVisible(slide){
    if(!slide) return;
    slide.querySelectorAll('[data-anim]').forEach(function(el){
      /* 必须先 cancel 元素上的动画：animate() 走 WAAPI，动画的 fill 状态优先级高于
         inline style，只写 el.style.opacity='1' 会被动画继续压成 0（实测：标签页冻结后
         解冻，元素永久停在 opacity 0）。cancel 掉动画后 inline style 才真正生效。 */
      el.getAnimations?.().forEach(function(a){ try{ a.cancel(); }catch(e){} });
      el.style.opacity='1';
      el.style.transform='none';
    });
  }
  const _guards = new Set();
  const _wrapPlay = function(fn){
    return function(i){
      const r = fn(i);
      const t = setTimeout(function(){ _guards.delete(t); forceVisible(slides[i]); }, 2200);
      _guards.add(t);
      return r;
    };
  };
  document.addEventListener('visibilitychange', function(){
    if(document.hidden) return;
    _guards.forEach(clearTimeout);
    _guards.clear();
    forceVisible(slides[lastIdx]);
  });

  function playSlide(i){
    const slide = slides[i];
    if(!slide) return;
    lastIdx = i;
    const recipe = slide.dataset.animate || (slide.classList.contains('hero') ? 'hero' : 'cascade');

    if(window.__lowPowerMode){
      revealStatic(slide);
      return;
    }

    if(recipe === 'pipeline'){
      pipeStep = -1;
      slide.querySelectorAll('[data-anim="step"]').forEach(el=>{
        el.style.opacity='0.15';
        el.style.transform='none';
      });
      // 非 step 元件（标题/kicker/label 等）立即正常入场，不被压灰（fix 2026-09-13）
      slide.querySelectorAll('[data-anim]:not([data-anim="step"])').forEach(el=>{
        el.style.opacity='1';
        el.style.transform='none';
      });
      return;
    }

    resetAnims(slide);
    const all = [...slide.querySelectorAll('[data-anim]')];
    if(!all.length) return;

    if(recipe === 'directional'){
      const lefts  = all.filter(el=>el.dataset.anim==='left');
      const divs   = all.filter(el=>el.dataset.anim==='divider');
      const rights = all.filter(el=>el.dataset.anim==='right');
      const others = all.filter(el=>!['left','right','divider'].includes(el.dataset.anim));
      if(others.length) animate(others, {opacity:[0,1], y:[12,0]}, {duration:.6, delay:stagger(.1, {start:.15}), easing:EASE});
      if(lefts.length)  animate(lefts,  {opacity:[0,1], x:[-24,0]}, {duration:.8, delay:.35, easing:EASE});
      if(divs.length)   animate(divs,   {opacity:[0,.25]},          {duration:.5, delay:.9});
      if(rights.length) animate(rights, {opacity:[0,1], x:[24,0]},  {duration:.8, delay:1.0, easing:EASE});
      return;
    }

    if(recipe === 'quote'){
      const lines = all.filter(el=>el.dataset.anim==='line');
      const others = all.filter(el=>el.dataset.anim!=='line');
      if(others.length) animate(others, {opacity:[0,1], y:[8,0]},    {duration:.6, delay:stagger(.12, {start:.2}), easing:EASE});
      if(lines.length)  animate(lines,  {opacity:[.35,1], y:[10,0]}, {duration:.8, delay:stagger(.55, {start:.5}), easing:EASE});
      return;
    }

    if(recipe === 'hero'){
      animate(all, {opacity:[0,1], y:[14,0]}, {duration:.9, delay:stagger(.16, {start:.2}), easing:EASE});
      return;
    }

    if(recipe === 'hbar'){
      const bars   = all.filter(el=>el.dataset.anim==='hbar-bar');
      const nums   = all.filter(el=>el.dataset.anim==='hbar-num');
      const others = all.filter(el=>!['hbar-bar','hbar-num'].includes(el.dataset.anim));
      if(others.length) animate(others, {opacity:[0,1], y:[12,0]}, {duration:.6, delay:stagger(.1, {start:.15}), easing:EASE});
      if(bars.length)   animate(bars, {opacity:[0,1], transform:['scaleX(0)','scaleX(1)']}, {duration:.85, delay:stagger(.09, {start:.3}), easing:EASE});
      nums.forEach((el,i)=>{ countUp(el, parseFloat(el.dataset.to||'0'), 320 + i*90, 700); });
      return;
    }
    if(recipe === 'kpitower'){
      const bars  = all.filter(el=>el.dataset.anim==='kpi-bar');
      const nums  = all.filter(el=>el.dataset.anim==='kpi-num');
      const others= all.filter(el=>!['kpi-bar','kpi-num'].includes(el.dataset.anim));
      if(others.length) animate(others,{opacity:[0,1],y:[12,0]},{duration:.6,delay:stagger(.1,{start:.15}),easing:EASE});
      if(bars.length)   animate(bars,{opacity:[0,1],transform:['scaleY(0)','scaleY(1)']},{duration:.9,delay:stagger(.12,{start:.3}),easing:EASE});
      nums.forEach((el,i)=>{ countUp(el, parseFloat(el.dataset.to||'0'), 320 + i*110, 750); });
      return;
    }

    if(recipe === 'loop'){
      const ring  = all.filter(el=>el.dataset.anim==='loop-ring');
      const dots  = all.filter(el=>el.dataset.anim==='loop-dot');
      const nodes = all.filter(el=>el.dataset.anim==='loop-node');
      const steps = all.filter(el=>el.dataset.anim==='loop-step');
      const others= all.filter(el=>!['loop-ring','loop-dot','loop-node','loop-step'].includes(el.dataset.anim));
      if(others.length) animate(others,{opacity:[0,1],y:[12,0]},{duration:.6,delay:stagger(.1,{start:.15}),easing:EASE});
      if(steps.length)  animate(steps,{opacity:[0,1],x:[-14,0]},{duration:.6,delay:stagger(.12,{start:.2}),easing:EASE});
      if(ring.length){
        const C = parseFloat(ring[0].getAttribute('stroke-dasharray')||'816.8');
        animate(ring,{opacity:[0,1],strokeDashoffset:[C,0]},{duration:1.15,delay:.35,easing:EASE});
      }
      if(dots.length)   animate(dots,{opacity:[0,1],scale:[0,1]},{duration:.5,delay:stagger(.18,{start:.85}),easing:EASE});
      if(nodes.length)  animate(nodes,{opacity:[0,1],scale:[0,1]},{duration:.5,delay:stagger(.18,{start:.95}),easing:EASE});
      return;
    }

    if(recipe === 'system'){
      const rings = all.filter(el=>el.dataset.anim==='sys-ring');
      const items = all.filter(el=>el.dataset.anim==='sys-item');
      const others= all.filter(el=>!['sys-ring','sys-item'].includes(el.dataset.anim));
      if(others.length) animate(others,{opacity:[0,1],y:[12,0]},{duration:.6,delay:stagger(.1,{start:.15}),easing:EASE});
      if(rings.length)  animate(rings,{opacity:[0,1],scale:[0,1]},{duration:.9,delay:stagger(.22,{start:.35}),easing:EASE});
      if(items.length)  animate(items,{opacity:[0,1],x:[-14,0]},{duration:.6,delay:stagger(.14,{start:.55}),easing:EASE});
      return;
    }
    if(recipe === 'wall'){
      const tiles = all.filter(el=>el.dataset.anim==='wall-tile');
      const others= all.filter(el=>el.dataset.anim!=='wall-tile');
      if(others.length) animate(others,{opacity:[0,1],y:[12,0]},{duration:.6,delay:stagger(.1,{start:.15}),easing:EASE});
      if(tiles.length)  animate(tiles,{opacity:[0,1],y:[18,0]},{duration:.7,delay:stagger(.15,{start:.3}),easing:EASE});
      return;
    }
    // default: cascade
    animate(all, {opacity:[0,1], y:[16,0]}, {duration:.75, delay:stagger(.1, {start:.15}), easing:EASE});
  }

  function pipeAdvance(){
    if(window.__lowPowerMode) return false;
    const slide = slides[lastIdx];
    if(!slide || slide.dataset.animate !== 'pipeline') return false;
    const steps  = [...slide.querySelectorAll('[data-anim="step"]')];
    const arrows = [...slide.querySelectorAll('[data-anim="arrow"]')];
    if(pipeStep >= steps.length - 1) return false;
    pipeStep++;
    animate(steps[pipeStep], {opacity:[0.15,1], y:[8,0]}, {duration:.5, easing:EASE});
    if(pipeStep > 0 && arrows[pipeStep-1]){
      animate(arrows[pipeStep-1], {opacity:[0.15,.7]}, {duration:.3, delay:.15});
    }
    return true;
  }

  window.__playSlide = _wrapPlay(playSlide);
  /* M10 分步揭示优先(2026-08-19): M10 ||| 分段时, 按右键/滚轮前进先揭示 .step-reveal.hidden, 揭示完才轮到 pipeline 分步动画或翻页 */
  const _basePipeAdvance = pipeAdvance;
  window.__pipeAdvance = function(){
    const _c = document.querySelectorAll('.slide')[window.__currentSlideIndex||0];
    if(_c){
      const _h = _c.querySelector('.step-reveal.hidden');
      if(_h){ _h.classList.remove('hidden'); _h.style.display='block'; return true; }
    }
    return _basePipeAdvance();
  };

  // 首屏:go(0) 已跑过(同步),没来得及触发动效 → 这里补一下
  playSlide(0);
}
'''


# 常量（本地资源，随引擎固化在 eink_assets/，build() 时拷到 <out>/assets/，完全离线、无 CDN 供应链风险）
# 动效库同样走 classic script（2026-09-27 由 ESM 动态 import 改回）：
# file:// 下 classic script 可加载同目录 js（lucide 早如此），动效不再静默失效；
# 产物里缺 assets/ 时 window.motion 为 undefined，_MOTION 段有静态降级分支兜住。
_LUCIDE_SRC  = '<script src="assets/lucide.umd.min.js"></script>'
_MOTION_SRC  = '<script src="assets/motion.min.js"></script>'
_LUCIDE_INIT = "<script>if(window.lucide) lucide.createIcons();</script>"  # 守卫：资产缺失时不抛 ReferenceError（2026-09-04 批次C）
_CANVASES    = ('<canvas id="bg-dark" class="bg"></canvas>\n<canvas id="bg-light" class="bg"></canvas>\n<div id="hint">← → 翻页 · B 静态 · ESC 索引</div>')

# ===== Deck 脚本：WebGL 双背景 + 导航（翻页 / 圆点 / 键盘 / 滚轮 / 触屏 / ESC 索引 / 分步前进） =====
# 2026-09-04 恢复：此段在 09-03 修复轮被误删（回归事故），已从 09-02 渲染产物原样抠回；
# 同日（老陈裁定选 A 成套恢复）WebGL 双背景段一并回归——canvas 元素 + CSS + GL 脚本三件套齐，
# 与 09-02 产物结构一致（WebGL 段在前、导航段在后，同一 <script> 内）。
_DECK_JS = r'''
/* =============== WebGL 双背景 ===============
   深色页：Holographic Dispersion（全息色散 · 钛金暗流）—— 彩虹微扰、鼠标径向涟漪
   浅色页：Spiral Vortex（旋转涡流 · 银色珍珠）—— domain-warp 流动、无中心
   修改风格请参考 references/webgl-backgrounds.md
*/
const VS = `attribute vec2 position;void main(){gl_Position=vec4(position,0.0,1.0);}`;

const FS_DARK = `precision highp float;
uniform vec2 u_resolution;uniform float u_time;uniform vec2 u_mouse;
uniform vec3 u_ink;uniform vec3 u_accent;
vec3 palette(float t,vec3 a,vec3 b,vec3 c,vec3 d){return a+b*cos(6.28318*(c*t+d));}
void main(){
  vec2 uv=gl_FragCoord.xy/u_resolution.xy;
  vec2 p=uv*2.0-1.0;p.x*=u_resolution.x/u_resolution.y;
  vec2 m=u_mouse*2.0-1.0;m.x*=u_resolution.x/u_resolution.y;
  float md=length(p-m);
  float mr=sin(md*15.0-u_time*4.0)*exp(-md*3.0);p+=mr*0.08;
  vec2 p0=p;
  for(float i=1.0;i<4.0;i++){
    p.x+=0.1/i*sin(i*3.0*p.y+u_time*0.4)+0.05;
    p.y+=0.1/i*cos(i*2.0*p.x+u_time*0.3)-0.05;
  }
  float r=length(p);float ang=atan(p.y,p.x);
  vec3 a=vec3(0.12,0.12,0.13);
  vec3 b=vec3(0.03,0.04,0.05);
  vec3 c=vec3(1.0,1.0,1.0);
  vec3 d=u_accent;
  vec3 col=palette(r*1.5+p0.x*0.5+u_time*0.1,a,b,c,d);
  float disp=sin(r*25.0-u_time*1.5+ang*2.0)*0.5+0.5;
  col+=vec3(disp*0.015,disp*0.01,disp*0.02);
  float hi=pow(sin(p.x*4.0+p.y*3.0+u_time)*0.5+0.5,8.0);
  col+=hi*0.08;
  vec3 base=u_ink*0.20;
  col=mix(base,col,0.85);
  gl_FragColor=vec4(col,1.0);
}`;

const FS_LIGHT = `precision highp float;
uniform vec2 u_resolution;uniform float u_time;uniform vec2 u_mouse;
uniform vec3 u_paper;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise(vec2 p){
  vec2 i=floor(p),f=fract(p);
  float a=hash(i),b=hash(i+vec2(1,0));
  float c=hash(i+vec2(0,1)),d=hash(i+vec2(1,1));
  vec2 u=f*f*(3.0-2.0*f);
  return mix(a,b,u.x)+(c-a)*u.y*(1.0-u.x)+(d-b)*u.x*u.y;
}
float fbm(vec2 p){
  float v=0.0,a=0.5;
  mat2 m=mat2(0.80,0.60,-0.60,0.80);
  for(int i=0;i<5;i++){v+=a*noise(p);p=m*p*2.02;a*=0.5;}
  return v;
}
void main(){
  vec2 uv=gl_FragCoord.xy/u_resolution.xy;
  vec2 p=uv;p.x*=u_resolution.x/u_resolution.y;
  vec2 m=u_mouse;m.x*=u_resolution.x/u_resolution.y;
  vec2 md=p-m;float dl=length(md);
  p+=normalize(md+vec2(0.0001))*exp(-dl*5.0)*0.03;
  vec2 q=vec2(fbm(p*1.8+u_time*0.07),fbm(p*1.8+vec2(5.2,1.3)+u_time*0.06));
  vec2 r=vec2(fbm(p*2.0+q*1.3+vec2(1.7,9.2)+u_time*0.05),
              fbm(p*2.0+q*1.3+vec2(8.3,2.8)+u_time*0.04));
  float f=fbm(p*2.2+r*1.5);
  vec3 silverDark=vec3(0.86,0.85,0.84);
  vec3 paper=u_paper;
  vec3 col=mix(silverDark,paper,f);
  float ph=r.x*2.2+u_time*0.35;
  col+=vec3(0.78,0.62,0.92)*sin(ph)*0.055;
  col+=vec3(0.55,0.72,0.95)*sin(ph*0.8+2.0)*0.05;
  float hl=smoothstep(0.48,0.92,f);
  col+=hl*0.06;
  gl_FragColor=vec4(col,1.0);
}`;

const mouse={x:0.5,y:0.5};
addEventListener('mousemove',e=>{mouse.x=e.clientX/innerWidth;mouse.y=e.clientY/innerHeight});

function bootGL(canvasId, fsSrc){
  const canvas=document.getElementById(canvasId);
  const gl=canvas.getContext('webgl',{alpha:false,antialias:true});
  if(!gl) return ()=>false;
  const mk=(t,s)=>{const sh=gl.createShader(t);gl.shaderSource(sh,s);gl.compileShader(sh);return sh};
  const prog=gl.createProgram();
  gl.attachShader(prog,mk(gl.VERTEX_SHADER,VS));
  gl.attachShader(prog,mk(gl.FRAGMENT_SHADER,fsSrc));
  gl.linkProgram(prog);gl.useProgram(prog);
  const buf=gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER,buf);
  gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);
  const pos=gl.getAttribLocation(prog,'position');
  gl.enableVertexAttribArray(pos);gl.vertexAttribPointer(pos,2,gl.FLOAT,false,0,0);
  const lRes=gl.getUniformLocation(prog,'u_resolution');
  const lT=gl.getUniformLocation(prog,'u_time');
  const lM=gl.getUniformLocation(prog,'u_mouse');
  const lInk=gl.getUniformLocation(prog,'u_ink');
  const lAcc=gl.getUniformLocation(prog,'u_accent');
  const lPaper=gl.getUniformLocation(prog,'u_paper');
  const resize=()=>{
    const d=Math.min(window.devicePixelRatio||1,2);
    canvas.width=innerWidth*d;canvas.height=innerHeight*d;
    gl.viewport(0,0,canvas.width,canvas.height);
  };
  addEventListener('resize',resize);resize();
  return (tSec)=>{
    gl.uniform2f(lRes,canvas.width,canvas.height);
  gl.uniform3f(lInk,__INK01__);gl.uniform3f(lAcc,__ACC01__);gl.uniform3f(lPaper,__PAPER01__);
    gl.uniform1f(lT,tSec);
    gl.uniform2f(lM,mouse.x,1-mouse.y);
    gl.drawArrays(gl.TRIANGLES,0,6);
    return true;
  };
}
let drawDark=null, drawLight=null, glRAF=0, glT0=Date.now();
function startGL(){
  if(window.__lowPowerMode || glRAF) return;
  if(!drawDark) drawDark=bootGL('bg-dark',FS_DARK);
  if(!drawLight) drawLight=bootGL('bg-light',FS_LIGHT);
  glT0=Date.now();
  function loop(){
    if(window.__lowPowerMode){glRAF=0;return;}
    const t=(Date.now()-glT0)/1000;
    drawDark(t);drawLight(t);
    glRAF=requestAnimationFrame(loop);
  }
  glRAF=requestAnimationFrame(loop);
}
function stopGL(){
  if(glRAF) cancelAnimationFrame(glRAF);
  glRAF=0;
}
startGL();
addEventListener('ppt-low-power-change', e=>{e.detail.on ? stopGL() : startGL();});

const deck=document.getElementById('deck');
const slides=deck.querySelectorAll('.slide');
const nav=document.getElementById('nav');
let idx=0,total=slides.length,lock=false;

// 关键：矫正 deck 宽度为 total * 100vw，否则翻页会错位
deck.style.width=(total*100)+'vw';

slides.forEach((s,i)=>{
  const b=document.createElement('button');
  b.className='dot';b.dataset.i=i;b.setAttribute('aria-label','Page '+(i+1));
  b.onclick=()=>go(i);
  nav.appendChild(b);
});

function go(n){
  if(lock)return;
  idx=Math.max(0,Math.min(total-1,n));
  window.__currentSlideIndex = idx;
  deck.style.transform=`translateX(${-idx*100}vw)`;
  nav.querySelectorAll('.dot').forEach((d,i)=>d.classList.toggle('active',i===idx));
  /* 主题切换：优先读 data-theme，其次从 class（light/dark）推断 */
  const el=slides[idx];
  const th=el.dataset.theme || (el.classList.contains('light')?'light':(el.classList.contains('dark')?'dark':'dark'));
  document.body.classList.toggle('light-bg',th==='light');
  /* 动效：翻页过渡中段触发当前页的入场动画（由 motion-boot 注册） */
  if(window.__playSlide) setTimeout(()=>window.__playSlide(idx), 450);
  lock=true;setTimeout(()=>lock=false,700);
}

/* =============== ESC 索引视图 =============== */
let overviewOn=false;
const ov=document.createElement('div');
ov.id='overview';
ov.style.cssText='position:fixed;inset:0;z-index:100;background:rgba(var(--ink-rgb),.92);backdrop-filter:blur(12px);display:none;overflow-y:auto;padding:4vh 4vw';
document.body.appendChild(ov);

function buildOverview(){
  ov.innerHTML='';
  const grid=document.createElement('div');
  grid.style.cssText='display:grid;grid-template-columns:repeat(4,1fr);gap:2vh 1.6vw;max-width:90vw;margin:0 auto';
  slides.forEach((s,i)=>{
    const card=document.createElement('div');
    card.style.cssText='cursor:pointer;border-radius:6px;overflow:hidden;border:2px solid '+(i===idx?'rgba(var(--paper-rgb),.8)':'rgba(var(--paper-rgb),.15)')+';transition:border-color .2s';
    card.onmouseenter=()=>card.style.borderColor='rgba(var(--paper-rgb),.6)';
    card.onmouseleave=()=>card.style.borderColor=i===idx?'rgba(var(--paper-rgb),.8)':'rgba(var(--paper-rgb),.15)';
    const wrap=document.createElement('div');
    wrap.style.cssText='width:100%;aspect-ratio:16/9;overflow:hidden;position:relative;pointer-events:none;background:'+(s.classList.contains('light')?'var(--paper)':'var(--ink)');
    const clone=s.cloneNode(true);
    clone.style.cssText='width:100vw;height:100vh;transform:scale('+(1/4.5)+');transform-origin:top left;position:absolute;top:0;left:0;pointer-events:none';
    wrap.appendChild(clone);
    const label=document.createElement('div');
    label.style.cssText='padding:6px 10px;font-family:var(--mono);font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:var(--paper);opacity:.7';
    label.textContent=(i+1)+' / '+total;
    card.appendChild(wrap);
    card.appendChild(label);
    card.onclick=()=>{toggleOverview();go(i)};
    grid.appendChild(card);
  });
  ov.appendChild(grid);
}

function toggleOverview(){
  overviewOn=!overviewOn;
  if(overviewOn){buildOverview();ov.style.display='block';}
  else{ov.style.display='none';}
}

/* M10 分步揭示（基础版，v2.4.1 起无条件定义，不依赖 motion）：
   __pipeAdvance 基础版在此（普通 script，早于 _MOTION 执行）无条件定义，
   step-reveal 揭示不依赖任何外部加载；motion 可用时，_MOTION 尾部
   仍会覆盖为「step 优先、回落 pipeline」的完整版。 */
window.__pipeAdvance = function(){
  const _c = document.querySelectorAll('.slide')[window.__currentSlideIndex||0];
  if(_c){
    const _h = _c.querySelector('.step-reveal.hidden');
    if(_h){ _h.classList.remove('hidden'); _h.style.display='block'; return true; }
  }
  return false;
};

addEventListener('keydown',e=>{
  if(e.key==='Escape'){e.preventDefault();toggleOverview();return;}
  if(e.key && e.key.toLowerCase()==='b' && !e.metaKey && !e.ctrlKey && !e.altKey){
    e.preventDefault();
    window.__setLowPowerMode(!window.__lowPowerMode);
    return;
  }
  if(overviewOn)return;
  if(e.key==='ArrowRight'||e.key==='PageDown'||e.key===' '||e.key==='ArrowDown'){
    if(window.__pipeAdvance && window.__pipeAdvance()) return;
    go(idx+1);
    return;
  }
  if(e.key==='ArrowLeft'||e.key==='PageUp'||e.key==='ArrowUp')go(idx-1);
  if(e.key==='Home')go(0);
  if(e.key==='End')go(total-1);
});

let wheelTO=null,wheelAcc=0;
addEventListener('wheel',e=>{
  wheelAcc+=e.deltaY+e.deltaX;
  if(Math.abs(wheelAcc)>50){
    if(wheelAcc>0 && window.__pipeAdvance && window.__pipeAdvance()){
      wheelAcc=0;
    }else{
      go(idx+(wheelAcc>0?1:-1));wheelAcc=0;
    }
  }
  clearTimeout(wheelTO);wheelTO=setTimeout(()=>wheelAcc=0,150);
},{passive:true});

let tx=0,ty=0;
addEventListener('touchstart',e=>{tx=e.touches[0].clientX;ty=e.touches[0].clientY},{passive:true});
addEventListener('touchend',e=>{
  const dx=(e.changedTouches[0].clientX-tx);
  const dy=(e.changedTouches[0].clientY-ty);
  if(Math.abs(dx)>50&&Math.abs(dx)>Math.abs(dy)){
    if(dx<0 && window.__pipeAdvance && window.__pipeAdvance()) return;
    go(idx+(dx<0?1:-1));
  }
},{passive:true});

go(0);

/* M16 参考链接：键盘聚焦后按空格/回车会同时「激活链接 + 触发翻页」；
   给 .ilink 拦截 keydown 并 stopImmediatePropagation，化解冲突（鼠标点击本就不翻页）。
   stopImmediatePropagation 比 stopPropagation 更彻底：连同一元素上的其他 keydown 监听器也不再执行（2026-09-06 修复）。 */
document.querySelectorAll('a.ilink').forEach(a=>{
  a.addEventListener('keydown',e=>{
    if(e.key===' '||e.key==='Enter'){ e.preventDefault(); e.stopImmediatePropagation(); }
  });
});
'''

# 追加样式（底座没有的新版式 / 增强；符合规范 §0/§2）
_CSS_EXTRA = """
/* ===== 双基线布局：标题区固定预留两行高，正文从固定行线起向下生长 =====
   由 _apply_dual 在后处理时自动把 kicker+标题包进 .head-block；frame 本身已 flex-start。 */
/* ===== 居中版式修复 + L27玻璃底 + L19深色/限宽 + 底部同行 + chain/callout贴底 ===== */
/* A. .frame.center 复合选择器：特异性(0,2,0)高于 .frame(flex-start)，恢复封面/扉页/金句/收束/互动垂直居中 */
.frame.center{justify-content:center;align-items:center;text-align:center}
/* B. L27 悬浮标题：半透明同主题玻璃底（替代不透明纸色块），深浅页各自协调；side 模式本就无背景 */
.ih-title-l27{background:rgba(238,223,199,.80);backdrop-filter:blur(6px) saturate(1.1);-webkit-backdrop-filter:blur(6px) saturate(1.1)}
.slide.dark .ih-title-l27{background:rgba(58,42,29,.72);color:var(--paper)}
.slide.dark .ih-title-l27 .h-xl,.slide.dark .ih-title-l27 .h-xl-line{color:var(--paper)}
.imagehero-l27.side .ih-title-l27{background:none;backdrop-filter:none;-webkit-backdrop-filter:none}
/* C-a. L19 深色数字：.hbar-val 写死 --ink，深底上补 paper（label 用 currentColor 无需覆盖） */
.slide.dark .hbar-val{color:var(--paper)}
/* C-c. L19 图表整体限宽居中，配合最长条 72% 封顶形成右侧留白 */
.hbar-list{width:68%;max-width:1100px;align-self:flex-start}
.slide.dark .hbar-track{background:rgba(var(--paper-rgb),.16)}
/* D. M13/M14 同处底部一行（两端对齐），替代上下错层；M13 自身虚线并入本行顶部 */
.aux-row{display:flex;justify-content:space-between;align-items:flex-end;gap:3vw;border-top:1px dashed currentColor;padding-top:1vh;margin-top:2.4vh}
.aux-row .annot{border-top:none;padding-top:0;margin-top:0;max-width:72%}
/* E. L12b 链条 / L10 引文框：标题区以下的内容空间内垂直居中（margin auto 上下均分），水平保持居中 */
.chain.chain-bottom{margin-top:auto;margin-bottom:auto;justify-content:safe center}
.callout.callout-bottom{margin-top:auto;margin-bottom:auto;align-self:center;max-width:78%}

.kicker:empty{display:none}
.head-block{flex:0 0 auto;min-height:var(--head-h,22vh);display:flex;flex-direction:column}
.head-block.head-1{justify-content:center}      /* 一行标题：区内上下居中，不贴眉标 */
.head-block.head-2{justify-content:flex-start} /* 两行标题：顶对齐、上下分布填满 */
.h-xl{font-size:5.4vw}                          /* 内页标题统一 5.4vw（覆盖底座 6.2vw） */
.h-xl-line{font-size:5.4vw}
.frame[class*="grid-2"]>.col .h-xl,.frame[class*="grid-2"]>.col .h-xl-line{font-size:clamp(24px,4.5vw,68px);line-height:1.1}
/* L16 文字标牌 stat-note：中文描述放大居中（接近 stat-card 但不带数字；优化意见(一)5） */
.stat-note-l16{font-family:var(--sans-zh);font-weight:400;font-size:clamp(17px,2vw,34px);line-height:1.6;text-align:left;color:var(--ink);opacity:.82;padding-left:1.4vw;border-left:2px solid var(--paper-tint);margin-bottom:1.2vh;}
/* dark 主题（accent 暗页）覆盖：否则深墨字落在深底上完全看不见（修复深色页 notes 不可见） */
.slide.dark .stat-note-l16{color:var(--paper);}
/* L16 首末条 accent 点睛（降级后仍保留一处强调，收束判断；配合 p_statnote 的 accent-note class） */
.stat-note-l16.accent-note{color:var(--accent);border-left-color:var(--accent);opacity:1;}
.slide.dark .stat-note-l16.accent-note{color:var(--accent-ink);}

/* L07 金句三段字号（长句更可读、短句更醒目；D 规划 P0） */
.q-big.q-short{font-size:max(26px,5.2vw);line-height:1.32;}
.q-big.q-long{font-size:max(20px,4.2vw);line-height:1.46;}
.q-big.q-std{font-size:max(22px,2.8vw);line-height:1.4;}

/* ===== L24 论断陈述（吸收 S03 之魂：一句核心判断；但用中文衬线粗体+强左轴+大留白+发丝线，
   不用瑞士 weight-200 在牛皮纸上显弱。承载「单句强判断」场景，与 L16 降级版分工） ===== */
.statement-l24{font-family:var(--serif-zh);font-weight:700;font-size:clamp(28px,5.2vw,84px);line-height:1.32;text-align:left;color:var(--ink);letter-spacing:.01em;max-width:82vw;border-left:3px solid var(--accent);padding-left:2.2vw;}
.slide.dark .statement-l24{color:var(--paper);border-left-color:var(--accent-ink);}
.stat-sub-l24{font-family:var(--sans-zh);font-size:max(14px,1.15vw);opacity:.8;margin-top:2.4vh;max-width:64vw;line-height:1.7;}

/* ===== L25 横向时间轴（轻于 L06/L12b：1px 线 + 8×8 方节点 + 等宽年份在上） ===== */
.timeline-l25{display:flex;justify-content:space-between;align-items:stretch;margin-top:7vh;flex:1;min-height:0;}
.tl-item-l25{flex:1;display:flex;flex-direction:column;align-items:center;padding:0 .8vw;}
.tl-year-l25{font-family:var(--mono);font-size:max(13px,1.05vw);opacity:.7;letter-spacing:.05em;margin-bottom:2.4vh;height:1.2em;line-height:1.2;}
.tl-noderow-l25{width:100%;height:0;position:relative;display:flex;align-items:center;justify-content:center;}
.tl-axis-l25{position:absolute;left:-1px;right:-1px;top:50%;transform:translateY(-50%);height:1px;background:currentColor;opacity:.32;z-index:1;}
.tl-node-l25{width:8px;height:8px;background:var(--accent);position:relative;z-index:2;}
.tl-title-l25{font-family:var(--serif-zh);font-weight:700;font-size:clamp(15px,1.5vw,23px);line-height:1.25;margin-top:2.4vh;margin-bottom:.6vh;min-height:2.5em;display:flex;align-items:center;justify-content:center;}
.tl-desc-l25{font-family:var(--sans-zh);font-size:max(12px,1vw);opacity:.78;line-height:1.5;max-width:18vw;text-align:center;}

/* ===== L26 微卡矩阵（吸 S16：3×2，每卡左上主句+右下小注，仅一处 accent 点睛） ===== */
.microcard-grid-l26{display:grid;grid-template-columns:repeat(3,1fr);grid-template-rows:repeat(2,1fr);gap:1.6vh 1.6vw;flex:1;min-height:0;margin-top:3vh;}
.mc-l26{border:1px solid rgba(42,30,19,.25);border-radius:8px;padding:2vh 1.4vw;display:flex;flex-direction:column;justify-content:space-between;background:rgba(238,223,199,.35);}
.mc-l26 .mc-main{font-family:var(--serif-zh);font-weight:700;font-size:clamp(17px,2vw,32px);line-height:1.25;color:var(--ink);}
.mc-l26 .mc-sub{font-family:var(--sans-zh);font-size:max(12px,1vw);opacity:.72;text-align:right;align-self:flex-end;margin-top:1.6vh;line-height:1.4;}
.mc-l26.accent{border-color:var(--accent);background:rgba(0,0,0,.04);}
.mc-l26.accent .mc-main{color:var(--accent);}
.slide.dark .mc-l26{background:rgba(255,255,255,.06);border-color:rgba(255,255,255,.25);}
.slide.dark .mc-l26 .mc-main{color:var(--paper);}
.slide.dark .mc-l26.accent{border-color:var(--accent-ink);background:rgba(255,255,255,.1);}
.slide.dark .mc-l26.accent .mc-main{color:var(--accent-ink);}

/* ===== L27 图幅主导（吸 S22：全出血图 + 居左悬浮标题块 + 图注 + 3列KPI；.side=竖图模式） ===== */
.imagehero-l27{position:absolute;inset:0;display:flex;flex-direction:column;}
.ih-top-l27{position:relative;flex:0 0 58%;overflow:hidden;}
.ih-img-l27{width:100%;height:100%;object-fit:cover;display:block;}
/* 图顶渐变 scrim，保证浮层眉标可读 */
.ih-top-l27::before{content:"";position:absolute;inset:0;z-index:1;pointer-events:none;background:linear-gradient(180deg,rgba(0,0,0,.46) 0%,rgba(0,0,0,.12) 32%,rgba(0,0,0,0) 56%);}
/* L27 信息图模式（contain/fit，2026-09-15）：图是需完整阅读的信息图（时间轴/地图/图表）——
   标题不再悬浮遮挡、落下方纸色区；scrim 弱化为仅保顶部 M01 眉标可读（16% 轻渐变）。 */
.imagehero-l27.infographic .ih-title-l27{position:static;max-width:none;background:none;backdrop-filter:none;-webkit-backdrop-filter:none;padding:3.4vh 6vw 0;}
.imagehero-l27.infographic .ih-title-l27 .kicker{color:var(--ink);opacity:.6;}
.imagehero-l27.infographic .ih-title-l27 .h-xl{color:var(--ink);}
.slide.dark .imagehero-l27.infographic .ih-title-l27{color:var(--paper);}
.slide.dark .imagehero-l27.infographic .ih-title-l27 .h-xl{color:var(--paper);}
.slide.dark .imagehero-l27.infographic .ih-title-l27 .kicker{color:var(--paper);opacity:.6;}
.imagehero-l27.infographic .ih-bottom-l27{padding-top:1.8vh;}
.imagehero-l27.infographic .ih-top-l27::before{background:linear-gradient(180deg,rgba(0,0,0,.32) 0%,rgba(0,0,0,0) 16%);}
.ih-side-l27{flex:1;display:flex;flex-direction:column;min-height:0;}
/* 标题：横幅模式 = 居左悬浮纸色小块，浮于图上（不再通栏压底切断图） */
.ih-title-l27{position:absolute;left:4vw;top:8.5vh;z-index:4;max-width:46vw;background:var(--paper);padding:2.4vh 2.1vw;}
.ih-title-l27 .kicker{margin-bottom:.7vh;color:var(--ink);opacity:.6;}
.ih-title-l27 .h-xl{font-size:clamp(20px,2.8vw,44px);line-height:1.14;color:var(--ink);}
.ih-bottom-l27{flex:1;display:flex;flex-direction:column;justify-content:center;gap:2.2vh;padding:3vh 6vw 4vh;min-height:0;}
.ih-cap-l27{font-family:var(--sans-zh);font-size:max(13px,1.05vw);opacity:.8;line-height:1.65;max-width:62vw;}
.ih-kpis-l27{display:grid;grid-template-columns:repeat(3,1fr);gap:3vw;}
.ih-kpi-l27{display:flex;flex-direction:column;gap:.7vh;border-top:1px solid rgba(127,127,127,.3);padding-top:1.4vh;}
.ih-kpi-v-l27{font-family:var(--serif-zh);font-weight:800;font-size:clamp(22px,3vw,46px);color:var(--accent);line-height:1;}
.slide.dark .ih-kpi-v-l27{color:var(--accent-ink);}
.ih-kpi-l-l27{font-family:var(--sans-zh);font-size:max(12px,1vw);opacity:.78;}
/* 外层 chrome 浮于全出血图顶（白字），foot 隐藏（信息已并入顶部/KPI） */
.slide:has(.imagehero-l27) .chrome{position:absolute;top:4.4vh;left:6vw;right:6vw;z-index:6;color:rgba(255,255,255,.92);}
.slide:has(.imagehero-l27) .foot{display:none;}
/* —— .side 竖图模式：图占左侧全高（contain 不裁），右侧纵向 title+bottom，标题不悬浮 —— */
.imagehero-l27.side{flex-direction:row;}
.imagehero-l27.side .ih-top-l27{flex:0 0 40%;height:100%;}
.imagehero-l27.side .ih-img-l27{object-fit:contain;background:rgba(0,0,0,.04);}
.slide.dark .imagehero-l27.side .ih-img-l27{background:rgba(255,255,255,.05);}
.imagehero-l27.side .ih-side-l27{flex:1;}
.imagehero-l27.side .ih-title-l27{position:static;max-width:none;background:none;padding:3.6vh 4vw 0;}
.imagehero-l27.side .ih-title-l27 .kicker{color:inherit;}
.imagehero-l27.side .ih-title-l27 .h-xl{color:inherit;font-size:clamp(22px,3.2vw,50px);}
.imagehero-l27.side .ih-bottom-l27{padding:2vh 4vw 4vh;justify-content:flex-start;}
/* side 模式隐藏右上讲题（右侧为主题底，白字会不可见），仅留 M01 白字浮图左上 */
.slide:has(.imagehero-l27.side) .chrome > div:last-child{display:none;}

/* ===== 页面级固定元件（任意版式可挂，引擎在 .frame 末尾统一注入） ===== */
/* M10 正文/小字：结构化版式不原生渲染 body 时，由引擎补挂，根治小字被吞 */
.body-fixed{font-family:var(--sans-zh);font-size:max(15px,1.22vw);line-height:1.7;color:var(--ink);opacity:.82;}
/* dark 页覆盖：修复 M10 补挂正文在深色页不可见（同 stat-note-l16 修复模式） */
.slide.dark .body-fixed{color:var(--paper);}
/* M11 引文作为固定元件（非 standalone callout 页时，底部挂引文框） */
.callout-fixed{font-family:var(--serif-zh);border-left:3px solid var(--accent);padding:.4vh 0 .4vh 1.2vw;max-width:62vw;}
.callout-fixed .q-big{font-size:max(17px,1.6vw);line-height:1.5;font-weight:600;}
.callout-fixed .callout-src{display:block;margin-top:1vh;font-family:var(--sans-zh);font-size:max(12px,.95vw);opacity:.6;}
/* M16 参考链接框（页面级，底部 slide-aux；新标签打开，accent 描边） */
.links-fixed{display:flex;align-items:baseline;flex-wrap:wrap;gap:.5em 1.4em;max-width:74vw;border-top:1px dashed var(--accent);padding-top:1.2vh;margin-top:2.4vh;font-family:var(--sans-zh);opacity:.9;}
.links-fixed .links-h{font-family:var(--yahei);font-weight:700;font-size:max(12px,.95vw);letter-spacing:.1em;color:var(--accent);white-space:nowrap;}
.slide.dark .links-fixed .links-h{color:var(--accent-ink);}
.links-fixed .links-list{display:flex;flex-direction:column;gap:.5vh;flex:1;}
.ilink{color:var(--accent);text-decoration:underline;text-underline-offset:2px;font-weight:600;transition:opacity .15s;}
.ilink:hover{opacity:.7;}
.slide.dark .ilink{color:var(--accent-ink);}
.ilink-text{opacity:.78;}
/* M13 注释（页面级小注） */
.annot{font-family:var(--sans-zh);font-size:max(13px,1vw);opacity:.6;line-height:1.6;max-width:64vw;border-top:1px dashed currentColor;padding-top:1vh;margin-top:2.4vh;}
/* M14 下标/出处（默认右对齐，可在大纲用 M14 对齐: 左/中/右 调整） */
.footnote{font-family:var(--sans-zh);font-size:max(12px,.95vw);opacity:.62;margin-top:2.4vh;}
.footnote.left{text-align:left;} .footnote.center{text-align:center;} .footnote.right{text-align:right;}
/* 设计指令占位（引擎按「设计:」标记渲染，待我按描述生成真实 SVG/版式后替换） */
.design-note{font-family:var(--sans-zh);font-size:max(13px,1vw);opacity:.78;border:1px dashed var(--accent);border-radius:6px;padding:2vh 2vw;  margin-top:3vh;max-width:66vw;color:var(--ink);line-height:1.7;}
/* dark 页覆盖：修复「设计:」占位注在深色页不可见 */
.slide.dark .design-note{color:var(--paper);}
.design-note b{color:var(--accent);}

/* ===== M11 引文出处 callout-src：默认右对齐 ===== */
.callout-src{display:block;text-align:right;}
/* ===== 下标字号档位（M14 字号: 大/小） ===== */
.footnote.size-lg{font-size:max(15px,1.25vw);}
.footnote.size-sm{font-size:max(10px,.8vw);}
/* ===== 注释字号档位（M13 字号: 大/小） ===== */
.annot.size-lg{font-size:max(20px,1.7vw);}
.annot.size-sm{font-size:max(11px,.9vw);}
/* ===== 正文块字号档位（M10 <size=大/小>） ===== */
.body-zh.size-lg{font-size:max(19px,1.5vw);}
.body-zh.size-sm{font-size:max(12px,1vw);}
/* ===== M06 两行 hero：逐行（居左/居右 等） ===== */
.h-hero-line{font-family:var(--serif-zh);font-weight:800;font-size:clamp(32px,10vw,140px);line-height:1.08;}
/* M08 h_xl 多行（用 / 分行）+ 逐行对齐(左/中/右) + 逐行字号(大/小) */
.h-xl-line{font-family:var(--serif-zh);font-weight:700;font-size:clamp(26px,6.2vw,96px);line-height:1.12;margin-top:1.4vh;}
.h-xl-line.size-lg{font-size:clamp(32px,7.6vw,120px);}
.h-xl-line.size-sm{font-size:clamp(18px,3.6vw,56px);}
/* 主题自适应前景色（关键修复：hero/dark 页用纸色，light 页用墨色；依赖 .slide 的 color 继承，这里显式兜底，根治"文字与背景同色隐身"） */
.slide.dark .h-hero-line,.slide.dark .h-xl-line{color:var(--paper);}
.slide.light .h-hero-line,.slide.light .h-xl-line{color:var(--ink);}
/* 内联 SVG 自适应宽度（P12/P21 等真实示意图） */
/* 2026-09-04 收敛：fig-svg 有两条规则，服务于不同 DOM 层级，均为必需 ——
     figure.fig-svg > svg：svg 直挂 figure（p_figsvg 结构）；
     .fig-svg svg      ：figure > div > svg（_img_figure 结构）。
     两条的兜底上限已统一为 58vh；页面用 M12 maxh 时由内联 max-height 优先覆盖。 */
.fig-svg svg{width:100%;height:auto;max-height:58vh;display:block;}
/* 真实配图（M12 文件: 存在）去掉全部装饰：虚线边框 + 实线内框(::before) + 占位框 padding；
   仅缺图占位（.img-slot 无 has-img）保留虚线框 +（+）提示（根治 P07/P11 真实图外仍套虚线/实线框，2026-08-19） */
.img-slot.has-img{border:0;padding:0;min-height:0;flex-shrink:1;}
.img-slot.has-img::before{display:none;}
/* 2026-09-11 根治：含图 figure 作 .slide(flex 列,100vh+overflow:hidden) 子项时，
   默认 min-height:auto 取 img 自然高、阻止压缩，宽屏下「图+标题+说明」总高超 100vh
   被 overflow:hidden 裁掉下半（img 本为 object-fit:contain，非裁切）。加 min-height:0;flex-shrink:1
   使其可在 flex 列内收缩到剩余空间，contain 保证整图完整。影响所有图文同页 deck 宽屏显示。 */

/* ===== 强调锚点 accent：主题强调色 + 加粗 + 比邻字大 1.2 倍 ===== */
.accent{font-weight:700;font-size:1.2em;color:var(--accent);}
.slide.dark .accent{color:var(--accent-ink);}
.stat-nb.accent{font-size:inherit;font-weight:700;}  /* 数据大字报里强调只加红+粗，不放大避免破版 */
/* ===== 行内局部放大 <size=大/中/小>...</size> ===== */
.sz-大{font-size:1.3em;font-weight:700;}
.sz-中{font-size:1.1em;}
.sz-小{font-size:.85em;}
/* ===== 行内弱化 <dim>...</dim> =====
   用 opacity 而非色值：随 currentColor 走，明暗页与 5 套主题都成立，写死灰色会撞主题。
   取值 .5 与 .foot(.5)/.chrome(.62) 同一套信息层级语汇；父元素已有 opacity 时会相乘，视觉上自然更弱。 */
.dim{opacity:.5}
/* ===== 行内图标 <ico=name>（替代 emoji，Lucide 渲染） ===== */
.ico-inline{display:inline-block;width:1em;height:1em;vertical-align:-0.15em;color:var(--accent);margin-right:.15em;}
.slide.dark .ico-inline{color:var(--accent-ink);}

/* ===== 底部固定元件容器：独立于 .frame，钉在 .slide 底部，永不被 .frame 溢出裁切（根治 P02/P07 脚注溢出） ===== */
.slide-aux{flex-shrink:0;margin-top:1.8vh;display:flex;flex-direction:column;gap:1.4vh;}
/* 正文填充区：内容偏多时占据剩余空间并内部裁切，保证 kicker/主题句始终可见（根治 P13 溢出裁切） */
.body-fill{flex:1;min-height:0;overflow:hidden;display:flex;flex-direction:column;justify-content:flex-start;}
/* M10 分步揭示（2026-08-19）：||| 分段的后续段初始隐藏，按右键/滚轮前进逐个揭示，揭示完才翻页 */
.step-reveal.hidden{display:none!important;}
/* 正文密度微调：行距/字号略收，让典型内容更稳地落在一屏内 */
.body-zh{font-size:max(14px,1.1vw);line-height:1.5;}
.h-xl-line{font-size:clamp(24px,5.6vw,82px);line-height:1.06;margin-top:1.1vh;}
.h-xl-line.size-lg{font-size:clamp(30px,6.6vw,104px);}
/* M11 引文整体放大（大纲 M11 字号: 大） */
.callout .q-big.size-lg,.callout-fixed .q-big.size-lg{font-size:max(26px,2.4vw);line-height:1.4;font-weight:700;}


/* ===== L17 互动页 ===== */
.interactive-tag{font-family:var(--mono);font-size:max(13px,1vw);opacity:.72;border:1px solid currentColor;border-radius:999px;padding:.3em 1.1em;margin-top:2vh;}

/* ===== L18 字源卡 ===== */
.ziyuan-grid{display:grid;gap:3vw;flex:1;align-content:center;}
.ziyuan-card{border:1px solid rgba(42,30,19,.25);border-radius:8px;padding:2.4vh 1.4vw;text-align:center;display:flex;flex-direction:column;gap:1.2vh;justify-content:center;}
.zy-ch{font-family:var(--serif-zh);font-weight:900;font-size:clamp(40px,6vw,84px);color:var(--accent);line-height:1;}
.zy-form{font-family:var(--sans-zh);font-size:max(14px,1.1vw);opacity:.8;}
.zy-mean{font-family:var(--serif-zh);font-size:max(15px,1.2vw);opacity:.92;}

/* ===== L12b 链条式 ===== */
.chain{display:flex;align-items:stretch;gap:0;flex-wrap:nowrap;overflow-x:auto;}
.chain-node{flex:1 1 0;min-width:120px;border:1px solid rgba(42,30,19,.3);border-radius:8px;padding:2vh 1vw;display:flex;flex-direction:column;gap:1vh;justify-content:center;text-align:center;background:rgba(238,223,199,.5);}
.chain-ch{font-family:var(--serif-zh);font-weight:700;font-size:clamp(18px,2.2vw,34px);color:var(--ink);line-height:1.2;}
.chain-blank{color:var(--accent);opacity:.7;font-weight:600;}
.chain-d{font-family:var(--sans-zh);font-size:max(12px,.95vw);opacity:.78;line-height:1.5;}
.chain-arrow{display:flex;align-items:center;justify-content:center;color:var(--accent);font-size:clamp(20px,2.4vw,38px);font-weight:700;padding:0 .6vw;flex:0 0 auto;}

/* ===== L23 多图证据墙 ===== */
.wall-grid{display:grid;gap:2vh 2vw;margin-top:4vh;flex:1;min-height:0;align-items:start;}
.wall-grid.n1{grid-template-columns:1fr;}
.wall-grid.n2{grid-template-columns:1fr 1fr;}
.wall-grid.n3{grid-template-columns:repeat(3,1fr);}
.wall-tile{margin:0;display:flex;flex-direction:column;gap:.8vh;min-height:0;}
.wall-tile img{width:100%;max-height:42vh;object-fit:contain;background:rgba(128,128,128,.08);border-radius:4px;}
.wall-ph{display:flex;align-items:center;justify-content:center;height:26vh;background:rgba(128,128,128,.12);border-radius:4px;font-family:var(--sans-zh);opacity:.5;}
.wall-cap{font-family:var(--sans-zh);font-size:max(11px,.88vw);opacity:.7;text-align:center;line-height:1.45;}

/* ===== L20 KPI 塔 ===== */
.kpi-cols{display:flex;align-items:flex-end;gap:3vw;margin-top:5vh;flex:1;min-height:0;}
.kpi-col{flex:1 1 0;display:flex;flex-direction:column;align-items:center;gap:.8vh;height:100%;}
.kpi-val{font-family:var(--serif-zh);font-weight:700;font-size:clamp(18px,2.6vw,42px);color:var(--ink);white-space:nowrap;}
.kpi-val.accent{color:var(--accent);}
.kpi-unit{font-family:var(--sans-zh);font-size:.5em;font-weight:400;opacity:.75;margin-left:.15em;}
.kpi-label{font-family:var(--sans-zh);font-size:max(12px,1vw);opacity:.8;text-align:center;}
.kpi-note{font-family:var(--sans-zh);font-size:max(11px,.82vw);opacity:.6;text-align:center;}
.kpi-tower{flex:1;width:58%;min-height:8vh;display:flex;align-items:flex-end;margin-top:1vh;}
.kpi-bar{width:100%;background:var(--accent);transform-origin:bottom center;border-radius:2px 2px 0 0;}
body.motion-ready [data-anim="kpi-bar"]{transform:scaleY(0);}
/* ===== L21 闭环图 ===== */
.loop-body{display:grid;grid-template-columns:1fr 1fr;gap:4vw;align-items:center;margin-top:4vh;flex:1;min-height:0;}
.loop-steps{display:flex;flex-direction:column;gap:2.2vh;}
.loop-step{display:flex;gap:.8vw;align-items:flex-start;}
.loop-nb{font-family:var(--mono,ui-monospace,monospace);font-size:max(13px,1.1vw);color:var(--accent);font-weight:700;}
.loop-t{font-family:var(--sans-zh);font-weight:600;font-size:max(14px,1.2vw);}
.loop-d{font-family:var(--sans-zh);font-size:max(12px,.95vw);opacity:.75;line-height:1.5;}
.loop-fig{display:flex;justify-content:center;align-items:center;}
.loop-svg{width:100%;max-width:34vh;height:auto;}
.loop-ring{fill:none;stroke:var(--accent);stroke-width:2.5;opacity:.75;}
.loop-dot{fill:var(--accent);}
.loop-mid{font-family:var(--serif-zh);font-size:22px;fill:currentColor;opacity:.7;}
.loop-node{font-family:var(--sans-zh);font-size:13px;font-weight:600;fill:var(--accent);opacity:.9;}
body.motion-ready [data-anim="loop-ring"]{stroke-dashoffset:816.8;}
body.low-power [data-anim="loop-ring"]{stroke-dashoffset:0;}
/* ===== L22 系统同心圆 ===== */
.sys-body{display:grid;grid-template-columns:1fr 1fr;gap:4vw;align-items:center;margin-top:4vh;flex:1;min-height:0;}
.sys-list{display:flex;flex-direction:column;gap:2.4vh;}
.sys-item{display:flex;gap:.9vw;align-items:flex-start;}
.sys-dot{width:.85em;height:.85em;background:var(--accent);flex:0 0 auto;margin-top:.35em;}
.sys-t{font-family:var(--sans-zh);font-weight:600;font-size:max(14px,1.2vw);}
.sys-d{font-family:var(--sans-zh);font-size:max(12px,.95vw);opacity:.75;line-height:1.5;}
.sys-fig{display:flex;justify-content:center;align-items:center;}
.sys-svg{width:100%;max-width:34vh;height:auto;}
.sys-ring{fill:none;stroke:var(--accent);stroke-width:2;opacity:.8;transform-box:fill-box;transform-origin:center;}
.sys-label{font-family:var(--sans-zh);font-size:15px;font-weight:600;fill:currentColor;opacity:.85;}
.sys-label.accent{fill:var(--accent);opacity:1;}
.loop-t.accent{color:var(--accent);}
.sys-t.accent{color:var(--accent);}
.wall-cap.accent{color:var(--accent);opacity:1;}
body.motion-ready [data-anim="sys-ring"]{transform:scale(0);}

/* ===== L19 条形图 ===== */
.hbar-list{display:flex;flex-direction:column;gap:2.2vh;margin-top:5vh;flex:1;min-height:0;justify-content:center;}
.hbar-row{display:grid;grid-template-columns:minmax(5em,13%) 1fr auto;align-items:center;gap:1.2vw;}
.hbar-label{font-family:var(--sans-zh);font-size:max(13px,1.05vw);opacity:.82;text-align:right;line-height:1.35;}
.hbar-track{height:2.6vh;min-height:16px;background:rgba(128,128,128,.18);border-radius:2px;overflow:hidden;}
.hbar-bar{height:100%;background:var(--accent);border-radius:2px;transform-origin:left center;}
.hbar-val{font-family:var(--serif-zh);font-weight:700;font-size:clamp(16px,1.9vw,30px);color:var(--ink);white-space:nowrap;}
.hbar-val.accent{color:var(--accent);}
.hbar-unit{font-family:var(--sans-zh);font-size:.55em;font-weight:400;opacity:.75;margin-left:.2em;}
.hbar-note{grid-column:2 / -1;font-family:var(--sans-zh);font-size:max(11px,.85vw);opacity:.62;margin-top:.3vh;}
.hbar-empty{font-family:var(--sans-zh);opacity:.5;font-size:max(13px,1.1vw);}
body.motion-ready [data-anim="hbar-bar"]{transform:scaleX(0);}
"""

# ----------------------------------------------------------------------------
# 2) 小工具
# ----------------------------------------------------------------------------
def esc(t):
    """文本节点转义（quote=False）：仅用于元素**文本内容**，不得用于 HTML 属性值。
    属性值（src/alt/data-* 等）必须用 esc_attr()（quote=True），否则属性内嵌引号会逃逸出
    属性造成 XSS。这是硬契约，新增代码务必遵守。"""
    return html.escape(t or "", quote=False)

def esc_attr(t):
    """属性值转义（含引号）。用于把外部数据塞进 HTML 属性值（src/alt/data-* 等），
    杜绝属性值里携 \" 逃逸出属性造成 XSS。"""
    return html.escape(t or "", quote=True)

# ----------------------------------------------------------------------------
# 安全闸：外部字符串 → CSS 长度 / 比例 / SVG 的净化（2026-08-21 统一加）
# ----------------------------------------------------------------------------
_LEN_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?(vh|vw|px|%)$")  # 2026-09-04：接受前导 +（SKILL §3 宣传的 `+3vh` 写法，此前被静默拒）
def _safe_length(val, unit="vh"):
    """把偏移/长度字段（M05-M14 的 垂直/水平、M12 maxh）净化为合法 CSS 长度。
    非法输入（含引号/字母/括号/脚本片段）一律返回 None，调用方应忽略该微调，不注入 style。"""
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    if not _LEN_RE.search(s):          # 无单位则补默认单位
        s = s + unit
    if not _LEN_RE.match(s):
        return None                     # 仍非法 → 拒绝
    return s

_RATIO_RE = re.compile(r"^\d+(?:\.\d+)?x\d+(?:\.\d+)?$")
def _safe_ratio(ratio):
    """配图比例：仅允许 NxM（如 3x4）或 auto；非法值回落 3x4（杜绝 class="...r-<注入>" 逃逸），
    None 回落 auto（读原图真实比例）。注意与 M12 未写 ratio 的默认 auto 区分开。"""
    if ratio is None:
        return "auto"
    s = str(ratio).strip().lower()
    if s == "auto":
        return "auto"
    if _RATIO_RE.match(s):
        return s
    return "3x4"

def sanitize_svg(svg):
    """清洗内联 SVG：剥离 script/foreignObject/iframe/object/embed/style（含未闭合残留段）、
    删除 link/meta/!ENTITY 声明，删除所有 on* 事件属性（含无值写法），
    把 javascript:/vbscript:/data:(仅放行 png/jpeg/gif/webp/bmp 图片) 协议 URL 置空。
    先做 HTML 实体解码归一化（防 &#106;avascript: 之类编码绕过，解码后重跑标签剥离）。
    几何/文本/样式元素原样保留。用于侧车 svg_inline、items 的 ic SVG 片段。"""
    if not svg:
        return ""
    s = svg
    _DANGER = ("script", "foreignObject", "iframe", "object", "embed", "style")
    # 1) 剥离危险标签：先删成对闭合段（含内容），再删未闭合的残余开/闭标签——不依赖闭合，
    #    杜绝"未闭合 <script> 吞掉后续页面/执行远程脚本"与"成对段内容残留"。
    for tag in _DANGER:
        s = re.sub(r"<\s*%s\b[\s\S]*?<\/\s*%s\s*>" % (tag, tag), "", s, flags=re.I)
        s = re.sub(r"<\s*%s\b[^>]*>" % tag, "", s, flags=re.I)
        s = re.sub(r"</\s*%s\s*>" % tag, "", s, flags=re.I)
    # 2) link/meta / !ENTITY
    s = re.sub(r"<\s*(?:link|meta)\b[^>]*\/?>", "", s, flags=re.I)
    s = re.sub(r"<\!\s*ENTITY\b[^>]*>", "", s, flags=re.I)
    # 3) HTML 实体解码归一化：把 &#106; 还原为 j，让协议正则能拦到编码绕过；
    #    若解码还原出 <script> 等标签（如 &lt;script&gt;），第 4 步会再删一遍。
    s = html.unescape(s)
    # 4) 解码后安全网：重跑危险标签剥离（实体编码的标签已还原为明文）
    for tag in _DANGER:
        s = re.sub(r"<\s*%s\b[\s\S]*?<\/\s*%s\s*>" % (tag, tag), "", s, flags=re.I)
        s = re.sub(r"<\s*%s\b[^>]*>" % tag, "", s, flags=re.I)
        s = re.sub(r"</\s*%s\s*>" % tag, "", s, flags=re.I)
    # 4.5) 事件属性归一化（2026-09-12 SEC-1 修复①，老陈批准）：HTML 分词器在标签名后的
    #      '/' 处断名，故 `<svg/onload=…>` 与 `<svg onload=…>` 对浏览器**等价**；而下面
    #      第 5 步的两条正则都要求 `\s+` 前置，`/` 前缀即漏网（**开页即执行、免点击**）。
    #      先把 `<tag/on…` 折成 `<tag on…`，让第 5 步能拦住。
    #      ⚠️ 精准限定「tag 名后紧跟 / 再紧跟字母」，不会触碰 `<circle …/>` 这类自闭合
    #      标签（其 / 前是引号或空白），也不会动 `</svg>`（< 后是 / 不是字母）。
    s = re.sub(r"(<[A-Za-z][\w:.-]*)/(?=[A-Za-z])", r"\1 ", s)
    # 5) on* 事件属性：带值（"x"/'x'/裸值）与无值（onload）写法都清
    s = re.sub(r"\s+on[a-z]+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)", " ", s, flags=re.I)
    s = re.sub(r"\s+on[a-z]+(?=\s|/?>)", " ", s, flags=re.I)
    # 6) 危险协议 URL 置空（data: 仅放行 png/jpeg/gif/webp/bmp 图片，禁 svg+xml 等可内嵌脚本子类型）。
    #    2026-09-12 SEC-1 修复②③（老陈批准）：旧值类 [^\s"'>] 把 空格/"/'/ > 四者一并排除，
    #    值中含任一即匹配不到闭合引号 → 带引号分支失配，无引号兜底又要求值不以引号开头，
    #    两条全落空（`href="javascript:alert('x')"` 这类无 `>` 的也幸存）；且未做 URL 归一化，
    #    值内 tab/换行（浏览器会剥除后执行）识别不到。
    #    现改为：双/单引号值各用 [^"]* / [^']*（值内任意字符，含 > 与空白）；
    #            首尾空白/控制符用 _URL_EDGE（浏览器解析 URL 时会剥除）；
    #            协议名容忍 [\t\n\r]*（浏览器会从 URL 内部删除这三者，故 java\tscript: 仍会执行；
    #            注意不用 \s——中间的普通空格浏览器并不删除，`java script:` 实际不构成 scheme）；
    #            合法 data:image/(png|jpeg|gif|webp|bmp) 白名单原样保留。
    _URL_EDGE = r"[\x00-\x20\x7f]*"      # 浏览器会剥除的首尾空白/控制符
    _URL_INNER = r"[\t\n\r]*"            # 浏览器会从 URL 内部删除的字符
    _ATTR = r"(?:href|xlink:href|src)\s*=\s*"

    def _scheme(name):
        return _URL_INNER.join(re.escape(c) for c in name)

    _DANGER_PROTO = (r"(?:" + _scheme("javascript") + r"|" + _scheme("vbscript") + r"|"
                     + _scheme("data") + r"\s*:(?!image/(?:png|jpe?g|gif|webp|bmp)(?:[;\s'\">]|$)))")
    s = re.sub(r"(%s)\"%s%s[^\"]*\"" % (_ATTR, _URL_EDGE, _DANGER_PROTO),
               r'\1"#"', s, flags=re.I)
    s = re.sub(r"(%s)'%s%s[^']*'" % (_ATTR, _URL_EDGE, _DANGER_PROTO),
               r"\1'#'", s, flags=re.I)
    s = re.sub(r"(%s)(?![\"'])%s%s[^\s>]*" % (_ATTR, _URL_EDGE, _DANGER_PROTO),
               r'\1"#"', s, flags=re.I)
    return s

def safe_url(url):
    """链接 URL 协议白名单（2026-08-24 新增 M16 链接）：仅放行 http/https/mailto；
        其余（javascript:/data:/vbscript:/以及无协议的相对路径/裸域名）一律返回 ''，
        调用方据此退回占位或置 '#'，杜绝借 <a href> 注入脚本（XSS）。
        剥离控制字符（%01 等绕过），用 urlsplit 取 scheme，避免大小写/编码绕过后门。"""
    if not url:
        return ""
    u = str(url).strip()
    u = re.sub(r"[\x00-\x20\x7f]", "", u)   # 去控制字符/空白（含换行、tab、DEL）
    if not u:
        return ""
    try:
        parts = urllib.parse.urlsplit(u)
    except Exception:
        return ""
    scheme = (parts.scheme or "").lower()
    if scheme in ("http", "https", "mailto"):
        return u
    return ""

def _link_html(url, text):
    """把一个「链接」渲染为安全的新标签 <a>（行内 <link> 与 M16 整页框共用）。
        文本 esc 转义；URL 经 safe_url 白名单；不合法则退回纯文本（不渲染可点链接）。"""
    safe = safe_url(url)
    label = esc((text or "").strip())
    if not safe:
        # 无合法 URL：若给了显示文字，仅显示文字；若连文字都没有，显示原始 url 片段（已转义）
        return label or esc(str(url).strip())
    href = esc_attr(safe)
    return '<a class="ilink" href="%s" target="_blank" rel="noopener noreferrer">%s</a>' % (href, label)

_ALIGN_CSS = {"居中": "center", "居左": "left", "居右": "right",
              "中": "center", "左": "left", "右": "right"}

def _inline_rich(val):
    """把正文中的行内标记转为安全 HTML（不套强调）：
       <size=大/中/小>...</size> → 局部放大 span；**...** → 加粗；<ico=name> → Lucide 图标。
       整段标记 <size=大> / <align=居中>（无闭合）被剥离，由调用方作为块级字号/对齐处理。"""
    if not val:
        return ""
    protected = []
    def _store(html_inner):
        protected.append(html_inner)
        return "\x00%d\x00" % (len(protected) - 1)
    # 1) 行内局部放大 <size=大/中/小>...</size>（命名档位）或 <size=1.5>...</size>（显式倍数）
    #    等号两侧与值内容忍空白（<size= 大 >），与解析层 _m10_block 的整段剥离口径一致（2026-09-06）
    val = re.sub(r'<size\s*=\s*(大|中|小|[\d.]+)\s*>(.*?)</size\s*>',
                 lambda m: _store(_size_span(m.group(1), _inline_rich(m.group(2)), raw=True)),
                 val, flags=re.S)
    # 2) 加粗 **...**
    val = re.sub(r'\*\*(.+?)\*\*',
                 lambda m: _store('<strong>%s</strong>' % esc(m.group(1))),
                 val, flags=re.S)
    # 3) 行内图标 <ico=name>
    val = re.sub(r'<ico=([\w-]+)>',
                 lambda m: _store('<i data-lucide="%s" class="ico-inline"></i>' % esc(m.group(1))),
                 val)
    # 3.5) 行内超链接 <link=URL>显示文字</link> → 新标签打开的安全 <a>（2026-08-24 新增 M16 行内写法）
    val = re.sub(r'<link=([^>]+)>(.*?)</link>',
                 lambda m: _store(_link_html(m.group(1), m.group(2))),
                 val, flags=re.S)
    # 3.6) 行内弱化 <dim>...</dim> → 半透明 span（2026-09-09 新增）
    #     只提供语义化「弱化」，不提供任意颜色：opacity 天然适配全部主题，
    #     而写死色值会在换主题时与纸张/墨色撞车。典型用场：对比页次要项、补充说明、数据免责小字。
    val = re.sub(r'<dim\s*>(.*?)</dim\s*>',
                 lambda m: _store('<span class="dim">%s</span>' % _inline_rich(m.group(1))),
                 val, flags=re.S)
    # 4) 剥离整段标记（无闭合的 <size=大> / <size=1.5> / <align=居中>）；容忍等号两侧空白
    val = re.sub(r'<size\s*=\s*(大|中|小|[\d.]+)\s*>', '', val)
    val = re.sub(r'<(?:align|direction)\s*=\s*(居中|居左|居右|左|右|中)\s*>', '', val)
    # 5) 转义
    val = esc(val)
    # 6) 还原受保护片段（多趟：嵌套时内层占位符被封在外层占位符里，单趟 replace 会漏还原）
    for _ in range(8):
        if "\x00" not in val:
            break
        for i, p in enumerate(protected):
            val = val.replace("\x00%d\x00" % i, p)
    return val

def em_html(html, phrases):
    """对已转义 HTML 套强调锚点（不二次转义）。

    2026-09-04 收敛（P2）：
      · 全文替换 —— 旧版 replace(...,1) 只标首处，同一强调词后续出现会漏标；
      · 只在「标签外」的文本片段内替换 —— 旧版会命中 href / data-lucide 等属性中的
        同名词，造成链接破损（实测：<a href=".../甲"> 的属性被改写）；
      · 短语去重 + 按长度降序 —— 短短语先命中会使长短语失效，且避免重复包裹嵌套。
    """
    if not html:
        return ""
    seen = set()
    pe_list = []
    for p in (phrases or []):
        pe = esc(p) if p else ""
        if pe and pe not in seen:
            seen.add(pe)
            pe_list.append(pe)
    if not pe_list:
        return html
    pe_list.sort(key=len, reverse=True)
    pat = re.compile("(%s)" % "|".join(re.escape(x) for x in pe_list))
    out = []
    # re.split 带捕获组：奇数下标为标签本身，原样保留，避免污染属性
    for i, seg in enumerate(re.split(r"(<[^>]*>)", html)):
        out.append(seg if i % 2 else pat.sub(r'<span class="accent">\1</span>', seg))
    return "".join(out)

def _size_span(kind, text, raw=False):
    """行内局部放大：命名档位（大/中/小）或显式倍数（如 1.5 → 1.5em）。

    raw=True：text 已是 _inline_rich 渲染好的 HTML 片段，不再转义。
    用于支持嵌套（如 <size=大>**粗且大**</size>）——2026-09-09 修复：
    旧版外层先占位，内层 ** 再也匹配不到，加粗被静默丢弃。"""
    body = text if raw else esc(text)
    if kind in ("大", "中", "小"):
        return '<span class="sz-%s">%s</span>' % (kind, body)
    try:
        float(kind)
    except ValueError:
        kind = "1.3"
    return '<span style="font-size:%sem;font-weight:700">%s</span>' % (kind, body)

def _font_cls(size):
    """元件级字号控制（2026-08-19 统一机制）：大→size-lg、小→size-sm、中→''、数字(1.2)→inline font-size。
    返回 (class_suffix, style_string)。"""
    if not size:
        return "", ""
    sz = str(size).strip()
    if sz in ("大", "lg", "L"):
        return " size-lg", ""
    if sz in ("小", "sm", "S"):
        return " size-sm", ""
    if sz in ("中", "md", "M"):
        return "", ""
    try:
        v = float(sz)
        return "", "font-size:%sem;" % v
    except ValueError:
        return "", ""

def _apply_ctrl(inner, s):
    """页面级元件统一三控后处理（2026-08-19）：
       M05 kicker / M07 h_sub / M09 h_md —— 字号(大/小/倍数) + 垂直(vh) + 水平(vw)。
       M06/M08/M10/M11/M13/M14 在各自渲染函数内处理（_hero_title/_hxl/_body_block/
       p_callout/_bottom_elements），这里只管这三类简单单元素。"""
    if not inner:
        return inner

    def _wrap_html(m, size, v, h):
        cls_name = m.group(1)  # 元素类名：kicker / h-sub / h-md
        content = m.group(2)   # 元素内容
        cls, sty = _font_cls(size)
        html = '<div class="%s%s" data-anim%s>%s</div>' % (
            cls_name, cls,
            (' style="%s"' % sty) if sty else "",
            content)
        return _movewrap(html, v, h)

    # M05 kicker：<div class="kicker" data-anim>…</div>
    s05 = (s.get("m05_size"), s.get("m05_v"), s.get("m05_h"))
    if any(s05):
        inner = re.sub(r'<div class="(kicker)" data-anim>((?:[^<]|<(?!div\b)|</(?!div>))*?)</div>',
                       lambda m: _wrap_html(m, *s05), inner, flags=re.S)
    # M07 h_sub：<div class="h-sub" data-anim>…</div>
    s07 = (s.get("m07_size"), s.get("m07_v"), s.get("m07_h"))
    if any(s07):
        inner = re.sub(r'<div class="(h-sub)" data-anim>((?:[^<]|<(?!div\b)|</(?!div>))*?)</div>',
                       lambda m: _wrap_html(m, *s07), inner, flags=re.S)
    # M09 h_md：<div class="h-md">…</div>（无 data-anim）
    s09 = (s.get("m09_size"), s.get("m09_v"), s.get("m09_h"))
    if any(s09):
        inner = re.sub(r'<div class="(h-md)">((?:[^<]|<(?!div\b)|</(?!div>))*?)</div>',
                       lambda m: _wrap_html(m, *s09), inner, flags=re.S)
    return inner

def _movewrap(html, v=None, h=None):
    """M12 图片四向调整（2026-08-19）：垂直 + 水平 双轴视觉平移（非 data-anim 包裹）。
    v：垂直偏移，默认单位 vh（负=上移、正=下移）；h：水平偏移，默认单位 vw（负=左移、正=右移）。
    支持显式单位 vh/vw/px/%（如 v="3vh"、h="-2vw"）。
    2026-08-21：v/h 经 _safe_length 白名单校验，非法值直接忽略该轴平移。"""
    vv = _safe_length(v, "vh")
    hh = _safe_length(h, "vw")
    if not vv and not hh:
        return html
    t = []
    if vv:
        t.append("translateY(%s)" % vv)
    if hh:
        t.append("translateX(%s)" % hh)
    return '<div class="vwrap" style="transform:%s">%s</div>' % (" ".join(t), html)

def em(t, phrases):
    """对文本套用本页强调锚点：行内标记 → HTML，再包 accent 强调色（随主题，非恒定红）。
       全站统一入口（标题/正文/条目/引文均经此），故行内 size/bold/icon 与强调处处一致生效。"""
    if not t:
        return ""
    return em_html(_inline_rich(t), phrases)

def _points(items, emphasis=None):
    if items is None:
        return ""
    if isinstance(items, str):
        items = [items]
    return "".join('<div class="body-zh" data-anim style="margin-top:1.2vh">· %s</div>' % em(x, emphasis) for x in items)

# ----------------------------------------------------------------------------
# 3) 版式原语（返回 .frame 内部 HTML）
# ----------------------------------------------------------------------------
def _hero_title(s, cls="h-hero"):
    """M06 h_hero 标题：支持单行，或多行（/ 分隔）+ 逐行对齐（居左/居右）+ 垂直/水平平移（m06_v/m06_h）。"""
    lines = s.get("title_lines")
    if not lines:
        html = '<h1 class="%s" data-anim>%s</h1>' % (cls, em(s.get("title", ""), s.get("emphasis")))
        return _movewrap(html, s.get("m06_v"), s.get("m06_h"))
    aligns = s.get("title_aligns") or (["left", "right"] if len(lines) == 2 else ["left"] * len(lines))
    out = []
    for i, ln in enumerate(lines):
        al = aligns[i] if i < len(aligns) else "left"
        out.append('<div class="%s-line" data-anim style="width:100%%;text-align:%s">%s</div>' % (cls, al, em(ln, s.get("emphasis"))))
    return _movewrap("".join(out), s.get("m06_v"), s.get("m06_h"))

def _hxl(s):
    """M08 h_xl 主题句：单行，或多行（/ 分隔）+ 逐行对齐（左/中/右）+ 逐行字号（大/小）。
    注意：每个 line 盒子必须 width:100%，否则在 flex 列容器下被 align-items 压成内容宽，
    text-align 失效（这正是上一轮 P03/P07/P11/P13「居左·居右仍全居中」的根因；
    M06 的 _hero_title 已加，这里 M08 一并补齐，系统性根治、不再逐页打补丁）。"""
    lines = s.get("title_lines")
    single_al = s.get("title_align", "left")
    if not lines:
        style = ' style="width:100%%;text-align:%s"' % single_al if single_al != "left" else ' style="width:100%"'
        html = '<h2 class="h-xl" data-anim%s>%s</h2>' % (style, em(s.get("title", ""), s.get("emphasis")))
        return _movewrap(html, s.get("m08_v"), s.get("m08_h"))
    aligns = s.get("title_aligns") or (["left", "right"] if len(lines) == 2 and single_al == "left" else [single_al] * len(lines))
    sizes = s.get("line_sizes") or ["std"] * len(lines)
    out = []
    for i, ln in enumerate(lines):
        al = aligns[i] if i < len(aligns) else single_al
        sz = sizes[i] if i < len(sizes) else "std"
        cls = "h-xl-line"
        if sz == "大":
            cls += " size-lg"
        elif sz == "小":
            cls += " size-sm"
        style = ' style="width:100%%;text-align:%s"' % al if al != "left" else ' style="width:100%"'
        out.append('<div class="%s" data-anim%s>%s</div>' % (cls, style, em(ln, s.get("emphasis"))))
    return _movewrap("".join(out), s.get("m08_v"), s.get("m08_h"))


def _img_size(path):
    """读取图片真实宽高（PNG/JPEG/GIF/WebP/BMP 头解析，不依赖 PIL）。失败返回 None。
    2026-08-19 新增：支持「M12 ratio: auto」按原图比例缩放，避免写错比例导致裁切。"""
    try:
        with open(path, "rb") as fh:
            head = fh.read(min(os.path.getsize(path), 512 * 1024))  # JPEG SOF 常在 EXIF/APP 段之后，需多读
    except OSError:
        return None
    if not head:
        return None
    try:
        if head[:8] == b"\x89PNG\r\n\x1a\n" and len(head) >= 24:
            w, h = struct.unpack(">II", head[16:24])
            return (w, h) if w and h else None
        if head[:6] in (b"GIF87a", b"GIF89a") and len(head) >= 10:
            w, h = struct.unpack("<HH", head[6:10])
            return (w, h) if w and h else None
        if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
            # 2026-09-15 修复：webp 有 VP8 / VP8L / VP8X 三种子格式，尺寸字段位置不同。
            # 旧写法直接读 12-17 字节，只对 VP8 简单有损「碰巧」可用；遇到带透明通道的
            # VP8X（RGBA）会把 chunk 头当尺寸读成天文数字 → 配图 aspect-ratio 爆掉、图塌成 0 高不可见。
            sub = head[12:16]
            if sub == b"VP8X" and len(head) >= 30:
                # 扩展格式：'VP8X'(4) + chunksize(4) + flags(1) + reserved(3)，
                # 其后 偏移 24-26 宽-1(24bit LE)、27-29 高-1(24bit LE)
                w = 1 + (head[24] | (head[25] << 8) | (head[26] << 16))
                h = 1 + (head[27] | (head[28] << 8) | (head[29] << 16))
                return (w, h) if w and h else None
            if sub == b"VP8L" and len(head) >= 25:
                # 无损格式：偏移 21 起 4 字节 LE，bit0-13 宽-1(14bit)、bit14-27 高-1(14bit)
                b = head[21] | (head[22] << 8) | (head[23] << 16) | (head[24] << 24)
                w = (b & 0x3FFF) + 1
                h = ((b >> 14) & 0x3FFF) + 1
                return (w, h) if w and h else None
            if sub == b"VP8 " and len(head) >= 30:
                # 简单有损：容器头后第 20 字节起为 VP8 帧负载，关键帧起始码 0x9D 0x01 0x2A
                # 其后 4 字节 LE 为「宽-1(14bit) | 高-1(14bit)」字（bit14-15/30-31 为缩放标志，掩掉）。
                i = head.find(b"\x9d\x01\x2a", 20)
                if i >= 0 and i + 7 < len(head):
                    word = head[i + 3] | (head[i + 4] << 8) | (head[i + 5] << 16) | (head[i + 6] << 24)
                    w = (word & 0x3FFF) or 1
                    h = ((word >> 16) & 0x3FFF) or 1
                    return (w, h)
                return None
            return None
        if head[:2] == b"BM" and len(head) >= 26:
            w, h = struct.unpack("<ii", head[18:26])
            w, h = abs(w), abs(h)
            return (w, h) if w and h else None
        if head[:2] == b"\xff\xd8":
            pos = 2
            while pos + 9 < len(head):
                if head[pos] != 0xFF:
                    pos += 1
                    continue
                marker = head[pos + 1]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    h = (head[pos + 5] << 8) | head[pos + 6]
                    w = (head[pos + 7] << 8) | head[pos + 8]
                    return (w, h) if w and h else None
                if marker == 0xD8 or (0xD0 <= marker <= 0xD9):
                    pos += 2
                    continue
                seglen = (head[pos + 2] << 8) | head[pos + 3]
                if seglen < 2:
                    return None
                pos += 2 + seglen
            return None
    except (struct.error, IndexError):
        return None
    return None


def _ratio_to_wh(ratio):
    """'4x3'/'12x5'/'1x1'（含 ×/:）→ (4.0,3.0)；auto/原图/空 → None（按图片真实比例）。"""
    if not ratio:
        return None
    r = str(ratio).strip().lower().replace("×", "x").replace("：", ":").replace(":", "x")
    if r in ("auto", "原图", "原比例", "none"):
        return None
    m = re.match(r"^([\d.]+)x([\d.]+)$", r)
    if m:
        return (float(m.group(1)), float(m.group(2)))
    return None


def _img_figure(s, ratio="auto"):
    """配图区统一渲染：优先 svg_inline（真实示意图，如 P19）→ 本地图片文件（如 P25）→ 虚线占位。
    2026-08-19 重写（修复 P11 上部被切）：
      - 容器 aspect-ratio 取「手动 ratio 或图片真实比例」，覆盖 .img-slot 默认 16:9；
      - img 改 height:100% + object-fit:contain —— 整图始终可见、绝不裁切（比例不一致时留白）；
      - max-height 仍是缩放大小的控制字段（占屏 vh）；
      - M12 对齐: 贴左|居中|贴右 控制 img 在框内水平位置（默认居中）。
    2026-08-21 安全加固：ratio/maxh 经白名单净化（杜绝 class/style 注入）；src/alt 用 esc_attr
    （防属性逃逸）；svg_inline 过 sanitize_svg。"""
    img = s.get("img", {})
    cap = ""  # 图片引用源 caption 已停用（图下不再显示来源），保留字段以兼容旧大纲
    maxh = _safe_length(img.get("maxh", "62"), "vh") or "62vh"
    ratio = _safe_ratio(ratio)
    svg = s.get("svg_inline")
    if svg:
        # 2026-08-23 穿透修复：内层 div 内联 max-height 覆盖 CSS 默认 54vh，
        # 使 M12 maxh: 对竖版示意图也生效（解除"竖版图被 54vh 卡死"的坑）。
        # 注意：SVG 图（fig-svg）不挂 r-%s 比例类——引擎 CSS 里无任何 .fig-svg.r-NxM
        # 规则（r-3x4 等只挂在光栅图 .frame-img/.img-slot，且光栅靠内联 aspect-ratio
        # 生效），挂了是死类。SVG 高度由 viewBox 比例 + max-height 决定（2026-09-03 清理）。
        fig = '<figure class="fig-svg" data-anim style="max-height:%s"><div style="max-height:%s">%s</div>%s</figure>' % (maxh, maxh, sanitize_svg(_svg_apply_maxh(svg, maxh)), cap)
        return _movewrap(fig, img.get("v"), img.get("h"))  # M12 垂直/水平 对 SVG 图位生效（2026-09-04：此前只包垂直，「水平」无效）
    f = img.get("file")
    if f:
        rw = _ratio_to_wh(ratio)
        ar = None
        if rw:
            ar = "%.4f" % (rw[0] / rw[1])
        elif img.get("_w") and img.get("_h"):
            # build() 已预解析真实尺寸（2026-08-19）：ratio=auto 时按原图比例，绝不因比例不符被裁
            ar = "%.4f" % (img["_w"] / img["_h"])
        else:
            size = _img_size(f)
            if size and size[1]:
                ar = "%.4f" % (size[0] / size[1])
        align = (img.get("align") or "").strip()
        op = "left center" if align in ("贴左", "left") else ("right center" if align in ("贴右", "right") else "center center")
        if ar:
            # 容器按比例 + img contain：整图可见，绝不裁
            fig = ('<figure class="img-slot has-img r-%s" data-anim style="aspect-ratio:%s;max-height:%s">'
                   '<img src="%s" alt="%s" style="width:100%%;height:100%%;object-fit:contain;'
                   'object-position:%s;display:block"/>%s</figure>'
                   ) % (ratio, ar, maxh, esc_attr(f), esc_attr(img.get("label", "")), op, cap)
        else:
            # 读不到尺寸（罕见格式）→ 兜底旧行为：width:100%;height:auto（不裁、可能溢出）
            fig = ('<figure class="img-slot has-img r-%s" data-anim style="max-height:%s">'
                   '<img src="%s" alt="%s" style="width:100%%;height:auto;display:block"/>%s</figure>'
                   ) % (ratio, maxh, esc_attr(f), esc_attr(img.get("label", "")), cap)
        # M12 垂直 / M12 水平 四向微调（2026-08-19，vh/vw 视觉平移，不参与布局流）
        return _movewrap(fig, img.get("v"), img.get("h"))
    label = img.get("label", "待补 · 配图")
    return ('<figure class="img-slot r-%s" data-anim style="max-height:%s">'
            '<div class="plus">+</div><div class="label">%s</div>%s</figure>'
            ) % (ratio, maxh, esc_attr(label), cap)


def p_cover(s, ctx):
    _MOUNT = {"M06", "M07", "meta-row"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    _subs = s.get("sub_lines")
    if _subs:
        sub_html = "".join('<div class="h-sub" data-anim>%s</div>' % em(x, s.get("emphasis")) for x in _subs)
    else:
        sub_html = '<div class="h-sub" data-anim>%s</div>' % em(s.get("subtitle", ""), s.get("emphasis"))
    return ('<div class="frame center" style="gap:2.4vh">'
            '<div class="kicker" data-anim>%s</div>'
            '%s'
            '%s'
            '<div class="meta-row" data-anim>%s</div>'
            '</div>') % (
        esc(s.get("kicker", "")),
        _hero_title(s, "h-hero"),
        sub_html,
        " · ".join(esc(m) for m in s.get("meta", [])) or "&nbsp;")

def p_hero(s, ctx):
    _MOUNT = {"M06", "M07"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    _subs = s.get("sub_lines")
    if _subs:
        sub_html = "".join('<div class="h-sub" data-anim>%s</div>' % em(x, s.get("emphasis")) for x in _subs)
    else:
        sub = s.get("subtitle", "")
        sub_html = '<div class="h-sub" data-anim>%s</div>' % em(sub, s.get("emphasis")) if sub else ""
    return ('<div class="frame center" style="gap:2vh">'
            '<div class="kicker" data-anim>%s</div>'
            '%s%s'
            '</div>') % (esc(s.get("label", "")), _hero_title(s, "h-hero"), sub_html)

def p_lead(s, ctx):
    _MOUNT = {"M08", "M10"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    return ('<div class="frame" style="justify-content:center">'
            '<div class="kicker" data-anim>%s</div>'
            '%s'
            '<div class="lead" data-anim style="margin-top:3vh;max-width:62vw">%s</div>'
            '</div>') % (esc(s.get("kicker","")), _hxl(s), _body_block(s.get("body"), s.get("emphasis"), v=s.get("m10_v"), h=s.get("m10_h")))

def p_statgrid(s, ctx):
    _MOUNT = {"M08", "M10", "stats:"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    cells = []
    emph = s.get("emphasis") or []
    for st in s.get("stats", []):
        nb = st.get("nb", "")
        unit = st.get("unit", "")
        unit_html = '<span class="stat-unit">%s</span>' % esc(unit) if unit else ""
        # 含中文的数字用衬线中文体（与第15讲一致）
        cjk = re.search(r"[\u4e00-\u9fff]", nb)
        font = ' style="font-family:var(--serif-zh)"' if cjk else ""
        # accent：显式字段优先；未指定时若 nb/label 命中本页强调锚点则上强调色（统一"强调色只点睛关键数字"纪律，不放大）；
        # 无锚点页兜底维持旧"全红"行为，避免历史大纲静默退色。
        acc = st.get("accent")
        if acc is None:
            acc = any(ph and (ph in nb or ph in st.get("label", "")) for ph in emph) if emph else True
        accent = " accent" if acc else ""
        cells.append(
            '<div class="stat-card" data-anim>'
            '<div class="stat-label">%s</div>'
            '<div class="stat-nb%s"%s>%s%s</div>'
            '<div class="stat-note">%s</div>'
            '</div>' % (esc(st.get("label","")), accent, font, esc(nb), unit_html, esc(st.get("note",""))))
    n = len(s.get("stats", []))
    # 自适应列数：按数据条数挂语义类（grid-2 / grid-3 / grid-4），让 CSS 字号放大规则生效
    #   · 2 条 → grid-2（2列一行，数字 7vw）
    #   · 3 条 → grid-3（3列一行，数字 6.8vw，CSS 已有）
    #   · 4 条 → grid-4（2×2，数字放大到 7.5vw，避免旧 5vw 过窄过小）
    #   · ≥5 条 → 回退 grid-3（3列自动换行），不内联 repeat 以免绕过字号规则
    grid_cls = {2: "grid-2", 3: "grid-3", 4: "grid-4"}.get(n, "grid-3")
    return ('<div class="frame">'
            '<div class="kicker" data-anim>%s</div>'
            '%s'
            '<div class="%s" style="margin-top:6vh;flex:1;min-height:0;align-items:start;gap:3vw">%s</div>'
            '</div>') % (esc(s.get("kicker","")), _hxl(s), grid_cls, "".join(cells))

def p_hbar(s, ctx):
    """L19 条形图：stats: label=标签 / nb=数值(决定条宽) / unit=单位 / note=注释。

    渐进增强：HTML 里直接写终值（JS 失效或低功耗时数字仍然正确），
    动效由 recipe `hbar` 负责把 bar 从 scaleX(0) 拉开、数字从 0 递增覆盖。
    """
    _MOUNT = {"M08", "M10", "scale:", "stats:", "whitespace:"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    stats = s.get("stats", []) or []
    emph = s.get("emphasis") or []
    vals = []
    for st in stats:
        try:
            vals.append(float(str(st.get("nb", "0")).replace(",", "")))
        except (TypeError, ValueError):
            vals.append(0.0)
    mx = max(vals) if vals else 0.0
    if mx <= 0:
        mx = 1.0
    # 留白双模式（2026-09-13）：绝对占比(默认——数据似百分比时 scale=100，条宽=值% 留白=100-值) /
    # 裸计数回退旧归一化(scale=数据最大值，最长条撑满)；页面级 whitespace:N 将最大条封顶到 100-N%
    _sc = s.get("scale") or s.get("hbar_scale")
    # scale:max = 显式裸计数归一化（小数裸计数如 5.6 万亿必须显式 max，否则会被当百分比）
    _scale_max = str(_sc).strip().lower() == "max"
    if _sc is None or _scale_max:
        _sc = mx if _scale_max else (100.0 if mx <= 100 else mx)
    try:
        scale = float(_sc)
    except (TypeError, ValueError):
        scale = 100.0 if mx <= 100 else mx
    _ws = s.get("whitespace")
    try:
        # 默认 28：最长条封顶 72%、右侧留约 3 成（作者显式 whitespace 覆盖；写 0 即顶满）
        ws = float(_ws) if _ws is not None else 28.0
    except (TypeError, ValueError):
        ws = 28.0
    ws = max(0.0, min(50.0, ws))
    rows = []
    for st, v in zip(stats, vals):
        raw = (v / scale * 100.0) if v > 0 else 0.0
        pct = raw * (100.0 - ws) / 100.0
        pct = max(pct, 1.5)
        txt = str(st.get("nb", ""))
        unit = st.get("unit", "")
        unit_html = '<span class="hbar-unit">%s</span>' % esc(unit) if unit else ""
        note = st.get("note", "")
        note_html = '<div class="hbar-note">%s</div>' % esc(note) if note else ""
        # accent：显式字段优先；未指定时若 nb/label 命中本页强调锚点则上强调色（与 p_statgrid 同纪律）
        acc = st.get("accent")
        if acc is None:
            acc = any(ph and (ph in txt or ph in str(st.get("label", ""))) for ph in emph) if emph else False
        acls = " accent" if acc else ""
        rows.append(
            '<div class="hbar-row" data-anim>'
            '<div class="hbar-label">%s</div>'
            '<div class="hbar-track"><div class="hbar-bar" data-anim="hbar-bar" style="width:%.1f%%"></div></div>'
            '<div class="hbar-val%s"><span class="hbar-num" data-anim="hbar-num" data-to="%s">%s</span>%s</div>'
            '%s'
            '</div>' % (esc(st.get("label", "")), pct, acls, repr(v), esc(txt), unit_html, note_html))
    if not rows:
        rows.append('<div class="hbar-empty">— 本页缺少 stats: 数据 —</div>')
    _bd = s.get("body")
    _bhtml = ('<div class="lead" data-anim style="margin-top:2.2vh;max-width:74vw">%s</div>'
              % _body_block(_bd, s.get("emphasis"), v=s.get("m10_v"), h=s.get("m10_h"))) if _bd else ""
    return ('<div class="frame">'
            '<div class="kicker" data-anim>%s</div>'
            '%s'
            '%s'
            '<div class="hbar-list">%s</div>'
            '</div>') % (esc(s.get("kicker", "")), _hxl(s), _bhtml, "".join(rows))
def p_kpitower(s, ctx):
    """L20 KPI 塔：stats: label / nb(数值,决定柱高) / unit / note。柱自底部拉起。"""
    _MOUNT = {"M08", "M10", "stats:"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    stats = s.get("stats", []) or []
    emph = s.get("emphasis") or []
    vals = []
    for st in stats:
        try:
            vals.append(float(str(st.get("nb", "0")).replace(",", "")))
        except (TypeError, ValueError):
            vals.append(0.0)
    mx = max(vals) if vals else 0.0
    if mx <= 0:
        mx = 1.0
    cols = []
    for st, v in zip(stats, vals):
        h = max(6.0, v / mx * 100.0) if v > 0 else 2.0
        txt = str(st.get("nb", ""))
        unit = st.get("unit", "")
        unit_html = '<span class="kpi-unit">%s</span>' % esc(unit) if unit else ""
        note = st.get("note", "")
        note_html = '<div class="kpi-note">%s</div>' % esc(note) if note else ""
        acc = st.get("accent")
        if acc is None:
            acc = any(ph and (ph in txt or ph in str(st.get("label", ""))) for ph in emph) if emph else False
        acls = " accent" if acc else ""
        cols.append(
            '<div class="kpi-col" data-anim>'
            '<div class="kpi-val%s"><span class="kpi-num" data-anim="kpi-num" data-to="%s">%s</span>%s</div>'
            '<div class="kpi-label">%s</div>'
            '%s'
            '<div class="kpi-tower"><div class="kpi-bar" data-anim="kpi-bar" style="height:%.1f%%"></div></div>'
            '</div>' % (acls, repr(v), esc(txt), unit_html, esc(st.get("label", "")), note_html, h))
    if not cols:
        cols.append('<div class="hbar-empty">— 本页缺少 stats: 数据 —</div>')
    _bd = s.get("body")
    _bhtml = ('<div class="lead" data-anim style="margin-top:2.2vh;max-width:74vw">%s</div>'
              % _body_block(_bd, s.get("emphasis"), v=s.get("m10_v"), h=s.get("m10_h"))) if _bd else ""
    return ('<div class="frame">'
            '<div class="kicker" data-anim>%s</div>'
            '%s'
            '%s'
            '<div class="kpi-cols">%s</div>'
            '</div>') % (esc(s.get("kicker", "")), _hxl(s), _bhtml, "".join(cols))


def p_loop(s, ctx):
    """L21 闭环图：steps: title / desc（3-5 步）。SVG 由引擎生成，作者不写 - svg:。

    节点文字：每个 step 的 title 自动渲染到环上对应节点旁（loop-node）。
    中心词：默认「闭环」，可用页面级 center: 覆盖（如 center: OODA循环）。
    渐进增强：HTML 内联已给最终形态，动效负责环描线 + 节点序列点亮。
    """
    _MOUNT = {"M08", "M10", "center:", "steps:"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    import math
    steps = s.get("steps", []) or []
    n = max(len(steps), 1)
    cx = cy = 160
    r = 130
    circ = 2 * math.pi * r
    _center = str(s.get("center") or "闭环")
    dots, nodes = [], []
    for i in range(n):
        a = -math.pi / 2 + i * 2 * math.pi / n
        dx, dy = cx + r * math.cos(a), cy + r * math.sin(a)
        dots.append('<circle class="loop-dot" data-anim="loop-dot" cx="%.1f" cy="%.1f" r="9"/>' % (dx, dy))
        _lt = str(steps[i].get("title", "")) if i < len(steps) else ""
        if _lt:
            _lx = cx + (r - 24) * math.cos(a)
            _ly = cy + (r - 24) * math.sin(a)
            nodes.append('<text class="loop-node" data-anim="loop-node" x="%.1f" y="%.1f" '
                         'text-anchor="middle" dominant-baseline="middle">%s</text>' % (_lx, _ly, esc(_lt)))
    svg = ('<svg class="loop-svg" viewBox="0 0 320 320" role="img" aria-label="闭环流程">'
           '<circle class="loop-ring" data-anim="loop-ring" cx="%d" cy="%d" r="%d" '
           'stroke-dasharray="%.1f" stroke-dashoffset="0"/>'
           '%s%s'
           '<text class="loop-mid" x="%d" y="%d" text-anchor="middle">%s</text>'
           '</svg>') % (cx, cy, r, circ, "".join(dots), "".join(nodes), cx, cy + 8, esc(_center))
    _emph = s.get("emphasis") or []
    lis = []
    for i, st in enumerate(steps):
        _t = str(st.get("title", ""))
        _hit = any(ph and ph in _t for ph in _emph) if _emph else False
        _cls = " accent" if _hit else ""
        lis.append('<div class="loop-step" data-anim="loop-step"><span class="loop-nb">%02d</span>'
                   '<div><div class="loop-t%s">%s</div><div class="loop-d">%s</div></div></div>'
                   % (i + 1, _cls, em(_t, _emph), esc(st.get("desc", ""))))
    _bd = s.get("body")
    _bhtml = ('<div class="lead" data-anim style="margin-top:2.2vh;max-width:74vw">%s</div>'
              % _body_block(_bd, s.get("emphasis"), v=s.get("m10_v"), h=s.get("m10_h"))) if _bd else ""
    return ('<div class="frame">'
            '<div class="kicker" data-anim>%s</div>'
            '%s'
            '%s'
            '<div class="loop-body"><div class="loop-steps">%s</div><div class="loop-fig">%s</div></div>'
            '</div>') % (esc(s.get("kicker", "")), _hxl(s), _bhtml,
                         "".join(lis) or '<div class="hbar-empty">— 本页缺少 steps: —</div>', svg)


def p_system(s, ctx):
    """L22 系统同心圆：items: t=层名 / d=说明（严格三层，由外向内 core<-middle<-outer）。

    SVG 由引擎生成，作者不写 - svg:。动效：三层由外向内 scale 入。
    """
    _MOUNT = {"M08", "M10", "items:"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    items = s.get("items", []) or []
    if len(items) > 3:
        print("  [L22 警告] 系统同心圆只支持 3 层，本页给了 %d 项，第 4 项起【不会显示】：%s"
              % (len(items), " / ".join(str(x.get("t", "")) for x in items[3:])))
    radii = [140, 100, 62]
    _semph = s.get("emphasis") or []
    rings, labels = [], []
    for i in range(3):
        rings.append('<circle class="sys-ring" data-anim="sys-ring" cx="160" cy="160" r="%d"/>' % radii[i])
        nm = str(items[i].get("t", "")) if i < len(items) else ""
        if not nm:
            continue
        hit = any(ph and ph in nm for ph in _semph) if _semph else False
        cls = "sys-label accent" if hit else "sys-label"
        labels.append('<text class="%s" data-anim="sys-label" x="160" y="%d" '
                      'text-anchor="middle">%s</text>' % (cls, 160 - radii[i] + 21, esc(nm)))
    svg = ('<svg class="sys-svg" viewBox="0 0 320 320" role="img" aria-label="三层系统图">'
           '%s%s</svg>') % ("".join(rings), "".join(labels))
    lis = []
    for it in items[:3]:
        _t = str(it.get("t", ""))
        _hit = any(ph and ph in _t for ph in _semph) if _semph else False
        _c = " accent" if _hit else ""
        lis.append('<div class="sys-item" data-anim="sys-item"><span class="sys-dot"></span>'
                   '<div><div class="sys-t%s">%s</div><div class="sys-d">%s</div></div></div>'
                   % (_c, em(_t, _semph), esc(it.get("d", ""))))
    _bd = s.get("body")
    _bhtml = ('<div class="lead" data-anim style="margin-top:2.2vh;max-width:74vw">%s</div>'
              % _body_block(_bd, s.get("emphasis"), v=s.get("m10_v"), h=s.get("m10_h"))) if _bd else ""
    return ('<div class="frame">'
            '<div class="kicker" data-anim>%s</div>'
            '%s'
            '%s'
            '<div class="sys-body"><div class="sys-list">%s</div><div class="sys-fig">%s</div></div>'
            '</div>') % (esc(s.get("kicker", "")), _hxl(s), _bhtml,
                         "".join(lis) or '<div class="hbar-empty">— 本页缺少 items: —</div>', svg)
def p_wall(s, ctx):
    """L23 多图证据墙：imgs: file=路径 / cap=图注（2-3 张同类图并列）。"""
    _MOUNT = {"M08", "M10", "imgs:"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    imgs = s.get("imgs", []) or []
    tiles = []
    for im in imgs:
        f = im.get("file", "")
        cap = im.get("cap", "")
        if f:
            inner = '<img src="%s" alt="%s" loading="lazy">' % (esc(f), esc(cap or "配图"))
        else:
            inner = '<div class="wall-ph">待补图</div>'
        _wemph = s.get("emphasis") or []
        _hit = any(ph and ph in str(cap) for ph in _wemph) if (cap and _wemph) else False
        _ccls = "wall-cap accent" if _hit else "wall-cap"
        cap_html = '<figcaption class="%s">%s</figcaption>' % (_ccls, em(str(cap), _wemph)) if cap else ""
        tiles.append('<figure class="wall-tile" data-anim="wall-tile">%s%s</figure>' % (inner, cap_html))
    n = len(tiles)
    cls = "wall-grid n%d" % min(max(n, 1), 3)
    _bd = s.get("body")
    _bhtml = ('<div class="lead" data-anim style="margin-top:2.2vh;max-width:74vw">%s</div>'
              % _body_block(_bd, s.get("emphasis"), v=s.get("m10_v"), h=s.get("m10_h"))) if _bd else ""
    return ('<div class="frame">'
            '<div class="kicker" data-anim>%s</div>'
            '%s'
            '%s'
            '<div class="%s">%s</div>'
            '</div>') % (esc(s.get("kicker", "")), _hxl(s), _bhtml, cls,
                         "".join(tiles) or '<div class="hbar-empty">— 本页缺少 imgs: —</div>')
def p_grid2(s, ctx):
    """L05 图文（增强·2026-09-13）：左文右图；支持 6:6/7:5/8:4 三档比例
    （页面级 `grid:` 或 `图文比例:` 显式选；不输则自动判断：竖图→8:4 窄列、否则→6:6 对半，默认 5:5=6:6）。
    左栏可挂 callout 引用（吸 guizang L10 高密度信息结构）。"""
    _MOUNT = {"M08", "M10", "M12", "callout:", "callout_src:", "grid:", "svg:", "svg_cap:", "图对齐", "图文比例"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    left = s.get("left", "")
    left_html = _body_block(left, s.get("emphasis"), v=s.get("m10_v"), h=s.get("m10_h"))
    # callout 引用（M11 callout / callout_src；兼容旧 text/src 键）
    co = s.get("callout") or s.get("text")
    co_src = s.get("callout_src") or s.get("src")
    if co:
        callout_html = '<div class="callout-fixed" data-anim><div class="q-big">%s</div>%s</div>' % (
            em(co, s.get("emphasis")),
            '<span class="callout-src">%s</span>' % esc(co_src) if co_src else "")
    else:
        callout_html = ""
    ratio = s.get("img", {}).get("ratio", "auto")
    img = _img_figure(s, ratio)
    # 三档比例：显式选 > 自动判断（竖图→8:4 窄列，其余→6:6 对半）
    g = str(s.get("grid") or s.get("图文比例") or "").replace(":", "").replace(" ", "")
    GRID = {"66": "grid-2-6-6", "75": "grid-2-7-5", "84": "grid-2-8-4"}
    if g in GRID:
        grid_cls = GRID[g]
    else:
        PORTRAIT = {"3x4", "4x5", "2x3", "9x16"}
        grid_cls = "grid-2-8-4" if ratio in PORTRAIT else "grid-2-6-6"
    # 图底对齐：显式「图对齐:底」优先；否则左栏挂 callout 时默认底对齐（图坐底而非顶对齐）
    _ia = str(s.get("图对齐") or s.get("img_align") or "").strip()
    extra = " img-bottom" if (_ia in ("底", "下", "bottom", "end") or (callout_html and not _ia)) else ""
    _nl = len(s.get("title_lines") or []) or 1
    _hc = "head-2" if _nl >= 2 else "head-1"
    return ('<div class="frame %s%s">'
            '<div class="col" style="display:flex;flex-direction:column;justify-content:flex-start">'
            '<div class="head-block %s"><div class="kicker" data-anim>%s</div>%s</div>'
            '%s%s'
            '</div>%s</div>') % (grid_cls, extra, _hc, esc(s.get("kicker", "")), _hxl(s), left_html, callout_html, img)

def p_rowline(s, ctx):
    _MOUNT = {"M08", "M10", "rows:"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    rows = []
    _n = len(s.get("rows", []))
    _rs = 1.0 if _n <= 5 else (0.82 if _n <= 7 else (0.72 if _n <= 9 else (0.62 if _n <= 12 else 0.54)))
    _rs_s = ("%.2f" % _rs)
    for r in s.get("rows", []):
        rows.append('<div class="rowline" data-anim style="flex:1;align-items:center;--rs:%s"><div class="k">%s</div><div class="v">%s</div><div class="m">%s</div></div>'
                    % (_rs_s, esc(r.get("k","")), em(r.get("v",""), s.get("emphasis")), esc(r.get("m",""))))
    # 容器 flex:1 纵向均分剩余页高：行数多→每行自动变矮装下不溢出；行数少→每行变高更大气
    return ('<div class="frame">'
            '<div class="kicker" data-anim>%s</div>'
            '%s'
            '<div style="margin-top:3vh;flex:1;display:flex;flex-direction:column;min-height:0">%s</div>'
            '</div>') % (esc(s.get("kicker","")), _hxl(s), "".join(rows))

def p_quote(s, ctx):
    _MOUNT = {"M07", "M10", "M11"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    text = s.get("text") or s.get("subtitle", "")
    qcls = "q-short" if len(text or "") <= 18 else ("q-long" if len(text or "") >= 40 else "q-std")
    return ('<div class="frame center" style="gap:3vh">'
            '<div class="kicker" data-anim>%s</div>'
            '<div class="q-big %s" data-anim="line">%s</div>'
            '<div class="callout-src" data-anim="line">%s</div>'
            '</div>') % (esc(s.get("kicker","")), qcls, em(text, s.get("emphasis")), esc(s.get("src","")))

def p_pillar(s, ctx):
    _MOUNT = {"M08", "M10", "items:"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    items = []
    for it in s.get("items", []):
        ic = it.get("ic", "")
        if ic and not ic.startswith("<"):
            if _LUCIDE_ICONS and ic not in _LUCIDE_ICONS:
                print('[render] ⚠ 图标 "%s" 不是 lucide 合法名（拼写/别名失效）——lucide 将静默跳过，该格图标留空。合法名见 engine/eink_assets/lucide_icons.txt' % ic)
            ic_html = '<i data-lucide="%s" class="ico-lg"></i>' % esc_attr(ic)
        else:
            ic_html = sanitize_svg(ic)  # 允许直接传 SVG 片段，但必须清洗
        items.append('<div class="pillar" data-anim><div class="ic">%s</div><div class="t">%s</div><div class="d">%s</div></div>'
                     % (ic_html, em(it.get("t",""), s.get("emphasis")), em(it.get("d",""), s.get("emphasis"))))
    # 条目数决定栅格：4 项→单行 4 列（不再 3+1）；2 项→2 列；其余→3 列
    n = len(s.get("items", []))
    if n == 4:
        g = "display:grid;grid-template-columns:repeat(4,1fr);gap:2.2vw;flex:1;align-content:center"
    elif n == 2:
        g = "display:grid;grid-template-columns:repeat(2,1fr);gap:4vw;flex:1;align-content:center"
    else:
        g = "display:grid;grid-template-columns:repeat(3,1fr);gap:3vw;flex:1;align-content:center"
    return ('<div class="frame">'
            '<div class="kicker" data-anim>%s</div>'
            '%s'
            '<div style="margin-top:5vh;%s">%s</div>'
            '</div>') % (esc(s.get("kicker","")), _hxl(s), g, "".join(items))

def p_directional(s, ctx):
    _MOUNT = {"M08", "M09", "M10", "left(M09+body):", "right(M09+body):"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    def side(d, anim, emphasis=None):
        pts = _points(d.get("points"), emphasis)
        return ('<div class="col" data-anim="%s">'
                '<div class="h-md">%s</div>%s</div>') % (anim, em(d.get("title",""), emphasis), pts)
    return ('<div class="frame">'
            '<div class="kicker" data-anim>%s</div>'
            '%s'
            '<div class="split" style="margin-top:5vh">%s%s</div>'
            '</div>') % (esc(s.get("kicker","")), _hxl(s),
                         side(s.get("left",{}), "left", s.get("emphasis")), side(s.get("right",{}), "right", s.get("emphasis")))

def _body_block(body, emphasis=None, wrap_cls="body-zh", v=None, h=None):
    """通用 M10 正文块渲染：接受 块列表 / 字符串 / 字符串列表，统一输出 HTML。
    块字典：{"text":..,"size":"大/小/数字倍数(如 1.5)","align":"left/center/right"} 或 {"items":[..]}（列表）。
    v/h：M10 垂直/水平微调（vh/vw，负上正下/负左正右），经 _movewrap 包裹，不参与布局流。"""
    if body is None:
        return ""
    if isinstance(body, str):
        return _movewrap('<div class="%s" data-anim style="margin-top:2vh;max-width:64vw">%s</div>' % (wrap_cls, em(body, emphasis)), v, h)
    if not isinstance(body, list):
        body = [body]
    out = []
    for blk in body:
        if isinstance(blk, str):
            out.append('<div class="%s" data-anim style="margin-top:1.4vh">%s</div>' % (wrap_cls, em(blk, emphasis)))
            continue
        if "items" in blk:
            for it in blk["items"]:
                out.append('<div class="%s" data-anim style="margin-top:1.4vh">· %s</div>' % (wrap_cls, em(it, emphasis)))
            continue
        if "steps" in blk:
            # 分步揭示（2026-08-19）：默认第一段正常显示、后续段 .step-reveal.hidden 初始隐藏，
            # 由注入 JS 的 __pipeAdvance 钩子在「按右键/滚轮前进」时逐个揭示（揭示完才翻页）。
            # lead_empty=True（大纲里 ||| 开头）→ 初始全隐，每按一次揭示一段（先发问、再揭晓）。
            sz = str(blk.get("size") or "")
            al = blk.get("align")
            lead_empty = blk.get("lead_empty", False)
            for i, st in enumerate(blk["steps"]):
                cls = wrap_cls
                stl = ["margin-top:1.4vh"]
                if sz == "大":
                    cls += " size-lg"
                elif sz == "小":
                    cls += " size-sm"
                elif re.match(r"^[\d.]+$", sz):
                    stl.append("font-size:%sem" % sz)  # 分步块数字倍数（2026-09-04，与普通块对称）
                if al:
                    stl.append("text-align:%s" % al)
                if i == 0 and not lead_empty:
                    out.append('<div class="%s" data-anim style="%s">%s</div>'
                               % (cls, "; ".join(stl), em(st, emphasis)))
                else:
                    out.append('<div class="%s step-reveal hidden" style="%s;display:none">%s</div>'
                               % (cls, "; ".join(stl), em(st, emphasis)))
            continue
        cls = wrap_cls
        st = []
        _sz = str(blk.get("size") or "")
        if _sz == "大":
            cls += " size-lg"
        elif _sz == "小":
            cls += " size-sm"
        elif re.match(r"^[\d.]+$", _sz):
            st.append("font-size:%sem" % _sz)  # 块级数字倍数，与行内 <size=1.5> 对称（2026-09-04，此前被静默丢弃）
        if blk.get("align"):
            st.append("text-align:%s" % blk["align"])
        style = "margin-top:1.4vh" + ("; " + "; ".join(st) if st else "")
        out.append('<div class="%s" data-anim style="%s">%s</div>' % (cls, style, em(blk.get("text", ""), emphasis)))
    return _movewrap("".join(out), v, h)

def p_callout(s, ctx):
    """L10 引文页（引文降级为页面级固定元件后，本版式仍可独立成页，且支持标题/正文/图片）。"""
    _MOUNT = {"M08", "M10", "M11", "M12"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    kicker = esc(s.get("kicker",""))
    parts = []
    if kicker:
        parts.append('<div class="kicker" data-anim>%s</div>' % kicker)
    if s.get("title"):  # M08 可选标题（引文页也可有主题句）
        parts.append('%s' % _hxl(s))
    qsz = " size-lg" if "大" in (s.get("q_size", "") or "") else ""
    parts.append(_movewrap('<div class="callout callout-bottom" data-anim>'
                           '<div class="q-big%s">%s</div>'
                           '<span class="callout-src">%s</span>'
                           '</div>' % (qsz, em(s.get("q",""), s.get("emphasis")), esc(s.get("cite",""))),
                           s.get("m11_v"), s.get("m11_h")))
    bh = _body_block(s.get("body"), s.get("emphasis"), v=s.get("m10_v"), h=s.get("m10_h"))
    if bh:
        parts.append(bh)
    _img = s.get("img", {}) or {}
    if _img.get("file"):
        parts.append(_img_figure(s, _img.get("ratio", "auto")))  # 真实图优先
    elif _img.get("label"):
        parts.append('<figure class="img-slot r-3x4" data-anim style="margin-top:3vh;max-height:42vh">'
                     '<div class="plus">+</div><div class="label">%s</div></figure>' % esc(_img["label"]))
    return '<div class="frame">%s</div>' % "".join(parts)

def p_imgslot(s, ctx):
    _MOUNT = {"M08", "M10", "M12", "svg:", "svg_cap:"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    ratio = s.get("img", {}).get("ratio", "auto")
    return ('<div class="frame">'
            '<div class="kicker" data-anim>%s</div>'
            '%s%s'
            '</div>') % (esc(s.get("kicker","")), _hxl(s), _img_figure(s, ratio))
def p_figsvg(s, ctx):
    """L12 示意图页：优先内联 SVG（真实示意图），其次 M12 文件 本地图片（2026-08-19 新增：
    此前只认 svg，M12 文件被丢——P09 图片不显示根因）。图片用 margin-top:auto 贴页面底部。
    M10 正文原生渲染在标题与图之间（2026-08-19 追加：避免 body-fixed 补挂到图下方挡住贴底）。"""
    _MOUNT = {"M08", "M10", "M12", "cap:", "svg:", "svg_cap:"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    svg = s.get("svg_inline") or s.get("svg", "")
    _maxh = _safe_length(s.get("img", {}).get("maxh", "62"), "vh") or "62vh"
    if svg:
        fig = ('<figure class="fig-svg" data-anim style="margin-top:3vh;max-height:%s">%s%s</figure>'
               % (_maxh, sanitize_svg(_svg_apply_maxh(svg, _maxh)),
                  ('<div class="svg-cap"><span>%s</span></div>' % esc(s.get("cap", ""))) if s.get("cap") else ""))
    elif s.get("img", {}).get("file"):
        ratio = s.get("img", {}).get("ratio", "auto")
        # align-items:flex-end —— 图贴内容区下沿（2026-08-19 P09 反馈：此前 center 使图在剩余空间居中、不贴底）
        fig = ('<div style="margin-top:auto;padding-top:2vh;flex:1;min-height:0;'
               'display:flex;align-items:flex-end;justify-content:center">%s</div>'
               % _img_figure(s, ratio))
    else:
        fig = ""
    bh = _body_block(s.get("body"), s.get("emphasis"), v=s.get("m10_v"), h=s.get("m10_h"))
    return ('<div class="frame">'
            '<div class="kicker" data-anim>%s</div>'
            '%s'
            '%s'
            '%s'
            '</div>') % (esc(s.get("kicker", "")), _hxl(s), bh, fig)

def p_text(s, ctx):
    _MOUNT = {"M08", "M10"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    body_html = _body_block(s.get("body"), s.get("emphasis"), v=s.get("m10_v"), h=s.get("m10_h"))
    return ('<div class="frame">'
            '<div class="kicker" data-anim>%s</div>'
            '%s'
            '<div class="body-fill">%s</div>'
            '</div>') % (esc(s.get("kicker","")), _hxl(s), body_html)

def p_pipeline(s, ctx):
    _MOUNT = {"M08", "M10", "steps:"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    cols = s.get("cols", 5)
    steps = []
    for i, st in enumerate(s.get("steps", [])):
        steps.append('<div class="step" data-anim="step"><div class="step-nb">%02d</div><div class="step-title">%s</div><div class="step-desc">%s</div></div>'
                     % (i+1, em(st.get("title",""), s.get("emphasis")), em(st.get("desc",""), s.get("emphasis"))))
    return ('<div class="frame">'
            '<div class="kicker" data-anim>%s</div>'
            '%s'
            '<div class="pipeline-section">'
            '<div class="pipeline-label" data-anim>进程</div>'
            '<div class="pipeline" data-cols="%d">%s</div>'
            '</div></div>') % (esc(s.get("kicker","")), _hxl(s), cols, "".join(steps))

def p_raw(s, ctx):
    return s.get("html", "")

def p_statnote(s, ctx):
    """L16 文字标牌（降级版·2026-09-13）：原「衬线大字居中」改为「非衬线常规/左轴/发丝线」，
    与粗标题形成明确层级；标题强制左轴（消除双行左/右错位）；首末条 accent 点睛。
    notes 以 / 或 、 分隔多条；含 ||| 走分步揭示（与 M10 同一约定）。"""
    _MOUNT = {"M08", "M10", "M10 notes:"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    # 标题强制左轴：消除 _hxl 双行默认「第一行居左、第二行居右」的错位
    s = dict(s)
    s["title_align"] = "left"
    s["title_aligns"] = ["left", "left"]
    notes = s.get("notes", [])
    if isinstance(notes, str):
        notes = [notes]
    notes = [str(x) for x in notes]
    import re as _re
    SPLIT = r"[/／、]"
    def _notes_of(seg):
        return [z.strip() for z in _re.split(SPLIT, seg) if z.strip()]
    def _div(z, acc):
        return '<div class="stat-note-l16%s" data-anim>%s</div>' % (" accent-note" if acc else "", em(z, s.get("emphasis")))
    has_steps = any("|||" in x for x in notes)
    if has_steps:
        # 跨元素累计分步：元素内的 ||| 切段，||| 之间为同一步
        steps, cur = [], []
        for x in notes:
            segs = x.split("|||")
            cur.append(segs[0])
            for seg in segs[1:]:
                steps.append(cur)
                cur = [seg]
        steps.append(cur)
        seq = [z for stp in steps for seg in stp for z in _notes_of(seg)]
        n = len(seq)
        parts, idx = [], 0
        for i, stp in enumerate(steps):
            its = [z for seg in stp for z in _notes_of(seg)]
            if not its:
                continue
            grp = "".join(_div(z, idx + j == 0 or idx + j == n - 1) for j, z in enumerate(its))
            idx += len(its)
            parts.append(grp if i == 0 else '<div class="step-reveal hidden" style="display:none">%s</div>' % grp)
        items = "".join(parts)
    else:
        seq = [z for x in notes for z in _notes_of(x)]
        n = len(seq)
        items = "".join(_div(z, i == 0 or i == n - 1) for i, z in enumerate(seq))
    return ('<div class="frame">'
            '<div class="kicker" data-anim>%s</div>'
            '%s'
            '<div style="margin-top:3vh;display:flex;flex-direction:column;gap:0;justify-content:flex-start;flex:1">%s</div>'
            '</div>') % (esc(s.get("kicker","")), _hxl(s), items)

def p_statement(s, ctx):
    """L24 论断陈述：一句核心判断（衬线粗体+强左轴+大留白+发丝线）。
    承载「单句强判断」场景（S03 之魂）；与 L16 降级版分工：L16=多条并列判断，L24=一句定调。"""
    _MOUNT = {"M08", "M10", "lead:", "statement:", "sub:", "text:"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    st = s.get("statement") or s.get("text") or s.get("subtitle", "")
    sub = s.get("sub") or s.get("lead") or ""
    sub_html = ('<div class="stat-sub-l24" data-anim>%s</div>' % em(sub, s.get("emphasis"))) if sub else ""
    bh = _body_block(s.get("body"), s.get("emphasis"), v=s.get("m10_v"), h=s.get("m10_h"))
    return ('<div class="frame" style="justify-content:center">'
            '<div class="statement-l24" data-anim>%s</div>'
            '%s%s'
            '</div>') % (em(st, s.get("emphasis")), bh, sub_html)

def p_timeline(s, ctx):
    """L25 横向时间轴：1px 线 + 8×8 方节点 + 等宽年份在上；每项 year/title/desc。
    线由每项的 noderow 内轴拼接（跨越相邻项全宽，节点居中压线），保证水平对齐连续。"""
    _MOUNT = {"M08", "M10", "items:"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    items = []
    for it in s.get("items", []):
        items.append(
            '<div class="tl-item-l25" data-anim>'
            '<div class="tl-year-l25">%s</div>'
            '<div class="tl-noderow-l25"><div class="tl-axis-l25"></div><div class="tl-node-l25"></div></div>'
            '<div class="tl-title-l25">%s</div>'
            '<div class="tl-desc-l25">%s</div>'
            '</div>' % (esc(it.get("year", "")), em(it.get("title", ""), s.get("emphasis")), em(it.get("desc", ""), s.get("emphasis"))))
    bh = _body_block(s.get("body"), s.get("emphasis"), v=s.get("m10_v"), h=s.get("m10_h"))
    return ('<div class="frame">'
            '<div class="kicker" data-anim>%s</div>'
            '%s%s'
            '<div class="timeline-l25">%s</div>'
            '</div>') % (esc(s.get("kicker", "")), _hxl(s), bh, "".join(items))

def p_microcard(s, ctx):
    """L26 微卡矩阵：3×2，每卡左上主句+右下小注，仅一处 accent 点睛（吸 S16 微卡）。
    accent 默认落在首卡；可在条目设 accent:true 显式指定，或 accent_first:false 取消。"""
    _MOUNT = {"M08", "M10", "items:"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    items = s.get("items", [])
    acc_first = s.get("accent_first", True)
    cards = []
    for i, it in enumerate(items):
        is_acc = bool(it.get("accent")) or (i == 0 and acc_first)
        cards.append('<div class="mc-l26%s" data-anim>'
                     '<div class="mc-main">%s</div>'
                     '<div class="mc-sub">%s</div></div>'
                     % (" accent" if is_acc else "", em(it.get("main", ""), s.get("emphasis")), esc(it.get("sub", ""))))
    bh = _body_block(s.get("body"), s.get("emphasis"), v=s.get("m10_v"), h=s.get("m10_h"))
    return ('<div class="frame">'
            '<div class="kicker" data-anim>%s</div>'
            '%s%s'
            '<div class="microcard-grid-l26">%s</div>'
            '</div>') % (esc(s.get("kicker", "")), _hxl(s), bh, "".join(cards))

def p_imagehero(s, ctx):
    """L27 图幅主导：全出血图 + 悬浮/下沉标题块 + 图注 + 3列KPI（吸 S22）。
    img_mode: cover（默认·横图裁切填满、标题悬浮）/
              contain（不裁留白、标题落下方）/
              fit（2026-09-15 新增·图区高度按图片真实比例自适应、无留白不裁切、标题落下方）/
              side（竖图：图占左全高、右侧纵向排）。
（图内主体位置由 cover/contain 布局决定；object-position 固定 center center，2026-09-15 阶段2 起不再支持微调。）"""
    _MOUNT = {"M08", "M10", "M12", "cap:", "img.file:", "img_mode:", "kpis:", "title:"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    img = s.get("img", {}) or {}
    f = img.get("file") or s.get("file")
    mode = (img.get("img_mode") or s.get("img_mode") or "cover").strip().lower()
    is_side = mode == "side"
    is_fit = mode == "fit"
    is_info = (mode in ("contain", "fit")) and not is_side   # 信息图模式：标题落下方、scrim 弱化
    fit = "contain" if (mode == "contain" or is_side or is_fit) else "cover"
    side_cls = " side" if is_side else (" infographic" if is_info else "")
    top_style = (' style="flex:0 0 auto;aspect-ratio:%s"' % img["fit_ratio"]) if (is_fit and img.get("fit_ratio")) else ""
    if f:
        img_html = ('<img class="ih-img-l27" src="%s" alt="%s" '
                    'style="object-fit:%s;object-position:center center"/>') % (
                    esc_attr(f), esc_attr(img.get("label", "")), fit)
    else:
        img_html = '<div class="ih-img-l27" style="display:flex;align-items:center;justify-content:center;background:rgba(42,30,19,.06);font-family:var(--sans-zh);opacity:.5">待补 · 配图</div>'
    bh = _body_block(s.get("body"), s.get("emphasis"), v=s.get("m10_v"), h=s.get("m10_h"))
    cap = s.get("cap") or s.get("caption") or ""
    cap_html = ('<div class="ih-cap-l27" data-anim>%s</div>' % em(cap, s.get("emphasis"))) if cap else ""
    kpis = s.get("kpis", []) or []
    kpi_html = ""
    if kpis:
        cells = []
        for k in kpis[:3]:
            cells.append('<div class="ih-kpi-l27" data-anim><span class="ih-kpi-v-l27">%s</span><span class="ih-kpi-l-l27">%s</span></div>'
                         % (em(k.get("v", ""), s.get("emphasis")), esc(k.get("l", ""))))
        kpi_html = '<div class="ih-kpis-l27">%s</div>' % "".join(cells)
    return ('<div class="frame" style="padding:0;position:absolute;inset:0">'
            '<div class="imagehero-l27%s">'
            '<div class="ih-top-l27"%s>%s</div>'
            '<div class="ih-side-l27">'
            '<div class="ih-title-l27"><div class="kicker" data-anim>%s</div>%s</div>'
            '<div class="ih-bottom-l27">%s%s%s</div>'
            '</div></div></div>') % (side_cls, top_style, img_html, esc(s.get("kicker", "")), _hxl(s), bh, cap_html, kpi_html)

def p_interactive(s, ctx):
    """L17 互动页：大问句/任务 + 可选提示(M10) + 互动标签(M07≈tag)。"""
    _MOUNT = {"M08", "M10", "tag:"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    bh = _body_block(s.get("body"), s.get("emphasis"), v=s.get("m10_v"), h=s.get("m10_h"))
    tag = s.get("tag", "思考 · 讨论")
    return ('<div class="frame center" style="gap:3vh">'
            '<div class="kicker" data-anim>%s</div>'
            '%s%s'
            '<div class="interactive-tag" data-anim>%s</div>'
            '</div>') % (esc(s.get("kicker", "")), _hxl(s), bh, esc(tag))

def p_ziyuan(s, ctx):
    """L18 字源卡：每个字一张卡（字形 ch / 构件 form / 本义 mean）。"""
    _MOUNT = {"M08", "M10", "items:"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    items = s.get("items", [])
    cards = []
    for it in items:
        cards.append('<div class="ziyuan-card" data-anim>'
                     '<div class="zy-ch">%s</div>'
                     '<div class="zy-form">%s</div>'
                     '<div class="zy-mean">%s</div></div>'
                     % (esc(it.get("ch", "")), esc(it.get("form", "")), em(it.get("mean", ""), s.get("emphasis"))))
    n = max(1, len(items))
    return ('<div class="frame">'
            '<div class="kicker" data-anim>%s</div>'
            '%s'
            '<div class="ziyuan-grid" style="margin-top:5vh;grid-template-columns:repeat(%d,1fr)">%s</div>'
            '</div>') % (esc(s.get("kicker", "")), _hxl(s), n, "".join(cards))

def p_chain(s, ctx):
    """L12b 链条式：横向节点链，节点间「→」；支持留白节点(blank)。
    2026-08-19 修复：①_ hxl 已自带 <h2>，去掉外层重复包裹（此前嵌套 h2 非法）；② M10 正文原生渲染在标题与链条之间（此前 body-fixed 补挂在链条后易被忽略）。"""
    _MOUNT = {"M08", "M10", "items:"}  # 本版式接受的大纲字段（MOUNTS 唯一源：gen_mounts.py 读取，禁止手改注册表）
    nodes = s.get("items", [])
    elems = []
    for i, it in enumerate(nodes):
        ch = it.get("ch", "")
        d = it.get("d", "")
        if it.get("blank"):
            node = '<div class="chain-node" data-anim><div class="chain-ch chain-blank">？留白</div></div>'
        else:
            ch_parts = [x for x in re.split(r"[/／]", ch) if x.strip()] if ch else []
            inner = '<div class="chain-ch">%s</div>' % "<br/>".join(em(c, s.get("emphasis")) for c in ch_parts) if ch_parts else ""
            if d:
                inner += '<div class="chain-d">%s</div>' % em(d, s.get("emphasis"))
            node = '<div class="chain-node" data-anim>%s</div>' % inner
        elems.append(node)
        if i < len(nodes) - 1:
            elems.append('<div class="chain-arrow">→</div>')
    bh = _body_block(s.get("body"), s.get("emphasis"), v=s.get("m10_v"), h=s.get("m10_h"))
    return ('<div class="frame">'
            '<div class="kicker" data-anim>%s</div>'
            '%s'
            '%s'
            '<div class="chain chain-bottom">%s</div>'
            '</div>') % (esc(s.get("kicker", "")), _hxl(s), bh, "".join(elems))

def _fixed_elements(s, ctx):
    """页面级固定元件：在 .frame 末尾统一注入（根治结构化版式吞掉 M10 小字）。

    规则：
    - M10 正文/小字：仅当本版式不原生渲染 body 时补挂（lead/grid2/text/callout 已原生处理，避免重复）。
    - M11 引文：仅当本页版式不是 callout 时，作为底部引文框挂上（引文降级为固定元件）。
    - M13 注释 / M14 下标：任意内容页可用；仅封面(L01)不渲染 M14（hero 及其他页均显示；M13 未按版式拦截）。
    - 位置/对齐/字号可由大纲 token 控制：m14_align(左/中/右)、m14_size、m13_align 等。
    """
    t = s.get("type")
    parts = []
    BODY_NATIVE = {"lead", "grid2", "text", "callout", "interactive", "figsvg", "chain", "hbar", "kpitower", "loop", "system", "wall", "statement", "timeline", "microcard", "imagehero"}
    # M10 正文/小字（补挂，留在 .frame 内作为主内容）
    _bhtml = _body_block(s.get("body"), s.get("emphasis"), "body-zh", s.get("m10_v"), s.get("m10_h"))
    if _bhtml and t not in BODY_NATIVE:
        parts.append('<div class="body-fixed">%s</div>' % _strip_anim(_bhtml))
    # 设计指令占位（待我按描述生成真实 SVG 后替换；已有 svg_inline 或本页已渲染真实节点链时不再显示）
    if s.get("design") and not s.get("svg_inline") and not s.get("svg") and s.get("type") != "chain":
        parts.append('<div class="design-note" data-anim><b>待设计 ·</b> %s</div>' % esc(s["design"]))
    return "".join(parts)

def _svg_apply_maxh(svg, maxh):
    """把 M12 maxh: 真正作用到底部图位的内联 SVG 上（2026-09-03 修复）。

    锁：CSS 里 `.fig-svg svg{max-height:54vh}`（DOM 里 svg 是 figure>div>svg，
    所以实际生效的是这条后代选择器；`figure.fig-svg>svg` 只管 svg 直挂 figure 的情形）
    是硬编码上限，而 maxh 此前只写进 figure / 内层 div 的 style（div 无 overflow:hidden，
    不裁剪），**SVG 自身从未收到 maxh**，于是永远停在 54vh——`M12 maxh: 80/90` 形同虚设。

    做法：把 `max-height:<maxh>` 注入 <svg> 自己的 style（内联样式优先级最高）。
    - 显式给了 maxh：用该值（可大于也可小于 CSS 默认上限——想调小就给小值）。
    - 没给 maxh（maxh 为空）：直接返回原 svg，交回 CSS 默认 54vh，图不会无故变大变小。
    ⚠️ 本函数只解决「上限」。SVG 显示高度还有另一道独立成因——见 _bottom_elements
    中 figure 的 `width:100%`：宽度若不确定（fit-content），高度 = 宽度 ÷ 画布比
    会连同一起塌缩。两处是两回事，别混为一谈。
    """
    if not svg or not maxh:
        return svg   # 未显式给 M12 maxh → 不注入，交回 CSS 默认上限（图不会无故变大变小）
    m = re.search(r'<svg\b([^>]*)>', svg)
    if not m:
        return svg
    attrs = m.group(1)
    add = 'max-height:%s' % maxh
    if re.search(r'style\s*=\s*"', attrs):
        new_attrs = re.sub(r'style\s*=\s*"([^"]*)"',
                           lambda mm: 'style="%s;%s"' % (mm.group(1).rstrip(';'), add),
                           attrs, count=1)
    else:
        new_attrs = attrs + ' style="%s"' % add
    return svg[:m.start()] + '<svg' + new_attrs + '>' + svg[m.end():]


def _bottom_elements(s, ctx):
    """底部固定元件（与内容区解耦，独立钉在 .slide 底部，永不被 .frame 溢出裁切）：
       M13 注释 / M14 下标 / M11 引文框。仅封面(cover)不挂 M14；hero 及其他页均挂。"""
    t = s.get("type")
    parts = []
    # 通用图位（路线2 · 2026-08-23）：非原生图位版式挂有 svg_inline 时，在底部 slide-aux
    # 钉一处示意图，避免被静默丢弃（仅在 L05/L11/L12 已原生渲图，
    # chain 走 items 链，二者跳过以免重复/错位）。_fixed_elements 的「待设计」占位本就要求
    # not svg_inline，所以挂上图后占位自动消失，零冲突。
    if s.get("svg_inline") and t not in ("grid2", "imgslot", "figsvg", "chain"):
        # 2026-08-23 穿透修复：底部通用图位也读 M12 maxh:/ratio:（经 _safe_length/_safe_ratio 净化），
        # 使任何版式都能用同一条大纲命令调示意图大小；未设则沿用安全默认 38vh / 92%。
        _img_cfg = s.get("img", {}) or {}
        _bmh = _safe_length(_img_cfg.get("maxh", "38"), "vh") or "38vh"
        # 注意：底部 SVG 图（fig-svg）**不挂 ratio 类**。
        # 原因：SVG 图示的高度由自身 viewBox 宽高比 + max-height 决定，
        # 引擎 CSS 里 .fig-svg 没有任何 r-NxM 规则（r-3x4/r-16x9 等只挂在
        # 光栅图 .frame-img 上），挂了也是死类、且容易让人误以为它在控比例。
        # 此前这里复用 _safe_ratio("") 的默认回落 "3x4"，导致每页被动加 r-3x4
        # 死类——现已移除（2026-09-03 清理）。
        _bcls = ""
        # width:100% 是必需的（2026-09-03 根因修复）：
        #   figure 是 .slide-aux（column flex）的 flex item，`margin-inline:auto` 的
        #   横向 auto 外边距会**取消 align-items:stretch**，宽度退回 fit-content；
        #   而内联 SVG 只有 viewBox、没有 width/height 属性（无内在尺寸），
        #   fit-content 取值时百分比 width:100% 解析为 auto → 塌缩到 CSS 默认
        #   对象尺寸 300×150，显示高度只剩 ~150px（约页面 1/5），改 maxh 完全无效。
        #   给 figure 一个确定宽度即彻底解除塌缩；max-width + auto 外边距仍负责居中和封顶。
        #
        # 2026-09-10 补图注：此前底部通用图位**只输出 figure，不输出 svg_cap**，
        # 于是「非 figure 版式（L14/L03/L08…）挂内联 SVG」时图注被静默丢弃
        # （p_figsvg 分支与 _img_figure 分支各有一份 cap 逻辑，此处漏了）。
        # 现补齐：与 p_figsvg / _img_figure 用同一个 `.svg-cap` 类，样式一致。
        _bcap = s.get("cap", "")
        _bcap_html = ('<div class="svg-cap"><span>%s</span></div>' % esc(_bcap)) if _bcap else ""
        parts.append('<figure class="fig-svg%s" data-anim style="max-height:%s;'
                     'width:100%%;max-width:min(1300px,95%%);margin-inline:auto">'
                     '<div style="max-height:%s">%s</div>%s</figure>'
                     % (_bcls, _bmh, _bmh, sanitize_svg(_svg_apply_maxh(s["svg_inline"], _bmh)), _bcap_html))
    # M13 注释 / M14 下标：同时存在时合并进 .aux-row（同一底部行、两端对齐，免上下错层）
    _m13 = ""
    if s.get("annotation"):
        a = s.get("m13_align", "left")
        sz = s.get("m13_size", "")
        szcls = " size-lg" if "大" in sz else (" size-sm" if "小" in sz else "")
        _m13 = _movewrap('<div class="annot%s" data-anim style="text-align:%s">%s</div>'
                         % (szcls, a, em(s["annotation"], s.get("emphasis"))),
                         s.get("m13_v"), s.get("m13_h"))
    _m14 = ""
    if s.get("footnote") and t != "cover":
        # 仅封面(L01)保持洁净不挂下标；章节扉页(hero/L02)及其他页均显示
        f = s.get("m14_align", "right")
        sz = s.get("m14_size", "")
        szcls = " size-lg" if "大" in sz else (" size-sm" if "小" in sz else "")
        _m14 = _movewrap('<div class="footnote %s%s" data-anim>%s</div>'
                         % (f, szcls, em(s["footnote"], s.get("emphasis"))),
                         s.get("m14_v"), s.get("m14_h"))
    if _m13 and _m14:
        parts.append('<div class="aux-row" data-anim>%s%s</div>' % (_m13, _m14))
    else:
        if _m13:
            parts.append(_m13)
        if _m14:
            parts.append(_m14)
    # M11 引文框（非 callout 页，作为底部引文框）
    if t != "callout" and s.get("callout_fixed"):
        cf = s["callout_fixed"]
        parts.append(_movewrap('<div class="callout-fixed" data-anim>'
                               '<div class="q-big">%s</div>'
                               '<span class="callout-src">%s</span></div>'
                               % (em(cf.get("q", ""), s.get("emphasis")), esc(cf.get("cite", ""))),
                               s.get("m11_v"), s.get("m11_h")))
    # M16 参考链接（2026-08-24 新增：页面级链接框，底部 slide-aux；支持多条，新标签打开）
    if s.get("links"):
        items_html = []
        for lk in s["links"]:
            txt = (lk.get("text") or "").strip()
            url = (lk.get("url") or "").strip()
            safe = safe_url(url)
            if safe:
                href = esc_attr(safe)
                label = esc(txt) if txt else esc(safe)
                items_html.append('<a class="ilink" href="%s" target="_blank" rel="noopener noreferrer">'
                                  '<i data-lucide="external-link" class="ico-inline"></i>%s</a>' % (href, label))
            elif txt:
                # 无合法 URL：仅显示文字（退化，不渲染可点链接）
                items_html.append('<span class="ilink-text">%s</span>' % esc(txt))
        if items_html:
            parts.append('<div class="links-fixed" data-anim>'
                         '<span class="links-h">参考链接</span>'
                         '<div class="links-list">%s</div></div>' % "".join(items_html))
    return "".join(parts)

def _strip_anim(html_str):
    """去掉 body 块里多余的 data-anim 包裹（固定元件统一带一个 data-anim 即可）。"""
    return html_str.replace(' data-anim', '', 1) if html_str else html_str

_PRIMITIVES = {
    "wall": (p_wall, "wall"),
    "kpitower": (p_kpitower, "kpitower"),
    "loop": (p_loop, "loop"),
    "system": (p_system, "system"),
    "hbar": (p_hbar, "hbar"),
    "cover": (p_cover, "hero"),
    "hero": (p_hero, "hero"),
    "lead": (p_lead, "cascade"),
    "statgrid": (p_statgrid, "cascade"),
    "grid2": (p_grid2, "cascade"),
    "rowline": (p_rowline, "cascade"),
    "quote": (p_quote, "quote"),
    "pillar": (p_pillar, "cascade"),
    "directional": (p_directional, "directional"),
    "callout": (p_callout, "cascade"),
    "imgslot": (p_imgslot, "cascade"),
    "figsvg": (p_figsvg, "cascade"),
    "text": (p_text, "cascade"),
    "pipeline": (p_pipeline, "pipeline"),
    "statnote": (p_statnote, "cascade"),
    "statement": (p_statement, "cascade"),
    "timeline": (p_timeline, "cascade"),
    "microcard": (p_microcard, "cascade"),
    "imagehero": (p_imagehero, "cascade"),
    "interactive": (p_interactive, "cascade"),
    "ziyuan": (p_ziyuan, "cascade"),
    "chain": (p_chain, "cascade"),
    "raw": (p_raw, "cascade"),
}

# ----------------------------------------------------------------------------
# 4) 节奏（无连续3同色）与编号
# ----------------------------------------------------------------------------
def _assign_colors(slides):
    is_hero = lambda s: s.get("type") in ("hero", "cover") or "hero" in (s.get("classes") or "")
    # 金句页（L07）默认暗底，强化仪式感（D1：复用 .slide.dark，不新增主题）
    for s in slides:
        if s.get("type") == "quote" and s.get("color") not in ("light", "dark"):
            s["color"] = "dark"
    colors = [s.get("color") if s.get("color") in ("light", "dark") else None for s in slides]
    # 自动填充：交替
    for i, c in enumerate(colors):
        if c is None:
            colors[i] = "light" if (i % 2 == 0) else "dark"
    # 打散连续≥3
    n = len(colors)
    for _ in range(40):
        bad = None
        i = 0
        while i < n:
            j = i
            while j + 1 < n and colors[j+1] == colors[i]:
                j += 1
            if j - i + 1 >= 3:
                bad = (i, j, colors[i]); break
            i = j + 1
        if not bad:
            break
        i, j, c = bad
        cands = [x for x in range(i, j+1) if not is_hero(slides[x])]
        if not cands:
            break
        mid = cands[len(cands)//2]
        colors[mid] = "dark" if c == "light" else "light"
    return colors

def _number(slides, total):
    """返回每页右下角 M04 页码：位置/总页数（含封面，封面为 01/total）。"""
    out = []
    for i, s in enumerate(slides):
        pos = i + 1
        out.append("%02d / %02d" % (pos, total))
    return out

# ----------------------------------------------------------------------------
# 5) 渲染整页
# ----------------------------------------------------------------------------
# 双基线跳过：封面/扉页/收束（h-hero 整页结构）、L24 论断（无标题）、L27 图幅主导、raw
_DUAL_SKIP_TYPES = {"cover", "hero", "statement", "imagehero", "interactive", "raw"}

def _apply_dual(inner, slide):
    """双基线后处理：把 frame 开头的「kicker＋标题」自动包进固定高 .head-block，
    标题行数决定区内对齐——1 行上下居中（不贴眉标）、2 行顶对齐上下分布；正文从固定行线起向下生长。
    所有内页原语统一生效、免逐个改；结构特殊版式（cover/hero/L24/L27/raw）跳过。"""
    t = slide.get("type", "text")
    if t in _DUAL_SKIP_TYPES:
        return inner
    fm = re.search(r'<div class="frame([^"]*)"((?:\s+style="[^"]*")?)>', inner)
    if not fm:
        return inner
    cls, style_attr = fm.group(1), (fm.group(2) or "")
    head_start = fm.end()
    # kicker（可选）＋标题（单行 h2.h-xl，或多行 .h-xl-line×N）
    hm = re.compile(
        r'\s*(<div class="kicker"[^>]*>.*?</div>)?'
        r'\s*(?:(<h[12] class="h-xl"[^>]*>.*?</h[12]>)|((?:<div class="h-xl-line[^>]*>.*?</div>)+))',
        re.S).match(inner, head_start)
    if not hm:
        return inner
    seg = hm.group(0)
    n_lines = 1 if hm.group(2) else (len(re.findall(r'<div class="h-xl-line', hm.group(3))) if hm.group(3) else 1)
    hc = "head-2" if n_lines >= 2 else "head-1"
    wrapped = '<div class="head-block %s">%s</div>' % (hc, seg)
    # 清理 frame 的 center 类与 inline justify-content:center（否则覆盖 flex-start）
    new_cls = re.sub(r'\bcenter\b', '', cls).strip()
    new_cls = (" " + new_cls) if new_cls else ""
    if style_attr:
        style_attr = re.sub(r'justify-content:\s*center;?', '', style_attr)
        if re.search(r'style="\s*"', style_attr):
            style_attr = ""
    open_tag = '<div class="frame%s"%s>' % (new_cls, style_attr)
    return inner[:fm.start()] + open_tag + wrapped + inner[hm.end():]

def _apply_frame_mods(inner, slide):
    """页面级 frame 修饰：- 纵向:顶/中/底 → v-top/v-mid/v-bottom；
    - 规则线:是 → rule-accent（标题上方 accent 短横线）。统一注入到首个 .frame 的 class，免各原语重复。"""
    add = []
    va = str(slide.get("纵向") or slide.get("v_align") or slide.get("vertical") or "").strip()
    VMAP = {"顶": "v-top", "上": "v-top", "top": "v-top",
            "中": "v-mid", "center": "v-mid",
            "底": "v-bottom", "下": "v-bottom", "bottom": "v-bottom"}
    if va in VMAP:
        add.append(VMAP[va])
    rl = str(slide.get("规则线") or slide.get("rule_line") or slide.get("rule") or "").strip()
    if rl in ("是", "true", "1", "yes", "on"):
        add.append("rule-accent")
    if not add:
        return inner
    anchor = inner.find('class="frame')
    if anchor == -1:
        return inner
    close_q = inner.find('"', anchor + 7)
    if close_q == -1:
        return inner
    return inner[:close_q] + " " + " ".join(add) + inner[close_q:]

def _render_slide(slide, ctx, color, num_right):
    t = slide.get("type", "text")
    if t not in _PRIMITIVES:
        t = "raw"
    fn, anim = _PRIMITIVES[t]
    inner = fn(slide, ctx)
    # 元件级三控后处理（M05 kicker / M07 h_sub / M09 h_md 的字号+垂直+水平，2026-08-19）
    inner = _apply_ctrl(inner, slide)
    inner = _apply_frame_mods(inner, slide)
    inner = _apply_dual(inner, slide)
    # 主题句对齐/多行/逐行字号已由 _hxl() 在版式原语内统一处理（居中/逐行对齐/大·小）
    # 页面级固定元件分两类：主内容补挂（body-fixed/design）注入 .frame 末尾；
    # 底部元件（M13/M14/M11 引文框）独立钉在 .slide 底部，永不被 .frame 溢出裁切。
    bottom = ""
    if t != "raw":
        fixed = _fixed_elements(slide, ctx)
        if fixed:
            # 稳健注入：定位 inner 中最后一个 </div>（即 .frame 闭合处）之前插入 fixed，
            # 不再依赖 inner 必须以 </div> 结尾（避免某些版式原语末节点非 </div> 时静默丢弃）。
            idx = inner.rfind('</div>')
            if idx != -1:
                inner = inner[:idx] + fixed + inner[idx:]
            else:
                inner = inner + fixed
        bottom = _bottom_elements(slide, ctx)
    bottom_html = ('<div class="slide-aux">%s</div>' % bottom) if bottom else ""
    is_hero = t in ("hero", "cover") or "hero" in (slide.get("classes") or "")
    is_cover = (t == "cover")  # 仅封面(L01)隐藏 顶右/底左/底右；章节扉页(hero/L02)及其他页全显示
    cls = "slide hero %s" % color if is_hero else "slide %s" % color
    if slide.get("classes"):
        cls += " " + slide["classes"]
    # ===== 四角布局（用户拍板 2026-08-18 终版）=====
    # 左上 TL = M01（每页显示，含封面/hero）
    chrome_left = slide.get("m01", "")
    # 右上 TR = M02 讲稿题目；仅封面(L01)隐藏，章节扉页(hero/L02)及其他页全显示
    chrome_right = "" if is_cover else ctx.get("lecture_title", "")
    # 左下 BL = M03 块·内容；仅封面隐藏
    foot_left = "" if is_cover else slide.get("foot_left", "")
    # 右下 BR = M04 页码(NN/总) · 系列名（可选）；仅封面隐藏
    _nr = num_right if num_right else "01 / %02d" % ctx.get("page_total", 0)
    _series = ctx.get("series", "")
    foot_right = "" if is_cover else (("%s · %s" % (_nr, _series)) if _series else _nr)
    anim = slide.get("data_animate") or anim  # 允许大纲局部覆盖默认动效（优化意见(一)7）
    data_anim = ' data-animate="%s"' % anim if anim else ""
    foot_left_html = esc(foot_left)
    sec = ('<section class="%s" data-theme="%s"%s>\n'
           '  <div class="chrome"><div>%s</div><div>%s</div></div>\n'
           '  %s\n'
           '  %s\n'
           '  <div class="foot"><div class="title">%s</div><div>%s</div></div>\n'
           '</section>') % (cls, color, data_anim, esc(chrome_left), esc(chrome_right),
                            inner, bottom_html, foot_left_html, esc(foot_right))
    return sec

# ----------------------------------------------------------------------------
# 6) 组装
# ----------------------------------------------------------------------------
# 6.5) 离线字体开关（子集内嵌）
#   默认字体走 Google Fonts CDN（唯一网络依赖）。启用离线模式（元数据 字体源: 本地 /
#   字体: 本地 / CLI --offline-fonts / profile 字体源: 本地）后，在构建期把本 deck
#   实际用到的中文字符从本地 Noto SC 源 woff2/ttf 切出子集，base64 内嵌进 <style>，
#   产物 self-contained、断网也不豆腐块。
#   本地字体源默认位于 ~/.workbuddy/eink-font-cache/（可用环境变量 EINK_FONT_DIR 改），
#   由 engine/eink_assets/get_fonts.py 一次性下载；缺源或 fonttools 时优雅回退 CDN 并告警。
# ----------------------------------------------------------------------------
_FONT_LOCAL = {
    "Noto Serif SC": "NotoSerifSC",
    "Noto Sans SC": "NotoSansSC",
}
_FONT_LOCAL_ALIASES = ("本地", "离线", "local", "offline")

def _is_offline_requested(raw_mode):
    return str(raw_mode or "").strip().lower() in _FONT_LOCAL_ALIASES

def _offline_font_cache_dir():
    return os.environ.get("EINK_FONT_DIR",
                          os.path.join(os.path.expanduser("~"), ".workbuddy", "eink-font-cache"))

def _build_offline_font_css(deck_text, title=""):
    """切本地 Noto SC 子集、base64 内嵌；不可用返回 None（调用方回退 CDN）。"""
    try:
        from fontTools.subset import Subsetter, Options
        from fontTools.ttLib import TTFont
    except Exception:
        print("[字体警告] 未安装 fonttools，无法嵌入离线字体，回退 Google Fonts CDN（产物仍需联网）")
        return None
    cache = _offline_font_cache_dir()
    # 抽取可见文本（去 HTML 标签），含标题，去重后作为子集范围
    text = re.sub(r"<[^>]+>", "", deck_text) + "\n" + (title or "")
    chars = "".join(sorted(set(text)))
    blocks = []
    any_ok = False
    for family, fname in _FONT_LOCAL.items():
        src = None
        for _ext in (".woff2", ".ttf"):
            _cand = os.path.join(cache, fname + _ext)
            if os.path.exists(_cand):
                src = _cand
                break
        if src is None:
            print("[字体警告] 缺少本地字体源 %s(.woff2/.ttf) —— %s 无法离线嵌入（请先跑 engine/eink_assets/get_fonts.py）" % (os.path.join(cache, fname), family))
            continue
        try:
            opts = Options()
            opts.recalc_bounds = False
            opts.notdef_outline = True
            opts.recalc_timestamp = False
            opts.drop_tables = []
            opts.glyph_names = False
            opts.layout_features = ['*']
            opts.name_IDs = ['*']
            opts.name_legacy = True
            opts.name_languages = ['*']
            subsetter = Subsetter(options=opts)
            subsetter.populate(text=chars)
            font = TTFont(src)
            subsetter.subset(font)
            buf = io.BytesIO()
            font.save(buf)
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            blocks.append(
                "@font-face{font-family:%s;src:url(data:font/woff2;base64,%s) format('woff2');font-weight:100 900;font-display:swap;}" % (family, b64))
            any_ok = True
        except Exception as _e:
            print("[字体警告] 子集化 %s 失败：%s" % (family, _e))
    if not any_ok:
        return None
    return "<style id='offline-fonts'>\n" + "\n".join(blocks) + "\n</style>"

def _assemble_head(title, offline_style=""):
    h = _HEAD.replace(re.search(r"<title>.*?</title>", _HEAD, re.S).group(0),
                     "<title>%s</title>" % esc(title))
    if offline_style:
        h = re.sub(r'<link rel="preconnect" href="https://fonts\.googleapis[^>]*>\n?', "", h)
        h = re.sub(r'<link rel="preconnect" href="https://fonts\.gstatic[^>]*>\n?', "", h)
        h = re.sub(r'<link href="https://fonts\.googleapis[^>]*>\n?', "", h)
        h += "\n" + offline_style
    return h

def build(lecture, out_dir, theme=None, font_mood=None, font_mode=None):
    slides = lecture["slides"]
    _theme = _resolve_theme(theme or lecture.get("theme"))
    _fm = (font_mood or lecture.get("font_mood") or _theme["font"] or "serif")
    _theme_css = ("\n  :root{\n"
                  "    --ink:%(ink)s; --ink-rgb:%(ink_rgb)s;\n"
                  "    --paper:%(paper)s; --paper-rgb:%(paper_rgb)s;\n"
                  "    --paper-tint:%(paper_tint)s; --ink-tint:%(ink_tint)s;\n"
                  "    --accent:%(accent)s; --accent-ink:%(accent_ink)s;\n"
                  "  }\n") % _theme
    if str(_fm).strip().lower() in ("sans", "无衬线"):
        _theme_css += '  :root{ --serif-zh: "Noto Sans SC",source-han-sans-sc,sans-serif; }\n'
    _ink01 = _hex2rgb01(_theme["ink"]); _acc01 = _hex2rgb01(_theme["accent"]); _paper01 = _hex2rgb01(_theme["paper"])
    total = len(slides)
    colors = _assign_colors(slides)
    nums = _number(slides, total)
    ctx = {
        "lecture_no": lecture.get("lecture_no", 1),
        # 系列总数缺省兜底：不写死任何系列的讲数，回落「当前讲次」以保证封面自洽
        "series_total": lecture.get("series_total") or lecture.get("lecture_no", 1),
        # 预留：当前 HTML 模板未消费 series_total（仅 Lecture() 传入并落 ctx），
        # 保留以备封面「第 N / M 讲」等处启用；勿误判为死代码而删除解析逻辑。
        "series": lecture.get("series_name", ""),
        "short_title": lecture.get("short_title", lecture.get("title", "")),
        "series_name": lecture.get("series_name", lecture.get("series", "")),  # M02 系列名
        "lecture_title": lecture.get("lecture_title", lecture.get("title", "")),      # M01 讲稿题目
        "page_total": total,
    }
    # 预解析本地配图真实尺寸（M12 文件 已拷进输出目录；img["file"] 是相对路径）
    # 供 _img_figure 在 ratio=auto 时按原图比例渲染（2026-08-19，修复 P11 被裁）
    for s in slides:
        _img = s.get("img") or {}
        _f = _img.get("file")
        if _f:
            real = _f if os.path.isabs(_f) else os.path.join(out_dir, _f)
            _sz = _img_size(real)
            if _sz:
                _img["_w"], _img["_h"] = _sz
    sections = []
    for s, c, nr in zip(slides, colors, nums):
        sections.append(_render_slide(s, ctx, c, nr))
    deck = "\n".join(sections)
    # WebGL 双背景主题色注入（2026-09-06 修）：替换占位符为当前主题 RGB（_ink01/_acc01/_paper01，
    # 原为 kraft 硬编码，换主题不生效；占位符未命中时 _DECK_JS 原样输出，不影响旧产物回归）。
    _deck_js = (_DECK_JS.replace("__INK01__", _ink01).replace("__ACC01__", _acc01)
                .replace("__PAPER01__", _paper01))

    # 离线字体开关（子集内嵌）：仅在请求且本地源可用时切子集、去 CDN 链接；否则原样走 CDN
    _font_mode = font_mode or lecture.get("font_mode") or ""
    offline_style = ""
    if _is_offline_requested(_font_mode):
        _off = _build_offline_font_css(deck, lecture.get("title", ""))
        if _off:
            offline_style = _off
        else:
            print("[字体] 离线字体不可用，已回退 Google Fonts CDN（产物仍需联网）")
    head = _assemble_head(lecture.get("title", ""), offline_style)

    html_doc = ("<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n%s\n"
                "<style>%s%s</style>\n<style id='theme-override'>%s</style>\n</head>\n<body>\n"
                "<script>%s</script>\n%s\n"
                "<div id=\"deck\">\n%s\n</div>\n<div id=\"nav\"></div>\n"
                "<script>%s</script>\n"
                "<script>%s</script>\n%s\n%s\n%s\n<script type=\"module\">%s</script>\n"
                "</body>\n</html>\n") % (
        head, _CSS, _CSS_EXTRA, _theme_css, _INIT, _CANVASES, deck, _deck_js, _STEP_JS,
        _LUCIDE_SRC, _LUCIDE_INIT, _MOTION_SRC, _MOTION)

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")
    open(out_path, "w", encoding="utf-8").write(html_doc)

    # 拷贝本地动效/图标依赖（离线可用；随引擎固化的稳定资源，不依赖任何已交付讲次与 CDN）
    for _name in ("motion.min.js", "lucide.umd.min.js"):
        src_asset = os.path.join(_THIS, "eink_assets", _name)
        dst_asset = os.path.join(out_dir, "assets", _name)
        if os.path.exists(src_asset):
            os.makedirs(os.path.dirname(dst_asset), exist_ok=True)
            shutil.copyfile(src_asset, dst_asset)
        else:
            print("[资产警告] 缺少 %s ——图标/动效将降级，请检查 engine/eink_assets/" % src_asset)  # 批次C：不再静默跳过
    return out_path

# ----------------------------------------------------------------------------
# 7) 校验
# ----------------------------------------------------------------------------
def validate(html_doc):
    secs = re.findall(r'<section class="slide([^"]*)"', html_doc)
    seq = "".join("L" if "light" in c else "D" for c in secs)
    runs = [(i, i+2) for i in range(len(seq)-2) if seq[i] == seq[i+1] == seq[i+2]]
    # emoji 检测范围（2026-09-08 修复 N3，补 U+2B00-2BFF 与零散码位）：
    #   1F000-1FAFF 主 emoji 区 / 2600-27BF 杂项符号+装饰符号（⚠✅❌ 等）
    #   2B00-2BFF 杂项符号与箭头（⭐⬛⭕➕ 等）——原正则漏掉，⭐ 无法被检出
    #   203C 2049 20E3 3030 303D 3297 3299 零散 emoji 码位（‼⁉ 键帽 〰〽㊗㊙）
    # 刻意【不】纳入 U+2190-2199/21FF 箭头区：引擎自身用「→」作 L12b 链条节点分隔符，
    # 纳入会把每页正常排版误判为 emoji（实测产物内含 ← → 各 1 处）。
    emoji = re.findall(
        r"[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF"
        r"\U0000203C\U00002049\U000020E3\U00003030\U0000303D\U00003297\U00003299]",
        html_doc)
    rep = {
        "页数": len(secs),
        "浅L/深D": (seq.count("L"), seq.count("D")),
        "连续3同色": runs if runs else "无",
        "emoji": len(emoji),
        "svg平衡": (html_doc.count("<svg"), html_doc.count("</svg>")),
        "figure平衡": (html_doc.count("<figure"), html_doc.count("</figure>")),
        "accent出现": html_doc.count('class="accent"') + html_doc.count('stat-nb accent'),
    }
    return rep

# ----------------------------------------------------------------------------
# 8) Lecture 容器（可选，便于 JSON 驱动）
# ----------------------------------------------------------------------------
def Lecture(title, lecture_no, series_total=1, slides=None, **kw):
    d = {"title": title, "lecture_no": lecture_no, "series_total": series_total,
         "slides": slides or [], "series": kw.get("series", ""),
         "short_title": kw.get("short_title", title), "foot_right": kw.get("foot_right", "")}
    return d

# ----------------------------------------------------------------------------
# 9) 示例：用一份样例数据跑通全部版式原语（证明模板可用）
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    # 自检样例一律用中性内容：不得出现任何具体系列的选题、人名、地名。
    # SVG 只用 currentColor / var(--accent)，贯彻引擎自身的「配色自适应铁律」。
    sample = Lecture(
        title="示例 · 通用模板验证",
        lecture_no=1, series_total=8, short_title="模板示例",
        slides=[
            {"type": "cover", "kicker": "通用 eink 演示引擎",
             "title": "模板验证示例", "subtitle": "主题化 · 单文件 HTML · 通用生成引擎",
             "meta": ["单文件 HTML", "浏览器放映", "B 键静态"]},
            {"type": "hero", "label": "第一块 · 版式总览", "title": "一套骨架，多讲通用", "color": "dark"},
            {"type": "lead", "kicker": "引言", "title": "为什么抽成引擎",
             "body": "把已验证的视觉底座与版式原语抽出来，以后每讲只填数据即可出同款 PPT；强调锚点在大纲阶段就定好，全系列一贯。",
             "emphasis": ["强调锚点", "一贯"]},
            {"type": "statgrid", "kicker": "数据大字报", "title": "引擎能力一览",
             "stats": [
                {"label": "内置版式", "nb": "19", "unit": "种", "note": "L01–L18b 全覆盖", "accent": True},
                {"label": "预设主题", "nb": "5", "unit": "套", "note": "incl. kraft / indigo", "accent": True},
                {"label": "产出文件", "nb": "1", "unit": "个", "note": "HTML 单文件自包含", "accent": True},
             ]},
            {"type": "grid2", "kicker": "图文", "title": "左文右图示例",
             "left": ["左侧放正文要点。", "可传字符串或列表，逐行呈现。"],
             "img": {"label": "待补 · 配图（公有领域）", "ratio": "3x4"}},
            {"type": "rowline", "kicker": "年表", "title": "里程碑节点",
             "rows": [
                {"k": "v2.0", "v": "引擎通用化，主题可配", "m": "架构"},
                {"k": "v2.4", "v": "第三方评审 P0/P1 修复", "m": "质量"},
                {"k": "v2.4.6", "v": "maxh / ratio 穿透修复", "m": "版式"},
             ], "emphasis": ["主题可配"]},
            {"type": "quote", "kicker": "名句", "text": "把重复的部分交给引擎，把判断留给人。",
             "src": "— 引擎设计自述", "emphasis": ["引擎"]},
            {"type": "pillar", "kicker": "支柱", "title": "三根支柱",
             "items": [
                {"ic": "layout-grid", "t": "版式", "d": "19 种版式原语，混用不重样。"},
                {"ic": "palette", "t": "主题", "d": "5 套预设配色，一键切换。"},
                {"ic": "sliders-horizontal", "t": "三控", "d": "字号 / 垂直 / 水平，逐元件微调。"},
             ]},
            {"type": "directional", "kicker": "对比", "title": "填空式 vs 手写式",
             "left": {"title": "填空式（本引擎）", "points": ["写大纲 md 即出片", "全系列视觉一致"]},
             "right": {"title": "手写式", "points": ["逐页手工排版", "易前后不一致"]},
             "emphasis": ["视觉一致"]},
            {"type": "callout", "kicker": "引文", "q": "一致性不是限制，是效率的前提。",
             "cite": "— 引擎设计自述"},
            {"type": "imgslot", "kicker": "配图", "title": "大图占位示例",
             "label": "待补 · 配图（公有领域）", "ratio": "3x4"},
            {"type": "figsvg", "kicker": "示意", "title": "渲染流程（示意）",
             "cap": "大纲 md → 引擎 → 单文件 HTML",
             "svg": '<svg viewBox="0 0 680 200" xmlns="http://www.w3.org/2000/svg">'
                    '<line x1="40" y1="100" x2="640" y2="100" stroke="currentColor" stroke-width="2"/>'
                    '<circle cx="80" cy="100" r="10" fill="var(--accent)"/><text x="80" y="140" fill="currentColor" font-size="16" text-anchor="middle">写大纲</text>'
                    '<circle cx="300" cy="100" r="10" fill="var(--accent)"/><text x="300" y="140" fill="currentColor" font-size="16" text-anchor="middle">跑引擎</text>'
                    '<circle cx="560" cy="100" r="10" fill="var(--accent)"/><text x="560" y="140" fill="currentColor" font-size="16" text-anchor="middle">出 HTML</text>'
                    '</svg>'},
            {"type": "pipeline", "kicker": "进程", "title": "使用三步", "cols": 4,
             "steps": [
                {"title": "定主题", "desc": "选预设或自定"},
                {"title": "写大纲", "desc": "按版式填字段"},
                {"title": "跑渲染", "desc": "一行命令出片"},
                {"title": "放映", "desc": "浏览器 / B 键静态"},
             ], "emphasis": ["一行命令"]},
            {"type": "text", "kicker": "正文", "title": "小结",
             "body": "本页验证通用段落版式。模板已覆盖封面/分隔/引言/数据/图文/年表/金句/支柱/对比/引文/配图/示意/进程/正文 等全部原语。",
             "emphasis": ["通用段落版式"]},
            {"type": "hero", "label": "收束", "title": "引擎就绪，逐讲填空", "color": "light"},
        ],
    )
    out = build(sample, os.path.join(_THIS, "_template_sample"))
    rep = validate(open(out, encoding="utf-8").read())
    print("已生成示例：", out)
    print("校验：", json.dumps(rep, ensure_ascii=False))
