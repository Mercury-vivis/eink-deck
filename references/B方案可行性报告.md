# B 方案可行性报告 · 通用渲染器声明式（28 版式共性梳理）

> 产出：2026-09-15 · 阶段3c-3 完成后的新增计划项④（用户拍板）
> 依据：`scan_layout_common.py` 对 `_eink_template.py` 28 个 p_* 函数的 AST 实扫（块/辅助函数分布）
> 结论先行：**B 方案完整形态（版式 = 纯声明数据 + 通用组装器）不可行；B 方案子集形态（骨架统一 + 数据块保留专属）中等可行，建议作为路线 A 的自然延伸在远期评估，不立项。**

---

## 1. 28 版式的骨架现状（实扫数据）

所有版式都是「`frame` 容器 + 内部块」的 HTML 拼接，公共块出现频次：

| 公共块 | 频次 | 现状 |
|---|---|---|
| kicker | **27/28** | 各 p_* 内联 `<div class="kicker" data-anim>`（3c-2 评估过提取，收益/风险比一般） |
| 标题（h-xl / h-hero） | 25+/28 | **已收敛为辅助函数** `_hxl` / `_hero_title`（3c-2 前即存在） |
| body 正文 | 15/28 | **已收敛为辅助函数** `_body_block`（18 处调用） |
| 三控/强调/转义 | 全版式 | `_movewrap`（14 处）/ `em(` / `esc(` 统一 |
| stats / items / steps / rows | 各 1–6 | **各版式专属渲染**，形态差异大（见 §2） |

即：**「标题 + 正文 + kicker + 三控」这四类共性在 3c-2 之前就已被辅助函数收敛**，真正的剩余差异集中在两处——数据块的渲染形态、版式专属 CSS 布局。

## 2. 收编潜力分类

### 可被「通用骨架」收编（壳统一，约 20/28）
frame 结构接近、差异在数据块形态：L03/L04/L05/L06/L10/L11/L12/L13/L14/L16/L17/L18/L19/L20/L23/L24/L25/L26/L12b
→ 这些版式若做"骨架统一"，仅需处理：数据块形态（stats 3 形态 / items 6 版式各异）+ 布局 CSS 变体。

### 半收编（骨架可统一但需特例参数，约 3/28）
L21 loop / L22 system（引擎自绘 SVG 图，数据 → 图算法）/ L27 imagehero（fit 模式，图区高度动态）。

### 强特例（不建议收编，约 5/28）
L01 cover / L02 hero / L15 收束（hero 家族，仪式化布局）/ L07 quote（暗底引文）/ L09 directional（双栏对比）。
→ 收编需为它们单开"布局类型"分支，抽象层复杂度不降反升。

## 3. 两种形态的可行性评估

### 形态 A：完整声明式（版式 = 纯数据声明 + 通用组装器）

**设计**：每个版式声明为 `{frame: {...}, blocks: [kicker, title, body, stats(style=hbar)...]}`，渲染器按声明顺序组装。

| 维度 | 评估 |
|---|---|
| 收编覆盖 | 数据块形态 20+ 变体（stats 3 形态 × items 6 版式 × steps 2 × rows 1 × 图 7）需全部抽象成"块渲染器 + 配置"——抽象层可能比 28 个直写函数更复杂 |
| 行为 | 重构 = 渲染输出变化（逐字节基线失效），需全量人工比对 17 份 HTML |
| 收益 | 新增版式免写渲染代码；但本引擎版式已稳定（28 个，近两月无新增），收益低频 |
| 风险 | 高。CSS 类变体（各版式独立 class 组合）无法完全配置化，需保留大量"特例逃逸口" |

**结论：不可行。** 通用组装器是"用配置复杂度换函数复杂度"，对本引擎的版式规模（28 个、已稳定）是负收益。

### 形态 B：骨架统一子集（壳统一 + 数据块保留专属）

**设计**：抽 `_render_frame(s, content, frame_style)` 统一 frame+kicker+底部通用图位+固定元件；数据块渲染保留各版式专属函数。

| 维度 | 评估 |
|---|---|
| 收编覆盖 | 约 20 个版式的"壳"统一（每版式减 3–5 行样板）；数据块零改动 |
| 行为 | **可零变化**（3c-2 式逐字节验证）——只重排 frame 拼接，不改任何输出 |
| 风险 | 中低。frame 变体 4 种（frame/frame center/frame %s/frame 特例），参数化可控 |
| 前置 | 依赖 3c-3 路线 A 已建立的 MOUNTS 声明体系（块声明可与 _MOUNT 合并） |

**结论：中等可行。** 但收益有限（主要消除 kicker 样板，标题/正文已收敛），且与"路线 A 已解决核心痛点（语法—引擎一致性）"叠加后边际价值低。

## 4. 建议

1. **B 方案不立项**（完整形态不可行；子集形态收益有限）。
2. 保留 3c-3 路线 A 的声明头体系，作为"版式—字段"唯一真相源；如未来新增版式，用 `_MOUNT` 声明 + 现有 p_* 直写模板即可（成本已低）。
3. 若未来出现"版式数量爆炸"（>50 个）或"多主题换肤"需求，再重估形态 B；届时骨架统一可作为 p_* 的辅助重构（仍非通用组装器）。
4. 本报告结论在引擎后续大修时可复用：**组件块模型收编的上限 ≈ 20/28 壳 + 4 类数据块函数，完整声明式不适配本引擎的版式规模与稳定度。**

---

## 附：共性统计原始表（scan_layout_common.py 输出摘要）

| 版式 | 渲染函数 | 含公共块 |
|---|---|---|
| L01 | p_cover | kicker, h-hero, h-sub, meta-row |
| L02/L15 | p_hero | kicker, h-hero, h-sub |
| L03 | p_lead | kicker, lead, body |
| L04 | p_statgrid | kicker, stats |
| L05 | p_grid2 | kicker, callout, img |
| L06 | p_rowline | kicker, rows |
| L07 | p_quote | kicker, callout |
| L08 | p_pillar | kicker, items, pillar |
| L09 | p_directional | kicker |
| L10 | p_callout | kicker, body, callout, img |
| L11 | p_imgslot | kicker, img |
| L12 | p_figsvg | kicker, body, svg, img |
| L13 | p_pipeline | kicker, steps |
| L14 | p_text | kicker, body, body-fill |
| L16 | p_statnote | kicker, notes |
| L17 | p_interactive | kicker, body, tag |
| L18 | p_ziyuan | kicker, items |
| L19 | p_hbar | kicker, lead, body, stats, bar |
| L20 | p_kpitower | kicker, lead, body, stats, kpi, bar |
| L21 | p_loop | kicker, lead, body, steps, svg, loop, ring |
| L22 | p_system | kicker, lead, body, items, svg, ring |
| L23 | p_wall | kicker, lead, body |
| L24 | p_statement | lead, body（唯一无 kicker） |
| L25 | p_timeline | kicker, body, items, timeline |
| L26 | p_microcard | kicker, body, items |
| L27 | p_imagehero | kicker, body, img, kpi |
| L12b | p_chain | kicker, body, items, chain |
