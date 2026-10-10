# -*- coding: utf-8 -*-
"""package_deck.py —— 两步打包器（交付步骤）：把渲染产物目录变成单文件交付稿
================================================================

背景（老陈 2026-09-09 裁定的两步方案，不改 build()、不动渲染流程）：
  步骤1（渲染）照旧：render_outline.py → <大纲>_eink/index.html + assets/（工作稿）；
  步骤2（打包，本脚本）：把产物目录打包成 **单文件** `<大纲名>.html`（交付稿）——
  拷到任何电脑双击即用：动效步进、B 键静态、WebGL 背景、中文字体全部自包含。

用法
----
    python package_deck.py <产物目录>
    python package_deck.py <产物目录> --out 自定义名.html

输出：<产物目录>/<去修饰词名>.html —— 目录名去掉 `_eink`，**再去掉 `大纲` 修饰词**
      （老陈 2026-09-09 要求，"大纲"是写作期概念，交付稿不该带）：
        第2讲_大纲_eink      → 第2讲.html
        第9讲-李靖-大纲_eink  → 第9讲-李靖.html
      删空则回退保留修饰词（绝不产出无名 `.html`）。
      ⚠️ 交付稿名跟随**大纲文件名**——想更有信息量，改大纲文件命名
      （如 `第2讲-车战与妇好钺_大纲.md` → `第2讲-车战与妇好钺.html`），别手改产物。

打包器做五件事
--------------
  1. 内联 assets/lucide.umd.min.js（UMD，直拼 <script>）；
  2. <script src="assets/motion.min.js"> 整段内联进 <script> 块（classic 版 motion，
     由 engine/eink_assets/build_motion_classic.py 生成）——工作稿在 file:// 下用
     classic script 取同目录 js 本来就能成功，内联则拷出产物目录也照样有动效；
  3. 注入 localStorage 守卫 shim：存储被禁（file:// 私密模式等）时用内存桩，
     B 键不因 SecurityError 静默失效；代价：静态/动态偏好不跨刷新持久（写进 SKILL）；
  4. 字体子集内嵌：按本 deck 实际用字，从 ~/.workbuddy/eink-font-cache/ 的可变 TTF
     （Noto Serif/Sans SC + Playfair Display + Source Serif 4）切 woff2 子集 base64
     内嵌，并剥掉 Google Fonts <link>——断网观感与在线一致。fonttools 未安装或
     缓存缺失时：保留 CDN 链接并明确告警（降级不阻断，中文永不豆腐块）；
  5. 本地配图内联：产物目录 images/ 下的真实配图（大纲 `M12 文件:` 引入）内联成
     **data URI**。渲染器只把图拷到 images/ 并在 HTML 里写相对路径 `images/xxx`，
     不内联则交付稿一旦拷出产物目录，图片全部开天窗
     （2026-09-09 老陈实测第2讲发现的 P0：单文件承诺在图片上是破的）；
     图缺失/路径越界 → 告警并保留原路径（不阻断，但交付稿会缺图，收尾会点名）。

安全与降级
----------
  - 锚点校验：产物里找不到预期结构（lucide 外链 / motion import）→ 大声报错退出(1)，
    绝不静默产出坏包——引擎升级改结构时这里是显式失败点；
  - 本脚本只读产物 + 写一个新文件，绝不修改原 index.html / assets/（工作稿保持可重渲）；
  - 绝不引入任何远程 URL（延续引擎「无 CDN 供应链」纪律）。
"""
import base64
import io
import os
import re
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FONT_DIR = os.path.join(os.path.expanduser("~"), ".workbuddy", "eink-font-cache")

# (CSS 家族名, 缓存文件名, font-weight 区间) —— 与 get_fonts.py 的 FONTS 输出对应
_FONT_SOURCES = [
    ("Noto Serif SC", "NotoSerifSC.ttf", "300 900"),
    ("Noto Sans SC", "NotoSansSC.ttf", "300 900"),
    ("Playfair Display", "PlayfairDisplay.ttf", "400 900"),
    ("Source Serif 4", "SourceSerif4.ttf", "200 900"),
]

_LOCALS_GUARD = """<script>/* package_deck: localStorage 守卫（file:// 私密模式等场景存储抛 SecurityError 时用内存桩，B 键不失效；代价：偏好不跨刷新持久） */
(function(){var _e=null;try{window.localStorage.getItem('__eink_probe')}catch(err){_e=err}
if(_e){var _m={};try{Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:function(k){return Object.prototype.hasOwnProperty.call(_m,k)?_m[k]:null},setItem:function(k,v){_m[k]=String(v)},removeItem:function(k){delete _m[k]},clear:function(){_m={}},key:function(i){return Object.keys(_m)[i]||null},get length(){return Object.keys(_m).length}}})}catch(e2){}}})()</script>"""


