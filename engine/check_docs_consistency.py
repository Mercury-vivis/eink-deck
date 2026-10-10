# -*- coding: utf-8 -*-
"""check_docs_consistency.py —— 文档 ↔ 语法注册表 一致性 guard（二期收尾 2026-09-15）
====================================================================
扫描文档（SKILL.md / 示例大纲 / 模板模块规范 / lecture SKILL）与
syntax_registry.py 对照，四类检查：

  1. 键登记检查（一期）：文档出现但注册表未登记的键 —— 语法散落；
     文档出现 DEPRECATED / DEAD 键 —— 引用废弃语法。
  2. 版式清单完整性（二期）：文档若列出版式清单且条目 ≥20，须齐 28 版式，
     缺项即报（抓「模板模块规范停在 24 版式、漏 L24–L27」类失管）。
  3. 字段 ⊆ mounts（二期）：文档「某版式行」声明的字段须 ∈ 注册表 MOUNTS[版式]
     渲染层消费集——「字段挂错版式 = 静默无效」（L24-27 已于阶段2 补渲染 M10）。
  4. 版本戳检查（2026-09-15 纪律化）：版本号只在 SKILL.md frontmatter；
     被管理文档不维护版本号（无版本戳=对齐指针式合法），出现版本号必须 == 权威。

用法：
    python check_docs_consistency.py [文档路径...]
    （不传路径 = 扫描 eink-deck 与 lecture-outline-design 的默认文档集）
退出码：0 = 一致；1 = 有疑点。
"""
import os
import re
import sys

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
EINK_DIR = os.path.dirname(ENGINE_DIR)          # eink-deck/
SKILLS_ROOT = os.path.dirname(EINK_DIR)         # .user_skills/

DEFAULT_DOCS = [
    os.path.join(EINK_DIR, "SKILL.md"),
    os.path.join(EINK_DIR, "engine", "generated", "示例大纲.md"),
    os.path.join(EINK_DIR, "engine", "generated", "语法速查.md"),
    os.path.join(EINK_DIR, "templates", "eink_模板模块规范.md"),
    os.path.join(SKILLS_ROOT, "lecture-outline-design", "SKILL.md"),
]

# `- 键:` / `- 键 子字段:` / `- 键(M09+body):` / `- img.file:` 提取
KEY_RE = re.compile(r"^-\s*([A-Za-z\u4e00-\u9fff][\w\u4e00-\u9fff]*(?:\(M\d+(?:\+\w+)?\))?(?:\.[A-Za-z]+)?(?:\s+[A-Za-z\u4e00-\u9fff][\w\u4e00-\u9fff]*)?)\s*[：:]", re.M)

# 已知噪声：示例性文本/注释里的键值对写法（不属于大纲语法，白名单过滤）
NOISE = {"v", "l", "label", "nb", "unit", "note", "ic", "t", "d", "ch", "form",
         "mean", "year", "title", "desc", "main", "sub", "file", "cap", "k", "m",
         "blank", "accent", "text", "lead", "statement", "q", "src", "cite",
         # 文档正文列表项（2026-09-15 guard 首跑人工确认，非语法键）
         "产物", "仅用于", "做三件事", "加载顺序", "引擎自动", "改图后", "新增主题",
         "配色", "顶部元数据", "不归本技能", "不走双基线", "本技能管", "核心思想",
         "目的", "落位", "记忆钉", "L19", "条宽口径",
         "版本", "变更记录", "落页判断"}


def scan_doc(path):
    """返回 {key: [行号...]}，key 为文档中出现的顶层语法键。"""
    found = {}
    try:
        text = open(path, encoding="utf-8-sig").read()
    except OSError as e:
        print("  [guard] 无法读取 %s：%s" % (path, e))
        return found
    for i, line in enumerate(text.splitlines(), 1):
        m = KEY_RE.match(line)
        if not m:
            continue
        key = m.group(1).strip()
        base = key.split(" ", 1)[0]
        if base in NOISE:
            continue
        found.setdefault(base, []).append(i)
    return found


# ---- 二期：版式清单完整性 ----
LAYOUT_TOK = re.compile(r"\bL(?:12b|\d{2})\b")


def scan_layouts(path):
    """返回文档中出现的版式码集合（去重）。"""
    try:
        text = open(path, encoding="utf-8-sig").read()
    except OSError:
        return set()
    return set(LAYOUT_TOK.findall(text))


# ---- 二期：字段 ⊆ mounts（模板规范表格行 / 示例大纲） ----
# 匹配表格行内任意位置的版式码（模板规范：`| `L04` | 4 | … |` 在首列；
# 示例大纲：`| `L04` | … |`）
LAYOUT_ROW = re.compile(r"^\|[^|]*\|\s*(\*{0,2}`?)(L(?:12b|\d{2}))(`?\*{0,2})\s*\|")
FIELD_TOK = re.compile(r"`([A-Za-z\u4e00-\u9fff][\w\u4e00-\u9fff]*(?:\.[A-Za-z]+)?)`")
MODULE_TOK = re.compile(r"\b(M\d{2})\b")


