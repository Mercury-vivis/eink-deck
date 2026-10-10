# -*- coding: utf-8 -*-
"""render_baseline.py —— 3c-2 行为零变化判据：渲染产物 sha256 基线
=============================================================
渲染示例大纲 + 16 讲 → HTML，记每个产物的 sha256 到 baseline.json。
3c-2 每步清理后重跑 --check：产物必须逐字节不变，任何 diff 即失败。

用法：
    python render_baseline.py            # 建基线（渲染全部，写 baseline.json）
    python render_baseline.py --check    # 重渲比对（0=零变化；1=有 diff）
    python render_baseline.py --update   # 重渲并覆盖基线（确认行为变化是预期时）
    python render_baseline.py --outlines <目录>   # 覆盖 16 讲实纲目录（亦可用环境变量 EINK_OUTLINES_DIR）

16 讲实纲目录的默认路径收编于同目录 _defaults.py（与 golden_check.py 同源），
两脚本都靠 resolve_outlines_dir() 解析，不再各自写死本机路径。
"""
import hashlib
import json
import os
import subprocess
import sys

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
EINK_DIR = os.path.dirname(ENGINE_DIR)
EX = os.path.join(ENGINE_DIR, "generated", "示例大纲.md")
from _defaults import OUTLINES_FLAG, cli_value, resolve_outlines_dir  # noqa: E402
OUTLINES_DIR = resolve_outlines_dir(cli_value(OUTLINES_FLAG))
RENDER = os.path.join(ENGINE_DIR, "render_outline.py")
BASELINE = os.path.join(ENGINE_DIR, "_baseline_renders.json")
TMP_ROOT = os.path.join(os.environ.get("TEMP", r"C:\Windows\Temp"), "eink_render_baseline")


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def render_one(outline, out_dir):
    r = subprocess.run([sys.executable, RENDER, outline, out_dir],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def collect_html(out_dir):
    """收集输出目录下全部 .html 的 (相对路径, sha256)。"""
    out = {}
    if not os.path.isdir(out_dir):
        return out
    for root, dirs, files in os.walk(out_dir):
        for fn in files:
            if fn.endswith(".html"):
                p = os.path.join(root, fn)
                rel = os.path.relpath(p, out_dir)
                out[rel] = sha256_file(p)
    return out


def targets():
    t = [("示例大纲", EX)]
    if OUTLINES_DIR and os.path.isdir(OUTLINES_DIR):
        for fn in sorted(os.listdir(OUTLINES_DIR)):
            if fn.endswith(".md") and "大纲" in fn:
                t.append((os.path.splitext(fn)[0], os.path.join(OUTLINES_DIR, fn)))
    return t


def build():
    os.makedirs(TMP_ROOT, exist_ok=True)
    result, fails = {}, []
    for name, outline in targets():
        out_dir = os.path.join(TMP_ROOT, name + "_eink")
        code, out = render_one(outline, out_dir)
        if code != 0:
            fails.append((name, out[-300:]))
            continue
        result[name] = collect_html(out_dir)
    with open(BASELINE, "w", encoding="utf-8") as f:
        json.dump({"count": len(result), "renders": result}, f, ensure_ascii=False, indent=1)
    if fails:
        for n, o in fails:
            print("[baseline] ✗ %s 渲染失败：%s" % (n, o))
        print("[baseline] 基线写入但含失败项：%d 成功 / %d 失败" % (len(result), len(fails)))
        return 1
    total = sum(len(v) for v in result.values())
    print("[baseline] 基线建立：%d 份大纲 / %d 个 HTML / sha256 清单 → %s"
          % (len(result), total, BASELINE))
    return 0


def check():
    if not os.path.exists(BASELINE):
        print("[baseline] 无基线文件，先运行 python render_baseline.py")
        return 1
    with open(BASELINE, encoding="utf-8") as f:
        base = json.load(f)["renders"]
    diffs = []
    for name, outline in targets():
        out_dir = os.path.join(TMP_ROOT, name + "_eink")
        code, out = render_one(outline, out_dir)
        if code != 0:
            diffs.append("%s：渲染失败" % name)
            continue
        cur = collect_html(out_dir)
        old = base.get(name, {})
        for rel in sorted(set(old) | set(cur)):
            if old.get(rel) != cur.get(rel):
                diffs.append("%s/%s：sha256 变化\n    旧 %s\n    新 %s" % (name, rel, old.get(rel, "-"), cur.get(rel, "-")))
    if diffs:
        print("[baseline] ✗ 行为变化（%d 处）：" % len(diffs))
        for d in diffs:
            print("  " + d)
        print("[baseline] 3c-2 违反「行为零变化」。回滚或修正后重跑；确属预期变化用 --update 覆盖基线。")
        return 1
    print("[baseline] 全部 %d 份大纲产物逐字节一致，行为零变化 ✓" % len(targets()))
    return 0


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(check())
    sys.exit(build())
