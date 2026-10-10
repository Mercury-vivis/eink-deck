# -*- coding: utf-8 -*-
"""lint_outline.py —— 大纲守护（渲染前检查；只报告，绝不阻断、绝不修改）
================================================================

用法：
    python lint_outline.py 大纲.md
    （也可被其他脚本 import：lint_outline(path) -> list[dict]）

定位（老陈 2026-09-09 裁定）：
  - AI 写大纲：SKILL 工作流规定「生成大纲 → 跑 lint → 按提示自改 → 0 错误后才渲染」；
  - 人工手写大纲：不指望作者主动跑，故渲染 bat 里渲染前自动跑一遍（不阻断渲染）。

设计纪律：
  - exit 恒为 0——lint 的职责是报告，不是拦截（拦截交给人/ AI 按报告处理）；
  - 每条问题 = 行号 + 等级 + 问题 + 坑转做法（不只报错，还给改法）；
  - 检查项全部来自 SKILL.md 已文档化的语法/坑，以及真实事故（2026-09-09 第9讲
    「强调: 裸短语整行被静默丢弃」「M10 notes 里写 ||| 不生效」）；
  - 纯标准库：系统 python（无第三方依赖）即可跑，bat 直接调用无门槛。

等级：
  [错误] 几乎必然坏页或静默丢内容；
  [警告] 部分失效 / 与引擎行为不一致 / 容易踩坑；
  [提示] 写法可能非本意，建议确认。

版本记录：
  - 2026-09-11：新增 2d「items 主行带值」检查——引擎解析器只认空值+缩进子项，带值行被静默
    忽略（稿2 外审发现，正则级证据）；同批把 L12b items 与图源同页的口径在文档层改为
    「引擎静默丢弃、仅 lint 拦截」（引擎 build_lecture() 只对 侧车/svg: 两源报错）。
  - 2026-09-12：新增 2e「data_animate: / 数据_animate: 取值合法性」检查——值须 ∈ 10 个已知
    recipe（cascade/hero/quote/directional/pipeline/hbar/kpitower/loop/system/wall）；拼错或带连字符
    写法会被渲染层静默退化为无入场动画，故归 警告 级拦截（与 _PRIMITIVES / _MOTION 口径对齐）。
  - 2026-09-17：新增「标题字段半空格斜杠」警告——仅对引擎按「两侧带空白 /」分行的字段
    （M06/M07/M08 标题、M05 kicker、M10 正文/notes/列表、页面级 title/callout）检测一侧贴字、
    一侧空格的斜杠（如「世界不太平、/ 国家」）；引擎只在「两侧都空白的 /」处切分，这种写法不换行、
    会渲染成带斜杠的一行。零空格内容斜杠（唐/突厥、TCP/IP）与全空格分隔符均不报，避免误报正常文字。
    根因：2026-09-17 第1次课大纲 10 处标题斜杠违规肉眼漏检（贴全角标点未空格），lint 此前无此项兜底。
  - 2026-09-18：新增「2i」ic= 图标名校验——引擎 p_pillar 把 ic 值原样写进 data-lucide，lucide 不识别
    的名字静默跳过、该格图标留空（第1次课 P12「filetext」事故：应 file-text，lint 0报但图标消失）。
    比对 engine/eink_assets/lucide_icons.txt（lucide kebab-case 白名单，由 _gen_lucide_list.mjs 从
    lucide.umd.min.js 提取）；未知名报 错误 级，渲染前拦住。lint 不解析 umd，只读预生成白名单（纯标准库）。
"""
import io
import json
import os
import re
import sys

# ---- 常量真源：syntax_registry.py（一期治理 2026-09-15：不再双份维护） ----
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import syntax_registry as REG

# ---- lucide 图标名白名单（ic= 校验数据源；由 engine/_gen_lucide_list.mjs 从
#      eink_assets/lucide.umd.min.js 提取，lucide 升级时重跑。2026-09-18 新增） ----
_LUCIDE_LIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eink_assets", "lucide_icons.txt")
_LUCIDE_ICONS = set()
try:
    with io.open(_LUCIDE_LIST, "r", encoding="utf-8") as _f:
        for _ln in _f:
            _ln = _ln.strip()
            if _ln:
                _LUCIDE_ICONS.add(_ln)
except Exception:
    _LUCIDE_ICONS = set()   # 读不到则不校验（不阻断 lint）