def check_layout_completeness(reg, layouts):
    """版式清单完整性：文档列出的版式 ≥20 项时须齐 28 项。"""
    problems = []
    if len(layouts) >= 20 and len(layouts) < len(reg.LAYOUTS):
        miss = sorted(reg.LAYOUT_CODES - layouts)
        problems.append("版式清单不全：文档列 %d/28，缺 %s（引擎 28 版式，模板规范曾停在 24 版式漏 L24-27 即此类失管）"
                        % (len(layouts), "、".join(miss)))
    return problems


def check_field_mounts(reg, path):
    """字段 ⊆ mounts：文档版式行声明的字段须 ∈ MOUNTS[版式]。"""
    problems = []
    try:
        text = open(path, encoding="utf-8-sig").read()
    except OSError:
        return problems
    for i, line in enumerate(text.splitlines(), 1):
        m = LAYOUT_ROW.match(line.strip())
        if not m:
            continue
        code = m.group(2)
        if code not in reg.MOUNTS:
            continue
        fields = set()
        for ft in FIELD_TOK.findall(line):
            base = ft.split(" ", 1)[0]
            fields.add(base if base.startswith("M") else base + ":")
        for mt in MODULE_TOK.findall(line):
            fields.add(mt)
        unknown = sorted(f for f in fields if f not in reg.MOUNTS[code]
                         and f not in reg.MOUNT_ALL)
        if unknown:
            problems.append("L%d：版式行声明的字段 %s 不在引擎该版式消费集（MOUNTS）内——写了静默无效"
                            % (i, "、".join(unknown)))
    return problems


# ---- 二期：版本戳完整性 ----
VERSION_PATTERNS = [
    (re.compile(r"当前：\s*\*\*(v?\d+\.\d+(?:\.\d+)?)\*\*"), "当前版本行"),
    (re.compile(r"契约版本：\s*\*\*(v?\d+\.\d+(?:\.\d+)?)\*\*"), "契约版本行"),
    (re.compile(r"对齐契约.*?v?\d+\.\d+(?:\.\d+)?", re.I), "对齐契约声明"),
    (re.compile(r"版本[:：]\s*(v?\d+\.\d+(?:\.\d+)?)"), "版本字段"),
    (re.compile(r"version[:：]\s*(v?\d+\.\d+(?:\.\d+)?)", re.I), "version 字段"),
    (re.compile(r"版本戳区.*?v?\d+\.\d+(?:\.\d+)?", re.I), "版本戳区"),
    (re.compile(r"\*\*v?\d+\.\d+(?:\.\d+)?\*\*"), "任意版本戳"),
]


def check_version_stamps(path):
    """文档头部（前 60 行）必须有版本行；返回 [缺失标记, 版本戳列表]。"""
    try:
        lines = open(path, encoding="utf-8-sig").read().splitlines()[:60]
    except OSError:
        return None, []
    head = "\n".join(lines)
    hits = []
    for pat, name in VERSION_PATTERNS:
        m = pat.search(head)
        if m:
            hits.append(m.group(1) if m.lastindex else m.group(0))
            break
    return (True if hits else False), hits


def read_authority_version(eink_dir):
    """权威版本 = eink-deck/SKILL.md frontmatter `version:`（版本单一源，2026-09-15 裁定）。"""
    p = os.path.join(eink_dir, "SKILL.md")
    try:
        head = open(p, encoding="utf-8-sig").read().splitlines()[:15]
    except OSError:
        return None
    for line in head:
        m = re.match(r"^\s*version[:：]\s*(v?\d+\.\d+(?:\.\d+)?)", line)
        if m:
            return m.group(1)
    return None


