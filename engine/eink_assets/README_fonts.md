# 离线字体（子集内嵌）· 附件说明

eink-deck 默认字体走 Google Fonts CDN（**唯一**网络依赖）。开启「离线字体开关」后，
引擎会在**构建期**把本 deck 实际用到的中文字符从本地 Noto SC 源 woff2 切出子集、
base64 内嵌进 `index.html`，产物自包含、断网也不豆腐块。

## 1. 三种触发方式（任选其一）

| 方式 | 写法 | 说明 |
|---|---|---|
| 大纲元数据（规范键） | `字体源: 本地` | 推荐；与 `字体: serif/sans` 基调互不干扰 |
| 大纲元数据（兼容快捷） | `字体: 本地` | 同时触发离线且基调回落默认衬线 |
| 命令行 | `--offline-fonts`（或 `--offline`） | 优先级最高，覆盖大纲 |
| 派生 profile | `字体源: 本地` | 武脉等系列可一次性固化默认离线 |

> `字体: serif/sans` 仍表示**衬线/无衬线基调**（旧语义不变）。离线时若想另指定基调，
> 用 `字体基调: sans` 等独立键，不与 `字体: 本地` 冲突。

## 2. 一次性准备本地字体源（构建机只需一次）

源 woff2 **不进产物**，只用于切子集；交付的 `index.html` 自带子集即可。

```bash
# 默认缓存目录 ~/.workbuddy/eink-font-cache/
python engine/eink_assets/get_fonts.py

# 或自定义目录（引擎与脚本读取同一个环境变量）
EINK_FONT_DIR=/your/cache python engine/eink_assets/get_fonts.py
```

- 下载来源：Google Fonts css2 API（桌面 UA 触发可变 woff2 整族）。
- 仅需标准库，无需第三方包。
- 网络受限时脚本会报失败，请手动把 `NotoSerifSC.woff2` / `NotoSansSC.woff2` 放到缓存目录。

## 3. 构建期依赖

离线切子集需要 `fonttools`（含 brotli 才能读写 woff2）：

```bash
pip install fonttools brotli
```

**优雅降级**：若 `fonttools` 未装、或本地源 woff2 缺失，引擎会打印明确告警并**回退到
Google Fonts CDN 链接**（产物仍需联网，但不会报错、不会豆腐块）。所以离线是「有就生效、
无就安全退网」的开关，不会因缺料而崩。

## 4. 产物行为

- 离线成功：`<head>` 中去掉 Google Fonts `<link>`，改内联 `@font-face`（base64 子集）；
  中文衬线/无衬线保证离线可用；西文字体（Playfair/Source Serif/IBM Plex Mono）仍走系统回退
  （Georgia 等），不影响中文离线。
- 子集按「本 deck 实际字符」切，大小随**去重字数**线性增长；以第9讲（约 1165 去重字）为例内嵌约 1.16 MB（整库 25 MB 仅取 3.8%），与 CDN 版体积相当，但产物自包含、断网可用，且保持单文件。小讲稿（去重少）可低至数百 KB。

## 5. 重要约束：子集是「冻结」的

子集只在**构建那一刻**按当时字集切好并内嵌。因此：

- **正常改稿必须回到大纲重渲**——这点和 CDN 模式一样，两者都要重渲。
- 但离线产物是「密封成品」：**不要手改产物 index.html 往里加字**（新字不在子集里 → 豆腐块 □）。
  要加字，回到大纲重渲（重渲会自动重新切子集）。
- 推荐工作流：**撰写期用 CDN（全量字体、零摩擦）**，**交付期加 `字体源: 本地` 重渲一次**冻结子集。

## 6. 目录约定

```
engine/eink_assets/
├── get_fonts.py          # 一次性下载源 woff2 到缓存目录
├── README_fonts.md       # 本文件
├── motion.min.js         # 本地动效（早已离线，与字体无关）
└── lucide.umd.min.js     # 本地图标（早已离线，与字体无关）

~/.workbuddy/eink-font-cache/   # 默认源缓存（可用 EINK_FONT_DIR 改；不在 skill 内，不随 OneDrive 同步）
├── NotoSerifSC.ttf
└── NotoSansSC.ttf
```
