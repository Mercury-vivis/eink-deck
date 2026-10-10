# eink-deck

> 把「大纲 Markdown」渲染成单文件横向翻页 HTML PPT——浏览器放映、B 键静态、WebGL 水墨背景、5 套主题。

## 这是什么

一个**通用 eink 网页 PPT 引擎**：输入一份大纲 Markdown，输出一个自包含的 `index.html`（含全部样式、脚本、字体子集，离线可双击打开）。
引擎 / 模板 / 示例全部随技能自带，**不依赖任何具体工作区**。

## 能力

- **28 个版式**（L01–L27 + L12b）+ 通用元件（M01 眉标 / M05–M14 元件三控 / M10 分步揭示 / M12 图片 / M13 注释 / M14 下标 / M16 参考链接框）。
- **5 套主题**（默认 `ink-classic` 墨水经典；含 `kraft` 牛皮纸等），配色可配。
- **WebGL 水墨背景** + 步进动画 + B 键静态翻页。
- **Lucide 图标**，动画由内嵌 Motion One 驱动（不依赖 CDN）。

## 给谁用

- 想用 Markdown 写讲义 / 汇报 / 分享页，又不想被 PPT 软件绑定的人。
- 需要「一份大纲 → 一份可分发 HTML」的轻量发布流。

## 安装

1. 准备 Python 3（建议 3.13）。
2. 直接用本技能自带的 bat 拖拽渲染即可；如需命令行渲染或打包字体子集，需 `fonttools` + `brotli`（打包离线字体用）+ `Pillow`：

   ```bash
   python -m pip install fonttools brotli Pillow
   ```

   缺少这些时，打包会降级为 CDN 字体链接（仍可用，仅离线字体不嵌入）。

## 快速上手（拖拽，零命令）

1. 把你的 `<xxx 大纲.md>` 拖到 `bat/00拖拽渲染-eink.bat` → 生成 `<xxx_eink>/index.html`。
2. 把生成的 `<xxx_eink>` 文件夹拖到 `bat/01交付打包-eink.bat` → 得到单文件 `<xxx>.html`，可发给任何人离线打开。

## 命令行

```bash
python engine/render_outline.py <大纲.md> <输出目录>
python engine/package_deck.py <输出目录>     # 打包成单文件 html
```

## 依赖与第三方资源

- 运行时零外部依赖（HTML / JS 内联）。
- 内嵌第三方资源见 [THIRD_PARTY.md](./THIRD_PARTY.md)：Motion One（MIT）、Lucide Icons（ISC）。

## 协议

[MIT](./LICENSE)。© 2026 老陈 / 帮帮。
