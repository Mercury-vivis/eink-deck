# -*- coding: utf-8 -*-
"""
渲染引擎（路径1：通用引擎读大纲 md）
======================================
读取《XX讲稿ppt大纲.md》 → 解析每页各模块 → 复用 `_eink_template` 版式原语 → 渲染 index.html。

用法：
    python render_outline.py 大纲.md [输出目录]
    （输出目录省略时，默认为 "<大纲名去掉扩展>_eink"）

大纲 md 格式（见 templates/eink_大纲填空模板.md）：
- 顶部元数据：- 讲次 / - 讲稿题目(M02) / - 系列名 / - 总讲次数 / - 讲次类型
      （M01 顶左眉标是逐页运行标签，不是顶部「讲稿题目」；讲稿题目是 M02）
      （可选 `- 块词表: 甲 / 乙 / 丙`：给 M03 前段做受控校验；不写则不校验）
- ### 逐页明细（展开关键页）
- ## Pxx · 简述        -> 每页小节
      - 版式: Lxx
      - M01: 本页运行眉标（顶左，逐页变；封面=第X讲·讲题／章节扉页=第X块·块名／内页=本页标签）
      - M03: 板块名 · 本页内容概括   (左下 foot_left；前段为板块标识，可选受控校验)
      - M05 kicker: ...        (内容区眉标，通常空；勿放系列名或顶左眉标)
      - M06 h_hero: ...  (cover/hero 大字，/ 分行两行)
      - M08 h_xl: ...    (内页主题句，/ 分行；M08 对齐/行对齐/行大小 控对齐与逐行字号)
      - M10 正文: ... 或 - M10 列表: 甲 / 乙 / 丙   (多段用多行；内联 <size=大/中/小> <align=居中/居左/居右>)
      - M10 notes: a / b / c   (L16 文字标牌；支持 ||| 分步：步内仍用 / 分条，按右键逐步揭示)
      - M11 callout: ...  / M11 callout_src: ...  (名句/引文 + 出处)
      - M12 img_slot: ... / M12 文件: images/xxx.png / M12 ratio: 4x3   (配图区；真实图须 images/ 前缀)
      - 强调: [词1, 词2]       (正文中命中即套主题 accent 强调色)
      - items: / stats: / steps: / rows:   后接缩进子项（key=value / 分隔）
      - left(M09+body): ... / right(M09+body): ...   (split 对比)
      - svg_cap: ...                       (L12 示意)
      - 设计: ...                        (给帮帮的画图指令，渲染为待设计占位，不原样进页面)
      - meta-row: ...                       (cover 元信息)
"""
import os, re, sys, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _eink_template import build, validate, sanitize_svg, _img_size

LAYOUT_MAP = {
    "L01": "cover", "L02": "hero", "L03": "lead", "L04": "statgrid", "L05": "grid2",
    "L06": "rowline", "L07": "quote", "L08": "pillar", "L09": "directional", "L10": "callout",
    "L11": "imgslot", "L12": "figsvg", "L13": "pipeline", "L14": "text", "L15": "hero",
    "L16": "statnote", "L17": "interactive", "L18": "ziyuan", "L12b": "chain",
    "L19": "hbar",
    "L20": "kpitower", "L21": "loop", "L22": "system", "L23": "wall",
    "L24": "statement", "L25": "timeline", "L26": "microcard", "L27": "imagehero",
}

# 正文溢出阈值（2026-09-04 实测校准：全系列 199 个正文页 最小23/中位110/p90=152/最大242；
# 取 200 → 触发 2 页真实长页，不制造噪声）。调此值即改告警灵敏度。
_BODY_WARN_CHARS = 200


def split_kv(s):
    """把复合字段「k=v / k2=v2」拆成 dict。

    分行/分项符与全文统一走 _split_struct（两侧带空白的 / 或 ／；贴字斜杠是内容不切）。
    键值分隔支持两种写法：k=v（等号，推荐）与 k: v（冒号，兼容兜底，键限 ASCII）。"""
    out = {}
    for part in _split_struct(s):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
        else:
            m = re.match(r"^\s*([A-Za-z_]+)\s*[:：]\s*(.*)$", part)
            if m:
                out[m.group(1).strip()] = m.group(2).strip()
    return out


def _parse_aligns(s):
    """把对齐描述串解析为逐行对齐列表：左/居左→left，右/居右→right，中/居中→center。"""
    out = []
    for part in re.split(r"[·•|/／,，]", s):
        p = part.strip()
        if not p:
            continue
        if "右" in p:
            out.append("right")
        elif "左" in p:
            out.append("left")
        elif "中" in p or "居" in p:
            out.append("center")
        else:
            out.append("left")
    return out


def _parse_sizes(s):
    """把逐行字号描述串解析为字号列表：含「大」→大，含「小」→小，否则 std。"""
    out = []
    for part in re.split(r"[·•|/／,，]", s):
        p = part.strip()
        if not p:
            continue
        if "大" in p:
            out.append("大")
        elif "小" in p:
            out.append("小")
        else:
            out.append("std")
    return out


def parse_compound_item(kind, s):
    kv = split_kv(s)
    if kind == "items":
        # 同一 items 标签服务三种版式：pillar(ic/t/d)、ziyuan(ch/form/mean)、chain(ch/d/blank)
        # 裸词 `blank`（无 = 无 :）split_kv 解析为 {}，此处特判生效——SKILL §6/§7 教的写法（2026-09-04 修复 Bug1）
        if (s or "").strip().lower() == "blank":
            return {"ic": "", "t": "", "d": "", "blank": True}
        out = {"ic": kv.get("ic", ""), "t": kv.get("t", ""), "d": kv.get("d", "")}
        if "ch" in kv:   out["ch"] = kv["ch"]
        if "form" in kv: out["form"] = kv["form"]
        if "mean" in kv: out["mean"] = kv["mean"]
        if "blank" in kv: out["blank"] = True
        # L25 横向时间轴 / L26 微卡矩阵 新键（仅当存在才提取，不影响 pillar/ziyuan/chain）
        for _k in ("year", "title", "desc", "main", "sub"):
            if _k in kv:
                out[_k] = kv[_k]
        if "accent" in kv:
            _rv = str(kv["accent"]).strip()
            out["accent"] = _rv in ("真", "是", "true", "True", "1", "yes", "开", "on")
        return out
    if kind == "stats":
        d = {"label": kv.get("label", ""), "nb": kv.get("nb", ""),
             "unit": kv.get("unit", ""), "note": kv.get("note", "")}
        # accent：去硬编码。显式字段优先（accent: 是/否/红/关…）；
        # 未指定则留空，交由模板按本页「强调锚点」推导（命中 nb/label 才上色），落实"强调色只点睛关键数字"纪律。
        raw = kv.get("accent")
        if raw is not None:
            rv = str(raw).strip()
            if rv in ("否", "false", "False", "0", "no", "关", "off"):
                d["accent"] = False
            elif rv in ("是", "true", "True", "1", "yes", "开", "on", "红"):
                d["accent"] = True
        return d
    if kind == "steps":
        return {"title": kv.get("title", ""), "desc": kv.get("desc", "")}
    if kind == "rows":
        return {"k": kv.get("k", ""), "v": kv.get("v", ""), "m": kv.get("m", "")}
    if kind == "imgs":
        return {"file": kv.get("file", ""), "cap": kv.get("cap", "")}
    if kind == "kpis":
        # L27 图幅主导：KPI 子项 v=数值 / l=标签（最多 3 个，原语侧截断）
        return {"v": kv.get("v", ""), "l": kv.get("l", "")}
    return {}


