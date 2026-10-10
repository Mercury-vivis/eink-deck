# -*- coding: utf-8 -*-
# _defaults.py —— eink-deck 引擎内「默认路径」的单一真相源
#
# 背景：golden_check.py 与 render_baseline.py 都要定位「16 讲实纲目录」，
#       该目录是作者本地回归用的实纲样本，不随技能分发。为避免写死本机路径
#       在他人机器上直接不存在、且复制即漂移，此处默认留空（None），
#       由环境变量 EINK_OUTLINES_DIR 或 --outlines 显式覆盖；两者皆空时，
#       golden_check.py 与 render_baseline.py 的 16 讲检查项自动跳过（不崩、不计入失败）。
#
# 本文件只放**跨脚本共享**的默认路径与解析规则，不放任何引擎渲染逻辑。
# 解析优先级：`--outlines <dir>` > 环境变量 `EINK_OUTLINES_DIR` > 内置默认。

import os
import sys

# 16 讲实纲所在目录（作者本地回归样本，不随技能分发；由 EINK_OUTLINES_DIR / --outlines 覆盖）
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


def resolve_outlines_dir(cli_value_override=None):
    """解析 16 讲实纲目录：显式参数 > 环境变量 > 内置默认。"""
    if cli_value_override:
        return cli_value_override
    env = os.environ.get(OUTLINES_ENV, "").strip()
    if env:
        return env
    return DEFAULT_OUTLINES_DIR
