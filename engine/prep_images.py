# -*- coding: utf-8 -*-
"""prep_images.py —— 配图预处理（渲染**前**的可选步骤）：压体积 / 缩长边 / 统一 WebP
================================================================================

为什么存在
----------
打包会把配图 base64 内嵌进单文件（膨胀约 33%），图越大交付稿越臃肿。
实测同一张 1080×1410 文物图：PNG 2.9MB → **WebP q80 336KB**，且**完整保留 alpha**；
而转 JPEG（431KB）既丢透明又更大——所以**统一转 WebP，别转 JPEG**。

⚠️ 关键认知（2026-09-09 实测）：deck 背景是 **WebGL 流体双背景**（浅/深两套随明暗页
切换），**不是纯色**。所以透明区**不要填成实色**去"融入背景"——填任何单色都只是近似、
仍露矩形边界；正确做法是**保留透明**（WebP 支持 alpha），让图自然融进动态背景。

做什么
------
1. **缩长边**：长边 > `--max-edge`（默认 1920）才等比缩小，只缩不放、不拉伸、不裁内容；
2. **可选去白边** `--trim`：自动裁掉四周纯色边框（按左上角像素判定）；
3. **统一转 WebP 并压体积**：照片类 WebP q80（默认）；颜色数 ≤256 的线条/图标类自动
   走 WebP 无损（保锐利），若无损反而更大则自动退回 q80；
4. **同名同目录、只换扩展名**：`a.png` → `a.webp`，**原文件保留不动**；
5. **只报不改**：脚本**绝不改大纲**，只在报告末尾列出需要同步修改的 `M12 文件:` 行。

用法
----
    python prep_images.py <图片文件或目录> [选项]

    --max-edge N     长边上限，默认 1920（一屏按 1920×1080 计，超过纯属浪费）
    --quality N      有损 WebP 质量，默认 80
    --trim           自动裁掉四周纯色边
    --dry-run        只出报告、不写文件（**建议先跑这个看收益**）
    --lossless       强制全部无损（线条图很多的场合）

输出示例
--------
    第2讲_P26_妇好钺.png   1080x1410  2951KB →  336KB  (-89%)  alpha保留  → 第2讲_P26_妇好钺.webp
    --------------------------------------------------
    共 1 张，节省 2615KB（88.6%）
    ⚠️ 需同步修改大纲（脚本不会替你改）：
       第2讲_大纲.md:323  images/第2讲_P26_妇好钺.png → images/第2讲_P26_妇好钺.webp

依赖
----
仅需 Pillow（`pip install Pillow`）。缺库会明确报出 python 路径，不会静默失败。
"""
import os
import sys

_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")


def _fail(msg):
    print("[配图][错误] %s" % msg)
    sys.exit(1)


def _warn(msg):
    print("[配图][警告] %s" % msg)


def _kb(n):
    return n / 1024.0


def _few_colors(im, limit=256):
    """颜色数是否 ≤ limit（线条图/图标/表格截图 → True；照片 → False）。"""
    try:
        cols = im.convert("RGBA").getcolors(maxcolors=limit + 1)
    except Exception:
        return False
    return cols is not None and len(cols) <= limit


def _trim_borders(im):
    """裁掉四周纯色边（按左上角像素当背景色）。失败则原样返回。"""
    try:
        from PIL import ImageChops
        rgb = im.convert("RGB")
        bg = rgb.getpixel((0, 0))
        diff = ImageChops.difference(rgb, rgb.new("RGB", rgb.size, bg))
        bbox = diff.getbbox()
        if bbox and ((bbox[2] - bbox[0]) < rgb.size[0] or (bbox[3] - bbox[1]) < rgb.size[1]):
            return im.crop(bbox)
    except Exception:
        pass
    return im


def _encode(im, lossless, quality):
    """编码成 WebP，返回 (字节串, 实际用的模式说明)。"""
    import io
    buf = io.BytesIO()
    if lossless:
        im.save(buf, "WEBP", lossless=True, method=6)
    else:
        im.save(buf, "WEBP", quality=quality, method=6)
    return buf.getvalue(), ("无损" if lossless else "q%d" % quality)


def _has_alpha(im):
    if im.mode in ("RGBA", "LA", "PA"):
        a = im.convert("RGBA").getchannel("A")
        return min(a.getextrema()) < 255
    return "transparency" in im.info


def _collect(target):
    if os.path.isfile(target):
        return [target] if target.lower().endswith(_SUFFIXES) else []
    out = []
    for root, _dirs, files in os.walk(target):
        for fn in files:
            if fn.lower().endswith(_SUFFIXES):
                out.append(os.path.join(root, fn))
    return out


def _md_hits(img_dir, stem, newname):
    """在图片目录及其父目录的 .md 里找引用了该图的大纲行，提示需同步修改。

    按**主干名**匹配（不论大纲里写的是 .png/.jpg/.jpeg），避免因为改过扩展名就漏提示。"""
    import re as _re
    # 必须匹配「主干名 + 已知扩展名」整体：光用 `stem in line` 会让短名误命中长名
    # （如 第12讲_P1 命中 第12讲_P11_野狐岭.png，替换却失败，报告出现"原文=改后"的假提示）
    pat = _re.compile(r"%s\.(png|jpg|jpeg|webp|bmp|tiff?)" % _re.escape(stem))
    hits = []
    roots = [img_dir, os.path.dirname(img_dir)]
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        try:
            names = [n for n in os.listdir(root) if n.lower().endswith(".md")]
        except Exception:
            continue
        for n in names:
            p = os.path.join(root, n)
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    for i, line in enumerate(f, 1):
                        # 只提示真正加载图的 `M12 文件:` 行——`M12 img_slot` 是占位框，不加载图
                        if "M12 文件" in line and pat.search(line):
                            fixed = pat.sub(newname, line.strip())
                            hits.append(("%s:%d  %s" % (n, i, line.strip()), fixed))
            except Exception:
                pass
    return hits


