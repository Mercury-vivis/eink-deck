# -*- coding: utf-8 -*-
"""
下载 eink-deck 离线字体所需的源字体（完整可变 TTF）：Noto Serif SC / Noto Sans SC（中文）＋ Playfair Display / Source Serif 4（西文，2026-09-09 打包交付新增）。

用途
----
引擎的「离线字体开关」（大纲 `字体源: 本地` / `字体: 本地` / CLI `--offline-fonts` /
profile `字体源: 本地`）会在*构建期*把本 deck 实际用到的中文字符从本地源字体切出子集、
base64 内嵌进 index.html，使产物自包含、断网也不豆腐块。

本脚本只需在**构建机**上跑一次，把源字体下载到缓存目录。下载下来的源文件**不进产物**，
只用于切子集；交付的 index.html 自带子集，无需这些源文件。

用法
----
    python get_fonts.py
    EINK_FONT_DIR=/path/to/cache python get_fonts.py     # 指定缓存目录

默认缓存目录：~/.workbuddy/eink-font-cache/
（引擎 _build_offline_font_css 读取同一目录，可用环境变量 EINK_FONT_DIR 改。）

依赖：仅标准库（urllib）。无需联网以外的第三方包。
下载来源：google/fonts 仓库的官方可变 TTF（raw.githubusercontent.com）。
  注：Google Fonts css2 对中文是按 unicode-range 切成上百个小切片分发的，取首个 URL 只能
  拿到拉丁基本区；因此这里直接从字体源仓库取「完整可变 TTF」，由 fonttools 在构建期按需切子集。
"""
import os
import re
import ssl
import sys
import urllib.request

DEFAULT_DIR = os.path.join(os.path.expanduser("~"), ".workbuddy", "eink-font-cache")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# family -> (源 URL, 输出文件名)
# 源：google/fonts 仓库 ofl 目录下的可变 TTF（方括号需 URL 编码为 %5B / %5D）
FONTS = {
    "Noto Serif SC": (
        "https://raw.githubusercontent.com/google/fonts/main/ofl/notoserifsc/NotoSerifSC%5Bwght%5D.ttf",
        "NotoSerifSC.ttf",
    ),
    "Noto Sans SC": (
        "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf",
        "NotoSansSC.ttf",
    ),
    # 西文字族（2026-09-09 打包交付新增）：打包器按 deck 用字切子集内嵌，
    # 使交付稿断网时西文标题/数字观感与在线一致（缺缓存则打包时回退 CDN 链接并告警）。
    "Playfair Display": (
        "https://raw.githubusercontent.com/google/fonts/main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
        "PlayfairDisplay.ttf",
    ),
    "Source Serif 4": (
        "https://raw.githubusercontent.com/google/fonts/main/ofl/sourceserif4/SourceSerif4%5Bopsz,wght%5D.ttf",
        "SourceSerif4.ttf",
    ),
}


def _ssl_context():
    """返回一个正确校验证书链的 SSL 上下文。

    优先用 certifi 的 CA 包（覆盖部分缺少系统根证书库的 Windows Python）；
    否则回落到 Python 自带的系统根证书上下文（同样会校验主机名与证书链）。
    任何情况下都不关闭证书校验——关闭校验会让字体下载可被中间人投毒（MITM）。
    若构建机确实缺根证书库，正确做法是 `pip install certifi`，而非降级为不校验。
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _fetch_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    # 始终走证书校验开启的上下文；缺根证书时给出明确指引而非静默降级
    try:
        with urllib.request.urlopen(req, timeout=180, context=_ssl_context()) as r:
            return r.read()
    except Exception as e:
        raise IOError(
            "字体下载失败（已启用证书校验）。若报证书错误，请在构建机安装 certifi："
            "pip install certifi；原始错误：%s" % e
        )


def main():
    out_dir = os.environ.get("EINK_FONT_DIR", DEFAULT_DIR)
    os.makedirs(out_dir, exist_ok=True)
    print("字体缓存目录：%s" % out_dir)
    for family, (url, fname) in FONTS.items():
        print("\n== %s ==" % family)
        print("  源：%s" % url)
        try:
            data = _fetch_bytes(url)
        except Exception as e:
            print("  [失败] 下载失败：%s" % e)
            continue
        if data[:4] not in (b"\x00\x01\x00\x00", b"wOF2", b"wOFF"):
            print("  [失败] 返回内容不是字体文件（sig=%r），疑似被拦截" % data[:4])
            continue
        dst = os.path.join(out_dir, fname)
        with open(dst, "wb") as f:
            f.write(data)
        print("  已保存：%s（%.2f MB）" % (dst, len(data) / 1024 / 1024))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已中断", file=sys.stderr)
        raise