def _split_struct(val):
    """结构分隔符切分——全引擎斜杠切分的唯一原语（2026-09-03 收敛；2026-09-04 split_kv 亦委托至此）。

    规则：**两侧带空白**的 `/` 或 `／` 才是分行/分项符；
    贴字斜杠（唐/突厥、从征/归附/谯发/垛集、"火力组/机动组"）是正文内容，不切。

    为什么必须要求空白：全系列实测 32 处贴字斜杠，其中 M10 正文 内就有
    「来源分从征/归附/谯发/垛集四类」「皇帝/中央—将领/地方—全民/兵民合一」等十余处，
    若按任意斜杠切会把正文拆得支离破碎（第13/14/16讲会直接毁页）。
    另保护 `</xxx>` 结束标签内的斜杠，避免 `<size=..>词</size>` 被切断、泄漏标签。"""
    if not val:
        return []
    protected = []
    s2 = val
    if "</" in val:
        def _p(m):
            protected.append(m.group(0))
            return "\x00%d\x00" % (len(protected) - 1)
        s2 = re.sub(r"</[^>]+>", _p, val)
    parts = [p.strip() for p in re.split(r"\s+[/／]\s+", s2) if p.strip()]
    for i, tok in enumerate(protected):
        parts = [p.replace("\x00%d\x00" % i, tok) for p in parts]
    return parts


def parse_split(s):
    """按「 / 」拆分 title / points（L09 双栏）。斜杠规则统一走 _split_struct。"""
    parts = _split_struct(s)
    if not parts:
        return {"title": "", "points": []}
    title = parts[0]
    points = [re.sub(r"^[\s·\-·]+", "", p) for p in parts[1:]]
    return {"title": title, "points": points}


_ALIGN_MAP = {"居中": "center", "居左": "left", "居右": "right",
              "中": "center", "左": "left", "右": "right"}

def _m10_block(val):
    """解析 M10 正文行：
       - 整段标记（无闭合的 <size=大/中/小> / <align=居中/...>）：抽为块级 size/align，并从文本剥离。
       - 行内局部标记（成对闭合 <size=大>...</size>）：保留原文，交引擎 _inline_rich 渲染为 .sz-* 局部放大。
       - **...** 加粗、<ico=...> 图标：保留原文，交引擎处理。
       - 分步揭示：文本用 ||| 分隔 → {"steps":[...]}，引擎渲染为「先显示第一段，按右键再显示后续段」"""
    size = None
    align = None
    m = re.search(r"<size=([^>]+)>", val)
    if m and "</size>" not in val:          # 整段放大（无闭合）
        size = m.group(1).strip()
    m = re.search(r"<(?:align|direction)=([^>]+)>", val)
    if m and "</align>" not in val and "</direction>" not in val:  # 整段对齐（无闭合）
        align = _ALIGN_MAP.get(m.group(1).strip(), m.group(1).strip())
    text = val
    if size is not None:
        # 整段标记剥离：容忍 <size= 大 > 这类带空格写法（2026-09-06 修复：原按值精确匹配会泄漏字面量）
        text = re.sub(r"<\s*size\s*=[^>]+>", "", text, count=1)
    if align is not None:
        text = re.sub(r"<\s*(?:align|direction)\s*=[^>]+>", "", text, count=1)
    if "|||" in text:
        parts = text.split("|||")
        # 前导空段（如「 ||| A ||| B」）= 用户要「初始空白，逐步揭示全部」：所有段都做成步进揭示
        lead_empty = (len(parts) > 1 and not parts[0].strip())
        steps = [s.strip() for s in parts if s.strip()]
        if len(steps) >= 2:
            return {"steps": steps, "size": size, "align": align, "lead_empty": lead_empty}
        # 不足两步（如尾随 `A |||`）：剥掉 ||| 字面量再落普通文本，不把分隔符渲染进页（2026-09-04 修复 Bug5）
        text = text.replace("|||", " ")
    text = text.strip()
    return {"text": text, "size": size, "align": align}

def _parse_link(val):
    """把 M16 链接的一行「显示文字 | URL」或「显示文字：URL」解析为 dict。
        优先以首个 | 分割；无 | 时以最后一个 中文/英文冒号 分割（避免 URL 内 :// 误切）。
        返回 {"text": 显示文字, "url": URL}：
          - 含合法协议（http/https/mailto）的整串 → 当 URL（text 空，渲染层退回 URL 显示）
          - 既无分隔符又不像 URL 的整串 → 当纯文字项（text=整串，url 空，渲染层显示纯文字）
          - 仅给 URL 无文字时 text 留空，由渲染层退回 URL 本身。
        「文字：非URL」的分隔写法（如「出处：见附录」）→ 冒号后半段不是合法 URL 时，
        整串当纯文字返回，防止后半句被静默吞掉（2026-09-06 修复）。"""
    import urllib.parse as _up
    s = (val or "").strip()
    if not s:
        return {"text": "", "url": ""}

    def _legal_url(u):
        try:
            sch = (_up.urlsplit(u).scheme or "").lower()
        except Exception:
            sch = ""
        return sch in ("http", "https", "mailto")

    if "|" in s:
        text, url = s.split("|", 1)
        if _legal_url(url.strip()):
            return {"text": text.strip(), "url": url.strip()}
        # URL 半段不是合法 URL（如「手册 | 第3章」）→ 整串当纯文字，不丢内容
        return {"text": s, "url": ""}
    # 无 |：看是否像 URL（含 scheme）
    try:
        scheme = (_up.urlsplit(s).scheme or "").lower()
    except Exception:
        scheme = ""
    if scheme in ("http", "https", "mailto"):
        return {"text": "", "url": s}   # 只有 URL，无显示文字
    # 无 |：若串中含 scheme://（如 https://），分隔符必在 URL 起点左侧——
    # 不能用 max(rfind)（URL 自带 :// 永远压过中文冒号，导致 `出处：https://…` 切坏，
    # 2026-09-04 修复 Bug2）：先定位 scheme 起点，再在其左侧找最靠近的分隔冒号。
    _m = re.search(r"(?:https?|mailto)://", s)
    if _m and _m.start() > 0:
        _left = s[:_m.start()]
        _c = max(_left.rfind("："), _left.rfind(":"))
        if _c > 0:
            return {"text": s[:_c].strip(), "url": s[_c+1:].strip()}
    # 取最后一个冒号（URL 的 https:// 含冒号，不能用首个）
    idx = max(s.rfind("："), s.rfind(":"))
    if idx > 0 and idx < len(s) - 1 and scheme == "":
        text, url = s[:idx], s[idx+1:]
        if _legal_url(url.strip()):
            return {"text": text.strip(), "url": url.strip()}
        # 冒号后的内容不是合法 URL（如「出处：见附录」）→ 整串当纯文字，不丢后半句
        return {"text": s, "url": ""}
    # 既无分隔符又不像 URL → 纯文字项（退化，渲染层显示纯文字不渲染链接）
    return {"text": s, "url": ""}