def main(argv):
    if not argv:
        print("用法: python prep_images.py <图片文件或目录> [--max-edge 1920] [--quality 80] "
              "[--trim] [--dry-run] [--lossless]")
        return 1

    target = argv[0]
    opts = argv[1:]

    def _opt(name, default):
        if name not in opts:
            return default
        i = opts.index(name)
        if i + 1 >= len(opts) or opts[i + 1].startswith("--"):
            _warn("%s 后缺数值参数，用默认 %s" % (name, default))
            return default
        try:
            return int(opts[i + 1])
        except ValueError:
            _warn("%s 参数非数字（%s），用默认 %s" % (name, opts[i + 1], default))
            return default

    max_edge = _opt("--max-edge", 1920)
    quality = _opt("--quality", 80)
    do_trim = "--trim" in opts
    dry = "--dry-run" in opts
    force_lossless = "--lossless" in opts

    if not os.path.exists(target):
        _fail("路径不存在：%s" % target)
    try:
        from PIL import Image
    except ImportError:
        _fail("本机 python 未装 Pillow（%s）——先 pip install Pillow 再跑" % sys.executable)

    files = _collect(target)
    if not files:
        _fail("没找到可处理的图片（支持 %s）" % "/".join(_SUFFIXES))

    print("=" * 78)
    print("目标   : %s（%d 张）" % (target, len(files)))
    print("长边≤  : %d    质量: %s    去白边: %s    模式: %s"
          % (max_edge, "无损" if force_lossless else "q%d" % quality,
             "是" if do_trim else "否", "只看报告" if dry else "写出文件"))
    print("=" * 78)

    total_old = total_new = 0
    done = 0
    need_md = []

    for path in files:
        name = os.path.basename(path)
        old_size = os.path.getsize(path)
        try:
            im = Image.open(path)
            im.load()
        except Exception as e:
            _warn("%s 无法打开，跳过（%s）" % (name, e))
            continue

        if getattr(im, "is_animated", False) and im.format == "GIF":
            print("  %-34s 动图，跳过（转 WebP 静图会丢动画）" % name)
            continue

        alpha = _has_alpha(im)
        im2 = im.convert("RGBA") if alpha else im.convert("RGB")

        resized = False
        w, h = im2.size
        if max(w, h) > max_edge:
            r = max_edge / float(max(w, h))
            im2 = im2.resize((max(1, int(w * r)), max(1, int(h * r))), Image.LANCZOS)
            resized = True
        if do_trim:
            im2 = _trim_borders(im2)

        # 已是 WebP 且无需缩放/去白边/无损强制时，跳过二次编码（避免重复有损劣化）
        if im.format == "WEBP" and not resized and not do_trim and not force_lossless:
            print("  %-34s 已是 WebP，跳过（无缩放/去白边）" % name)
            continue

        # 线条/图标类默认无损；无损反而更大则退回有损
        lossless = force_lossless or _few_colors(im2)
        data, mode = _encode(im2, lossless, quality)
        if lossless and not force_lossless and len(data) >= old_size:
            data, mode = _encode(im2, False, quality)

        new_size = len(data)
        new_path = os.path.splitext(path)[0] + ".webp"
        new_name = os.path.basename(new_path)

        if not dry:
            with open(new_path, "wb") as f:
                f.write(data)

        pct = (1 - new_size / float(old_size)) * 100 if old_size else 0
        flag = "✓" if new_size < old_size else "·"
        print("  %s %-32s %4dx%-4d %7.0fKB → %6.0fKB (%+5.1f%%)  %s  alpha%s  缩:%s"
              % (flag, name, im2.size[0], im2.size[1], _kb(old_size), _kb(new_size), -pct,
                 mode, "保留" if alpha else "无", "是" if resized else "否"))
        total_old += old_size
        total_new += new_size
        done += 1
        if new_size >= old_size:
            print("       └ 没变小（原图已够优或内容复杂），可继续用原图")
        # 用绝对路径算父目录：否则相对路径（images/a.png）的父目录会算错，找不到大纲
        for hit, fixed in _md_hits(os.path.dirname(os.path.abspath(path)),
                                   os.path.splitext(name)[0], new_name):
            need_md.append((hit, fixed))

    print("-" * 78)
    if dry:
        print("干跑（--dry-run）：未写入任何文件。预计 %d 张  %.0fKB → %.0fKB（省 %.0fKB / %.1f%%）"
              % (done, _kb(total_old), _kb(total_new), _kb(total_old - total_new),
                 (1 - total_new / float(total_old)) * 100 if total_old else 0))
    else:
        print("共 %d 张：%.0fKB → %.0fKB，节省 %.0fKB（%.1f%%）。原文件已保留。"
              % (done, _kb(total_old), _kb(total_new), _kb(total_old - total_new),
                 (1 - total_new / float(total_old)) * 100 if total_old else 0))

    if need_md:
        print()
        print("⚠️ 需同步修改大纲（脚本不会替你改）——把引用换成 .webp 后重渲：")
        seen = set()
        for hit, fixed in need_md:
            if hit in seen:
                continue
            seen.add(hit)
            print("   %s" % hit)
            print("      → %s" % fixed)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
