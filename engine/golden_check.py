# -*- coding: utf-8 -*-
"""golden_check.py —— golden test 门禁（一期）
================================================
回归门：语法正确性的「照抄样本 + 机器校验」双通道之二（机器校验侧）。

检查项：
  1. 示例大纲（28 页全版式） lint --strict 0 错误 0 警告；
  2. 示例大纲渲染成功，校验行全绿（svg/figure 平衡、无连续 3 同色、emoji 0）；
  3. 16 讲实纲 lint --strict 0 错误 0 警告。

用法：
    python golden_check.py [--skip-render]   （--skip-render：跳过渲染检查，只跑 lint）
    python golden_check.py --outlines <目录> （覆盖 16 讲实纲目录；亦可用环境变量 EINK_OUTLINES_DIR）
退出码：0 = 全过；1 = 有失败。

16 讲实纲目录的默认路径收编于同目录 _defaults.py（与 render_baseline.py 同源），
不再在此写死——写死既易与基线脚本分叉，也会在另一台机上直接找不到目录。
"""
import os
import re
import subprocess
import sys

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
EINK_DIR = os.path.dirname(ENGINE_DIR)
EX = os.path.join(EINK_DIR, "engine", "generated", "示例大纲.md")
from _defaults import OUTLINES_FLAG, cli_value, resolve_outlines_dir  # noqa: E402
OUTLINES_DIR = resolve_outlines_dir(cli_value(OUTLINES_FLAG))
RENDER_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_golden_render")

LINT = os.path.join(ENGINE_DIR, "lint_outline.py")
RENDER = os.path.join(ENGINE_DIR, "render_outline.py")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    skip_render = "--skip-render" in sys.argv
    fails = []

    # 1. 示例大纲 lint --strict
    code, out = run([sys.executable, LINT, EX, "--strict"])
    ok = code == 0 and "0 警告" in out
    print("[golden] 示例大纲 lint --strict:", "PASS" if ok else "FAIL")
    if not ok:
        fails.append("示例大纲 lint")
        print(out[-1200:])

    # 2. 示例大纲渲染
    if not skip_render:
        code, out = run([sys.executable, RENDER, EX, RENDER_OUT])
        m = re.search(r"校验：\s*(\{.*\})", out)
        ok = code == 0 and m and '"svg平衡": [3, 3]' in m.group(1) and '"figure平衡": [6, 6]' in m.group(1) \
             and '"连续3同色": "无"' in m.group(1) and '"emoji": 0' in m.group(1)
        print("[golden] 示例大纲渲染:", "PASS" if ok else "FAIL")
        if not ok:
            fails.append("示例大纲渲染")
            print(out[-1200:])

    # 3. 16 讲 lint --strict（未配置目录则跳过，不计入失败）
    if not OUTLINES_DIR or not os.path.isdir(OUTLINES_DIR):
        print("[golden] 16 讲 lint --strict: SKIP（未配置目录；设 EINK_OUTLINES_DIR 或 --outlines 启用）")
    else:
        bad = []
        for fn in sorted(os.listdir(OUTLINES_DIR)):
            if fn.endswith(".md") and "大纲" in fn:
                p = os.path.join(OUTLINES_DIR, fn)
                code, out = run([sys.executable, LINT, p, "--strict"])
                if code != 0:
                    bad.append((fn, out[-400:]))
        print("[golden] 16 讲 lint --strict:", "PASS（%d 份全绿）" % len(bad) if not bad else "FAIL")
        if bad:
            fails.append("16 讲 lint")
            for fn, o in bad:
                print("  ✗ %s\n%s" % (fn, o))

    if fails:
        print("\n[golden] 失败项：%s" % "、".join(fails))
        return 1
    print("\n[golden] 全部通过：示例大纲（lint+渲染）+ 16 讲（lint）零回归。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
