# eink-deck

> 原创 Markdown → HTML 渲染引擎：一份大纲 Markdown，渲染成单文件横向翻页 HTML PPT——浏览器放映、B 键静态、WebGL 水墨背景、5 套主题。

## 这是什么

eink-deck 的核心是一套**易用的 Python 渲染引擎**：输入一份大纲 Markdown，输出一个自包含的 `index.html`（样式、脚本、图标、字体子集全部内联，离线双击即可放映）。

「写大纲」直接等于「出成片」——不需要打开任何 PPT 软件，也不需要手改 HTML：

```
大纲 .md ──▶ engine/render_outline.py ──▶ 横向翻页 index.html ──▶ engine/package_deck.py ──▶ 单文件 HTML
```

- **零手写 HTML**：28 个版式由引擎按大纲契约自动装配，动画、配色、字体全部自动处理。
- **输出零依赖**：Lucide 图标、Motion One 动画全部内联，不依赖 CDN，发给谁都能离线打开。
- 引擎 / 模板 / 示例全部随技能自带，**不依赖任何具体工作区**。

## 能力

- **28 个版式**（L01–L27 + L12b）+ 通用元件（M01 眉标 / M05–M14 元件三控 / M10 分步揭示 / M12 图片 / M13 注释 / M14 下标 / M16 参考链接框）。
- **5 套主题**（默认 `ink-classic` 墨水经典；含 `kraft` 牛皮纸等），配色可配。
- **WebGL 水墨背景** + 步进动画 + B 键静态翻页。

## 原创部分（© 2026 老陈 / 帮帮）

- **整套 Python 渲染引擎**（`engine/*.py`，约 7,344 行 / 18 个文件）：大纲契约 → 版式分发 → HTML 装配的完整渲染管线，从零创作，不含任何第三方模板代码。
- **版式体系**：L01–L27（28 个版式）+ 通用元件，在上游约 10 个布局基础上扩展逾一倍。
- **工具链**：bat 拖拽渲染 / 交付打包 / 压缩配图 / 自检、tests 冒烟测试、golden 自检、单文件打包。

## 风格来源与致谢

本项目的视觉风格受益于 [guizang-ppt-skill](https://github.com/op7418/guizang-ppt-skill)（作者 op7418，AGPL-3.0）——「电子墨水」主题、WebGL 双背景与版式语法体系出自该作品，它为这套幻灯片提供了**风格与地基**，在此致谢。

eink-deck 在其上重建了从 Markdown 到成片的全部渲染链路，并将版式扩展至 28 个。迭代基础为 guizang-ppt-skill 的 WorkBuddy 市场版 v1.0.0（约 2026-07-22）。

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

## 协议与著作权

- **著作权**：渲染引擎、28 版式与工具链 © 2026 老陈 / 帮帮；上游视觉主题 © 2026 op7418。两者并列独立，AGPL-3.0 不改变归属，明细见 [NOTICE](./NOTICE)。
- **许可**：因包含 guizang-ppt-skill（AGPL-3.0）代码，整包以 [AGPL-3.0](./LICENSE) 发布；你基于本引擎的修改同样须以 AGPL-3.0 开放。
- **第三方资源**：Motion One（MIT）、Lucide Icons（ISC），见 [THIRD_PARTY.md](./THIRD_PARTY.md)。