def _three_ctrl(cur, prefix, f, val, size_empty_field=False):
    """页级三控：把 字号/垂直/水平 写入 cur[prefix+'_size'/'_v'/'_h']。

    返回 True 表示本字段被三控消费；调用方据此决定是否走 else 兜底分支。
    size_empty_field=True 时，字号空值回退为字段名本身（M13/M14 的历史行为，保留）。"""
    if f.startswith("字号"):
        cur[prefix + "_size"] = val if (val or not size_empty_field) else f
        return True
    if f.startswith("垂直"):
        cur[prefix + "_v"] = val
        return True
    if f.startswith("水平"):
        cur[prefix + "_h"] = val
        return True
    return False


def apply_module(cur, mod, field, val):
    f = field
    if mod == "M01":
        cur["m01"] = val
    elif mod == "M05":
        # M05 kicker（内容区眉标）：支持 字号 / 垂直(vh) / 水平(vw) 三控
        if not _three_ctrl(cur, "m05", f, val):
            cur["kicker"] = val
    elif mod == "M06":
        # M06 h_hero（cover/hero 大字）：支持「/」分行 + 逐行对齐（居左·居右）+ 垂直/水平平移
        # 分行走 _split_struct（保护 </size> 等结束标签内的斜杠，贴字斜杠是内容不切）
        if "垂直" in field:
            cur["m06_v"] = val
        elif "水平" in field:
            cur["m06_h"] = val
        elif "对齐" in field:  # 如「M06 行对齐: 居左·居右」「M06 对齐: 左·右」
            cur["title_aligns"] = _parse_aligns(val)
        elif "字号" in field:
            # M06 无字号三控（SKILL §G 已知坑）：写「M06 字号:」会静默把主标题覆盖成该值。
            # 这里显式警告并忽略，保住原标题（2026-09-06 修复）。
            print("  [模块警告] M06 不支持「字号」三控（会覆盖主标题）；请改用行内 <size=0.6>：%s" % val)
        elif val:
            if "/" in val or "／" in val:
                cand = _split_struct(val)
                if len(cand) > 1:
                    cur["title_lines"] = cand
            cur["title"] = val
    elif mod == "M07":
        # M07 h_sub（副标题）：支持 字号 / 垂直 / 水平 三控
        if not _three_ctrl(cur, "m07", f, val):
            cur["subtitle"] = val
            if "/" in val or "／" in val:
                _c = _split_struct(val)
                if len(_c) > 1:
                    cur["sub_lines"] = _c
    elif mod == "M09":
        # M09 h_md（L09 对比页左右栏小标题）：支持 字号 / 垂直 / 水平 三控（页面级，作用于两栏）
        _three_ctrl(cur, "m09", f, val)
    elif mod == "M08":
        # M08 h_xl（内页主题句）：
        # - 值含「/」→ 拆成多行（title_lines），逐行渲染（P4/P9/P16 等）
        # - 「M08 行对齐: 居左·居右」→ title_aligns（逐行对齐，mirror M06）
        # - 「M08 行大小: 小·大」/「M08 行字号: 小·大」→ line_sizes（逐行字号 大/小）
        # - 整体对齐 token（居中/居左/居右）→ title_align
        if "行对齐" in field:
            cur["title_aligns"] = _parse_aligns(val)
        elif "行大小" in field or "行字号" in field:
            cur["line_sizes"] = _parse_sizes(val)
        elif "字号" in field:
            # M08 无整体字号三控（SKILL §G 已知坑）：写「M08 字号:」会静默把主题句覆盖成该值。
            # 逐行字号用「M08 行大小: 小·大」。显式警告并忽略，保住主题句（2026-09-06 修复）。
            print("  [模块警告] M08 不支持「字号」三控（会覆盖主题句）；请改用「M08 行大小: 小·大」：%s" % val)
        # 对齐仅认 field 含「对齐」（或裸字段「- M08: 中」的历史写法兜底）；
        # 内容值（如标题恰好是「中/左/右」）不再被当对齐指令静默吞掉（2026-09-04 修复）
        elif ("对齐" in field) or (not field and val in ("居中", "居左", "居右", "中", "左", "右", "center", "left", "right")):
            al = None
            for kw, a in [("居中", "center"), ("居右", "right"), ("居左", "left"),
                          ("中", "center"), ("右", "right"), ("左", "left")]:
                if kw in (field + val):
                    al = a
                    break
            if al:
                cur["title_align"] = al
        elif "垂直" in field:
            cur["m08_v"] = val
        elif "水平" in field:
            cur["m08_h"] = val
        else:
            if "/" in val or "／" in val:
                cand = _split_struct(val)
                if len(cand) > 1:
                    cur["title_lines"] = cand
            cur["title"] = val
    elif mod == "M10":
        if f.startswith("字号"):
            # M10 无「字号」三控（SKILL §G）：该值此前被 _three_ctrl 解析存下却从未透传，
            # 页面毫无变化、日志也无提示——与 M06/M08 同款坑（那两个 2026-09-06 已加警告）。
            # 2026-09-08 修复 R3：显式告警并指路真正有效的写法。
            # ⚠️ 正确替代品是行尾未闭合 <size=大>（整段放大）或 <size=大>词</size>（局部放大），
            # 不是「M10 垂直 / 水平」——那是位移，替代不了字号。
            print("  [模块警告] M10 不支持「字号」三控（写了不生效）；整段放大请在本行行尾写未闭合 "
                  "<size=大>，局部放大用 <size=大>词</size>：%s" % val)
        elif not _three_ctrl(cur, "m10", f, val):
            if f.startswith("notes"):
                cur["notes"] = val
                if not val.strip():
                    cur["_notes_pending"] = True   # 空值 + 缩进子项 → 收集进 notes 列表（L16，v2.4.1）
            elif val:
                if "列表" in f:
                    items = _split_struct(val)
                    cur.setdefault("body_blocks", []).append({"items": items})
                else:
                    # M10 正文 认「两侧带空白的 / 」为分行（与 M08 h_xl 同一约定）；
                    # 贴字斜杠是内容，不切（否则「从征/归附/谯发/垛集四类」会被拆碎）。
                    segs = _split_struct(val)
                    if len(segs) > 1 and "|||" in val:
                        # ||| 分步与「 / 」分行并存时只认分步；显式警告防止内容被静默吞（2026-09-04）
                        print("  [模块警告] M10 值同时含「|||」与「 / 」：「/」分行被忽略（分步优先）：%s" % val[:40])
                    if len(segs) > 1 and "|||" not in val:
                        head = _m10_block(val)  # 只取整段级 size/align，避免标记只落在末段
                        for sg in segs:
                            blk = _m10_block(sg)
                            blk["size"] = head.get("size")
                            blk["align"] = head.get("align")
                            cur.setdefault("body_blocks", []).append(blk)
                    else:
                        cur.setdefault("body_blocks", []).append(_m10_block(val))
        # val 为空 → 留给 body_list_pending 捕获后续缩进列表（不预设空 body）
    elif mod == "M11":
        if f.startswith("callout_src"):
            cur["_m11src"] = val
        elif not _three_ctrl(cur, "m11", f, val):
            if val:  # 空值不落 _m11：此前空串也落，is not None 判定会渲染出空引文框（2026-09-04 修复）
                cur["_m11"] = val
    elif mod == "M12":
        if f == "文件" or ("文件" in field):
            # 本地真实配图：M12 文件: images/xxx.png（相对大纲目录）；渲染时拷到输出目录并改写路径
            img = cur.setdefault("img", {})
            if "file" in img:
                # 同页多条 M12 文件: 静默 last-wins 会吞掉前值——显式警告（2026-09-06 修复）
                print("  [模块警告] 同页多条「M12 文件:」，仅最后一条生效：%s → %s" % (img["file"], val))
            img["file"] = val
        elif f.startswith("ratio") or "比例" in field:
            # M12 ratio: 4x3 / 1x1 / 3x4（控制配图框纵横比；P25 默认 3x4）
            cur.setdefault("img", {})["ratio"] = val
        elif f.startswith("maxh") or "高度" in field:
            # M12 maxh: 50（控制配图框最大高度占屏 vh，默认 62）——即「缩放大小」控制字段
            cur.setdefault("img", {})["maxh"] = val
        elif f.startswith("对齐") or "align" in field:
            # M12 对齐: 贴左|居中|贴右（图片在框内水平位置；默认居中）
            cur.setdefault("img", {})["align"] = val
        elif f.startswith("垂直") or "vertical" in field:
            # M12 垂直: 3vh（图片整体上下平移，负=上、正=下；默认 vh）
            cur.setdefault("img", {})["v"] = val
        elif f.startswith("水平") or "horizontal" in field:
            # M12 水平: 3vw（图片整体左右平移，负=左、正=右；默认 vw）
            cur.setdefault("img", {})["h"] = val
        elif "来源" in field or "caption" in field:
            # 「M12 图片来源 / M12 caption」已停用（图下不再显示来源）；安全忽略，不渲染
            pass
        else:
            cur.setdefault("img", {})["label"] = val
    elif mod == "M03":
        cur["foot_left"] = val
    elif mod == "M13":
        # M13 注释（页面级小注）；字段「对齐」控制位置，「字号」控 大/小（mirror M14）。
        # 字号：大 → 只设字号，不覆盖注解正文；注解正文走 annot/注释 或兜底。
        if not _three_ctrl(cur, "m13", f, val, size_empty_field=True):
            if f.startswith("对齐"):
                # 认 左/中/右 及 居左/居中/居右（2026-09-06 补映射，原「居中」会产出非法 CSS 静默失效）
                cur["m13_align"] = {"左": "left", "中": "center", "右": "right",
                                    "居左": "left", "居中": "center", "居右": "right"}.get(val, val)
            else:
                cur["annotation"] = val
    elif mod == "M14":
        # M14 下标/出处（默认右对齐）；「对齐」控 左/中/右，「字号」控 大/小，「垂直」控上/下平移（vh）。
        if f.startswith("对齐"):
            cur["m14_align"] = {"左": "left", "中": "center", "右": "right",
                                "居左": "left", "居中": "center", "居右": "right"}.get(val, val)
        elif not _three_ctrl(cur, "m14", f, val, size_empty_field=True):
            cur["footnote"] = val
    elif mod == "M16":
        # M16 参考链接（2026-08-24 新增：页面级链接框，底部 slide-aux，新标签打开）
        # 语法：
        #   单行：  - M16 链接: 显示文字 | URL
        #   多条：  - M16 链接:            （空值）
        #             - 显示文字A | URL_A
        #             - 显示文字B | URL_B
        # 分隔符支持「|」「：」「:」（优先首个出现的 |，否则按 文字<分隔>URL 的最后一个分隔符切）
        if f.startswith("链接") or f == "link":
            if val.strip():
                cur.setdefault("links", []).append(_parse_link(val))
            else:
                cur["_links_pending"] = True   # 空值 + 缩进子项 → 收集进 links 列表


    else:
        print("  [模块警告] 未知/未支持的模块 %s（字段=%s）已忽略" % (mod, field))

