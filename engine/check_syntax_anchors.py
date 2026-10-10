# -*- coding: utf-8 -*-
"""check_syntax_anchors.py —— 注册表锚点自检 + 键集合 diff（阶段 X 升级）
================================================================
两部分检查：

A. 锚点自检（一期保留）：遍历 syntax_registry.py 中所有 anchor 串，验证
   「文件.函数/__main__块:分支」的函数名能在对应引擎源文件中检索到。

B. 键集合 diff（阶段 X 新增）：AST 从引擎源码提取「引擎实际消费的键」，
   与注册表逐类双向比对（反向 fail）：
   · 顶层键（parse_outline regex 链展开） ⊆ PAGE_KEYS
   · meta 键（build_lecture / __main__ 的 meta.get 字面量） ⊆ META_KEYS
   · M 模块（apply_module 的 mod == "Mxx" 分支） ⊆ MODULE_FIELDS
   · 复合子项键（parse_compound_item 的 kv 消费） ⊆ COMPOUND_KEYS 全部 subitems 并集
   · 引擎消费但注册表未登记 = 漏登记 → fail（阶段 X 核心：堵死"引擎新增键
     注册表不知道"类漂移——v2.4.42 版本戳滞后、img_pos DEAD 同类根因）

边界（如实标注，不假装覆盖）：
   · ENUMS / INLINE_MARKS / SLASH_RULE：引擎侧多为散落字面量或无字面量
     （data_animate 解析只抓字母、不校验 recipes），保持锚点级检查，
     不升级为键集合 diff。
   · 解析层为「宽容透传」设计（未知键不报错）：本检查只认「显式消费点」
     （regex / meta.get / mod 分支），透传区由渲染层 MOUNTS 消费集兜底。

用法：
    python check_syntax_anchors.py
退出码：0 = 全部通过；1 = 有缺失或漂移。
"""
import ast
import os
import re
import sys

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
RO_SRC = os.path.join(ENGINE_DIR, "render_outline.py")


# =====================================================================
# A. 锚点自检（一期，保留）
# =====================================================================
def collect_anchors(reg):
    out = []
    for v in reg.META_KEYS.values():
        out.append(v.get("anchor"))
    for v in reg.PAGE_KEYS.values():
        out.append(v.get("anchor"))
    for v in reg.MODULE_FIELDS.values():
        out.append(v.get("anchor"))
    for v in reg.COMPOUND_KEYS.values():
        out.append(v.get("anchor"))
    for v in reg.INLINE_MARKS.values():
        out.append(v.get("anchor"))
    out.append(reg.SLASH_RULE.get("anchor"))
    return [a for a in out if a]


def check_anchors(reg):
    misses = []
    total = 0
    for a in collect_anchors(reg):
        total += 1
        f, rest = a.split(".", 1)
        fn = rest.split(":", 1)[0]
        src = os.path.join(ENGINE_DIR, f + ".py")
        if not os.path.exists(src):
            misses.append((a, "源文件缺失"))
            continue
        text = open(src, encoding="utf-8").read()
        if fn == "__main__块":
            if "if __name__ == \"__main__\"" not in text:
                misses.append((a, "__main__ 执行块缺失"))
        elif not re.search(r"def\s+" + re.escape(fn) + r"\b", text):
            misses.append((a, "函数缺失"))
    return total, misses


# =====================================================================
# B. 键集合 diff
# =====================================================================
def _ro_tree():
    return ast.parse(open(RO_SRC, encoding="utf-8").read())


def _collect_re_match_patterns(tree, fn_name):
    """收集指定函数内 re.match(pattern, ...) 的 pattern 常量（限 str 常量）。"""
    pats = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != fn_name:
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                    and sub.func.attr == "match" and sub.args \
                    and isinstance(sub.args[0], ast.Constant) \
                    and isinstance(sub.args[0].value, str):
                pats.append(sub.args[0].value)
    return pats