LAYOUT_CODES = REG.LAYOUT_CODES                 # 28 版式码（含 L12b）
MODULE_CODES = set(REG.MODULE_FIELDS.keys())    # M01–M16
RECIPES = REG.RECIPES                           # 10 个动效 recipe
SPLIT_FIELDS = REG.SPLIT_FIELDS                 # 会按「两侧空白 /」分行的字段
STEP_OK_FIELDS = REG.STEP_OK_FIELDS             # 允许 ||| 分步的字段
PAGE_RE = re.compile(r"^#{2,4}\s+(P\d+[A-Za-z]?)\s*[·•\-]?\s*(.*)$")
MODULE_RE = re.compile(r"^(\s*)-\s*(M\d{1,2})\s*([^:]*)\s*[：:]\s*(.*)$")   # 全角冒号兼容（引擎同款）
EMPH_RE = re.compile(r"^\s*-\s*强调\s*[：:]\s*(.*)$")
EMOJI_RE = re.compile(r"[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF"
                      r"\U0001F1E6-\U0001F1FF\U00002700-\U000027BF]")
# 会按「两侧带空白的 /」分行的字段（用于单独斜杠提示的判别）
# 会原生渲染 svg_inline 的版式（其余版式走底部通用图位；chain 不渲染）
NATIVE_SVG_LAYOUTS = {"L05", "L11", "L12"}
# 通用内联 SVG 字段（2026-09-10 新增）：`- svg: <svg …>`
SVG_FIELD_RE = re.compile(r"^\s*-\s*svg\s*[：:]\s*(.*)$", re.I)
# 复合键主行带值（2026-09-11 items / 2026-09-15 扩展到全部 6 个复合键）：
# 引擎只认空值+缩进子项，带值行被静默忽略
COMPOUND_KEYS = set(REG.COMPOUND_KEYS.keys())          # items/stats/steps/rows/imgs/kpis
COMPOUND_NONEMPTY_RE = re.compile(r"^\s*-\s*(items|stats|steps|rows|imgs|kpis)\s*[：:]\s*(.+)$", re.I)
# 复合键缩进子项必须带 `- ` 或 `数字.` 前缀（引擎 parse_outline 只认这两种；
# 无前缀缩进行被 continue 静默跳过——2026-09-15 111 处事故的直接根因）
COMPOUND_CHILD_PREFIX_RE = re.compile(r"^\s+[-]\s*|^\s+\d+\.\s*")
# 合法动效 recipe（与 _eink_template.py _MOTION 分支 + _PRIMITIVES 注册表对齐；2026-09-12 新增 lint 校验）
# 局部动效覆盖字段（render_outline.py:557-560 同款匹配；2026-09-12 起由 lint 校验取值合法性）
DATA_ANIMATE_RE = re.compile(r"^\s*-\s*(?:数据_?animate|data_animate)\s*[：:]\s*(.*)$", re.I)
# L27 图幅主导（2026-09-15）：img.file / img_mode 取值校验
IMG_FILE_RE = re.compile(r"^\s*-\s*img\.file\s*[：:]\s*(.*)$", re.I)
IMG_MODE_RE = re.compile(r"^\s*-\s*img_mode\s*[：:]\s*(.*)$", re.I)
# 3a. 未知顶层键（2026-09-15 阶段3a）：引擎 parse_outline 对不认识的顶层键行——
# 所有正则分支都不匹配 → 整行被静默跳过（不上屏、不报错）。此检查把它显式化。
TOPKEY_RE = re.compile(r"^-\s*([A-Za-z\u4e00-\u9fff][\w\u4e00-\u9fff]*(?:\(M\d+\+\w+\))?(?:\.[A-Za-z]+)?)\s*[：:]\s*(.*)$")
# 合法顶层键 = 元数据键 + 页面级键 + 复合键（M 前缀走 MODULE_RE 已有检查，不在此列）
VALID_TOPKEYS = set(REG.META_KEYS) | set(REG.PAGE_KEYS) | set(REG.COMPOUND_KEYS)
# 文末留痕区节标题（三道闸/教师备注/配图设计说明等）：这些节里的列表行是教师自检产物，
# 不是页面字段——命中即进入 in_gate（3a 未知键检查跳过），直到下一个页头恢复。
GATE_SECTION_RE = re.compile(r"^#{2,4}\s*(闸一|闸二|闸三|三道闸|教师备注|备注|本讲配图设计说明|配图设计说明|逐页明细|教师参考|变更日志)")


def _is_pageish(line):
    """像页头但可能不合式的行：## 开头且首个词含数字或以 P 开头。"""
    if not re.match(r"^#{2,4}\s+\S", line):
        return False
    tok = line.lstrip("#").strip().split(" ")[0].split("\t")[0]
    return bool(re.match(r"^(P?\d|P[A-Za-z])", tok, re.I))