def _fail(msg):
    print("[打包][错误] %s" % msg)
    sys.exit(1)


def _warn(msg):
    print("[打包][警告] %s" % msg)


def _read(p):
    with io.open(p, "r", encoding="utf-8") as f:
        return f.read()


def _deck_charset(html_text):
    """提取产物可见文本字符集（去 script/style/标签、解实体）——用于字体子集。"""
    import html as _h
    s = re.sub(r"<script\b.*?</script>", " ", html_text, flags=re.S | re.I)
    s = re.sub(r"<style\b.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = _h.unescape(s)
    chars = set(s) - set("\n\r\t \u00a0")
    return "".join(c for c in sorted(chars) if c.isprintable() or c == "\u3000")


def _has_fonttools():
    """本机 python 能否切字体子集（区分"没装库"与"没字体缓存"，两者修法不同）。"""
    try:
        import fontTools  # noqa: F401
        return True
    except Exception:
        return False


def _subset_font(src_path, chars):
    """把 src_path 按字符集切成 woff2，返回 (base64, 字节数)。fontTools 缺失返回 None。"""
    try:
        from fontTools import subset
    except Exception:
        return None
    try:
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.desubroutinize = True
        opts.drop_tables += ["DSIG"]
        font = subset.load_font(src_path, opts)
        ss = subset.Subsetter(opts)
        ss.populate(text=chars)
        ss.subset(font)
        buf = io.BytesIO()
        font.save(buf)
        data = buf.getvalue()
        return base64.b64encode(data).decode("ascii"), len(data)
    except Exception as e:
        _warn("字体子集化失败 %s：%s" % (os.path.basename(src_path), e))
        return None


def _build_font_css(chars, html_text):
    """按字符集内嵌字体子集，返回 (css 或 "", 处理说明)。

    策略：能嵌的家族全嵌；全嵌成功 → 剥 Google Fonts <link>（零网络依赖）；
    部分成功/全失败 → 保留 <link>（在线时缺失家族仍可从 CDN 补）并告警。"""
    font_dir = os.environ.get("EINK_FONT_DIR", DEFAULT_FONT_DIR)
    rules, ok_fams, miss = [], [], []
    for fam, fname, wrange in _FONT_SOURCES:
        src = os.path.join(font_dir, fname)
        if not os.path.exists(src):
            miss.append(fam)
            continue
        r = _subset_font(src, chars)
        if r is None:
            miss.append(fam)
            continue
        b64, nbytes = r
        rules.append("@font-face{font-family:'%s';font-style:normal;font-weight:%s;"
                     "src:url(data:font/woff2;base64,%s) format('woff2');font-display:swap}"
                     % (fam, wrange, b64))
        ok_fams.append("%s(%.0fKB)" % (fam, nbytes / 1024))
    if not rules:
        # 分情况报，便于一眼定位（2026-09-09：合并文案导致"到底是没库还是没字体"查不出来）
        if not _has_fonttools():
            return "", ("当前 python 未装 fonttools（%s）——无法切子集，保留 CDN 链接；\n"
                        "修复：先 pip install fonttools brotli，再跑 engine/eink_assets/get_fonts.py，最后用同一 python 重打包。\n"
                        "候选已装解释器（可逐一试）：系统 PATH 中的 python，或你自己安装的 python3 路径"
                        % sys.executable)
        return "", ("字体缓存为空（%s）——先跑 engine/eink_assets/get_fonts.py 备字体再重打包；"
                    "本次保留 CDN 链接（联网正常，断网回退系统字体）" % font_dir)
    css = "<style id='packaged-fonts'>%s</style>" % "".join(rules)
    if miss:
        # 部分家族缺缓存：保留 CDN <link> 兜底（在线可补，离线回退系统字体）
        note = "已内嵌 %s；缺缓存未嵌：%s——保留 CDN 链接（联网可补，断网时该族回退系统字体）" % (
            ", ".join(ok_fams), ", ".join(miss))
        return css, note
    # 全部内嵌成功 → 剥掉 Google Fonts link 与 preconnect（产物零网络字体依赖）
    css += "\n"
    return css, "已内嵌 %s；已剥离 Google Fonts <link>（产物零网络字体依赖）" % ", ".join(ok_fams)


_IMG_MIME = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".jpe": "image/jpeg",
    ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp",
    ".svg": "image/svg+xml", ".bmp": "image/bmp", ".ico": "image/x-icon",
    ".avif": "image/avif", ".tif": "image/tiff", ".tiff": "image/tiff",
}

