# -*- coding: utf-8 -*-
r"""eink-deck 冒烟测试（TST-1 / TST-2 / TST-4 / TST-5）—— 零依赖，可裸跑。

用法：
    python tests/test_smoke.py      # 裸跑：逐条打印 PASS/FAIL，有失败则退出码 1
    pytest tests/                   # 装了 pytest 时同样可收集运行

设计要点：
  * **不需要 pytest**：本文件自带极简 runner（见 main()），因为目标机上未安装 pytest。
  * **不在同步区留字节码**：入口处设 sys.dont_write_bytecode=True，import 引擎时不生成
    engine/__pycache__（OneDrive 同步区不该有 .pyc 噪声）。
  * **用真实数据**：TST-2 直接解析 examples/示例大纲.md 并逐个渲染，不构造假 slide，
    避免"fixture 与真实数据漂移导致测试假绿"。

覆盖（对应审查报告附录 D）：
  TST-1  apply_module M 码 × 字段矩阵；页面级字段全角/半角冒号等价性
  TST-2  28 个版式原语注册表完整 + 示例大纲 28 页全部渲染非空 + raw 直通
  TST-4  _assign_colors 无连续 ≥3 同色（hero 页豁免为已记录边界）
  TST-5  safe_url / sanitize_svg / _parse_link / _link_html 安全白名单
"""
import copy
import os
import re
import sys
import traceback

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(ROOT, "engine")
EXAMPLES_MD = os.path.join(ROOT, "engine", "generated", "示例大纲.md")
if ENGINE not in sys.path:
    sys.path.insert(0, ENGINE)

_CASES = []
_KNOWN_GAPS = []


def case(fn):
    """把函数登记为一条冒烟用例（同时保留 test_ 前缀，便于 pytest 收集）。"""
    _CASES.append(fn)
    return fn


def known_gap(reason):
    """登记一条「已知缺陷」用例：它断言的是**当前有缺陷的行为**。

    * 断言通过 → 缺陷仍在（XFAIL），不计入失败；
    * 断言失败 → 缺陷可能已被修复（XPASS），runner 会高声提示"请更新用例"。
    这样缺陷不会被遗忘，修好时也会立刻显形。
    """
    def deco(fn):
        fn.__known_gap_reason__ = reason
        _KNOWN_GAPS.append(fn)
        return fn
    return deco


# ---------------------------------------------------------------------------
# 惰性 import：让 import 失败表现为一条用例失败，而不是收集期直接崩
# ---------------------------------------------------------------------------
def _ro():
    import render_outline
    return render_outline


def _et():
    import _eink_template
    return _eink_template


def _ctx(total):
    """复刻 _eink_template.build() 里构造的 ctx 字典（键名与 :2233 一致）。"""
    return {
        "lecture_no": 1,
        "series_total": total,
        "series": "冒烟系列",
        "short_title": "冒烟",
        "series_name": "冒烟系列 · 自检",
        "lecture_title": "冒烟课",
        "page_total": total,
    }