def _has_half_spaced_slash(s):
    """检测字符串里是否存在「半空格斜杠」：/ 或 ／ 一侧紧邻非空白字符、另一侧为空白。

    引擎只在 ``\\s+[/／]\\s+``（两侧都空白）处切分换行；这种半空格写法不会换行、
    会渲染成带斜杠的一行（bug）。零空格内容斜杠（唐/突厥、TCP/IP）与全空格分隔符
    均返回 False——避免误报正常文字。跳过 HTML 结束标签 </xxx> 内的斜杠。
    """
    for m in re.finditer(r"[/／]", s):
        j = m.start()
        left = s[j - 1] if j > 0 else ""
        right = s[j + 1] if j + 1 < len(s) else ""
        if left == "<":            # </xxx> 结束标签，斜杠非分隔符
            continue
        left_ws = (left == "" or left.isspace())
        right_ws = (right == "" or right.isspace())
        if left_ws != right_ws:   # 恰一侧空白 → 半空格 → bug
            return True
    return False


def lint_outline(path):
    """主入口：返回问题列表 [{line, level, msg, fix}]。只读，不改任何文件。"""
    issues = []
    try:
        with io.open(path, "r", encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
    except Exception as e:
        return [{"line": 0, "level": "错误", "msg": "无法读取大纲文件：%s" % e, "fix": "确认路径与编码（utf-8 / utf-8-sig）"}]

    page = None            # 当前页号（如 "P11"）
    in_gate = False        # 文末留痕区（三道闸/教师备注等）：3a 未知键检查跳过
    seen_pages = {}        # 页号 -> 首次出现行号
    m12_files = {}         # 当前页已出现的 M12 文件 数
    svg_pages = {}         # 当前页已出现的通用 svg: 数（2026-09-10 新增）
    l12b_pages = {}        # 当前页是否 L12b（页号 -> 行号）
    items_pages = {}       # 当前页是否有 items: 链
    in_compound_key = None # 当前复合键名（items/stats/...；2026-09-15 子项前缀检查状态）
    outline_dir = os.path.dirname(os.path.abspath(path))

    def add(ln, level, msg, fix):
        issues.append({"line": ln, "level": level, "msg": msg, "fix": fix,
                       "page": page or "-", "text": (lines[ln - 1].strip() if 0 < ln <= len(lines) else "")})

    for i, raw in enumerate(lines, 1):
        line = raw.rstrip()

        # ---- 1. 页头 ----
        if line.lstrip().startswith("#"):
            if GATE_SECTION_RE.match(line.strip()):
                in_gate = True
                continue
            if _is_pageish(line):
                m = PAGE_RE.match(line.strip())
                if not m:
                    add(i, "错误", "页头不合式（引擎将整行忽略，页面丢失）",
                        "标准写法：## P3 · 简述（## + 空格 + P编号 + 可选 · 简述）")
                else:
                    pid = m.group(1)
                    if pid in seen_pages:
                        add(i, "警告", "页号 %s 重复（首次出现在第 %d 行）；后页会覆盖前页内容" % (pid, seen_pages[pid]),
                            "每页编号唯一；若有意拆页请改用 P3a/P3b")
                    else:
                        seen_pages[pid] = i
                    page = pid
                    m12_files = {}
                    svg_pages = {}
                    in_gate = False
                continue
            # 其他 ## 标题（如「### 逐页明细」）不检查
            continue

        # ---- 2. 强调字段（必须 [ ]，否则整行被静默丢弃——2026-09-09 第9讲真实事故） ----
        em = EMPH_RE.match(line)
        if em:
            val = em.group(1).strip()
            if not val.startswith("["):
                add(i, "错误", "「强调:」裸短语缺方括号——正则不匹配，整行会被静默丢弃（不变红、无提示）",
                    "改法：强调: [词1, 词2]（方括号内逗号分隔锚点词，正文中命中即变红）")
            elif not val.strip("[]").strip():
                add(i, "警告", "「强调: []」为空锚点——本页将无任何强调色",
                    "删掉本行（无锚点页 stats 走全红兜底）或写入真实锚点词")
            continue

        # ---- 2b. 通用内联 SVG 字段（2026-09-10 新增 `- svg:`） ----
        sv = SVG_FIELD_RE.match(line)
        if sv:
            val = sv.group(1).strip()
            if not val:
                add(i, "错误", "「svg:」值为空——该行不生效（不会出图、也不显示占位）",
                    "填入 <svg …>…</svg>；若本页还没图，把设计说明写到文末「本讲配图设计说明」块，页面不留占位行")
            elif "<svg" not in val:
                add(i, "错误", "「svg:」值里没有 <svg 标签——引擎按原文注入，页面上会显示一串源码文本",
                    "值必须是完整 SVG 源码（以 <svg …> 开头，单行写完；多行会被逐行解析器截断）")
            if page:
                svg_pages[page] = svg_pages.get(page, 0) + 1
                if svg_pages[page] > 1:
                    # 2026-09-10 老陈裁定：同页多源直接报错，不再静默取"最后一条"
                    add(i, "错误", "同页第 %d 条「svg:」——一页只允许一个示意图源，多源会互相覆盖" % svg_pages[page],
                        "一页一张示意图；多图请拆页")
            continue

        # ---- 2d. 复合键主行带值（2026-09-11 items；2026-09-15 扩到全部 6 键） ----
        # 引擎只认空值+缩进子项，带值行被静默忽略（不上屏、无提示）
        ck = COMPOUND_NONEMPTY_RE.match(line)
        if ck:
            add(i, "警告", "「%s:」带了值——引擎解析器只认空值 + 缩进子项，这个值会被静默忽略（不上屏、无提示）" % ck.group(1),
                "写成 `- %s:`（冒号后留空），子项放在缩进行：`- 子键=值 / 子键=值`" % ck.group(1))
            continue
        # ---- 2d2. 复合键缩进子项必须带 `- ` 或 `数字.` 前缀（2026-09-15 新增） ----
        # 引擎 parse_outline 对复合块内的缩进行只认 `^\s+[-]\s*` 或 `^\s+\d+\.`；
        # 无前缀的缩进行（如 `  k=值` 或 `  子键=值`）被 continue 静默跳过——
        # 这是 2026-09-15 第 1-4 讲 111 处「子项缺 - 前缀」事故的直接根因。
        # 状态机：进入复合键（空值行）后，遇到缩进行须带前缀；遇新顶层 bullet 退出。
        if in_compound_key:
            if re.match(r"^-", line):
                in_compound_key = False
            elif line.strip() == "":
                pass
            elif line.startswith((" ", "\t")):
                if not COMPOUND_CHILD_PREFIX_RE.match(line):
                    add(i, "错误", "复合键「%s:」的缩进子项缺「- 」前缀——引擎会静默跳过这行，内容不上屏、不报错" % in_compound_key,
                        "子项必须写成 `- 子键=值 / 子键=值`（或 `数字. ` 前缀）；不能是裸 `  子键=值`")
                else:
                    # 3a（阶段3a）：子项键名校验——引擎 parse_compound_item 只认 subitems 里的键，
                    # 未知键（如 stats 写 `- num=5`）整项被静默丢弃
                    csm = re.match(r"^\s+[-]\s*([A-Za-z\u4e00-\u9fff][\w\u4e00-\u9fff]*)\s*=", line)
                    if csm and csm.group(1) not in REG.COMPOUND_KEYS[in_compound_key]["subitems"]:
                        add(i, "警告", "复合键「%s:」子项键「%s」引擎不识别——该子项被静默丢弃（不上屏、不报错）" % (in_compound_key, csm.group(1)),
                            "合法子项键：%s" % " / ".join(sorted(REG.COMPOUND_KEYS[in_compound_key]["subitems"])))
                    # 2i（2026-09-18 新增）：ic= 图标名校验
                    # 引擎 p_pillar 把 ic 值原样写进 data-lucide，lucide 不识别的名字静默跳过
                    # → 该格图标留空、lint 此前无此项兜底（第1次课 P12「filetext」事故：应 file-text）。
                    # 白名单来自 engine/eink_assets/lucide_icons.txt（lucide kebab-case，由 _gen_lucide_list.mjs 提取）。
                    if _LUCIDE_ICONS:
                        _icm = re.search(r'ic\s*=\s*([^\s/／]+)', line)
                        if _icm:
                            _icv = _icm.group(1).strip()
                            if _icv not in _LUCIDE_ICONS:
                                add(i, "错误", "「ic=%s」不是 lucide 合法图标名——引擎原样写进 data-lucide，lucide 静默跳过、该格图标留空（不变红、无提示）" % _icv,
                                    "lucide 用 kebab-case（如 file-text 不是 filetext）；写前查官方命名或 eink 语法速查；合法名见 engine/eink_assets/lucide_icons.txt")
        if re.match(r"^\s*-\s*(items|stats|steps|rows|imgs|kpis)\s*[：:]\s*$", line):
            in_compound_key = re.match(r"^\s*-\s*(items|stats|steps|rows|imgs|kpis)\s*[：:]\s*$", line).group(1)
            continue

        # ---- 2e. 局部动效覆盖字段 data_animate: / 数据_animate:（2026-09-12 新增） ----
        # 值须 ∈ RECIPES；拼错/带连字符时渲染层正则匹配不到或 JS 不识别，本页静默退化为无入场动画
        da = DATA_ANIMATE_RE.match(line)
        if da:
            val = da.group(1).strip()
            if not val:
                add(i, "警告", "「data_animate:」值为空——本页动效退回版式默认 recipe（写了等于没写，无指定动效）",
                    "删掉本行（沿用默认）或填入合法 recipe 名（见 SKILL.md「动效全表」10 选 1）")
            elif val not in RECIPES:
                add(i, "警告", "「data_animate: %s」不是已知 recipe——JS 不识别，本页静默退化为无入场动画（不变红、无提示）" % val,
                    "合法值（10 选 1，纯字母无连字符）：cascade / hero / quote / directional / pipeline / "
                    "hbar / kpitower / loop / system / wall；拼错或 h-bar 此类连字符写法都会静默失效")
            continue

        # ---- 2f. 纵向/规则线/图对齐 取值校验 ----
        vmd = re.match(r"^-\s*(纵向|规则线|图对齐)[：:]\s*(.*)$", line)
        if vmd:
            vk, vv = vmd.group(1), vmd.group(2).strip()
            if vk == "纵向" and vv not in ("顶", "中", "底"):
                add(i, "警告", "「纵向: %s」非法——只认 顶/中/底，其他写法本页静默沿用默认居中" % vv,
                    "合法值：顶（贴页眉）/ 中（默认，剩余空间居中）/ 底（贴页脚）")
            elif vk == "规则线" and vv not in ("是", "否"):
                add(i, "警告", "「规则线: %s」非法——只认 是/否" % vv,
                    "写「规则线: 是」在标题上方加一条 accent 短横线（仅居左页、全系列一贯）")
            elif vk == "图对齐" and vv not in ("底", "顶"):
                add(i, "警告", "「图对齐: %s」非法——只认 底/顶（默认顶对齐）" % vv,
                    "写「图对齐: 底」让 L05 右图坐底")
            continue

        # ---- 2g. L27 img_mode 取值校验（2026-09-15 新增） ----
        imd = IMG_MODE_RE.match(line)
        if imd:
            vv = imd.group(1).strip().lower()
            if vv not in REG.ENUMS["img_mode"]:
                add(i, "警告", "「img_mode: %s」非法——只认 cover/contain/fit/side，其他写法本页静默回退默认" % vv,
                    "cover（裁切填满·标题悬浮）/ contain（不裁·标题落下方）/ fit（按图比例自适应·标题落下方）/ side（竖图占左 40%）")
            continue

        # ---- 2h. L27 img.file 路径提示（2026-09-15 新增） ----
        ifd = IMG_FILE_RE.match(line)
        if ifd:
            vv = ifd.group(1).strip().strip("\"'")
            if not vv:
                add(i, "错误", "「img.file:」值为空——L27 无图，页面只剩标题区", "填入 images/ 相对路径")
            elif not vv.startswith("images/"):
                add(i, "警告", "「img.file: %s」不是 images/ 相对路径——真实图应放 images/ 目录" % vv,
                    "路径写法：images/文件名.webp（禁绝对路径与目录穿越，引擎会拦截）")
            continue

        # ---- 3/4/5/7/8. 模块行 ----
        mm = MODULE_RE.match(line)
        if mm:
            indent, mod, field, val = mm.group(1), mm.group(2).upper(), mm.group(3).strip(), mm.group(4)
            if mod not in MODULE_CODES:
                add(i, "错误", "未知模块码 %s（引擎会打印警告并忽略整行）" % mod,
                    "模块码范围 M01–M16，见 SKILL.md 语法速查")
                continue
            # M12 文件 计数（同页多条仅最后一条生效）
            if mod == "M12" and ("文件" in field):
                m12_files[page] = m12_files.get(page, 0) + 1
                if m12_files[page] > 1:
                    add(i, "警告", "同页第 %d 条「M12 文件:」，仅最后一条生效（前值被覆盖）" % m12_files[page],
                        "一页一个图位；多图请拆页或用 L18 资源页")
                # M12 路径存在性（相对大纲目录；真实图须 images/ 前缀）
                if val.strip():
                    fp = val.strip().strip("\"'")
                    full = os.path.join(outline_dir, fp.replace("/", os.sep))
                    if not os.path.exists(full):
                        hint = "" if fp.startswith("images/") else "（另注意：真实图须 images/ 前缀）"
                        add(i, "警告", "M12 文件指向的图不存在：%s%s" % (fp, hint),
                            "补图或改路径；渲染会退回占位框")
                continue
            # 标题行数（M06 h_hero / M08 h_xl）：双基线只预留两行，三行以上溢出标题区、与正文叠压
            if mod in ("M06", "M08") and re.search(r"h_(hero|xl)", field):
                _tn = len(re.split(r"\s+[/／]\s+", val))
                if _tn >= 3:
                    add(i, "错误", "标题分成 %d 行——双基线标题区只预留两行，三行会溢出、与正文叠压" % _tn,
                        "精简到两行内（结论型短标题）；或拆成两页、一页一个判断")
                    continue
            # 字号三控（M06/M08/M10 不支持，写了不生效）
            if mod in ("M06", "M08", "M10") and field.startswith("字号"):
                add(i, "警告", "M%s 不支持「字号」三控（引擎告警并忽略，写了不生效）" % mod,
                    {"M06": "行内 <size=0.6>词</size>", "M08": "「M08 行大小: 小·大」",
                     "M10": "行尾未闭合 <size=大>（整段）或 <size=大>词</size>（局部）"}[mod])
                continue
            # ||| 位置检查（2026-09-09 起仅 M10 正文/notes/列表 支持分步）
            if "|||" in val and mod != "M10":
                add(i, "警告", "「|||」写在 %s %s——该字段不支持分步，||| 会按字面量渲染进页面" % (mod, field or "(主值)"),
                    "分步揭示只认「M10 正文」与「M10 notes」（2026-09-09 起）；其余字段请删掉 |||")
                continue
            if mod == "M10" and "|||" in val:
                fld = field.strip()
                if fld.startswith("字号") or fld.startswith("垂直") or fld.startswith("水平"):
                    continue
                ok_field = any(fld == f or fld.startswith(f) for f in STEP_OK_FIELDS)
                if not ok_field:
                    add(i, "警告", "「|||」写在 M10 %s——该子字段不支持分步" % (fld or "(正文)"),
                        "分步只认「M10 正文:」「M10 notes:」（列表: 亦不解析 |||）")
                elif not fld.startswith("notes") and re.search(r"\s+[/／]\s+", val):
                    add(i, "警告", "M10 值同时含「|||」与「 / 」：「/」分行被忽略（分步优先）",
                        "若想两者并存，把同一分步内的并列内容改用「、」或改写；确要 / 分行请拆到多行")
                continue
            # 单独贴字斜杠提示（仅对会分行的字段；有空白斜杠时不必提示）
            if mod == "M10" and not field.startswith(("字号", "垂直", "水平")) and field.strip() not in ("notes",):
                if val and re.search(r"\S[/／]\S", val) and not re.search(r"\s+[/／]\s+", val):
                    add(i, "提示", "值里有贴字斜杠（如 a/b）——本字段按约定不切分，斜杠将原样显示",
                        "若想分行/分项，用两侧带空白的「 / 」；若是内容斜杠（如 唐/突厥）请忽略本条")
            # 半空格斜杠警告（2026-09-17 新增）：仅对「按两侧空白 / 才分行」的字段，
            # 检测一侧贴字、一侧空格的斜杠（如「世界不太平、/ 国家」）——引擎只在 \s+/\s+ 处切分，
            # 这种写法不会换行、会渲染成带斜杠的一行。零空格内容斜杠（唐/突厥）与全空格分隔符均不报。
            if (mod in ("M06", "M07", "M08") or field.strip() in REG.SPLIT_FIELDS) and val:
                if _has_half_spaced_slash(val):
                    add(i, "警告", "标题/字段含半空格斜杠（一侧贴字、一侧空格）——本字段按「两侧带空白的 /」才分行，这里不会换行、会显示成带斜杠的一行",
                        "想换行用「 / 」（两侧空格）；若确为内容斜杠（如 唐/突厥）请写成无空格「X/Y」")
            continue

        # ---- 8a. 页面级分行字段半空格斜杠（2026-09-17 新增） ----
        # title:（L27）/ callout:（L05/L07）按「两侧空白 /」分行；半空格斜杠不会换行。
        pk = re.match(r"^\s*-\s*(title|callout)\s*[：:]\s*(.*)$", line)
        if pk and pk.group(2):
            if _has_half_spaced_slash(pk.group(2)):
                add(i, "警告", "标题/字段含半空格斜杠（一侧贴字、一侧空格）——本字段按「两侧带空白的 /」才分行，这里不会换行、会显示成带斜杠的一行",
                    "想换行用「 / 」（两侧空格）；若确为内容斜杠（如 唐/突厥）请写成无空格「X/Y」")

        # ---- 8b. 版式行 ----
        lm = re.match(r"^\s*-\s*版式\s*:\s*(\S+)\s*(?:[·•\-]\s*(.*))?$", line)
        if lm:
            code = lm.group(1).strip()
            if code not in LAYOUT_CODES:
                if code.upper() in {c.upper() for c in LAYOUT_CODES}:
                    add(i, "错误", "版式码 %s 大小写不符（引擎按原样查找，查不到会告警并退回默认版式）" % code,
                        "版式码为大写 L + 两位数字（L12b 除外），如 L13")
                else:
                    add(i, "错误", "未知版式码 %s（不在 L01–L27 / L12b 内）" % code,
                        "见 SKILL.md「19 版式全展开」；L12b 是链式版式的独立码")
            if code == "L12b":
                l12b_pages[page or "-"] = i   # 记下本页用了 L12b，稍后与 svg:/items 交叉校验
            continue

        # ---- 9. emoji ----
        if EMOJI_RE.search(line):
            add(i, "警告", "检测到 emoji（引擎渲染时会剔除，页面上不显示）",
                "需要图标语义请用 M13/M14 文字标注，或行内 <ico=名> 图标（见 SKILL.md）")

        # ---- 3a. 未知顶层键（2026-09-15 阶段3a；放循环末尾：此前各分支已 continue 掉合法行） ----
        # 走到这里的非缩进顶层键行 = 引擎 parse_outline 不认识的字段（所有正则分支都不匹配）
        # → 整行静默跳过。「写了不报错=静默无效」的土壤，此处显式化。
        # in_gate（文末留痕区）内不做此检查——三道闸/教师备注里的列表行是自检产物，非页面字段。
        tk = TOPKEY_RE.match(line)
        if tk and not in_gate and not line[:1].isspace() and not tk.group(1).startswith("M"):
            if tk.group(1) not in VALID_TOPKEYS:
                add(i, "警告", "「%s:」不是引擎认识的字段——整行被静默忽略（不上屏、不报错）" % tk.group(1),
                    "核对语法速查（engine/generated/语法速查.md）：合法顶层键 = §1 元数据键 / §2 页面级键 / §4 复合键；拼错或臆造字段都会静默丢")

    # ---- 10b. L12b（链式）与 svg: 同页冲突（2026-09-10 老陈裁定：同页多源直接报错） ----
    # 放在循环外做整页判断，避免依赖「版式行出现在 svg 行之前」这种脆弱顺序。
    _pg_buf, _cur = {}, None
    for _i, _raw in enumerate(lines, 1):
        _hm = re.match(r"^#{2,4}\s*(P\d+)\b", _raw)
        if _hm:
            _cur = _hm.group(1)
            _pg_buf.setdefault(_cur, {"l12b": 0, "svg": 0, "items": 0})
            continue
        if _cur is None:
            continue
        _b = _pg_buf[_cur]
        if re.match(r"^\s*-\s*版式\s*:\s*L12b\b", _raw):
            _b["l12b"] = _i
        elif SVG_FIELD_RE.match(_raw):
            _b["svg"] = _i
        elif re.match(r"^\s*-\s*items\s*:\s*$", _raw):
            _b["items"] = _i
    for _p, _b in _pg_buf.items():
        if _b["l12b"] and _b["svg"]:
            issues.append({"line": _b["svg"], "level": "错误", "page": _p,
                           "msg": "L12b（链式）页同时挂了「svg:」——本页用 `items:` 渲染节点链，"
                                  "两套内容同级打架；且 chain 版式不渲染底部图位，svg 会被静默丢弃",
                           "fix": "二选一：留 items 链就删 `- svg:`；要用示意图则版式改 L12 并删 items",
                           "text": lines[_b["svg"] - 1].strip()})

    # ---- 10c. L21/L22 自绘图形页与 svg: 同页冲突（2026-09-11 新增 5 版式） ----
    # 这两个版式的 SVG 由引擎按 steps:/items: 自动生成；再挂图源会形成同页双图源。
    _pg2, _cur2 = {}, None
    for _i, _raw in enumerate(lines, 1):
        _hm = re.match(r"^#{2,4}\s*(P\d+)\b", _raw)
        if _hm:
            _cur2 = _hm.group(1)
            _pg2.setdefault(_cur2, {"selfdraw": 0, "svg": 0})
            continue
        if _cur2 is None:
            continue
        _b2 = _pg2[_cur2]
        if re.match(r"^\s*-\s*版式\s*:\s*L(?:21|22)\b", _raw):
            _b2["selfdraw"] = _i
        elif SVG_FIELD_RE.match(_raw):
            _b2["svg"] = _i
    for _p, _b2 in _pg2.items():
        if _b2["selfdraw"] and _b2["svg"]:
            issues.append({"line": _b2["svg"], "level": "错误", "page": _p,
                           "msg": "L21（闭环图）/ L22（系统同心圆）的图形由引擎按 steps:/items: 自动生成，"
                                  "同页再挂「svg:」会形成双图源、互相打架",
                           "fix": "二选一：留 steps:/items: 让引擎绘图；要手绘示意图则版式改 L12 并删 steps:/items:",
                           "text": lines[_b2["svg"] - 1].strip()})

    # ---- 10d. M12 文件 与 svg: 同页共存（2026-09-15 二期：workbuddy #3 机器校验） ----
    # 引擎 _img_figure 优先 svg_inline，同页 M12 文件图被 svg 覆盖且无任何报错——作者无感知。
    # 与 10b/10c 同法做整页扫描（不依赖「版式行/字段行先后顺序」）。
    _pg3, _cur3 = {}, None
    for _i, _raw in enumerate(lines, 1):
        _hm = re.match(r"^#{2,4}\s*(P\d+)\b", _raw)
        if _hm:
            _cur3 = _hm.group(1)
            _pg3.setdefault(_cur3, {"m12f": 0, "svg": 0})
            continue
        if _cur3 is None:
            continue
        _b3 = _pg3[_cur3]
        if re.match(r"^\s*-\s*M12\s*[^:]*文件\s*[：:]\s*\S", _raw):
            _b3["m12f"] += 1
        elif SVG_FIELD_RE.match(_raw):
            _b3["svg"] += 1
    for _p, _b3 in _pg3.items():
        if _b3["m12f"] and _b3["svg"]:
            issues.append({"line": _b3["svg"], "level": "警告", "page": _p,
                           "msg": "同页出现「M12 文件:」与「svg:」——引擎 _img_figure 优先渲染 svg，M12 图片被静默覆盖",
                           "fix": "二选一：删掉 M12 文件 行（保留示意图）或删掉 svg:（保留真实图）",
                           "text": lines[_b3["svg"] - 1].strip()})

    # ---- 11. 侧车 JSON（默认输出目录 <stem>_eink/_svg_overrides.json） ----
    stem = os.path.splitext(os.path.basename(path))[0]
    side = os.path.join(outline_dir, (stem + "_eink"), "_svg_overrides.json")
    if os.path.exists(side):
        try:
            with io.open(side, "r", encoding="utf-8-sig") as f:
                d = json.load(f)
            if not isinstance(d, dict):
                issues.append({"line": 0, "level": "警告", "page": "-",
                               "msg": "侧车 %s 内容不是字典（实际为 %s），渲染时会整份忽略" % (side, type(d).__name__),
                               "fix": "侧车必须是 {键: svg字符串} 纯 JSON 字典", "text": ""})
        except Exception as e:
            issues.append({"line": 0, "level": "警告", "page": "-",
                           "msg": "侧车 %s JSON 解析失败（渲染时整份忽略、零提示）：%s" % (side, str(e)[:60]),
                           "fix": "检查 JSON 合法性：尾随逗号 / 双引号未转义 / 用 UTF-8 无 BOM 保存", "text": ""})

    return issues


_LEVEL_ORDER = {"错误": 0, "警告": 1, "提示": 2}


def _fmt(it):
    loc = ("%s " % it["page"]) if it.get("page") and it["page"] != "-" else ""
    ln = ("L%d" % it["line"]) if it.get("line") else "--"
    txt = (' ｜原文: %s' % it["text"][:48]) if it.get("text") else ""
    return "[%s] %s%s  %s%s\n        ↳ %s" % (it["level"], loc, ln, it["msg"], txt, it["fix"])


def main(argv):
    # --strict：错误或警告均视为失败（退出码 1）——供 golden test / CI 使用（2026-09-15 一期）
    strict = "--strict" in argv
    argv = [a for a in argv if a != "--strict"]
    if not argv:
        print("用法: python lint_outline.py 大纲.md [--strict]")
        return 0
    path = argv[0]
    issues = lint_outline(path)
    issues.sort(key=lambda x: (_LEVEL_ORDER.get(x["level"], 3), x["line"]))
    if not issues:
        print("[lint] %s —— 未发现问题（0 错误 / 0 警告）" % os.path.basename(path))
        return 0
    n_err = sum(1 for x in issues if x["level"] == "错误")
    n_warn = sum(1 for x in issues if x["level"] == "警告")
    n_tip = sum(1 for x in issues if x["level"] == "提示")
    print("[lint] %s —— %d 错误 / %d 警告 / %d 提示" % (os.path.basename(path), n_err, n_warn, n_tip))
    for it in issues:
        print(_fmt(it))
    if n_err:
        print("[lint] 存在 %d 个错误级问题：请修正后重渲（AI 流程：按提示自改后再渲染）。" % n_err)
    print("[lint] 本报告不阻断渲染（exit 0）%s。" % ("；--strict 模式下警告亦视为失败" if strict else ""))
    return 1 if (n_err or (strict and n_warn)) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