# 单张超过此体积只告警不阻断（base64 膨胀约 33%，过大拖慢浏览器首屏）
_IMG_WARN_MB = 1.5


def _inline_images(html_text, deck_dir):
    """把产物里 images/ 相对路径的配图内联成 data URI。

    覆盖两种写法：<img src="images/x.png">（M12 配图）与 CSS url(images/x.png)。
    路径安全沿用渲染器纪律：拒绝绝对路径与 .. 穿越，解析后必须落在 deck_dir 内。
    返回 (new_html, 内联说明, 缺失清单)。"""
    from urllib.parse import unquote

    deck_norm = os.path.normpath(deck_dir)
    done, missing = [], []

    def _to_data(rel):
        rel = unquote(rel)
        if os.path.isabs(rel) or ".." in rel.replace("\\", "/").split("/"):
            missing.append("%s（路径可疑，拒绝读取）" % rel)
            return None
        p = os.path.normpath(os.path.join(deck_norm, rel))
        if p != deck_norm and not p.startswith(deck_norm + os.sep):
            missing.append("%s（越界，拒绝读取）" % rel)
            return None
        if not os.path.exists(p):
            missing.append(rel)
            return None
        ext = os.path.splitext(p)[1].lower()
        mime = _IMG_MIME.get(ext)
        if not mime:
            missing.append("%s（未知图片类型 %s）" % (rel, ext or "无扩展名"))
            return None
        with open(p, "rb") as f:
            raw = f.read()
        mb = len(raw) / 1024 / 1024
        if mb > _IMG_WARN_MB:
            _warn("配图 %s 体积 %.1fMB——内联后单文件明显变大，建议先压缩再打包" % (rel, mb))
        done.append("%s(%.0fKB)" % (rel, len(raw) / 1024))
        return "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode("ascii"))

    def _sub(m):
        d = _to_data(m.group(2))
        return m.group(1) + (d if d else m.group(2)) + m.group(3)

    html_text = re.sub(r"(src\s*=\s*[\"'])(images/[^\"']+)([\"'])", _sub, html_text)
    html_text = re.sub(r"(url\(\s*['\"]?)(images/[^)'\"]+)(['\"]?\s*\))", _sub, html_text)

    note = ("已内联配图 %d 张：%s" % (len(done), ", ".join(done))) if done \
        else "本 deck 无 images/ 本地配图引用"
    return html_text, note, missing


def _delivery_stem(dirname):
    """交付稿文件名主干：目录名去 `_eink`，再去 `大纲` 修饰词（含 `-大纲`/`_大纲`）。

    老陈 2026-09-09 要求：`第2讲_大纲_eink` → `第2讲`，不带"大纲"二字。
    删空（极端命名如目录就叫 `大纲_eink`）则回退保留修饰词，绝不产出无名 `.html`。"""
    stem = dirname[:-5] if dirname.endswith("_eink") else dirname
    stripped = re.sub(r"[-_]?大纲", "", stem).strip("-_ ")
    return stripped or stem