def _legal_key(k):
    """展开产物合法性校验（fail-safe 兜底）：键必须是大纲键形态。

    合法形态：中英文/数字/下划线/连字符（M03、数据_animate、svg_cap、meta-row、
    图文比例…）；img.file；left(M09+body)/right(M09+body)；特殊 ::design、M*。
    含正则元字符/括号/空白等未展开残留 → 非法（宁严勿漏，报 problem 人工核对）。
    """
    if k in ("::design", "M*"):
        return True
    if "(" in k:
        return re.fullmatch(r"[A-Za-z\u4e00-\u9fff_]+\(M09\+body\)", k) is not None
    if "." in k:
        return re.fullmatch(r"[A-Za-z]+\.[A-Za-z]+", k) is not None
    return re.fullmatch(r"[\w\u4e00-\u9fff\-]+", k) is not None


def _add(keys, problems, p, k):
    if _legal_key(k):
        keys.add(k)
    else:
        problems.append(p)


def _expand_top_keys(patterns):
    """从 parse_outline 的顶层键 regex 链展开键名（受控形态，fail-safe）。

    支持形态：字面量 / (a|b|c) / (?:a|b|c) / _? 双展开 / (M\\d+) → M* / 组后固定后缀
    （如 (left|right)\\(M09\\+body\\)）。无法解析的模式 → problems（调用方 fail）。
    """
    keys, problems = set(), []
    for p in patterns:
        if not p.startswith(r"^-\s*"):
            continue
        if r"([^:：]+)" in p:          # meta 开放字典（不枚举键名，跳过）
            continue
        body = p[len(r"^-\s*"):]
        # 截断到字面「[：:] / [:：]」字符类处（源码的 [：:] 含全角+半角两个冒号，
        # 须用 `+` 匹配 1–2 个，且匹配 `[`+冒号+`]` 整体——不能只匹配冒号，
        # 否则 `[` 字面量与组内 `::design` 会被误截）
        m = re.search(r"\[[:：]+\]", body)
        if m:
            body = body[:m.start()]
        body = re.sub(r"\\s\*$", "", body).strip()   # 清 `[` 前可选的 \s* 残留
        if body.startswith(r"(M\d+)"):
            keys.add("M*")
            continue
        if "(?:" in body:
            mm = re.search(r"\(\?:([^()]*)\)", body)
            if not mm:
                problems.append(p)
                continue
            for a in mm.group(1).split("|"):
                if "_?" in a:
                    _add(keys, problems, p, a.replace("_?", ""))
                    _add(keys, problems, p, a.replace("_?", "_"))
                else:
                    _add(keys, problems, p, a)
            continue
        if "(" in body:
            mm = re.search(r"\(([^()]*)\)", body)
            if not mm:
                problems.append(p)
                continue
            suffix = re.sub(r"\\\(|\\\)|\\\+|\\\.|\\\\", lambda x: {
                r"\(": "(", r"\)": ")", r"\+": "+", r"\.": ".", r"\\": ""}[x.group(0)],
                             body[mm.end():])
            for a in mm.group(1).split("|"):
                _add(keys, problems, p, a + suffix)
            continue
        _add(keys, problems, p, body.replace(r"\.", "."))
    return keys, problems


def _collect_meta_get(tree):
    """收集全模块 meta.get("X") 的 X（build_lecture + __main__ 块；obj 名须为 meta）。"""
    keys = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "get" and node.args \
                and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[0].value, str) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "meta":
            keys.add(node.args[0].value)
    return keys


def _collect_mod_eq(tree):
    """收集 apply_module 内 mod == "Mxx" 的分支常量。"""
    mods = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "apply_module":
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Compare) and len(sub.ops) == 1 \
                    and isinstance(sub.ops[0], ast.Eq) and len(sub.comparators) == 1 \
                    and isinstance(sub.left, ast.Name) and sub.left.id == "mod" \
                    and isinstance(sub.comparators[0], ast.Constant) \
                    and isinstance(sub.comparators[0].value, str):
                mods.add(sub.comparators[0].value)
    return mods


def _collect_subitem_keys(tree):
    """收集 parse_compound_item 消费的子项键：kv.get("X") / "X" in kv / for _k in (...)。"""
    keys = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "parse_compound_item":
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                    and sub.func.attr == "get" and sub.args \
                    and isinstance(sub.args[0], ast.Constant) \
                    and isinstance(sub.args[0].value, str):
                keys.add(sub.args[0].value)
            elif isinstance(sub, ast.Compare) and len(sub.ops) == 1 \
                    and isinstance(sub.ops[0], ast.In) \
                    and isinstance(sub.left, ast.Constant) \
                    and isinstance(sub.left.value, str):
                keys.add(sub.left.value)
            elif isinstance(sub, ast.For) and isinstance(sub.iter, (ast.Tuple, ast.List)):
                for el in sub.iter.elts:
                    if isinstance(el, ast.Constant) and isinstance(el.value, str):
                        keys.add(el.value)
    return keys


