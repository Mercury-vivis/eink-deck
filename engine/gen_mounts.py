# -*- coding: utf-8 -*-
"""gen_mounts.py —— 3c-3 路线 A：MOUNTS + LAYOUT_TYPES 生成器（声明 → 派生物）
=====================================================================
唯一真相源：
  · MOUNTS —— `_eink_template.py` 各 p_* 函数头部的 `_MOUNT = {...}` 声明。
  · LAYOUT_TYPES —— `render_outline.py` 的 `LAYOUT_MAP`（版式码 → type 的 parse 层真源）。
本脚本扫描 28 个版式对应的渲染函数，读取 _MOUNT，并从 render_outline 取 LAYOUT_MAP，
生成 `_generated_mounts.py`（MOUNTS + LAYOUT_TYPES 派生物，禁手改）。
注册表 `syntax_registry.py` 直接 import 该派生物 —— 改字段 = 改声明/LAYOUT_MAP →
重跑本脚本。

用法：
    python gen_mounts.py           # 从声明生成 _generated_mounts.py（覆盖写）
    python gen_mounts.py --check   # 校验磁盘派生物与声明一致（不一致 exit 1）
"""
import ast
import io
import os
import sys

ENGINE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ENGINE)
import syntax_registry as REG
import _eink_template as TPL
import render_outline as RO

TPL_SRC = os.path.join(ENGINE, "_eink_template.py")
OUT = os.path.join(ENGINE, "_generated_mounts.py")


def extract_mounts():
    """扫描全部 p_* 的 _MOUNT 声明 → {函数名: set}。缺声明即报错（fail 设计）。"""
    src = io.open(TPL_SRC, encoding="utf-8").read()
    tree = ast.parse(src)
    decls = {}
    missing = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("p_"):
            continue
        for st in node.body:
            if isinstance(st, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "_MOUNT" for t in st.targets):
                vals = set()
                if isinstance(st.value, (ast.Set, ast.List, ast.Tuple)):
                    for el in st.value.elts:
                        if isinstance(el, ast.Constant) and isinstance(el.value, str):
                            vals.add(el.value)
                        else:
                            missing.append("%s：_MOUNT 含非字符串元素 %s" % (node.name, ast.unparse(el)))
                decls[node.name] = vals
                break
    return decls, missing


def build_mounts():
    """按 render_outline.LAYOUT_MAP（parse 层真源 Lxx → type）→ _PRIMITIVES（type → p_*）
    生成 MOUNTS。直读真源，不再经派生值 REG.LAYOUTS[type]——消除生成器内部"render 段读
    真源、build 段读派生值"的两源并用（2026-09-15 阶段X 收尾）。"""
    decls, missing = extract_mounts()
    if missing:
        print("[gen_mounts] ✗ 声明异常：%s" % "; ".join(missing))
        sys.exit(1)
    mounts = {}
    no_decl = []
    for layout in sorted(RO.LAYOUT_MAP, key=lambda x: (len(x), x)):
        ltype = RO.LAYOUT_MAP[layout]
        fn = TPL._PRIMITIVES[ltype][0].__name__
        if fn not in decls:
            no_decl.append("%s(%s→%s)" % (layout, ltype, fn))
            continue
        mounts[layout] = sorted(decls[fn])
    if no_decl:
        print("[gen_mounts] ✗ 以下版式对应函数缺 _MOUNT 声明：%s" % ", ".join(no_decl))
        sys.exit(1)
    return mounts


def render(mounts):
    lines = [
        "# -*- coding: utf-8 -*-",
        '"""由 gen_mounts.py 自动生成 —— MOUNTS + LAYOUT_TYPES 派生物（引擎声明 → 注册表）。',
        "禁止手改：改 MOUNTS 请改 _eink_template.py 对应 p_* 函数头部的 _MOUNT 声明；",
        "改 LAYOUT_TYPES 请改 render_outline.py 的 LAYOUT_MAP；",
        '然后重跑 python gen_mounts.py。"""',
        "MOUNTS = {",
    ]
    for layout in sorted(mounts, key=lambda x: (len(x), x)):
        vals = ", ".join('"%s"' % v for v in mounts[layout])
        lines.append('    "%s": {%s},' % (layout, vals))
    lines.append("}")
    lines.append("")
    lines.append("# 版式码 → type（真源：render_outline.LAYOUT_MAP；按 LAYOUT_MAP 原序）")
    lines.append("LAYOUT_TYPES = {")
    for code in RO.LAYOUT_MAP:
        lines.append('    "%s": "%s",' % (code, RO.LAYOUT_MAP[code]))
    lines.append("}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    mounts = build_mounts()
    new = render(mounts)
    if "--check" in argv:
        if not os.path.exists(OUT):
            print("[gen_mounts] ✗ 派生物不存在，先运行 python gen_mounts.py")
            return 1
        cur = io.open(OUT, encoding="utf-8").read()
        if cur == new:
            print("[gen_mounts] ✓ 派生物与声明一致（%d 版式）" % len(mounts))
            return 0
        print("[gen_mounts] ✗ 派生物过期 —— 声明已变，运行 python gen_mounts.py 重新生成")
        return 1
    io.open(OUT, "w", encoding="utf-8", newline="").write(new)
    print("[gen_mounts] ✓ 已生成 _generated_mounts.py（MOUNTS + LAYOUT_TYPES，%d 版式）—— 禁手改，改动走 p_* 声明 / render_outline.LAYOUT_MAP" % len(mounts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