def _flush_pend(cur):
    """把 M10 紧跟的缩进列表项（_pend_list）按书写顺序落进 body_blocks（2026-09-03 收敛修复）。
    此前 body_list 永远 append 在 body_blocks 之后，导致「段→列表→段」顺序丢失。"""
    if not cur:
        return
    _pend = cur.pop("_pend_list", None)
    if _pend:
        cur.setdefault("body_blocks", []).append({"items": _pend})

def parse_outline(path):
    # utf-8-sig：兼容带 BOM 的大纲（Windows 记事本/部分编辑器另存即带 BOM）。
    # 用 utf-8 时 BOM 会残留在首行开头，使元数据正则 ^-\s*([^:：]+)[:：] 对首行零匹配，
    # 静默吞掉第一条元数据——通常是「讲次」，进而使侧车复合键从「第X讲/Pxx」退化成「Pxx」，
    # 该讲 SVG 全部消失且无任何提示（2026-09-08 修复 R2）。utf-8-sig 对无 BOM 文件行为不变。
    if not os.path.exists(path):
        sys.stderr.write("ERROR: 大纲文件不存在：%s\n" % path)
        sys.exit(2)
    lines = open(path, encoding="utf-8-sig").read().splitlines()
    meta, pages = {}, []
    state, cur, in_compound, body_list_pending, in_split = "meta", None, None, False, None
    for raw in lines:
        line = raw.rstrip("\n")
        m = re.match(r"^#{2,4}\s+(P\d+[A-Za-z]?)\s*[·•\-]?\s*(.*)$", line)
        if m:
            if cur is not None:
                _flush_pend(cur)   # 上一页收尾：残留缩进列表 flush 进其 body_blocks
            state, cur = "page", {
                "_pid": m.group(1), "_sub": m.group(2).strip(), "emphasis": [],
                "img": {}, "kicker": "", "title": "", "foot_left": "",
            }
            pages.append(cur); in_compound = None; body_list_pending = False
            continue
        if state == "meta":
            mm = re.match(r"^-\s*([^:：]+)[:：]\s*(.*)$", line)
            if mm:
                meta[mm.group(1).strip()] = mm.group(2).strip().strip("`")
            continue
        if state == "page" and cur is not None:
            # 遇到新的顶层 bullet，退出 split 嵌套
            if re.match(r"^-", line):
                in_split = None
                _flush_pend(cur)   # 新顶层 bullet 起，结束上一块的缩进列表捕获（按书写顺序落位）
            # split 嵌套内容：left/right 下的缩进 M09 h_md / body 子项
            if in_split:
                sub = re.match(r"^\s+-\s*(M09\s+h_md|body)\s*[:：]\s*(.*)$", line)
                if sub:
                    blk = cur.setdefault("split", {}).get(in_split, {"title": "", "points": []})
                    if "h_md" in sub.group(1):
                        blk["title"] = sub.group(2).strip()
                    else:
                        blk.setdefault("points", []).append(sub.group(2).strip())
                    cur["split"][in_split] = blk
                    continue
                if re.match(r"^\s", line):
                    continue  # 嵌套区内的空行/未识别缩进行，留在 split 内忽略
            # 复合字段子项（缩进 - 或 数字.）：子项前的空行/缩进非子项行不终止复合块
            if in_compound in ("items", "stats", "steps", "rows", "imgs", "kpis"):
                sm = re.match(r"^\s+[-]\s*(.+)$", line) or re.match(r"^\s+\d+\.\s*(.+)$", line)
                if sm:
                    cur.setdefault(in_compound, []).append(parse_compound_item(in_compound, sm.group(1)))
                    continue
                if re.match(r"^\s", line) or line.strip() == "":
                    continue  # 空行/缩进非子项：留在复合块内，等待下一个子项
                in_compound = None  # 遇到顶层新指令才结束复合块
            if body_list_pending:
                sm = re.match(r"^\s+\d+\.\s*(.+)$", line) or re.match(r"^\s+[-]\s*(.+)$", line)
                if sm:
                    cur.setdefault("_pend_list", []).append(sm.group(1).strip())
                    continue
                if re.match(r"^\s", line) or line.strip() == "":
                    continue  # 空行/缩进非列表项：保持 pending，等待下一个列表项
                # 遇到新的顶层指令（非缩进列表项）→ 把此前收集的缩进列表 flush 进 body_blocks（按出现顺序）
                _flush_pend(cur)
                body_list_pending = False
            # M10 notes 缩进子项收集（v2.4.1）：`- M10 notes:` 空值 + 缩进列表 → 收集进 notes 列表（L16）
            if cur.get("_notes_pending"):
                sm = re.match(r"^\s+\d+\.\s*(.+)$", line) or re.match(r"^\s+[-]\s*(.+)$", line)
                if sm:
                    if not isinstance(cur.get("notes"), list):
                        cur["notes"] = []
                    cur["notes"].append(sm.group(1).strip())
                    continue
                if re.match(r"^\s", line) or line.strip() == "":
                    continue
                cur["_notes_pending"] = False
            # M16 参考链接 缩进子项收集（2026-08-24 新增）：`- M16 链接:` 空值 + 缩进列表 → 收集进 links 列表
            if cur.get("_links_pending"):
                sm = re.match(r"^\s+\d+\.\s*(.+)$", line) or re.match(r"^\s+[-]\s*(.+)$", line)
                if sm:
                    cur.setdefault("links", []).append(_parse_link(sm.group(1).strip()))
                    continue
                if re.match(r"^\s", line) or line.strip() == "":
                    continue
                cur["_links_pending"] = False
            # M03 简写（块·内容，无 field 后缀，如 "- M03: 概述 · 开场"）
            m3 = re.match(r"^-\s*M03\s*[：:]\s*(.*)$", line)
            if m3:
                cur["foot_left"] = m3.group(1).strip()
                continue
            # 版式
            lm = re.match(r"^-\s*版式[：:]\s*`?([A-Za-z0-9]+)`?", line)
            if lm:
                cur["layout"] = lm.group(1); continue
            # 强调
            em = re.match(r"^-\s*强调[：:]\s*\[(.*)\]\s*$", line)
            if em:
                cur["emphasis"] = [x.strip().strip("'\"") for x in em.group(1).split(",") if x.strip()]
                continue
            # 信源字段已停用（页脚不再显示信源小 tag）；旧大纲里的 `信源:` 行现被安全忽略
            # 局部动效覆盖（可选，优化意见(一)7）：data_animate: hero|cascade|quote|directional|pipeline
            da = re.match(r"^-\s*(?:数据_?animate|data_animate)[：:]\s*([A-Za-z]+)\s*$", line)
            if da:
                cur["data_animate"] = da.group(1); continue
            # 设计指令标记（关键新增）：「设计:」/「示意:」/「::design」—— 这是给"我（帮帮）"的描述，
            # 意思是"按这段描述生成真实 SVG/版式"，而非把文字直接当内容复制。引擎渲染为待设计占位，
            # 实际 SVG 由我在渲染前按描述手绘并注入 svg:/raw: 字段。
            dm = re.match(r"^-\s*(?:设计|示意|::design)[:：]\s*(.*)$", line)
            if dm:
                cur["design"] = dm.group(1).strip(); continue
            # 互动标签（L17）：- tag: 文案
            tg = re.match(r"^-\s*tag[：:]\s*(.*)$", line)
            if tg:
                cur["tag"] = tg.group(1).strip(); continue
            # 环中心词（L21 闭环图，页面级）：- center: OODA循环（省略则默认「闭环」）
            cm = re.match(r"^-\s*center[：:]\s*(.*)$", line)
            if cm:
                cur["center"] = cm.group(1).strip(); continue
            # split 左右（L09 对比）：同行内联 → 解析；空值 + 缩进子项 → 进入嵌套模式
            sp = re.match(r"^-\s*(left|right)\(M09\+body\)[：:]\s*(.*)$", line)
            if sp:
                side, inline = sp.group(1), sp.group(2).strip()
                if inline:
                    cur.setdefault("split", {})[side] = parse_split(inline)
                else:
                    cur.setdefault("split", {})[side] = {"title": "", "points": []}
                    in_split = side
                continue
            # 通用内联 SVG：`- svg: <svg …>` 任意版式通用——
            # 解析后直接进 svg_inline，走 _bottom_elements 的底部通用图位
            # （L05/L11/L12 原生渲图，chain 除外），等价于侧车注入但不依赖外部 JSON 文件。
            # 优先级：侧车（_svg_hit）> 大纲内联 `svg:`；二者都无则显示「待设计」占位。
            sv = re.match(r"^-\s*svg[：:]\s*(.*)$", line, re.I)
            if sv:
                _v = sv.group(1).strip()
                if _v:
                    cur["svg"] = sanitize_svg(_v)
                continue
            # 版式特有字段（无 M 前缀）：svg_cap / meta-row
            sf = re.match(r"^-\s*(svg_cap|meta-row)[：:]\s*(.*)$", line)
            if sf:
                key = sf.group(1)
                if key == "meta-row":
                    cur["meta"] = [x.strip() for x in sf.group(2).split("·") if x.strip()]
                else:
                    cur[key] = sf.group(2).strip()
                continue
            # 新版式字段（L24-L27 + L05 grid + L19 scale/whitespace；逐字对齐 eink SKILL.md 版式详解）
            nf = re.match(r"^-\s*(statement|text|sub|lead|cap|grid|图文比例|scale|whitespace|img_mode|title|callout|callout_src)[：:]\s*(.*)$", line)
            if nf:
                # 「图文比例」是 grid 的中文别名（渲染侧 p_grid2 双读，解析侧归一化到 grid 键）
                _nk = "grid" if nf.group(1) == "图文比例" else nf.group(1)
                cur[_nk] = nf.group(2).strip()
                continue
            # 页面级纵向落位/规则线/图底对齐：- 纵向:顶/中/底、- 规则线:是、- 图对齐:底
            vmk = re.match(r"^-\s*(纵向|规则线|图对齐)[：:]\s*(.*)$", line)
            if vmk:
                cur[vmk.group(1)] = vmk.group(2).strip()
                continue
            # L27 图幅主导：img.file:（点号键，进 img 字典）
            if_img = re.match(r"^-\s*img\.file[：:]\s*(.*)$", line)
            if if_img:
                cur.setdefault("img", {})["file"] = if_img.group(1).strip()
                continue
            # 复合字段开始
            cmp = re.match(r"^-\s*(items|stats|steps|rows|imgs|kpis)[：:]\s*$", line)
            if cmp:
                in_compound = cmp.group(1); cur[in_compound] = []; continue
            # 模块字段 - Mxx field: value（兼容全角冒号：；field 可省略，如 - M01: 顶左眉标）
            mf = re.match(r"^-\s*(M\d+)(?:\s+(\S+?))?[：:]\s*(.*)$", line)
            if mf:
                mod, field, val = mf.group(1), (mf.group(2) or "").strip(), mf.group(3).strip()
                apply_module(cur, mod, field, val)
                if mod == "M10" and not field.startswith("notes"):
                    # M10 无论有无首句都进入 pending：后续缩进列表项（- / 1. 开头）收集进 body_list
                    # （2026-08-19：支持「首句 + 缩进子项」写法，此前只有空值才收集）
                    # notes 例外（v2.4.1）：M10 notes 的子项走 _notes_pending 收集进 notes，不走 body_list
                    body_list_pending = True
                continue
    if cur is not None:
        _flush_pend(cur)   # 末页收尾
    return meta, pages


