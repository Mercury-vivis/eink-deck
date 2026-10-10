# -*- coding: utf-8 -*-
"""check_engine_mounts.py —— 3c-1 双向 guard：渲染层 p_* 原语实际消费的字段 ⊆ 注册表 MOUNTS
=====================================================================

定位（阶段3c-1，2026-09-15）：
  - 问题：MOUNTS 为手维护时，引擎加了渲染忘记同步注册表（2026-09-15 L24-27 M10
    缺口实证）→ 四道门禁全漏。阶段3c-3 起 MOUNTS 已派生化（gen_mounts.py 从 p_*
    _MOUNT 声明生成），本脚本用 AST 静态扫描把「引擎消费字段」自动化，
    与注册表 MOUNTS 双向比对，不一致即失败。
  - 单向（正向，fail）：p_* 函数消费的字段必须 ⊆ MOUNTS[版式] ∪ MOUNT_ALL ∪ 通用放行。
  - 反向（人工清单，不 fail）：MOUNTS[版式] 登记的键若 p_* 未直接消费，可能是
    解析层/固定元件消费（M06/M08 由 build_lecture 写 title、M10 由 _fixed_elements
    补挂等），输出清单供人工核对，不自动 fail。
  - 版式映射：LAYOUT_FN（Lxx → p_* 函数名）从 REG.LAYOUTS[L]["type"]（派生物，
    真源 render_outline.LAYOUT_MAP）构建，本脚本不再维护 LAYOUT_MAP 镜像。

用法：
    python check_engine_mounts.py            # 全量双向检查（正向 fail exit 1）
    python check_engine_mounts.py --dump     # 只输出各 p_* 消费键清单（校准用）

设计：
  - AST 只认字面量键：s.get("key") / s["key"] 等（str 常量键）；变量键无法静态判定，
    归入「动态访问」提示。
  - 对象作用域：s=slide dict（大纲字段）；img=img 子键；item/it/row/r/itm/st/k/im=
    复合键子项键（归 COMPOUND_KEYS 管）；其他局部变量=内部键。
  - 归一化：内部组装键（body/title/kicker 等）→ 大纲字段口径（M10/M08/M05…），
    KEY_NORM 显式映射；内部态键（layout/type/m10_h 等）→ IGNORE 排除。
"""
import ast
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import syntax_registry as REG
import _eink_template as TPL

ENGINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_eink_template.py")

# ---- p_* 函数名 → 版式（真源 REG.LAYOUTS[L]["type"] → _PRIMITIVES[type][0]） ----
PRIM_FN = {k: v[0].__name__ for k, v in TPL._PRIMITIVES.items()}
LAYOUT_FN = {L: PRIM_FN[REG.LAYOUTS[L]["type"]] for L in REG.LAYOUTS}

# ---- 内部组装键 → 大纲字段口径（归一化） ----
# key -> 候选大纲键集合（任一命中即视为已登记；多义键按版式取并集）
KEY_NORM = {
    "body": {"M10"},
    "title": {"title:"},                        # 其余版式 title 来自 M06/M08（build_lecture 统一写）→ mount_ok 特殊放行
    "statement": {"statement:", "text:"},
    "text": {"statement:", "text:", "M11", "callout:"},   # L24 别名 / L07 引文(M11) / L05 callout 兼容
    "sub": {"sub:", "lead:"},
    "lead": {"sub:", "lead:"},
    "img_mode": {"img_mode:"},
    "cap": {"cap:"},
    "caption": {"cap:"},                        # 死读兼容（build_lecture 不写），比对上 cap: 亦通过
    "tag": {"tag:"},
    "center": {"center:"},
    "meta": {"meta-row"},
    "emphasis": {"强调"},
    "data_animate": {"data_animate"},
    "grid": {"grid:"},
    "scale": {"scale:"},
    "whitespace": {"whitespace:"},
    "callout": {"callout:"},
    "callout_src": {"callout_src:"},
    "svg": {"svg:"},
    "svg_inline": {"svg:"},
    "kicker": {"M05"},
    "left": {"M10", "left(M09+body):"},         # L05 左栏=body；L09 split 左栏
    "right": {"M10", "right(M09+body):"},
    "src": {"M11", "callout_src:"},             # L07 出处 / L05 callout 兼容
    "cite": {"M11"},                            # L10 引文出处（M11 callout_src）
    "q": {"M11"},                               # L10 引文正文（M11 callout）
    "q_size": {"M11"},                          # L10 m11_size 三控
    "notes": {"M10 notes:"},                    # L16 标牌内容
    "img": {"M12"},                             # M12 或 L27 img.file 均经此 dict（见 obj=='img' 分支）
    "file": {"img.file:"},                      # 死读兜底（无解析入口），比对放行
}
COMPOUND_INTERNAL = {"items", "stats", "steps", "rows", "imgs", "kpis"}