def check_key_diff(reg):
    """四类键集合双向比对。返回 (fails, notes)。"""
    tree = _ro_tree()
    fails, notes = [], []

    # 1) 顶层键 ⊆ PAGE_KEYS
    pats = _collect_re_match_patterns(tree, "parse_outline")
    top, problems = _expand_top_keys(pats)
    for p in problems:
        fails.append("parse_outline 顶层键模式无法解析（需人工核对）：%s" % p)
    m_star = "M*" in top
    top.discard("M*")
    # M03 简写（`- M03:` 顶层直写）归 MODULE_FIELDS，其余按 PAGE_KEYS
    page_hit = {k for k in top if re.fullmatch(r"M\d+", k)}
    page_keys = {k for k in top if not re.fullmatch(r"M\d+", k)}
    miss = sorted(page_keys - set(reg.PAGE_KEYS))
    if miss:
        fails.append("引擎顶层键未登记（PAGE_KEYS 缺）：%s" % "、".join(miss))
    if m_star:
        notes.append("顶层 M 字段 regex `(M\\d+)` 为宽容消费，存在性由 apply_module 分支比对覆盖（M* 豁免）")
    if page_hit and not (page_hit <= set(reg.MODULE_FIELDS)):
        fails.append("引擎顶层 M03 简写未登记（MODULE_FIELDS 缺）：%s"
                     % "、".join(sorted(page_hit - set(reg.MODULE_FIELDS))))

    # 2) meta 键 ⊆ META_KEYS
    meta_hit = _collect_meta_get(tree)
    miss = sorted(meta_hit - set(reg.META_KEYS))
    if miss:
        fails.append("引擎 meta.get 消费未登记（META_KEYS 缺）：%s" % "、".join(miss))
    notes.append("meta 键提取范围：build_lecture + __main__ 块的 meta.get 字面量（%d 项）"
                 % len(meta_hit))

    # 3) M 模块 ⊆ MODULE_FIELDS
    mod_hit = _collect_mod_eq(tree)
    miss = sorted(mod_hit - set(reg.MODULE_FIELDS))
    if miss:
        fails.append("引擎 apply_module 分支未登记（MODULE_FIELDS 缺）：%s" % "、".join(miss))
    known_exc = sorted(set(reg.MODULE_FIELDS) - mod_hit - {"M02", "M04", "M15"})
    if known_exc:
        notes.append("MODULE_FIELDS 登记但引擎无 apply 分支：%s（M02=元数据专用 / M04=页码自动 / M15=强调无分支，注册表已注明）"
                     % "、".join(known_exc))

    # 4) 复合子项键 ⊆ COMPOUND_KEYS 全部 subitems 并集
    sub_hit = _collect_subitem_keys(tree)
    reg_sub = set()
    for v in reg.COMPOUND_KEYS.values():
        reg_sub |= set(v.get("subitems", {}))
    miss = sorted(sub_hit - reg_sub)
    if miss:
        fails.append("引擎复合子项键未登记（COMPOUND_KEYS.subitems 缺）：%s" % "、".join(miss))

    return fails, notes


def main():
    sys.path.insert(0, ENGINE_DIR)
    import syntax_registry as reg

    fails, notes = [], []

    total, misses = check_anchors(reg)
    if misses:
        fails.append("锚点 %d 个中 %d 个失效：%s"
                     % (total, len(misses),
                        "；".join("%s——%s" % (a, why) for a, why in misses)))
    else:
        notes.append("锚点 %d 个全部命中（注册表 ↔ 引擎函数存在性）" % total)

    kfails, knotes = check_key_diff(reg)
    fails += kfails
    notes += knotes

    print("[anchors] %s" % ("✗ " + "；".join(fails) if fails else "✓ 全部通过"))
    for n in notes:
        print("  · %s" % n)
    if fails:
        print("[anchors] %d 处不一致 —— 引擎与注册表脱节，需补登记或改引擎。" % len(fails))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