def _apply_header_fields(p, s, t):
    """页头组装：foot_left / title / kicker / body / m01 / 垂直微调 / grid2 left / notes / 引文。"""
    if p.get("foot_left"):
        s["foot_left"] = p["foot_left"]
    if t in ("cover", "hero"):
        s["title"] = p.get("title", "")
        if p.get("subtitle"):
            s["subtitle"] = p["subtitle"]
        if p.get("sub_lines"):
            s["sub_lines"] = p["sub_lines"]
        s["kicker"] = p.get("kicker", "")
        if t == "hero":
            s["label"] = p.get("kicker", "")
    else:
        if p.get("kicker"):
            s["kicker"] = p["kicker"]
        s["title"] = p.get("title", "")
    # M10 正文：统一为「块列表」(list[block])，每段可独立设 size/align。
    # 缩进子项由 _pend_list → _flush_pend 按书写顺序落进 body_blocks（2026-09-03 收敛）。
    s["body"] = p.get("body_blocks") or []
    # 每页 M01（四角顶左，独立可填；不填隐藏）
    s["m01"] = p.get("m01", "")
    # 垂直微调（M08/M10 垂直）：透传到版式原语（_hxl / _body_block 经 _movewrap 平移）
    if p.get("m08_v") is not None:
        s["m08_v"] = p["m08_v"]
    if p.get("m10_v") is not None:
        s["m10_v"] = p["m10_v"]
    # grid2 左栏用 body
    if t == "grid2":
        s["left"] = s["body"]
    if p.get("notes") is not None:
        s["notes"] = p["notes"]
    # 引文/名句：quote 页以 M11 callout 文本优先，无 M11 时退回 M07 作引文；
    # M11 callout_src 一律作为出处（src）。这样仅 M07+callout_src 也能双显。
    if t == "quote":
        qt = p.get("_m11") if p.get("_m11") is not None else p.get("subtitle", "")
        if qt:
            s["text"] = qt
        if p.get("_m11src"):
            s["src"] = p["_m11src"]
    else:
        if p.get("_m11") is not None:
            s["q"], s["cite"] = p["_m11"], p.get("_m11src", "")
        if p.get("m11_size"):
            s["q_size"] = p["m11_size"]