def _example_slides():
    """解析示例大纲并构建 slides（真实数据，覆盖 24 页 / 23 个版式）。"""
    import shutil
    import tempfile
    ro = _ro()
    meta, pages = ro.parse_outline(EXAMPLES_MD)
    tmp = tempfile.mkdtemp(prefix="eink_smoke_")
    try:
        lec = ro.build_lecture(meta, pages, os.path.dirname(EXAMPLES_MD), tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return lec["slides"]


def _example_lecture():
    """解析示例大纲并构建完整 lecture 字典（供主题渲染测试整链调用 build()）。"""
    import shutil
    import tempfile
    ro = _ro()
    meta, pages = ro.parse_outline(EXAMPLES_MD)
    tmp = tempfile.mkdtemp(prefix="eink_lecture_")
    try:
        lec = ro.build_lecture(meta, pages, os.path.dirname(EXAMPLES_MD), tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return lec


@case
def test_tst_d_themes_all_render_and_distinct():
    """TST-D（新增覆盖）：5 套预设主题必须都能整链渲染，且主题 CSS 真的注入产物、相互不雷同。

    防两类回归：
      * 某主题名拼写错/漏注册 → THEMES 里查不到，build 回落默认 → accent 与实际不符；
      * 主题被静默忽略（如 _theme_css 没接进产物）→ 5 套 accent 全相同或全等于默认。
    5 套主题 accent 互异（ink-classic/indigo/forest/kraft/dune 各不同），故"全相同"即判红。
    """
    import shutil
    import tempfile
    et = _et()
    lec = _example_lecture()
    accents = {}
    for name in ("ink-classic", "indigo", "forest", "kraft", "dune"):
        assert name in et.THEMES, "THEMES 注册表缺少主题 %r" % name
        d = tempfile.mkdtemp(prefix="eink_theme_")
        try:
            out = et.build(lec, d, theme=name)
            html = open(out, encoding="utf-8").read()
            # 断言必须在 finally 清理目录之前做（否则文件已被 rmtree 删掉）
            assert len(html) > 2000, "%s 产物过小（%d 字节）" % (name, len(html))
            # 主题 CSS 必须真进产物：含该主题专属 accent 值（build 在 <style id='theme-override'> 注入）
            acc = et.THEMES[name]["accent"]
            assert re.search(r"--accent:\s*%s" % re.escape(acc), html), \
                "%s 主题 CSS 未注入产物（期望 accent=%s）" % (name, acc)
            accents[name] = acc
        finally:
            shutil.rmtree(d, ignore_errors=True)
    # 5 套 accent 互异 → 若主题被静默忽略会全回落默认 accent，此断言必红
    assert len(set(accents.values())) == len(accents), \
        "多主题 accent 相同，疑似主题被静默忽略：%r" % accents


def _max_run(colors):
    best = cur = 0
    prev = None
    for c in colors:
        cur = cur + 1 if c == prev else 1
        prev = c
        if cur > best:
            best = cur
    return best


# --- sanitize_svg 的「语义口径」危险检测器（供 TST-5 与其 known-gap 用例使用） ----
# 为什么不用朴素子串（直接搜 "javascript:"）：它会漏掉 `java\tscript:` 这类被控制字符
# 拆断的写法 —— 浏览器解 URL 会先剥掉 tab/换行，于是照样执行。用子串法会把"没真拦"
# 误判成"已修"。故此处按浏览器同向口径归一化后再判定。
_SVG_URL_ATTR_RES = (
    re.compile(r"(?:href|xlink:href|src)\s*=\s*\"([^\"]*)\"", re.I),
    re.compile(r"(?:href|xlink:href|src)\s*=\s*'([^']*)'", re.I),
    re.compile(r"(?:href|xlink:href|src)\s*=\s*([^\s>]+)", re.I),
)
_SVG_EVENT_ATTR_RE = re.compile(r"(?:^|[\s\"'</])on[a-z]+\s*=", re.I)
# 与 _eink_template.py:893 的白名单保持一致。
# ⚠️ 若把裸 `data:` 一律当危险，会把刻意放行的 data:image/png 判成漏网 → 假红。
_SVG_DATA_OK = ("data:image/png", "data:image/jpeg", "data:image/jpg",
                "data:image/gif", "data:image/webp", "data:image/bmp")


def _dangerous_svg(s):
    """按语义口径判断清洗结果里是否仍藏可执行内容。安全返回 ''，否则返回类别名。

    两步与浏览器同向的归一化：
      1. `<tag/on…` → `<tag on…`：HTML 分词器在标签名后的 '/' 处断名，事件属性仍会挂上；
      2. 属性值内的空白与控制字符全部剥除：浏览器解 URL 时正是这么做的。
    """
    t = s or ""
    t = re.sub(r"<([A-Za-z][\w:.-]*)/(?=[A-Za-z])", r"\1 ", t)
    for rx in _SVG_URL_ATTR_RES:
        for m in rx.finditer(t):
            val = re.sub(r"[\s\x00-\x20\x7f]+", "", m.group(1).lower())
            if val.startswith(("javascript:", "vbscript:")):
                return "危险协议"
            if val.startswith("data:") and not val.startswith(_SVG_DATA_OK):
                return "非白名单 data:"
    if _SVG_EVENT_ATTR_RE.search(t):
        return "事件属性"
    return ""


EXPECTED_PRIMITIVES = sorted([
    "callout", "chain", "cover", "directional", "figsvg", "grid2", "hbar",
    "hero", "imgslot", "interactive", "kpitower", "lead", "loop", "pillar",
    "pipeline", "quote", "raw", "rowline", "statgrid", "statnote", "system",
    "text", "wall", "ziyuan", "statement", "timeline", "microcard", "imagehero",
])


# ===========================================================================
# TST-1 · apply_module M 码 × 字段矩阵
# ===========================================================================
@case
def test_tst1_apply_module_mcode_matrix():
    am = _ro().apply_module

    # M01 眉标 / M03 页脚左
    cur = {}
    am(cur, "M01", "", "第1讲 · 冒烟")
    assert cur.get("m01") == "第1讲 · 冒烟", cur
    cur = {}
    am(cur, "M03", "", "概述 · 锚点")
    assert cur.get("foot_left") == "概述 · 锚点", cur

    # M05 kicker；三控落 m05_size/_v/_h
    cur = {}
    am(cur, "M05", "", "2026 · 速览")
    assert cur.get("kicker") == "2026 · 速览", cur
    for field, key, val in (("字号", "m05_size", "大"),
                            ("垂直", "m05_v", "3vh"),
                            ("水平", "m05_h", "2vw")):
        cur = {}
        am(cur, "M05", field, val)
        assert cur.get(key) == val, (field, cur)

    # M06 h_hero：值 / 「 / 」分行 / 逐行对齐；三控；「字号」必须告警且不覆盖主标题
    cur = {}
    am(cur, "M06", "h_hero", "示例标题")
    assert cur.get("title") == "示例标题", cur
    cur = {}
    am(cur, "M06", "h_hero", "从一句话 / 开始")
    assert cur.get("title_lines") == ["从一句话", "开始"], cur
    cur = {}
    am(cur, "M06", "行对齐", "居左·居右")
    assert cur.get("title_aligns") == ["left", "right"], cur
    cur = {}
    am(cur, "M06", "垂直", "2vh")
    assert cur.get("m06_v") == "2vh", cur
    cur = {}
    am(cur, "M06", "水平", "-1vw")
    assert cur.get("m06_h") == "-1vw", cur
    cur = {"title": "原标题"}
    am(cur, "M06", "字号", "0.6")
    assert cur.get("title") == "原标题", "M06「字号」三控不得覆盖主标题：%r" % cur
    assert "m06_size" not in cur, cur

    # M07 h_sub + 三控
    cur = {}
    am(cur, "M07", "h_sub", "副标题")
    assert cur.get("subtitle") == "副标题", cur
    cur = {}
    am(cur, "M07", "字号", "大")
    assert cur.get("m07_size") == "大", cur

    # M08 h_xl：分行 / 逐行对齐 / 逐行字号 / 整体对齐；「字号」必须告警且不覆盖
    cur = {}
    am(cur, "M08", "h_xl", "元件三控， / 一句到位")
    assert cur.get("title_lines") == ["元件三控，", "一句到位"], cur
    cur = {}
    am(cur, "M08", "行对齐", "居左·居右")
    assert cur.get("title_aligns") == ["left", "right"], cur
    cur = {}
    am(cur, "M08", "行大小", "小·大")
    assert cur.get("line_sizes") == ["小", "大"], cur
    cur = {}
    am(cur, "M08", "对齐", "居中")
    assert cur.get("title_align") == "center", cur
    cur = {"title": "原标题"}
    am(cur, "M08", "字号", "大")
    assert cur.get("title") == "原标题", "M08「字号」三控不得覆盖主题句：%r" % cur

    # M09 三控（页面级，作用于对比页两栏）
    cur = {}
    am(cur, "M09", "字号", "小")
    assert cur.get("m09_size") == "小", cur

    # M10 notes / 正文块 / 列表块
    cur = {}
    am(cur, "M10", "notes", "口播备注一")
    assert cur.get("notes") == "口播备注一", cur
    cur = {}
    am(cur, "M10", "正文", "第一段")
    assert len(cur.get("body_blocks") or []) == 1, cur
    cur = {}
    am(cur, "M10", "列表", "甲 / 乙")
    blocks = cur.get("body_blocks") or []
    assert blocks and "items" in blocks[0], cur
    assert len(blocks[0]["items"]) == 2, cur

    # M11 引文框：空值不得落 _m11（否则渲染出空引用框——历史回归位）
    cur = {}
    am(cur, "M11", "callout", "")
    assert "_m11" not in cur, cur
    cur = {}
    am(cur, "M11", "callout", "引文内容")
    assert cur.get("_m11") == "引文内容", cur

    # M12 配图槽位
    cur = {}
    am(cur, "M12", "文件", "images/a.png")
    assert cur.get("img", {}).get("file") == "images/a.png", cur
    cur = {}
    am(cur, "M12", "ratio", "4x3")
    assert cur.get("img", {}).get("ratio") == "4x3", cur
    cur = {}
    am(cur, "M12", "", "待补 · 建议配图")
    assert cur.get("img", {}).get("label") == "待补 · 建议配图", cur

    # M13 注释 + 对齐中英映射
    cur = {}
    am(cur, "M13", "注释", "小注")
    assert cur.get("annotation") == "小注", cur
    cur = {}
    am(cur, "M13", "对齐", "居中")
    assert cur.get("m13_align") == "center", cur

    # M14 下标 + 对齐映射 + 兜底 footnote
    cur = {}
    am(cur, "M14", "对齐", "居右")
    assert cur.get("m14_align") == "right", cur
    cur = {}
    am(cur, "M14", "出处", "见附录")
    assert cur.get("footnote") == "见附录", cur

    # M16 链接：单行形态 / 空值挂起形态
    cur = {}
    am(cur, "M16", "链接", "官网 | https://example.com")
    assert cur.get("links") == [{"text": "官网", "url": "https://example.com"}], cur
    cur = {}
    am(cur, "M16", "链接", "")
    assert cur.get("_links_pending") is True, cur


# ---- 以下为「静默丢数据」历史回归位（附录 D TST-1 的"无"列） ----
@case
def test_tst1_emphasis_anchor_not_silently_dropped():
    """强调锚点必须进 pages[N]['emphasis']；历史 bug 是裸短语整行被静默丢弃。"""
    ro = _ro()
    pages = _parse_inline(ro, "\n".join([
        "- 讲次: 第1讲",
        "",
        "## P01 · 测试",
        "- 版式: L03",
        "- M08 h_xl: 主题句",
        "- 强调: [字号, 强调锚点]",
    ]))
    assert pages[0].get("emphasis") == ["字号", "强调锚点"], pages[0]


@case
def test_tst1_m10_notes_not_silently_dropped():
    """M10 notes 必须落 notes；历史 bug 是早期完全不生效。"""
    am = _ro().apply_module
    cur = {}
    am(cur, "M10", "notes: 口播文字", "口播文字")
    assert cur.get("notes") == "口播文字", cur


def _parse_inline(ro, text):
    """把一段大纲文本写进临时文件再 parse，返回 pages。"""
    import tempfile
    fd, path = tempfile.mkstemp(prefix="eink_inline_", suffix=".md")
    os.close(fd)
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text.rstrip("\n") + "\n")
        _meta, pages = ro.parse_outline(path)
        return pages
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


@case
def test_tst1_fullwidth_colon_equals_halfwidth():
    """页面级字段用全角「：」必须与半角「:」完全等价（批次2 修复的回归位）。

    用「同一段大纲半角/全角各解析一次、逐字段比对」来断言，而不是硬编码字段名——
    这样即使字段名演进，只要等价性成立测试就有效。
    """
    ro = _ro()
    half = "\n".join([
        "- 讲次: 第1讲",
        "- 主题: ink-classic",
        "",
        "## P01 · 测试页",
        "- 版式: L14",
        "- M03: 页脚左",
        "- 强调: [词]",
        "- center: 闭环",
        "- tag: 标签",
        "- items:",
        "  - t=甲 / d=第一条",
        "  - t=乙 / d=第二条",
    ])
    full = half.replace(": ", "：").replace(":\n", "：\n")
    # 构造校验：全角样本里不得残留任何半角冒号，否则测的不是全角路径。
    assert "：" in full and ":" not in full, "全角样本构造失败：%r" % full

    ph = _parse_inline(ro, half)
    pf = _parse_inline(ro, full)
    assert len(ph) == len(pf) == 1, (len(ph), len(pf))

    # 逐字段断言**期望的真实值**（两侧各一遍），而不是只断言"两边相等"——
    # 后者在"两边都解析失败因而都为 None"时也会通过，属假等价（复验建议，2026-09-12 补）。
    expect = {
        "layout": "L14",
        "foot_left": "页脚左",
        "emphasis": ["词"],
        "center": "闭环",
        "tag": "标签",
    }
    for k, want in expect.items():
        assert ph[0].get(k) == want, "半角解析 %r 期望 %r，实得 %r" % (k, want, ph[0].get(k))
        assert pf[0].get(k) == want, "全角解析 %r 期望 %r，实得 %r" % (k, want, pf[0].get(k))
    # items 是列表：条目数、条目内文本、两侧等价，三样都要真解析出来
    assert len(ph[0].get("items") or []) == 2, ph[0].get("items")
    assert ph[0]["items"] == pf[0]["items"], (ph[0].get("items"), pf[0].get("items"))
    assert [it.get("t") for it in ph[0]["items"]] == ["甲", "乙"], ph[0]["items"]
    assert [it.get("d") for it in ph[0]["items"]] == ["第一条", "第二条"], ph[0]["items"]


# ===========================================================================
# TST-2 · 版式原语
# ===========================================================================
@case
def test_tst2_layout_registry_is_complete():
    et = _et()
    got = sorted(et._PRIMITIVES.keys())
    missing = sorted(set(EXPECTED_PRIMITIVES) - set(got))
    extra = sorted(set(got) - set(EXPECTED_PRIMITIVES))
    assert got == EXPECTED_PRIMITIVES, "版式注册表变动：缺失 %r；多出 %r" % (missing, extra)


_SLIDE_SHELL_KEYS = ("type", "color", "classes")


@case
def test_tst2_all_example_pages_render_their_content():
    """每页渲染产物的长度必须**严格大于**「剥掉内容后的空壳」长度。

    为什么不用 `'class="slide' in html`：`_render_slide` 末尾恒返回
    `<section class="slide …">`，任何非空字符串都会通过 —— 那是**空转断言**
    （2026-09-12 复验发现并换掉）。
    空壳对照法自校准、与实现细节解耦：网页内容真进了产物，长度必然增加；
    某版式若把正文静默丢掉，长度就退化成空壳，立刻变红。
    """
    et = _et()
    slides = _example_slides()
    assert len(slides) >= 24, "示例大纲页数异常：%d" % len(slides)
    ctx = _ctx(len(slides))
    nr = "01 / %02d" % len(slides)
    bad = []
    for i, s in enumerate(slides):
        hull = {k: copy.deepcopy(v) for k, v in s.items() if k in _SLIDE_SHELL_KEYS}
        real = et._render_slide(copy.deepcopy(s), ctx, "light", nr)
        shell = et._render_slide(copy.deepcopy(hull), ctx, "light", nr)
        if not isinstance(real, str) or len(real) <= len(shell):
            bad.append((i, s.get("type"), len(real or ""), len(shell)))
    assert not bad, "以下页面的内容未进产物（长度未超过空壳）：%r" % bad
    types = sorted({s.get("type") for s in slides})
    assert len(types) >= 23, "示例大纲覆盖的版式数下降：%d (%r)" % (len(types), types)


@case
def test_tst2_raw_passthrough():
    et = _et()
    html = et._render_slide({"type": "raw", "html": "<div>RAW-MARK</div>"},
                            _ctx(1), "light", "01 / 01")
    assert "RAW-MARK" in html, html[:200]


# ===========================================================================
# TST-4 · _assign_colors「无连续 ≥3 同色」
# ===========================================================================
@case
def test_tst4_assign_colors_never_triples():
    et = _et()
    # 无预设 → 交替
    assert et._assign_colors([{"type": "text"} for _ in range(6)]) == \
        ["light", "dark", "light", "dark", "light", "dark"]
    # 人为制造连续同色 → 必须被打散
    slides = [{"type": "text", "color": "light"} for _ in range(5)]
    colors = et._assign_colors(slides)
    assert _max_run(colors) < 3, "出现连续 ≥3 同色：%r" % colors
    assert "dark" in colors, "打散后应出现 dark：%r" % colors
    # 多长度 × 多预设扫一遍
    for n in (3, 4, 7, 12, 25):
        for preset in (None, "light", "dark"):
            sl = [{"type": "text", "color": preset} for _ in range(n)]
            c = et._assign_colors(sl)
            assert _max_run(c) < 3, "n=%d preset=%r → %r" % (n, preset, c)


@case
def test_tst4_hero_pages_are_exempt_known_limit():
    """已记录边界：整段全是 hero/cover 时无候选可换，算法保留原色（≥3 不被打破）。

    这是**现状行为的固化断言**，用于在将来改进该算法时立刻显形。"""
    et = _et()
    slides = [{"type": "hero", "color": "light"} for _ in range(4)]
    assert et._assign_colors(slides) == ["light"] * 4


# ===========================================================================
# TST-5 · 安全白名单
# ===========================================================================
@case
def test_tst5_safe_url_whitelist():
    et = _et()
    ok = ["http://example.com/a?b=1&c=2", "https://x.cn/p#f", "mailto:a@b.cn"]
    for u in ok:
        assert et.safe_url(u) == u, (u, et.safe_url(u))
    bad = ["javascript:alert(1)", "JavaScript:alert(1)", "java\tscript:alert(1)",
           " data:text/html,<script>alert(1)</script>", "vbscript:msgbox(1)",
           "/relative/path", "example.com", "", None]
    for u in bad:
        assert et.safe_url(u) == "", (u, et.safe_url(u))


@case
def test_tst5_sanitize_svg_blocks_execution():
    """正向：这些载荷必须被真拦住（语义口径）+ 危险标签被剥 + 合法内容不被误伤。"""
    et = _et()
    evil = [
        '<svg><script>alert(1)</script><circle/></svg>',
        '<svg><script>alert(1)',                                    # 未闭合
        '<svg onload="alert(1)"><circle/></svg>',
        '<svg><a href="javascript:alert(1)">x</a></svg>',
        '<svg><foreignObject><body onload="x()"></body></foreignObject></svg>',
        '<svg><style>*{}</style></svg>',
        '<svg><a href="&#106;avascript:alert(1)">x</a></svg>',      # 实体编码绕过
        '<svg><a href="data:image/svg+xml,AAAA">x</a></svg>',       # svg+xml 子类型
        # —— 以下 10 条是 2026-09-12 SEC-1 复验发现的三类绕过家族；
        #    修复（老陈批准）落地后由 known-gap 登记册转为**正向断言**，锁死回归位。
        '<svg/onload=alert(1)><circle/></svg>',                      # ① 斜杠事件（免点击执行）
        '<a/onclick=alert(1)>x</a>',                                 # ① 斜杠事件
        '<a href="javascript:alert(1)>">x</a>',                      # ② 值内含 >
        '<a href="javascript:alert(\'x\')">x</a>',                   # ② 值内含单引号
        '<a href="javascript: alert(1)">x</a>',                      # ② 值内含空格
        '<a href="javascript:alert(1) ">x</a>',                      # ② 值尾空格
        '<a href="  javascript:alert(1)">x</a>',                     # ② 前导空白
        '<a href="data:image/svg+xml,<svg/>">x</a>',                 # ② data:image/svg+xml
        '<a href="java\tscript:alert(1)">x</a>',                     # ③ 值内 tab
        '<a href="java\nscript:alert(1)">x</a>',                     # ③ 值内换行
    ]
    for src in evil:
        s = et.sanitize_svg(src)
        # 1) 语义口径：不得残留可执行协议 / 事件属性
        why = _dangerous_svg(s)
        assert not why, "sanitize_svg 未拦住（%s）：%r → %r" % (why, src, s)
        # 2) 结构口径：危险标签必须被剥掉
        low = s.lower()
        for banned in ("<script", "<style", "foreignobject", "<iframe", "<embed"):
            assert banned not in low, "sanitize_svg 未剥掉 %r：%r → %r" % (banned, src, s)
    # 3) 反向对照（防"过度清洗"造成的假红）----
    # 3a 合法几何 SVG 必须逐字节不变；特意含**自闭合标签**——那是最易被宽松归一化误伤之处
    keep = ('<svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="4" '
            'fill="var(--accent)"/></svg>')
    assert et.sanitize_svg(keep) == keep, et.sanitize_svg(keep)
    # 3b 刻意放行的 data:image/png 必须保留（若把裸 data: 一律当危险，这里就会假红）
    png = '<image href="data:image/png;base64,iVBORw0KGgo="/>'
    assert et.sanitize_svg(png) == png, et.sanitize_svg(png)


# 【已修复·2026-09-12 SEC-1】上面登记过的三类绕过（① `<tag/on…` 事件属性、
# ② 危险协议值类排除 空格/"/'/ > 、③ 值内 tab/换行未归一化）已由老陈批准修复，
# 原 known-gap 登记册用例已转为 test_tst5_sanitize_svg_blocks_execution 里的
# **正向断言**（见该用例 evil 表中标注 ①②③ 的 10 条）。
# `known_gap` 机制本身保留，供未来登记新发现的缺陷；登记用例必须用
# `_dangerous_svg` 的**语义口径**判定，朴素子串会造成假 XPASS。


@case
def test_tst5_parse_link_and_link_html_never_unsafe():
    ro = _ro()
    et = _et()
    pl = ro._parse_link
    assert pl("官网 | https://example.com") == {"text": "官网", "url": "https://example.com"}
    assert pl("https://example.com") == {"text": "", "url": "https://example.com"}
    assert pl("mailto:a@b.cn") == {"text": "", "url": "mailto:a@b.cn"}
    # 右半段不是合法 URL → 整串当纯文字，**不得静默吞掉后半句**（历史修复位）
    assert pl("手册 | 第3章") == {"text": "手册 | 第3章", "url": ""}
    assert pl("出处：见附录") == {"text": "出处：见附录", "url": ""}
    # 危险 scheme 一律不得进 url
    for evil in ("javascript:alert(1)", "话术：javascript:alert(1)",
                 "x | javascript:alert(1)", "data:text/html,<script>x</script>",
                 "vbscript:msgbox(1)"):
        r = pl(evil)
        assert r["url"] == "", "危险 scheme 进了 url：%r → %r" % (evil, r)
    # 渲染层安全网：非法 URL 不产出可点链接
    for evil in ("javascript:alert(1)", "话术：javascript:alert(1)"):
        h = et._link_html(evil, "点我").lower()
        assert "javascript:" not in h and "href=" not in h, h


@case
def test_tst5_esc_escaping():
    et = _et()
    assert et.esc('<b>&"') == '&lt;b&gt;&amp;"', et.esc('<b>&"')
    assert "&quot;" in et.esc_attr('a"b'), et.esc_attr('a"b')


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------
def main():
    print("eink-deck smoke test")
    print("  root   : %s" % ROOT)
    print("  python : %s" % sys.version.split()[0])
    print("-" * 68)
    n_pass = 0
    failures = []
    for fn in _CASES:
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            failures.append((fn.__name__, "%s: %s" % (type(e).__name__, e),
                             traceback.format_exc()))
            print("  [FAIL] %s" % fn.__name__)
        else:
            n_pass += 1
            print("  [PASS] %s" % fn.__name__)

    # 已知缺陷：断言的是"当前有缺陷的行为"。通过 = 缺陷仍在；失败 = 疑似已修。
    n_xfail = 0
    xpass = []
    for fn in _KNOWN_GAPS:
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            xpass.append((fn.__name__, getattr(fn, "__known_gap_reason__", ""),
                          "%s: %s" % (type(e).__name__, e)))
            print("  [XPASS!] %s  <- 已知缺陷疑似已修" % fn.__name__)
        else:
            n_xfail += 1
            print("  [XFAIL] %s  <- 已知缺陷仍在" % fn.__name__)

    print("-" * 68)
    for name, msg, tb in failures:
        print("")
        print("### FAIL %s" % name)
        print(msg)
        print(tb.rstrip())
    for name, reason, msg in xpass:
        print("")
        print("### XPASS %s  <- 已知缺陷疑似已修，请更新 tests/test_smoke.py" % name)
        print("  登记原因：%s" % reason)
        print("  %s" % msg)
    print("TOTAL: %d passed, %d failed, %d known-gap(xfail), %d xpass, %d total"
          % (n_pass, len(failures), n_xfail, len(xpass),
             len(_CASES) + len(_KNOWN_GAPS)))
    # XPASS 也判失败：已知缺陷被修好后，本套件必须同步更新（把该用例转成正向断言），
    # 否则会长期挂着一条已失效的"缺陷登记"。不能静默放行（复验建议，2026-09-12 采纳）。
    if xpass:
        print("提示：XPASS 表示登记在案的缺陷已不复现，请把对应用例改成正向断言后重跑。")
    return 1 if (failures or xpass) else 0


if __name__ == "__main__":
    sys.exit(main())