# ---- 内部态键（非大纲字段，AST 扫到直接忽略） ----
IGNORE = {
    "layout", "type", "classes", "color", "recipe", "tone", "design", "left", "right",
    "split", "svg", "foot", "foot_left", "foot_right",
    "body_list", "pending", "notes_pending", "body_pending", "raw", "theme", "idx",
    "n", "i", "num", "total", "title_lines", "sub_lines", "subtitle", "label",
    "aligns", "sizes", "size", "maxh", "ratio", "alt",
    "k", "v", "m", "t", "d", "ic", "ch", "form", "mean", "blank", "year", "desc",
    "main", "nb", "unit", "note", "accent", "l", "hero", "kicker",
    "m01", "m03", "m05", "m11", "m13", "m14", "m16", "link", "links", "src",
    "rows_inner", "steps_inner", "items_inner", "kpis_inner", "stats_inner", "imgs_inner",
    "callout_box", "quote", "pipe", "items_n", "steps_n", "has_meta", "has_note",
    "footnote", "annotation", "meta_notes", "m14_align", "callout_fixed",
    # 内部应用键（apply_module/build_lecture 写入，非大纲字段）：
    "m10_h", "m10_v", "m11_h", "m11_v", "m08_v", "m08_h",
    "title_align", "title_aligns", "hbar_scale", "accent_first",
    "img_align", "cols", "points", "fit_ratio",
}

# 复合键子项变量名（obj 属于它们 → 子项键，归 COMPOUND_KEYS 管，不参与 MOUNTS 比对）
SUBITEM_VARS = {"item", "it", "row", "r", "itm", "st", "k", "im"}


def extract_fn_pairs(tree, fn_name):
    """AST 提取 p_* 函数内所有字面量字符串键，记录对象名（obj.key 形态）。"""
    pairs, dyn = [], []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != fn_name:
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                    and sub.func.attr == "get" and sub.args and \
                    isinstance(sub.args[0], ast.Constant) and isinstance(sub.args[0].value, str):
                obj = sub.func.value.id if isinstance(sub.func.value, ast.Name) else "?"
                pairs.append((obj, sub.args[0].value))
            elif isinstance(sub, ast.Subscript) and isinstance(sub.slice, ast.Constant) \
                    and isinstance(sub.slice.value, str):
                obj = sub.value.id if isinstance(sub.value, ast.Name) else "?"
                pairs.append((obj, sub.slice.value))
            elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                    and sub.func.attr == "get" and sub.args and not (
                    isinstance(sub.args[0], ast.Constant) and isinstance(sub.args[0].value, str)):
                try:
                    dyn.append(ast.unparse(sub.args[0])[:40])
                except Exception:
                    pass
    return pairs, sorted(set(dyn))


def norm_pairs(pairs):
    """(obj, key) 对 → (outline, ignored, subitems)。"""
    outline, ignored, subitems = set(), set(), set()
    for obj, k in pairs:
        if obj in SUBITEM_VARS:
            subitems.add(k)
            continue
        if obj == "img":
            if k == "file":
                outline.add("img.file:")
            elif k == "img_mode":
                outline.add("img_mode:")
            else:
                ignored.add("img.%s" % k)
            continue
        if obj != "s":
            ignored.add("%s.%s" % (obj, k))
            continue
        if k in KEY_NORM:
            outline |= KEY_NORM[k]
        elif k in COMPOUND_INTERNAL:
            outline.add(k + ":")
        elif k in IGNORE:
            ignored.add(k)
        else:
            outline.add(k)
    return outline, ignored, subitems