def _warn_body_overflow(s, page_no):
    """正文溢出可观测（2026-09-04 收敛）：.body-fill 为 overflow:hidden，超量会被静默裁切。
    这里按字符数给出阈值提示，不阻断渲染，由作者决定拆页 / 精简 / 调 M12 maxh。"""
    _n = 0
    for _b in (s.get("body") or []):
        if not isinstance(_b, dict):
            continue
        _n += len(str(_b.get("text", "") or ""))
        for _it in (_b.get("items") or []):
            _n += len(str(_it.get("t", _it)) if isinstance(_it, dict) else str(_it))
    if _n > _BODY_WARN_CHARS:
        print("[溢出提示] 第%d页 正文约 %d 字（阈值 %d）· .body-fill 可能裁切，"
              "建议拆页 / 精简 / 调 M12 maxh" % (page_no, _n, _BODY_WARN_CHARS))


def _apply_fit_mode(p, s, out_dir, base):
    """L27 img_mode: fit —— 图区高度按图片真实宽高比自适应（无留白、不裁切、不变形）。"""
    if not p.get("img"):
        return
    _im = p["img"]
    if str(p.get("img_mode", "")).strip().lower() == "fit" and _im.get("file"):
        _fpath = _im["file"]
        _cand = os.path.join(out_dir, _fpath) if _fpath.startswith("images/") else os.path.join(base, _fpath)
        _sz = _img_size(_cand)
        if _sz and _sz[1]:
            _im["fit_ratio"] = "%.3f" % (_sz[0] / float(_sz[1]))
        else:
            print("  [L27 fit 提示] 无法读取图片尺寸（%s），回退 contain 模式" % _fpath)
    s["img"] = _im


def _apply_content_fields(p, s):
    """复合字段 + 新版式字段 + 页面级落位 + 互动标签 透传。"""
    if p.get("items"):
        s["items"] = p["items"]
    if p.get("stats"):
        s["stats"] = p["stats"]
    if p.get("steps"):
        s["steps"] = p["steps"]; s["cols"] = len(p["steps"])
    if p.get("center"):
        s["center"] = p["center"]  # L21 闭环图中心词覆盖（默认「闭环」）
    if p.get("rows"):
        s["rows"] = p["rows"]
    if p.get("imgs"):
        s["imgs"] = p["imgs"]
    # 新版式字段透传（L24-L27 + L05 grid + L19 scale/whitespace）
    for _nk in ("statement", "text", "sub", "lead", "cap", "img_mode", "grid", "scale", "whitespace", "callout", "callout_src"):
        if _nk in p:
            s[_nk] = p[_nk]
    if p.get("kpis"):
        s["kpis"] = p["kpis"]
    if p.get("split"):
        s["left"] = p["split"].get("left", {"title": "", "points": []})
        s["right"] = p["split"].get("right", {"title": "", "points": []})
    if p.get("meta"):
        s["meta"] = p["meta"]
    if p.get("data_animate"):
        s["data_animate"] = p["data_animate"]  # 局部动效覆盖
    # 纵向落位/规则线/图底对齐：透传，供 _apply_frame_mods / p_grid2 消费
    for _vk in ("纵向", "规则线", "图对齐"):
        if p.get(_vk) is not None:
            s[_vk] = p[_vk]
    if p.get("tag"):
        s["tag"] = p["tag"]  # L17 互动标签


