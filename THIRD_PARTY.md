# 第三方资源声明（THIRD_PARTY）

本技能内嵌以下第三方资源（vendored，非本仓库原创），按其原许可证分发：

| 资源 | 版本 | 原许可证 | 来源 | 用途 |
|---|---|---|---|---|
| Motion One（Motion） | motion@11.11.17（classic build） | **MIT** | npm `motion`；upstream github.com/motiondivision/motion（© Matt Perry / motion.dev） | `engine/eink_assets/motion.min.js`、`motion.source.esm.js`、`build_motion_classic.py` 挂 `window.motion`，驱动步进动画 |
| Lucide Icons | v0.488.0 | **ISC** | lucide.dev；`@license lucide - ISC`，见 `lucide.umd.min.js` 文件头 | `engine/eink_assets/lucide.umd.min.js` 提供 `<ico=name>` 图标 |

## 许可证说明

- **MIT（Motion One）**：npm registry `motion` 包的 `license` 字段为 `MIT`（author Matt Perry / motion.dev）。本仓库 vendored 的是 `motion@11.11.17` classic build（`motion.min.js` 文件头注明 `Original file: /npm/motion@11.11.17`），MIT 条款与 [LICENSE](./LICENSE) 相同。
- **ISC（Lucide）**：`lucide.umd.min.js` 文件头内置 `@license lucide v0.488.0 - ISC` 与 "This source code is licensed under the ISC license." ISC 与 MIT 功能等效，原文见 https://opensource.org/licenses/ISC 。

## 字体

`engine/eink_assets/get_fonts.py` 负责下载 / 子集化字体（如思源宋体等）。字体文件本身**不随本仓库分发**（由用户在本地按其各自许可证获取），仅入库脚本与缓存目录（已被 `.gitignore` 排除 `eink-font-cache/`）。

## 上游项目（风格与模板基础）

本仓库的渲染引擎、版式体系与工具链为从零原创；视觉与模板基础来自上游项目 **guizang-ppt-skill**（作者 op7418，[GitHub](https://github.com/op7418/guizang-ppt-skill)），按 AGPL-3.0 署名如下，保留原作者版权。

| 资源 | 迭代基础版本 | 原许可证 | 来源 | 与本仓库的关系 |
|---|---|---|---|---|
| guizang-ppt-skill | WorkBuddy 市场版 v1.0.0（技能内部版本 1.0.1，约 2026-07-22 安装） | **AGPL-3.0** | github.com/op7418/guizang-ppt-skill（© 2026 op7418） | 本仓库的「电子墨水」视觉主题、WebGL 双背景（light/dark）、版式语法体系与字体栈（Playfair Display / Source Serif 4 / IBM Plex Mono / Noto Serif SC / Noto Sans SC）源自此技能；本仓库重写了渲染引擎（Python）、将版式由约 10 个扩充至 L01–L27（28 个）、并移除了其瑞士国际主义风格（Style B）。 |
