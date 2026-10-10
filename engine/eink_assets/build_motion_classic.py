# -*- coding: utf-8 -*-
"""build_motion_classic.py —— 把 ESM 版 Motion One 编译成 classic script（window.motion）
=================================================================================

背景（2026-09-27 老陈裁定「改 classic script 根治」）
----------------------------------------------------
引擎原先用 ES module 动态 import 加载动效库：

    motion = await import('./assets/motion.min.js');

浏览器以 file:// 直接打开产物时，动态 import 被 CORS 拦掉 → 整段动效初始化
（入场动画 / 数字递增 / M10 分步）静默失效，只剩静态原值，排查成本极高。
classic `<script src>` 不受此限制（lucide.umd.min.js 早就是这么加载的），
因此把动效库也改成 classic 加载方式，file:// 与 http:// 行为完全一致。

本脚本做的事
------------
  1. 读 ESM 源文件 motion.source.esm.js（Motion One 官方 rollup 产物，纯 ESM）；
  2. 解析末尾 `export{local as name, ...}` 导出组与 `export default null;`；
  3. 剥掉这些 ESM 语法，在末尾按导出映射挂 window.motion；
  4. 写回 motion.min.js（**产物路径不变**，build() 拷贝与打包器锚点都不用改）；
  5. 用 node --check 做语法闸门，失败即中止，绝不产出坏包。

升级 Motion One 时
------------------
  换掉 motion.source.esm.js（或覆盖后重跑本脚本）即可，无需手改产物。

用法
----
    python build_motion_classic.py           # 同级目录下 motion.source.esm.js → motion.min.js
退出码：0 = 成功；1 = 失败（源缺失 / 未找到导出 / 语法闸门不过）。
"""
import io
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
SRC_ESM = os.path.join(_HERE, "motion.source.esm.js")
OUT = os.path.join(_HERE, "motion.min.js")

_HEADER = ("/* motion.min.js —— Motion One classic build（由 build_motion_classic.py 生成）\n"
           "   ESM 源见 motion.source.esm.js；本文件挂 window.motion，供 <script src> 直接加载。\n"
           "   勿手改本文件：改完下次重跑生成脚本会被覆盖。 */\n"
           "'use strict';\n")


def _fail(msg):
    print("[motion] [错误] %s" % msg)
    sys.exit(1)


def parse_exports(src):
    """返回 (导出映射 list[(name, local)], 去 ESM 语法后的源码)。"""
    pairs = []
    for grp in re.findall(r"export\s*\{([^}]*)\}", src):
        for item in grp.split(","):
            item = item.strip()
            if not item:
                continue
            if " as " in item:
                local, name = [x.strip() for x in item.split(" as ", 1)]
            else:
                local = name = item
            pairs.append((name, local))
    body = re.sub(r"export\s*\{[^}]*\}\s*;?", "", src)
    body = re.sub(r"export\s+default\s+[^;\n]*;?", "", body)
    return pairs, body


def node_check(path):
    """用 node --check 验语法（classic script 语义）。node 不可用时跳过并告警，不阻断。"""
    node = os.environ.get("EINK_NODE") or shutil_which_node()
    if not node:
        print("[motion] 未找到 node，跳过语法闸门（建议装 node 后重跑以加固）")
        return True
    r = subprocess.run([node, "--check", path], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0:
        print((r.stdout or "") + (r.stderr or ""))
        return False
    return True


def shutil_which_node():
    for cand in ("node.exe", "node", "node.cmd"):
        from shutil import which
        p = which(cand)
        if p:
            return p
    return None


def main():
    if not os.path.exists(SRC_ESM):
        _fail("缺少 ESM 源：%s" % SRC_ESM)
    src = io.open(SRC_ESM, "r", encoding="utf-8").read()
    pairs, body = parse_exports(src)
    if not pairs:
        _fail("源里没找到 export{} 导出组——Motion One 版本变了？检查 %s" % SRC_ESM)
    mapping = "".join("\nwindow.motion.%s = %s;" % (n, l) for n, l in pairs)
    out = _HEADER + body + "\n/* ---- eink-deck 挂载（classic 版独有）---- */\n" \
        + "window.motion = window.motion || {};" + mapping + "\n"
    if "</script>" in out:   # 防御：脚本里出现字面 </script> 会被 HTML 解析器截断
        _fail("生成的脚本里含 </script> 字面量，内联进 HTML 会截断——请勿手改源文件")
    io.open(OUT, "w", encoding="utf-8").write(out)
    print("[motion] 已生成 %s（%d 字节，导出 %d 项）" % (OUT, len(out.encode("utf-8")), len(pairs)))
    if not node_check(OUT):
        os.remove(OUT)
        _fail("语法闸门未过，已删除产物 %s" % OUT)
    print("[motion] 语法闸门通过（node --check）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