def _apply_fixed_elements(p, s, t):
    """页面级固定元件：M11 引文框 / M13 注释 / M14 下标 / M16 链接 / 标题与全元件三控。"""
    # M11 引文：作为页面级固定元件 —— 仅当本页版式不是 callout/quote 时，挂到底部引文框
    if p.get("_m11") is not None and t not in ("callout", "quote"):
        s["callout_fixed"] = {"q": p["_m11"], "cite": p.get("_m11src", "")}
    if p.get("annotation"):
        s["annotation"] = p["annotation"]
    if p.get("footnote"):
        s["footnote"] = p["footnote"]
    # M16 参考链接（2026-08-24 新增）：透传页面级链接列表到底部链接框
    if p.get("links"):
        s["links"] = p["links"]
    if p.get("m14_align"):
        s["m14_align"] = p["m14_align"]
    if p.get("m13_align"):
        s["m13_align"] = p["m13_align"]
    if p.get("m13_size"):  # M13 注释字号（大/小）
        s["m13_size"] = p["m13_size"]
    # M06 两行 hero + 逐行对齐（居左·居右）
    if p.get("title_lines"):
        s["title_lines"] = p["title_lines"]
    if p.get("title_aligns"):
        s["title_aligns"] = p["title_aligns"]
    if p.get("title_align"):  # M08 主题句对齐（居中/左/右）
        s["title_align"] = p["title_align"]
    if p.get("line_sizes"):  # M08 逐行字号（大/小），配合 title_lines 生效
        s["line_sizes"] = p["line_sizes"]
    if p.get("m14_size"):  # M14 下标字号（大/小）
        s["m14_size"] = p["m14_size"]
    if p.get("m14_v") is not None:  # M14 垂直微调（vh，负上正下）
        s["m14_v"] = p["m14_v"]
    if p.get("m13_v") is not None:  # M13 垂直微调（vh，负上正下）
        s["m13_v"] = p["m13_v"]
    # M05-M14 全元件三控透传（2026-08-19：字号 / 垂直 / 水平）
    for _k in ("m05_size", "m05_v", "m05_h", "m06_v", "m06_h",
               "m07_size", "m07_v", "m07_h", "m08_h",
               "m09_size", "m09_v", "m09_h", "m10_h",
               "m11_v", "m11_h", "m13_h", "m14_h"):
        if p.get(_k) is not None:
            s[_k] = p[_k]
    if p.get("design"):
        s["design"] = p["design"]


def _inject_svg(p, s, lec_label, svg_ov):
    """SVG 注入：唯一来源是页面内联 `- svg:`。
    🟥 同页多源直接报错 —— 不做静默优先级二选一。侧车 `_svg_overrides.json` 仍保留
    功能（旧讲次兼容 / 临时覆盖），但一旦与本页 `svg:` 同时出现，即视为配置错误直接抛错，
    避免"改了侧车却没生效" / "加了 svg: 却被侧车盖掉"这类无声故障。"""
    _ov_key = ("%s/%s" % (lec_label, p["_pid"])) if lec_label else p["_pid"]
    _svg_hit = svg_ov.get(_ov_key) or svg_ov.get(p["_pid"])
    _has_inline = bool(p.get("svg"))
    _n_src = sum([bool(_svg_hit), _has_inline])
    if _n_src > 1:
        _srcs = []
        if _svg_hit:
            _srcs.append("侧车 _svg_overrides.json（键 %s）" % _ov_key)
        if _has_inline:
            _srcs.append("页面内联 `- svg:`")
        raise SystemExit(
            "❌ 同页多源：讲次「%s」第 %s 页同时有 %d 个图源 —— %s\n"
            "   一页只允许一个图源（2026-09-10 老陈裁定：同页多源直接报错）。\n"
            "   请只保留一个：新写法统一用页面内联 `- svg:`；"
            "若确有侧车，删掉它或删掉页面内的 `- svg:`。"
            % (lec_label or "?", p.get("_pid", "?"), _n_src, "、".join(_srcs)))
    if _svg_hit:
        s["svg_inline"] = sanitize_svg(_svg_hit)
        s["cap"] = p.get("svg_cap", "")
    elif p.get("svg"):
        # 通用内联 SVG：`- svg: <svg …>` 直接写在页面里（唯一推荐通道）。
        s["svg_inline"] = p["svg"]
        s["cap"] = p.get("svg_cap", "")


def _load_svg_overrides(base=None, out_dir=None):
    """加载 SVG 覆盖侧车（键 → 内联 SVG 字符串），替换「设计:」占位；缺失则空字典。
    2026-08-21 安全重构：侧车改为 **JSON 纯字符串字典**（_svg_overrides.json），
      引擎用 json.load 读取，**绝不 import/exec 任何 Python 代码**——彻底消除
      旧版 .py 侧车被篡改即可任意代码执行（RCE）的风险。
    加载顺序 = **生成目录（输出目录）→ 大纲所在目录 → 引擎文件目录**（多讲天然隔离）。
      修复背景：16 讲大纲同放一个目录时，旧版 .py 侧车共用一份会互相覆盖
      （2026-08-20 第1讲 SVG 全丢事故）；现侧车放各自生成目录根治。
    键支持两种：
      - 复合键「讲次/页号」（如 "第1讲/P11"，多讲共用同一目录也不串页）
      - 纯页号（如 "P11"，旧格式向后兼容）
    返回值：强制键/值均为字符串，且值统一过 sanitize_svg（剥离 script/事件等）。"""
    if out_dir:
        out_dir = os.path.abspath(out_dir)
    for d in [out_dir, base, os.path.dirname(os.path.abspath(__file__))]:
        if not d:
            continue
        try:
            json_path = os.path.join(d, "_svg_overrides.json")
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data:
                    return {str(k): sanitize_svg(str(v)) for k, v in data.items()}
                if not isinstance(data, dict):
                    print("  [侧车警告] %s 内容不是字典（实际为 %s），已忽略"
                          % (json_path, type(data).__name__))
        except Exception as _e:
            # 2026-09-08 修复 R4：此前 except 静默吞异常，JSON 非法（尾随逗号 / 未转义引号）
            # 时侧车整份失效却零提示，只能靠人工「落盘前先 json.load 校验」的纪律兜。
            # 现显式告警，让可自检的错误在渲染日志里直接可见。
            print("  [侧车警告] 解析失败、已忽略（请检查 JSON 合法性：尾随逗号 / 双引号未转义）："
                  "%s | %s" % (json_path, _e))
            continue
    return {}


