# -*- coding: utf-8 -*-
"""gen_syntax_docs.py —— 文档生成器（一期：语法文档全部由注册表生成）
====================================================================
从 syntax_registry.py 生成一份人读文档：

  generated/语法速查.md       —— 元数据 / 页面级键 / 模块字段 / 复合键 / 版式 / 枚举 / 行内标记 / 挂载矩阵

设计原则（用户已确认）：
  · 引擎代码是唯一真相源，注册表是其显式化；人读文档是【生成物】，机器不读；
  · 生成物头部标注「机器生成 · 勿手改」——改语法只改引擎 + 注册表，再重跑本生成器；
  · 生成器全面：凡注册表登记的 ACTIVE 项一律输出，DEPRECATED 仅以「已废弃」脚注出现，DEAD 不输出。

用法：
    python gen_syntax_docs.py
输出目录：本文件同目录 generated/（不存在自动创建）。
"""
import os
import sys
from datetime import datetime

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ENGINE_DIR, "generated")
sys.path.insert(0, ENGINE_DIR)

# L27 配图建议（2026-09-15 用户实测校准：2.8:1–3.8:1，文档生成器统一口径）
L27_IMAGE_RATIO_ADVICE = "2.8:1 ～ 3.8:1（横宽幅；过窄/过宽会导致图区异常高或异常扁，破坏版面）"

HEADER = (
    "> **机器生成 · 勿手改**：本文件由 `engine/gen_syntax_docs.py` 从 `engine/syntax_registry.py` 生成。\n"
    "> 改语法 = 改引擎 + 注册表，然后重跑生成器；任何手改都会被下次生成覆盖。\n"
)

def _ver_stamp(reg):
    return HEADER


def _status_mark(st):
    return "" if st == "ACTIVE" else ("（已废弃，仅兼容）" if st == "DEPRECATED" else "（引擎残留）")