def package(deck_dir, out_name=None):
    deck_dir = os.path.abspath(deck_dir)
    index = os.path.join(deck_dir, "index.html")
    if not os.path.exists(index):
        _fail("产物目录里没有 index.html：%s" % deck_dir)
    html_text = _read(index)

    # ---- 锚点校验（引擎结构变了就大声失败，绝不静默出坏包） ----
    lucide_tag = '<script src="assets/lucide.umd.min.js"></script>'
    if lucide_tag not in html_text:
        _fail("锚点缺失：未找到 %s —— 产物可能由旧版/新版引擎生成，请确认引擎版本后同步本脚本" % lucide_tag)
    motion_tag = '<script src="assets/motion.min.js"></script>'
    if motion_tag not in html_text:
        _fail("锚点缺失：未找到 %s —— 产物可能由旧版/新版引擎生成，请确认引擎版本后同步本脚本" % motion_tag)
    mod_block = re.search(r"<script type=\"module\">.*?</script>", html_text, flags=re.S)
    if not mod_block:
        _fail("锚点缺失：未找到 <script type=\"module\"> 块")

    # ---- 1. lucide 内联（UMD → 普通 <script>） ----
    lucide_src = os.path.join(deck_dir, "assets", "lucide.umd.min.js")
    if os.path.exists(lucide_src):
        html_text = html_text.replace(
            lucide_tag,
            "<script>/* inlined lucide.umd.min.js (package_deck) */\n%s</script>" % _read(lucide_src))
        print("[打包] lucide 已内联（%s KB）" % (os.path.getsize(lucide_src) // 1024))
    else:
        _warn("缺 assets/lucide.umd.min.js——保留外链写法，图标在无 assets 目录时不可用")

    # ---- 2. motion 内联（classic script → 内联 <script>，整段原样拼入） ----
    motion_src = os.path.join(deck_dir, "assets", "motion.min.js")
    if os.path.exists(motion_src):
        src = _read(motion_src)
        if "</script>" in src:
            _fail("assets/motion.min.js 含 </script> 字面量——内联会截断 HTML，不要手改该资产")
        html_text = html_text.replace(
            motion_tag,
            "<script>/* inlined motion.min.js (package_deck) */\n%s</script>" % src)
        print("[打包] motion 已内联（%s KB）" % (os.path.getsize(motion_src) // 1024))
    else:
        _warn("缺 assets/motion.min.js——保留外链写法，动效不可用（内容/图标/基础步进仍工作）")

    # ---- 3. localStorage 守卫 shim（插在 <head> 之后，先于一切脚本） ----
    html_text = html_text.replace("<head>\n", "<head>\n" + _LOCALS_GUARD + "\n", 1)

    # ---- 4. 字体子集内嵌 ----
    chars = _deck_charset(html_text)
    css, note = _build_font_css(chars, html_text)
    fonts_selfcontained = bool(css) and "已剥离" in note
    if css:
        if fonts_selfcontained:
            html_text = re.sub(r"<link rel=\"preconnect\"[^>]*>\n?", "", html_text)
            html_text = re.sub(r"<link href=\"https://fonts\.googleapis\.com/css2[^\"]*\"[^>]*>\n?", "", html_text)
        html_text = html_text.replace("</head>", css + "</head>", 1)
    print("[打包] 字体：%s（deck 去重字符 %d 个）" % (note, len(chars)))

    # ---- 5. 本地配图内联（必须放在字体内嵌**之后**：图片 base64 会污染字体子集字符集） ----
    html_text, img_note, img_missing = _inline_images(html_text, deck_dir)
    print("[打包] 配图：%s" % img_note)
    if img_missing:
        _warn("以下配图未内联，交付稿拷出产物目录后将不显示：%s" % "；".join(img_missing))

    # ---- 收尾校验：不应残留任何会 fetch 本地 assets 的引用 ----
    # （先剥 JS 块注释再查——_deck_js 的历史注释里含字面 import('./assets/…')，非真实引用）
    # （再剥 data URI：base64 里含 "/" 字符，不清掉会干扰下面的残留匹配）
    check_copy = re.sub(r"data:[A-Za-z0-9+/=]+", " ", re.sub(r"/\*.*?\*/", " ", html_text, flags=re.S))
    leftover_src = re.findall(r"<script[^>]*src=\"assets/[^\"]*\"", check_copy)
    leftover_imp = re.findall(r"import\('\./assets/", check_copy)
    if leftover_src or leftover_imp:
        _warn("仍残留本地 assets 引用（src=%d, import=%d）——若交付时不含 assets 目录，对应功能降级"
              % (len(leftover_src), len(leftover_imp)))
    leftover_img = re.findall(r"[\"'(]images/[^\"')]+", check_copy)
    if leftover_img:
        _warn("仍残留 %d 处 images/ 外部图片引用——交付稿拷出产物目录后这些图不显示" % len(leftover_img))

    # ---- 输出 <去修饰词名>.html（目录名去 _eink，再去「大纲」修饰词） ----
    base = os.path.basename(deck_dir)
    stem = _delivery_stem(base)
    out_path = os.path.join(deck_dir, out_name or (stem + ".html"))
    html_text = html_text.replace("<!DOCTYPE html>",
                                  "<!DOCTYPE html>\n<!-- packaged single-file deliverable by eink-deck package_deck.py -->",
                                  1)
    with io.open(out_path, "w", encoding="utf-8") as f:
        f.write(html_text)
    print("[打包] 交付稿已生成：%s（%.2f MB）" % (out_path, os.path.getsize(out_path) / 1024 / 1024))
    if fonts_selfcontained:
        print("[打包] 使用方式：拷这**一个文件**到任何电脑，双击即可放映（步进/B/背景/中文字体全自包含）。")
    else:
        print("[打包] 使用方式：拷这**一个文件**到任何电脑，双击即可放映（步进/B/背景自包含）；"
              "本次中文字体未内嵌（联网显示正常、断网回退系统字体）——"
              "在装了 fonttools 且已跑 get_fonts.py 的 python 上重新打包即可全自包含。")
    return out_path


def main(argv):
    if not argv:
        print("用法: python package_deck.py <产物目录> [--out 自定义名.html]")
        return 1
    deck_dir = argv[0]
    out_name = None
    if "--out" in argv:
        i = argv.index("--out")
        if i + 1 < len(argv):
            out_name = argv[i + 1]
    package(deck_dir, out_name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
