# -*- coding: utf-8 -*-
# _defaults.py —— eink-deck 引擎内「默认路径」的单一真相源
#
# 背景：golden_check.py 与 render_baseline.py 都要定位「实纲目录」（作者本地回归用的
#       大纲样本，不随技能分发）。此处默认留空（None），由 `--outlines` 或环境变量
#       EINK_OUTLINES_DIR 覆盖；两者皆空时，两个脚本的「实纲」检查项自动跳过
#       （不崩、不计入失败）。
#
# 【多系列】实纲目录可以有多个——武脉千年一套、别的系列另一套，各占一个目录。写法：
#   · 环境变量：EINK_OUTLINES_DIR=D:\A\PPT制作;D:\B\PPT制作（Windows 分号，POSIX 冒号）
#   · 命令行  ：--outlines D:\A\PPT制作 --outlines D:\B\PPT制作（可重复，亦可分隔符分隔）
#   两者可混用，按出现顺序去重；不写死任何一台机器的路径。
#
# 本文件只放**跨脚本共享**的默认路径与解析规则，不放任何引擎渲染逻辑。
# 解析优先级：`--outlines` > 环境变量 `EINK_OUTLINES_DIR` > 内置默认。

import os
import sys

# 实纲目录（作者本地回归样本，不随技能分发；由 EINK_OUTLINES_DIR / --outlines 覆盖）
DEFAULT_OUTLINES_DIR = None

# 环境变量名（跨机/跨工作区覆盖用，不必改代码）
OUTLINES_ENV = "EINK_OUTLINES_DIR"

# 命令行标记
OUTLINES_FLAG = "--outlines"


def cli_value(flag, argv=None):
    """取 `--flag <值>` 的值（引擎脚本惯用的轻量参数解析，不想为每个开关上 argparse）。"""
    argv = list(sys.argv[1:]) if argv is None else list(argv)
    if flag in argv:
        i = argv.index(flag)
        if i + 1 < len(argv):
            return argv[i + 1]
    return None


def cli_values(flag, argv=None):
    """取 `--flag <值>` 的全部出现（同一开关可重复传入）。"""
    argv = list(sys.argv[1:]) if argv is None else list(argv)
    out = []
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            out.append(argv[i + 1])
    return out


def resolve_outlines_dirs(extra=None):
    """解析实纲目录列表：`--outlines`（可重复，或分隔符分隔） > 环境变量 > 内置默认。

    返回去重后的目录列表；空列表表示未配置，调用方各自跳过该检查项。
    """
    raw = list(cli_values(OUTLINES_FLAG))
    if extra:
        raw.append(extra)
    if not raw:
        env = os.environ.get(OUTLINES_ENV, "").strip()
        if env:
            raw.append(env)
        elif DEFAULT_OUTLINES_DIR:
            raw.append(DEFAULT_OUTLINES_DIR)
    dirs = []
    for item in raw:
        for d in item.split(os.pathsep):
            d = d.strip().strip('"').strip("'")
            if d and d not in dirs:
                dirs.append(d)
    return dirs