def mount_ok(layout, outline_key):
    """outline_key 是否被 MOUNTS[layout] ∪ MOUNT_ALL ∪ 通用放行覆盖。"""
    mounts = REG.MOUNTS.get(layout, set())
    if outline_key in mounts or outline_key in REG.MOUNT_ALL:
        return True
    # title 多义：M06/M08 在 mounts 即视为已覆盖（build_lecture 统一写 title）
    if outline_key == "title:" and (mounts & {"M08", "M06"}):
        return True
    # KEY_NORM 多值集合：同源归一化的候选键任一命中即视为全部通过
    # （如 left→{M10, left(M09+body):}：L05 命中 M10、L09 命中 left(M09+body):）
    for norm_set in KEY_NORM.values():
        if outline_key in norm_set and (mounts & norm_set):
            return True
    # svg:/svg_cap: 全版式可挂（L21/L22/L12b 例外由 lint 拦）
    if outline_key in ("svg:", "svg_cap:") and layout not in REG.SVG_MOUNT_EXCEPT:
        return True
    return False


def main():
    dump = "--dump" in sys.argv
    src = io.open(ENGINE, encoding="utf-8").read()
    tree = ast.parse(src)
    fn_defs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}

    fails, notes, all_dump = [], [], []
    for layout in sorted(LAYOUT_FN, key=lambda x: (len(x), x)):
        fn = LAYOUT_FN[layout]
        if fn not in fn_defs:
            fails.append("版式 %s → 渲染函数 %s 不存在！" % (layout, fn))
            continue
        pairs, dyn = extract_fn_pairs(tree, fn)
        outline, ignored, subitems = norm_pairs(pairs)
        if dump:
            all_dump.append("\n[%s] %s  pairs=%s\n    outline=%s\n    ignored=%s\n    subitems=%s\n    dyn=%s"
                            % (layout, fn, sorted(pairs), sorted(outline), sorted(ignored), sorted(subitems), dyn))
            continue
        mounts = REG.MOUNTS.get(layout, set())
        for ok in sorted(outline):
            if not mount_ok(layout, ok):
                fails.append("版式 %s（%s）消费了「%s」但 MOUNTS[%s] ∪ MOUNT_ALL 未登记"
                             % (layout, fn, ok, layout))
        # 反向清单（人工核对；M 字段与通用元件由解析层/固定元件消费，自动豁免）
        for mk in sorted(mounts):
            if mk in REG.MOUNT_ALL or mk.startswith("M") or mk in ("svg:", "svg_cap:", "title:"):
                continue
            mkk = mk.rstrip(":") if mk.endswith(":") else mk
            if mkk in IGNORE or mk in ("图对齐", "纵向", "规则线"):
                continue
            consumed = any(
                mk == o or (mk.endswith(":") and mkk == o.rstrip(":")) or
                (o in KEY_NORM and any(mk == cand or (cand.endswith(":") and mk == cand) for cand in KEY_NORM[o])) or
                (o in COMPOUND_INTERNAL and mk == o + ":")
                for o in outline)
            if not consumed:
                notes.append("提示：MOUNTS[%s] 登记「%s」，但 %s 未直接消费（可能由解析层/固定元件消费，人工核对）"
                             % (layout, mk, fn))

    if dump:
        print("\n".join(all_dump))
        return 0

    print("==== 3c-1 双向 guard：引擎消费字段 ⊆ MOUNTS ====")
    if fails:
        print("\n".join("  [FAIL] " + f for f in fails))
        print("共 %d 处不一致 —— 引擎消费了 MOUNTS 未登记的字段。修正：补 MOUNTS 或改引擎。" % len(fails))
    else:
        print("  正向（引擎消费 ⊆ MOUNTS）：全部通过，无缺漏。")
    if notes:
        print("\n反向清单（不阻断，人工核对）：")
        print("\n".join("  " + n for n in notes))
    print("\n覆盖版式：%d / 28" % len([1 for L in LAYOUT_FN if LAYOUT_FN[L] in fn_defs]))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