def main(argv):
    sys.path.insert(0, ENGINE_DIR)
    import syntax_registry as REG

    docs = argv if argv else DEFAULT_DOCS
    problems = 0

    # 先扫示例大纲（唯一真实语法样本），建立「大纲里真实出现过的键」基准集
    real_keys = set()
    ex_path = os.path.join(EINK_DIR, "engine", "generated", "示例大纲.md")
    if os.path.exists(ex_path):
        real_keys = set(scan_doc(ex_path))

    authority = read_authority_version(EINK_DIR)
    print("[guard] 权威版本（eink SKILL frontmatter）：%s" % (authority or "未读到！"))
    lecture_md = os.path.join(SKILLS_ROOT, "lecture-outline-design", "SKILL.md")
    for doc in docs:
        if not os.path.exists(doc):
            print("[guard] 跳过（不存在）：%s" % doc)
            continue
        name = os.path.relpath(doc, SKILLS_ROOT)
        doc_problems = []

        # 1. 键登记
        keys = scan_doc(doc)
        unknown_hi, unknown_lo, stale = [], [], []
        for k, lines in sorted(keys.items()):
            status = None
            if k in REG.META_KEYS:
                status = REG.META_KEYS[k]["status"]
            elif k in REG.PAGE_KEYS:
                status = REG.PAGE_KEYS[k]["status"]
            elif k in REG.MODULE_FIELDS:
                status = "ACTIVE"
            elif k in REG.COMPOUND_KEYS:
                status = REG.COMPOUND_KEYS[k]["status"]
            if status is None:
                (unknown_hi if k in real_keys else unknown_lo).append((k, lines[0]))
            elif status in ("DEPRECATED", "DEAD"):
                stale.append((k, status, lines[0]))

        # 2. 版式清单完整性（仅对「声称全量版式清单」的文档检查，防止非清单文档误报）
        if "模板模块规范" in os.path.basename(doc):
            layouts = scan_layouts(doc)
            for p in check_layout_completeness(REG, layouts):
                doc_problems.append("  ?【版式清单】%s" % p)
        else:
            layouts = scan_layouts(doc)

        # 3. 字段 ⊆ mounts
        for p in check_field_mounts(REG, doc):
            doc_problems.append("  ✗【挂载越界】%s" % p)

        # 4. 版本戳检查（2026-09-15 纪律：版本号只在 SKILL frontmatter，被管理文档不维护版本号）
        #    无版本戳 = 对齐指针式（合法）；有版本号必须 == 权威；lecture 独立管理自身版本。
        has_ver, ver_hits = check_version_stamps(doc)
        if os.path.abspath(doc) == os.path.abspath(os.path.join(EINK_DIR, "SKILL.md")):
            print("  ·【版本戳·权威】%s" % (ver_hits[0] if has_ver else "未读到！"))
        elif os.path.abspath(doc) == os.path.abspath(lecture_md):
            if has_ver:
                print("  ·【版本戳】%s（独立技能，自身版本自管）" % ver_hits[0])
            else:
                print("  ·【版本戳】无（独立技能）")
        elif not has_ver:
            print("  ·【版本戳】无（对齐指针式，2026-09-15 起被管理文档不维护版本号）")
        elif authority and ver_hits[0] != authority:
            doc_problems.append("  ✗【版本戳】%s ≠ 权威 %s（SKILL frontmatter）——版本号只许出现在 SKILL 头部，此处应删除或对齐" % (ver_hits[0], authority))
        else:
            print("  ·【版本戳】%s == 权威" % ver_hits[0])

        if unknown_hi or unknown_lo or stale:
            problems += 1
            print("[guard] %s —— 键登记疑点：" % name)
            for k, ln in unknown_hi:
                print("  ✗【高置信】「%s」在示例大纲中真实出现但注册表未登记（L%d）—— 语法散落，必须补登记" % (k, ln))
            for k, ln in unknown_lo:
                print("  ?【待确认】「%s」（L%d）—— 示例大纲未出现该键，疑似文档正文列表项；若确为语法请补登记，否则可忽略" % (k, ln))
            for k, st, ln in stale:
                print("  ⚠ 文档引用了 %s 态键「%s」（L%d）—— 若为「废弃/禁止」说明属合规提及，若为推荐写法需删除" % (st, k, ln))
        if doc_problems:
            problems += 1
            print("[guard] %s —— 版本/挂载/清单检查：" % name)
            for p in doc_problems:
                print(p)
        if not unknown_hi and not unknown_lo and not stale and not doc_problems:
            print("[guard] %s —— 一致（键 %d · 版式 %d/28 · 版本戳在位）" % (name, len(keys), len(layouts)))

    if problems:
        print("[guard] 共 %d 份文档有疑点 —— 高置信项必须处理；待确认项可人工审一次后决定是否加入 NOISE 白名单。" % problems)
        return 1
    print("[guard] 全部文档与注册表一致。")
    # 3c-1（2026-09-15 阶段3）：引擎消费字段 ⊆ MOUNTS —— 双向 guard 纳入日常门禁
    import check_engine_mounts as CEM
    if CEM.main() != 0:
        print("[guard] 3c-1 失败：引擎消费字段与 MOUNTS 不一致，见上方报告。")
        return 1
    # 3c-3（2026-09-15）：MOUNTS 派生物与引擎 _MOUNT 声明一致性（防手改派生物/声明改了没重跑）
    import gen_mounts as GM
    if GM.main(["--check"]) != 0:
        print("[guard] 3c-3 失败：MOUNTS 派生物过期（改声明后需重跑 python gen_mounts.py），见上方报告。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