def gen_syntax_cheatsheet(reg):
    L = []
    L.append("# eink 大纲语法速查（注册表生成）\n")
    L.append(_ver_stamp(reg))
    L.append("> 生成于 %s。\n" % datetime.now().strftime("%Y-%m-%d %H:%M"))

    # 1. 顶部元数据
    L.append("## 1. 顶部元数据（文件最顶，必填 4 项）\n")
    L.append("| 键 | 必填 | 说明 | 取值约束 |")
    L.append("|---|---|---|---|")
    for k, v in reg.META_KEYS.items():
        if v["status"] == "DEAD":
            continue
        req = "✔" if v.get("required") else "—"
        note = v["semantics"] + _status_mark(v["status"])
        L.append("| `%s` | %s | %s | %s |" % (k, req, note, v.get("constraint", "") or "—"))

    # 2. 页面级键
    L.append("\n## 2. 页面级键（`- 键: 值`）\n")
    L.append("| 键 | 说明 | 版式范围 | 硬约束 |")
    L.append("|---|---|---|---|")
    for k, v in reg.PAGE_KEYS.items():
        if v["status"] == "DEAD":
            continue
        lks = "、".join(v["layouts"]) if v.get("layouts") else "任意"
        L.append("| `%s` | %s%s | %s | %s |" % (k, v["semantics"], _status_mark(v["status"]), lks,
                                               (v.get("constraint") or "—").replace("\n", " ")))

    # 3. 模块字段
    L.append("\n## 3. 模块字段（M01–M16）\n")
    for m, v in reg.MODULE_FIELDS.items():
        note = v.get("note", "")
        ctrl = v.get("controls", "")
        fields = v.get("fields", {})
        L.append("### %s %s%s\n" % (m, v["desc"], (" —— " + note) if note else ""))
        if ctrl:
            L.append("三控：%s\n" % ctrl)
        if fields:
            L.append("| 子字段 | 说明 |")
            L.append("|---|---|")
            for sub, sem in fields.items():
                L.append("| `%s` | %s |" % (sub or "（裸值）", sem))
        L.append("")

    # 4. 复合键
    L.append("\n## 4. 复合键（空值 + 缩进子项）\n")
    L.append("> 🟥 引擎只认**空值 + 缩进子项**；主行带值或被静默忽略（lint 已拦截）。子项必须 `- 子键=值` 前缀。\n")
    for k, v in reg.COMPOUND_KEYS.items():
        lks = "、".join(v["layouts"])
        subs = "；".join("`%s`=%s" % (s, sem) for s, sem in v["subitems"].items())
        L.append("- **`%s:`**（%s）。子项：%s。规则：%s"
                 % (k, lks, subs, v["rule"]))

    # 5. 版式
    L.append("\n## 5. 版式注册（28 选 1）\n")
    L.append("| 版式 | 名称 | 主字段 | 硬约束 |")
    L.append("|---|---|---|---|")
    for code in sorted(reg.LAYOUTS.keys(), key=lambda c: (len(c), c)):
        v = reg.LAYOUTS[code]
        L.append("| `%s` | %s | %s | %s |" % (code, v["name"], "、".join(v["primary"]),
                                             v.get("constraint", "—")))
    L.append("\n> L27 配图建议：%s\n" % L27_IMAGE_RATIO_ADVICE)
    L.append("> - fit 模式：图区高度 = 屏宽 ÷ 图片真实宽高比（引擎读图片文件头计算，不依赖 PIL）。")
    L.append("> - contain/fit 为信息图模式：标题默认落下方纸色区，零遮挡；cover 为装饰图模式：标题悬浮。")

    # 6. 枚举
    L.append("\n## 6. 取值枚举\n")
    for k, vals in reg.ENUMS.items():
        L.append("- **%s**：`%s`" % (k, "` / `".join(vals)))
    L.append("")

    # 7. 行内标记
    L.append("\n## 7. 行内标记（M10 正文内）\n")
    for k, v in reg.INLINE_MARKS.items():
        L.append("- **`%s`**：%s" % (k, v["semantics"]))

    # 8. 斜杠规则
    L.append("\n## 8. 斜杠规则\n")
    L.append("- %s" % reg.SLASH_RULE["semantics"])
    L.append("")

    # 9. 版式挂载矩阵（MOUNTS 真相源；2026-09-15 阶段1 并入速查，原独立文档删除）
    L.append("\n## 9. 版式挂载矩阵（可挂内容字段）\n")
    L.append("> 真相源：`syntax_registry.MOUNTS`（渲染层版式原语实际消费的字段；解析层全透传）。\n")
    L.append("> 通用元件（M01/M03/M05/M11/M13/M14/M16/强调/data_animate/纵向/规则线/各模块三控）全版式可挂，不在矩阵内。\n")
    L.append("> M10 正文全部版式可挂：BODY_NATIVE 原生渲染，其余版式补挂 body-fixed（L24–L27 已补渲染，2026-09-15 阶段2）。\n")
    L.append("> `svg:` / `svg_cap:` 全版式可挂（底部通用图位）：L05/L11/L12 原生 figure 图位；"
             "L21/L22 引擎自绘禁挂（lint 拦截）；L12b 与 svg: 同页静默丢图。例外集：%s。\n"
             % "、".join(sorted(reg.SVG_MOUNT_EXCEPT)))
    L.append("| 版式 | 名称 | 可挂内容字段 |")
    L.append("|---|---|---|")
    for code in sorted(reg.LAYOUTS.keys(), key=lambda c: (len(c), c)):
        fields = "、".join("`%s`" % f for f in sorted(reg.MOUNTS.get(code, set())))
        L.append("| `%s` | %s | %s |" % (code, reg.LAYOUTS[code]["name"], fields or "—"))
    L.append("")
    return "\n".join(L)


def main():
    import syntax_registry as reg
    os.makedirs(OUT_DIR, exist_ok=True)
    files = {
        "语法速查.md": gen_syntax_cheatsheet(reg),
    }
    for name, content in files.items():
        p = os.path.join(OUT_DIR, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        print("[gen] %s —— %d 行" % (p, content.count("\n") + 1))
    print("[gen] 全部生成完毕。改语法 = 改引擎 + 注册表 → 重跑本生成器。")


if __name__ == "__main__":
    main()