def build_lecture(meta, pages, base=None, out_dir=None):
    slides = []
    _m = re.search(r"\d+", meta.get("讲次", "1"))
    lec_no = int(_m.group()) if _m else 1
    _lec_label = (meta.get("讲次", "") or "").strip()
    title = meta.get("讲稿题目(M02)", meta.get("讲稿题目(M01)", meta.get("讲稿题目", "未命名")))
    series = meta.get("系列名(M02)", meta.get("系列名", ""))
    theme = meta.get("主题", meta.get("theme", ""))
    # —— 字体：基线(衬线/无衬线) 与 字体源(网络/本地离线) 两个独立维度 ——
    #   字体: serif/sans           → 基调(font_mood)，沿用旧语义
    #   字体: 本地/离线/local/...  → 同时触发「离线嵌入」且基调回落默认衬线（兼容旧快捷写法）
    #   字体源: 本地/...           → 离线嵌入（不干扰基调）
    #   字体基调: serif/sans       → 离线时另指定基调（与 字体 不冲突）
    _font_raw = str(meta.get("字体", meta.get("font", ""))).strip().lower()
    _font_src = str(meta.get("字体源", meta.get("字体本地", ""))).strip().lower()
    _is_local = _font_raw in ("本地", "离线", "local", "offline") or _font_src in ("本地", "离线", "local", "offline")
    if _is_local and _font_raw in ("serif", "sans", "无衬线"):
        font_mood = _font_raw
    elif _font_raw in ("serif", "sans", "无衬线"):
        font_mood = _font_raw
    else:
        font_mood = str(meta.get("字体基调", "")).strip()  # 离线时另指定基调
    font_mode = "local" if _is_local else ""
    SVG_OV = _load_svg_overrides(base, out_dir)
    for _pi, p in enumerate(pages, 1):
        t = LAYOUT_MAP.get(p.get("layout", ""), "text")
        s = {"type": t, "emphasis": p.get("emphasis", [])}
        _apply_header_fields(p, s, t)
        _warn_body_overflow(s, _pi)
        _apply_fit_mode(p, s, out_dir, base)
        _apply_content_fields(p, s)
        _apply_fixed_elements(p, s, t)
        _inject_svg(p, s, _lec_label, SVG_OV)
        slides.append(s)
    # M03 前段受控校验（可选，默认关闭）
    # ⚠️ 反污染规则：通用引擎**不得内置任何系列的专属词表**（如某系列的固定 5 板块名）。
    # 词表一律由调用方显式提供——大纲顶部 `- 块词表: 甲 / 乙 / 丙`，或经 --profile 注入。
    # 未配置即不校验，通用场景零打扰。
    _bw_raw = str(meta.get("块词表", "") or "").strip()
    if _bw_raw:
        fixed = {w.strip() for w in re.split(r"[/、,，|\s]+", _bw_raw) if w.strip()}
        for p in pages:
            fl = p.get("foot_left", "")
            head = fl.split("·")[0].strip() if fl else ""
            if head and head not in fixed:
                print("  [块词表警告] %s 的 M03 前段「%s」不在词表 %s"
                      % (p["_pid"], head, "/".join(sorted(fixed))))
    _st = meta.get("总讲次数", "")
    _st = int(_st) if (str(_st).strip().isdigit() and int(_st) > 0) else len(pages)
    return {"title": title, "lecture_no": lec_no, "series_total": _st,
            "series_name": series, "lecture_title": title, "theme": theme,
            "font_mood": font_mood, "font_mode": font_mode, "slides": slides}


def _prepare_local_images(pages, base, out_dir):
    """把大纲里 M12 文件: 指定的本地配图拷到 输出目录/images/，并把 file 改写为输出相对路径。
    找不到文件则退回虚线占位（删掉 file），不让渲染崩。
    2026-08-21 安全加固：拒绝**绝对路径**与**目录穿越（..）**，并确保解析后的真实路径
    落在 base 之内；越界/可疑路径直接退回占位，杜绝借 M12 文件: 把任意本地文件读出并外泄。"""
    import shutil
    img_dir = os.path.join(out_dir, "images")
    base_norm = os.path.normpath(base)
    for p in pages:
        # L23 多图证据墙：imgs: 列表逐张拷贝——必须放在【单图逻辑之前】，
        # 否则遇到无单图的页面会被下面的 `continue` 跳过，导致多图一张都不拷。
        for im in (p.get("imgs") or []):
            g = (im or {}).get("file")
            if not g:
                continue
            if os.path.isabs(g) or ".." in g.replace("\\", "/").split("/"):
                print("  [图片安全拦截] 拒绝可疑路径（绝对路径/穿越），跳过：%s" % g)
                im.pop("file", None)
                continue
            gsrc = os.path.normpath(os.path.join(base, g))
            if gsrc != base_norm and not gsrc.startswith(base_norm + os.sep):
                print("  [图片安全拦截] 路径越界，跳过：%s" % gsrc)
                im.pop("file", None)
                continue
            if not os.path.exists(gsrc):
                print("  [图片警告] 找不到本地配图，跳过：%s" % gsrc)
                im.pop("file", None)
                continue
            os.makedirs(img_dir, exist_ok=True)
            shutil.copyfile(gsrc, os.path.join(img_dir, os.path.basename(gsrc)))
            im["file"] = "images/" + os.path.basename(gsrc)
        f = p.get("img", {}).get("file")
        if not f:
            continue
        # 拒绝绝对路径与穿越
        if os.path.isabs(f) or ".." in f.replace("\\", "/").split("/"):
            print("  [图片安全拦截] 拒绝可疑路径（绝对路径/穿越），退回占位：%s" % f)
            p["img"].pop("file", None)
            continue
        src = os.path.normpath(os.path.join(base, f))
        # 解析后必须仍在 base 之内
        if src != base_norm and not src.startswith(base_norm + os.sep):
            print("  [图片安全拦截] 路径越界，退回占位：%s" % src)
            p["img"].pop("file", None)
            continue
        if not os.path.exists(src):
            print("  [图片警告] 找不到本地配图，退回占位：%s" % src)
            p["img"].pop("file", None)
            continue
        os.makedirs(img_dir, exist_ok=True)
        dst = os.path.join(img_dir, os.path.basename(src))
        shutil.copyfile(src, dst)
        p["img"]["file"] = "images/" + os.path.basename(src)


if __name__ == "__main__":
    _argv = sys.argv[1:]
    # 先抽走 -- 选项，避免被当成位置参数（2026-09-03 修复：--theme 被吞为输出目录的 P0）
    theme_arg = ""
    profile_arg = ""
    _pos = []
    offline_arg = False
    for _a in _argv:
        if _a.startswith("--theme="):
            theme_arg = _a.split("=", 1)[1]
        elif _a.startswith("--profile="):
            profile_arg = _a.split("=", 1)[1]
        elif _a in ("--offline-fonts", "--offline"):
            offline_arg = True
        else:
            _pos.append(_a)
    path = _pos[0] if _pos else "outline.md"
    out_dir = _pos[1] if len(_pos) > 1 else os.path.join(os.path.dirname(os.path.abspath(path)), os.path.splitext(os.path.basename(path))[0] + "_eink")
    meta, pages = parse_outline(path)
    # 专用派生技能（profile 机制）：固化项通过 --profile 注入，覆盖大纲默认值
    if profile_arg:
        try:
            import json as _json
            with open(profile_arg, encoding="utf-8") as _pf:
                _prof = _json.load(_pf)
            for _k, _v in _prof.items():
                meta[_k] = _v
            print("已载入 profile：%s（固化 %d 项）" % (profile_arg, len(_prof)))
        except Exception as _e:
            print("  [profile 警告] 读取失败，忽略：%s" % _e)
    print("解析：共 %d 页，讲次=%s，讲次类型=%s，块词表=%s" % (
        len(pages), meta.get('讲次', '—'), meta.get('讲次类型', '—'),
        meta.get('块词表', '（未设置·不校验）')))
    base = os.path.dirname(os.path.abspath(path))
    _prepare_local_images(pages, base, out_dir)
    lec = build_lecture(meta, pages, base, out_dir)
    _font_mode = "local" if offline_arg else (lec.get("font_mode") or None)
    out = build(lec, out_dir, theme=theme_arg if theme_arg else None, font_mode=_font_mode)
    rep = validate(open(out, encoding="utf-8").read())
    print("已生成：", out)
    print("校验：", json.dumps(rep, ensure_ascii=False))
