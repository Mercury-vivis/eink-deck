# eink-deck 变更日志（CHANGELOG）

> **版本唯一源**：`SKILL.md` frontmatter `version`（本文件不设版本号；引擎/注册表/文档均不再维护版本号）。
> **纪律**（2026-09-15）：凡修改必落日志；已解决的坑、已修复的问题、已过时的表述一律删除，不留档。
> 本文件 2026-09-15 阶段1 收编：原 SKILL.md「版本」节历史（去重 v2.4.42 重复行）＋ 原《大纲制作接口约定》changelog（该两处均已从原文件删除）。

---

## 2026-10-10 · v2.4.56 —— GitHub 发布准备（去本机痕迹 + 开源合规件 + 全量核验）
- 发布就绪改造（次版本，非契约破坏性）：① 去本机路径/机名痕迹——`_defaults.py` 的 `DEFAULT_OUTLINES_DIR` 由写死目录改为 `None`（`EINK_OUTLINES_DIR`/`--outlines` 覆盖，皆空时门禁跳过）；`golden_check.py`/`render_baseline.py` 优雅跳过；4 个 bat 改 `%~dp0..` 推导 + `%USERPROFILE%\.workbuddy\skills\eink-deck` 兜底，Python 选择去写死路径；SKILL.md/CHANGELOG 去绝对路径与机名。② 补 MIT `LICENSE` / `README.md` / `THIRD_PARTY.md`（Motion MIT + Lucide ISC）/ `.gitignore`。③ `_tools/check_drift.py --strict` 全绿、14/14 冒烟测试通过、示例大纲确认通用 demo（无夹带真实配图、无领域污染）。
- 本机影响：`DEFAULT_OUTLINES_DIR` 改 `None` 后，本机跑 16 讲 golden 实纲 lint 需设 `EINK_OUTLINES_DIR`（或支持跳过）；bat 改 `%~dp0` 后更抗造。

## 2026-09-27 · v2.4.54 —— 入场动画落终值保底（标签页冻结后内容永久透明）

- **根因**：入场动画 `animate()/stagger()` 的 CSS 默认态是 `body.motion-ready [data-anim]{opacity:0}`，靠 WAAPI 推进。标签页被浏览器冻结（系统休眠唤醒／长时间不活跃的标签被冻结／投屏与远程桌面帧调度异常）时动画停在 0，**内容永久不可见**；`countUp` 上次只兜了数字，没兜这一半。
- **修法（模板 `_MOTION` 段一处）**：`window.__playSlide` 改为 `_wrapPlay(playSlide)` 包装，两重触发——① 每次 `playSlide` 后挂 2200ms 定时器（覆盖最长动画 stagger 1.0s + duration 0.8s），超时把该页 `[data-anim]` 强制点亮；② `visibilitychange` 转可见时清掉定时器并立即补点亮。
- **坑（必须记）**：`forceVisible()` **必须先 `el.getAnimations().cancel()` 再写 inline**——`animate()` 走 WAAPI，动画的 fill 状态优先级高于 inline style，只写 `el.style.opacity='1'` 会被继续压成 0。首版漏了 cancel，实测解冻后仍全透明。
- **验证（无头浏览器 `file://` 直开，CDP `Page.setWebLifecycleState` 真实冻结，新旧模板同环境对照）**：旧版解冻后 6 秒仍 `opacity 0 / 可见 0/3`；新版解冻后约 2.2 秒落到 `1.00 / 可见 3/3`。
- ⚠️ **模拟方式更正**：早期用「页面加载后覆盖 `window.requestAnimationFrame`」模拟 rAF 停摆**无效**（动画照常推进，新旧版数据一致）——Motion One 走 WAAPI，不吃这个。要复现必须用 CDP 真实冻结，别再用注入法得出"动画冻结"的结论。

## 2026-09-27 · v2.4.53 —— 动效改 classic script 加载（file:// 不再静默失效）＋ 数字递增落终值保底（修复）

- **根因（两个叠加）**：① 动效库以 ES module 动态 `import()` 加载，`file://` 下被 CORS 拦掉 → catch 只 `console.warn`，`if(motion)` 整段不执行 → 入场动效／数字递增／`window.__playSlide` 全不定义，页面看起来"能翻页但不动"，排查时被误导到内容丢失方向（老陈 2026-09-27 第1讲 P16「只有万」的疑问即由此而来：打包件内联了 motion、动效一活，countUp 就把数字清零，而工作稿侥幸正确）。② `countUp()` 入口同步写 `0`，窗口转后台／投屏时 rAF 被节流甚至停摆，数字**永久冻结在 0**。
- **动效改 classic script（根治 ①）**：
  - 新增 `engine/eink_assets/motion.source.esm.js`（Motion One 官方 ESM 原版，只当源）＋ `build_motion_classic.py`（剥 `export{}`／`export default`、加 `'use strict'`、按导出映射挂 `window.motion`；带 `node --check` 语法闸门，失败即删产物退出）。升级 Motion One 时只换源重跑，不手改产物。
  - 产物文件名不变，`motion.min.js` 现在是 classic build；引擎新增常量 `_MOTION_SRC = '<script src="assets/motion.min.js"></script>'`（与 lucide 同款写法，装配进 `html_doc`），`_MOTION` 段开头由 `await import(...)` 改为 `const motion = window.motion || null`，**保留静态降级分支**（assets 缺失时置 `opacity:1`，内容永不白屏）。
- **`countUp()` 落终值保底（修 ②）**：转后台立即落终值；rAF 停摆时 `setTimeout(delay+dur+400)` 强制落终值；`visibilitychange` 触发时把在跑的递增就地 settle。递增仍是装饰，任何中断都落在终值而不是 0。
- **`package_deck.py` 同步**：锚点校验改为检测 classic `<script src="assets/motion.min.js">`；内联方式由「剥 export + 建导出映射再塞进 module」简化为「整段内联 classic script」，并加 `</script>` 字面量防御（命中即报错退出）。
- **验证**：示例大纲 lint `--strict` + 渲染 PASS，第1讲重渲校验全绿；实机（无头 CDP，`file://` 直开）渲染稿与交付稿均为 `motionLoaded=true`／44 个 API／`__playSlide` 已定义／`motion-ready` 生效；P16 三数最终 `125|120|163`，伪造转后台 200ms 即落终值；掐死 rAF 后 ≤2.0s 落终值（不再永久冻结）。第1讲交付稿重打包 2.05MB（字体子集全内嵌 + 配图 base64）。
- **已知未改**：`golden_check.py` 第 3 项（16 讲 lint）FAIL，来自 3 份大纲的非法图标名 `ic=bullet`／`ic=balance`（lucide 合法名分别应为 `circle`／`scale` 类）——既有问题，与本次改动无关，改大纲须老陈点头。

## 2026-09-18 · v2.4.51 —— lint 新增 lucide 图标名校验 + render 兜底警告（修复增强，零渲染行为变化）

- **根因**：2026-09-17 第1次课大纲 `ic=filetext`（错，正确 `file-text`）被引擎原样写进 `data-lucide`、lucide 运行时静默跳过，图标格子留空且 lint 0 报——放映时才发现。
- **lint_outline.py 新增 `2i` 检查**：复合键 `items:` 子项的 `ic=` 比对 `engine/eink_assets/lucide_icons.txt` 白名单（1768 个 kebab-case 合法名，由新增 `_gen_lucide_list.mjs` 从 `lucide.umd.min.js` 提取、lucide 升级时重跑刷新）；未知名报 **错误** 级（渲染前拦住）。lint 只读预生成 txt，纯标准库、不解析 umd。
- **`_eink_template.py` 的 `p_pillar` 兜底警告**：未知 `ic` 渲染时打印 `[render] ⚠ 图标 "xxx" 不是 lucide 合法名…`，给不跑 lint 直接渲染的人二次保险。
- **新增资产**：`engine/_gen_lucide_list.mjs`（node 提取脚本，固化）、`engine/eink_assets/lucide_icons.txt`（白名单，固化）。
- **验证**：py_compile 通过；故意错名 `filetext` 测试大纲 → lint 报 1 错误；正确名 `file-text` → 0 错误/0 警告；错名渲染 → 打印 `[render] ⚠` 警告；第1次课大纲（已修 `file-text`）重渲 0 错 0 警、P12 四项图标（scale/book/file-text/users）全合法。
- **影响面**：纯新增只读校验 + 渲染兜底警告，不改语法/版式/《接口约定》选型表；lecture-outline-design（契约消费者）自管加一句软提醒（图标命名须 kebab-case）；eink 示例/wumai/eink2pptx 均不需同步。

## 2026-09-15 · v2.4.50 —— 阶段 X 收尾：清两处代码气味（死代码 + 生成器闭环）

- `syntax_registry.py`：删除模块级死赋值 `LAYOUT_TYPES = {v["type"] for v in LAYOUTS.values()}`（L539）——该名已被顶部 import 的派生物字典（code→type）占用，集合形态无任何消费者（全库 grep 证实）；删除后字典名语义纯净。`LAYOUT_CODES`（lint 真源，有消费者）保留。
- `gen_mounts.py`：`build_mounts` 由「读派生值 `REG.LAYOUTS[L]["type"]`」改为「直读真源 `RO.LAYOUT_MAP[L]`」——消除生成器内部"render 段读真源、build 段读派生值"的两源并用，闭环不再依赖 --check 兜底。
- 验证：py_compile 全过；gen_mounts 重新生成派生物（28 版式，与声明一致）；anchors+keys（80 锚点 + 键集合 diff）全过；guard 文档一致性全过；golden（示例大纲 + 16 讲 lint）零回归；smoke 14/14；render_baseline 17 份逐字节一致（引擎运行行为零变化）。
- 备份沿用 `_backup_20260915_阶段X前`（本轮改动文件均在该快照覆盖范围内）。

## 2026-09-15 · v2.4.49 —— 阶段 X：键集合 diff guard + LAYOUTS 唯一源派生化

**LAYOUTS 版式唯一源（消除三源并存漂移）**
- `render_outline.py` 的 `LAYOUT_MAP` 确立为版式码→type 的 parse 层真源（既有）。
- `gen_mounts.py`：扩展为 **MOUNTS + LAYOUT_TYPES 生成器**——新增 `import render_outline as RO`，`render()` 追加输出 `LAYOUT_TYPES`（按 LAYOUT_MAP 原序）；docstring/main 文案同步。
- `_generated_mounts.py`（派生物，禁手改）：重新生成，现含 `MOUNTS`（28 版式）+ `LAYOUT_TYPES`（28 版式）。
- `syntax_registry.py`：LAYOUTS 手写 `type` 删除 → `_LAYOUT_META`（版式名/primary/constraint/skip_dual）+ `type` 从 `LAYOUT_TYPES` 注入；头部新增「派生物（禁手改）」节，统一 `from _generated_mounts import MOUNTS, LAYOUT_TYPES`（删文件中部旧重复 import）；构建时键集合一致性硬校验（缺/多即 SystemExit）。
- `check_engine_mounts.py`：删手写 `LAYOUT_MAP` 镜像（28 行）→ `LAYOUT_FN` 从 `REG.LAYOUTS[L]["type"]`（派生物）构建；docstring "MOUNTS 手动维护"→"派生物"。

**guard 升级：check_syntax_anchors.py → 键集合 diff（反向 fail）**
- 保留一期 79+1 锚点存在性检查（现 80 个）。
- 新增 AST 提取「引擎实际消费的键」并与注册表双向比对，**反向 fail**（引擎消费但注册表未登记 = 漏登记 → exit 1）：
  · 顶层键：`parse_outline` regex 链展开（受控形态展开器：字面量 / `(a|b|c)` / `(?:a|b|c)` / `_?` 双展开 / `(M\d+)`→M* / 组后固定后缀；`[：:]` 须按字面「`[`+冒号×1–2+`]`」整体截断）⊆ `PAGE_KEYS`
  · meta 键：`build_lecture` + `__main__` 的 `meta.get` 字面量 ⊆ `META_KEYS`
  · M 模块：`apply_module` 的 `mod == "Mxx"` 分支 ⊆ `MODULE_FIELDS`
  · 复合子项键：`parse_compound_item` 的 kv 消费（get / in / tuple）⊆ `COMPOUND_KEYS.subitems` 并集
  · fail-safe：无法解析的 regex 形态与非法展开产物（含正则元字符残留）→ problems 上报（宁严勿漏）
- 边界如实标注：ENUMS / INLINE_MARKS / SLASH_RULE 保持锚点级检查（引擎侧散落字面量/无字面量，不强行升级）。
- **实战捕获 1 处真实漏登记**：`字体本地`（引擎 `meta.get("字体源", meta.get("字体本地", ""))` 兜底消费，注册表从未登记）→ 已补登记 `DEPRECATED`（与 `字体源` 同语义，新大纲写 `字体: 本地/离线` 或 `字体源:`）。
- 语法速查（generated/）重新生成：318 行，含 `字体本地` 兼容条目。

**验证（阶段 X 全绿）**
- 锚点 80 命中 / 键集合 diff 四类全过 / 自测 5 项（新增顶层键、新增 M 分支、新增子项键、漏登记捕获、无法解析形态上报——均验证 fail 行为）/ guard 文档一致性 / 3c-1 双向 guard / gen_mounts --check / golden（示例大纲 + 16 讲 lint）/ smoke 14/14 / render_baseline 17 份逐字节一致（引擎运行行为零变化，仅 guard/注册表/生成器）。
- 备份：`_backup_20260915_阶段X前`（6 文件）。

**eink 侧清理（对应老陈 7 点 + workbuddy 稿2 验收）**
- SKILL.md：删 `examples/` 退役目录行（目录已物理删除）；修复 2 处断链（`templates/eink_大纲填空模板.md`、`examples/示例大纲.md` → 均改指 `engine/generated/示例大纲.md`）。
- syntax_registry.py：删头部手写版本戳（v2.4.42，违反"版本只在 SKILL 头部"，且滞后 5 版）；docstring "三份文档"→"仅语法速查.md"；正文版本号散落清除（v2.4.42/v2.4.36/v2.4.39）。
- gen_syntax_docs.py：docstring 同步"一份文档"（与实现 files dict 一致）。
- check_docs_consistency.py：删「最后核验 eink-deck」死模式（接口约定已删，匹配不到任何文档）；NOISE 白名单补 lecture 正文词（版本/变更记录/落页判断）。
- 模板模块规范：L24–L27「⚠️ 不渲染 M10」→「✅ 已渲染 M10」（与引擎阶段2 行为一致；L24 位置=statement 后/sub 前、L27=标题块后/图注前，已核 p_statement/p_imagehero）。
- 示例大纲：P25 补 M10 演示行（golden 缺口，手维护）。
- 引擎注释版本号散落清除（render_outline/_eink_template/lint_outline，纯注释文本级，渲染行为零变化；render_baseline 基线已 --update）。
- lecture-outline-design 重构至 v1.9.0（纯方法论化），eink SKILL 侧核实无反向重复（L76/L107/L303 指针正确、L309 协议声明如实）。

## 2026-09-15 · v2.4.47 —— 阶段3c-3（路线 A：MOUNTS 声明式化，注册表挂载矩阵变派生物）

**p_* 函数声明头（_eink_template.py）**
- 27 个 p_* 函数头部插入 `_MOUNT = {...}` 声明（L02/L15 共用 p_hero）：声明 = 该版式接受的大纲字段（值源 = 3c-1 已校准的 MOUNTS，生成物差异核验 = 0）。
- 声明随函数走：改渲染函数必然看见声明（防"引擎加了渲染忘同步注册表"类漂移的物理屏障）。

**MOUNTS 生成器（gen_mounts.py，新建）**
- 扫描 p_* 的 `_MOUNT` 声明 → 生成 `_generated_mounts.py`（MOUNTS 派生物，28 版式）。
- `--check` 校验模式：派生物与声明不一致即 exit 1（防手改派生物 / 声明改了没重跑）。
- 注册表 `syntax_registry.py`：手动 MOUNTS 段（L503-532）删除，改为 `from _generated_mounts import MOUNTS`。SVG_MOUNT_EXCEPT / MOUNT_ALL 保留（lint 语义配置，非渲染事实，不入派生物）。

**guard 升级（check_docs_consistency.py）**
- 新增 3c-3 检查：`gen_mounts --check`（派生物一致性）接入日常门禁。

**防漂移闭环（负例验证全过）**
- 删 p_text 声明 M10 → guard 拦（阶段A：派生物过期；重跑生成器后阶段B：3c-1 正向「消费 ⊄ MOUNTS」接力拦截）✓
- 手改派生物加假键 → gen_mounts --check 拦 ✓
- 回滚后恢复全绿 ✓

**验证**：生成物与旧 MOUNTS 差异 = 0 · 锚点 79/79 · guard（含 3c-1+3c-3）全绿 · golden 零回归 · smoke 14/14 · render_baseline 17 份产物逐字节一致（行为零变化）· 版本 2.4.47（SKILL+pyproject 同步）· 备份 `_backup_20260915_阶段3c3前\`（35 文件）在位。

**新增计划项④（同批完成）**：28 版式共性梳理 + B 方案可行性报告 → `references/B方案可行性报告.md`。结论：完整声明式不可行（数据块 20+ 变体、版式规模 28 个已稳定、行为大改）；骨架统一子集中等可行但收益有限；**B 方案不立项**，保留路线 A 声明头为"版式—字段"唯一真相源。

---

## 2026-09-15 · v2.4.46 —— 阶段3c-2（引擎结构清理：删死代码 + 拆大函数）

**删死代码**
- `_eink_template.py` 删 `_vwrap`（L1162，定义零调用；`_movewrap` 为真身，功能相同且被 14 处使用）。
- 注册表 DEAD/DEPRECATED 键 ↔ 引擎渲染读交叉核对：`信源`/`src_tag`/`img_pos` 引擎侧零引用（阶段1-2 清理干净）；`font`/`theme`/`讲稿题目(M01)`/`系列名(M02)` 等 11 处引用均为**有意的兼容回退链**（旧大纲可用），非死代码，保留。

**拆大函数（render_outline.py）**
- `build_lecture` 219 行 → 精简编排（~30 行）+ 6 个职责私有函数：
  `_apply_header_fields`（页头组装）/ `_warn_body_overflow`（溢出提示）/ `_apply_fit_mode`（L27 fit）/ `_apply_content_fields`（复合+新版式字段透传）/ `_apply_fixed_elements`（固定元件+全元件三控）/ `_inject_svg`（SVG 注入+同页多源报错）。
- `_BODY_WARN_CHARS` 提为模块级常量（原函数内局部）。

**顺句式（文档）**
- render_outline docstring：填空模板指针改指 `engine/generated/语法速查.md`（填空模板已删除）；删 `- 设计:` 行（DEPRECATED，页面内不得写，防教 DEAD 写法）。

**未动（有意克制）**
- `parse_outline`(182)/`apply_module`(178)/`lint_outline`(343)：解析/分发状态机，线性可读，拆分引入跨函数状态传递反而降可读性——留 3c-3 声明式化处理。
- kicker/frame 重复包装（27 处 `class="kicker" data-anim>` / 22 处 `class="frame"`）：提取收益打折（27 处调用点非全统一）、风险集中，3c-3 声明式化时自然统一。
- `_CSS` 单行超长字符串：主题样式字面量，非逻辑问题，改动风险>收益。

**验证**：render_baseline 17 份大纲产物**逐字节一致**（行为零变化）· 锚点 79/79 · guard（含 3c-1）全绿 · golden 零回归 · smoke 14/14 · 版本 2.4.46（SKILL+pyproject 同步）。备份 `_backup_20260915_阶段3c2前\`（33 文件）在位。

---

## 2026-09-15 · v2.4.45 —— 阶段3a + 3c-1（未知字段 lint 告警 + AST 双向 guard）

**3a 解析层未知字段告警（lint_outline.py）**
- 新增「未知顶层键」检查：引擎 parse_outline 不认识的字段行（所有正则分支不匹配 → 整行静默跳过），现显式告警「不是引擎认识的字段——整行被静默忽略」。合法键集 = META+PAGE+COMPOUND（M 前缀走 MODULE_RE 已有检查）。
- 新增「复合键子项未知键」检查：parse_compound_item 只认 subitems 键，未知子项键（如 stats 写 `num=5`）整项静默丢，现告警并列出合法子项键。
- 文末留痕区（三道闸/教师备注/配图设计说明等节）in_gate 状态机：自检产物列表行不作字段检查（第13讲「所用版式」误报修复）。
- 验证：16 讲 + 示例大纲 0 告警；构造负例（行大小/未知字段/num=5）三条全命中。

**3c-1 AST 双向 guard（check_engine_mounts.py，新建）**
- AST 静态扫描 `_eink_template.py` 全部 p_* 函数，提取 `s.get("键")`/`s["键"]` 消费键（对象作用域区分：s=大纲字段 / img=img 子键 / item·it·row·st·k·im=复合子项键 / 其余=内部键），与注册表 MOUNTS 双向比对。
- 正向（fail）：p_* 消费字段 ⊆ MOUNTS[版式] ∪ MOUNT_ALL ∪ 通用放行（svg:/svg_cap:、title 多义、KEY_NORM 同源集合 or 语义）；反向（人工清单）：MOUNTS 登记但 p_* 未直接消费 → 提示（M 字段/通用元件自动豁免）。
- 校准发现并登记：**L05 真别名「图文比例」**（引擎 p_grid2 双读 grid/图文比例，注册表此前漏登记——3a 会误报、guard 会漏查）；**MOUNTS L12 补 cap:**（p_figsvg 消费，此前漏登记）。其余 74 处初扫 fail 均为内部态键（m10_h/m10_v/三控应用等）与 KEY_NORM 归一化口径，非真缺口。
- 纳入 guard 日常门禁：check_docs_consistency.py 末尾调用，不一致即失败。
- 验证：正向 28/28 版式全绿；负例（删 L24 M10 / L12 cap: / L27 kpis:）三条全捕获。

**版本**：SKILL frontmatter + pyproject 2.4.44 → 2.4.45；语法速查重跑（新增图文比例键行）。

**验证**：锚点 79/79 · guard（含 3c-1）全绿 · golden（示例大纲 lint+渲染 + 16 讲 lint）零回归 · smoke 14/14。

---

## 2026-09-15 · v2.4.44 —— 验收收尾（挂载矩阵补缺 + _pptx_build 删除 + 文档清清爽爽）

**挂载矩阵补缺（workbuddy 验收抓出的真缺口）**
- 注册表 MOUNTS：L24/L25/L26/L27 补 **M10**（引擎阶段2 已补渲染、注册表未同步——引擎↔注册表不一致，四道门禁全漏的典型）；L05/L11 补 **svg:/svg_cap:**（原生 figure 图位）。
- 新增 **SVG_MOUNT_EXCEPT**（L21/L22 禁挂 lint 拦、L12b 静默丢）；速查 §9 输出 svg 通用图位说明行。
- 生成器 §4 复合键子项描述**不再截断**（stats accent"缺省由强调锚点推导"完整可见）。

**_pptx_build 删除（用户裁定）**
- engine/_pptx_build.py 删除；SKILL 工作流 5（转 PPTX 暂不可用）整节删、后续节重排；description/L14/L36 去 PPTX 声明；requirements/pyproject 删 python-pptx。

**文档清清爽爽**
- 速查头部删「版本：以 SKILL frontmatter 为准」行；「生成于」保留（每次重跑更新）。
- 模板规范：删头部版本句；L12 行「示意 figsvg」→「手绘示意」（与现行 `svg:` 字段口径一致）。
- 示例大纲：删「L19–L23 为 2026-09-11 新增的…」历史废话行；「斜杠即可换行（v2.4.39）」去版本号。
- pyproject version 2.4.32 → 2.4.44（与 SKILL frontmatter 同步）。

**guard 修复**
- 版本戳判定 `basename=="SKILL.md"` → `abspath==EINK_DIR/SKILL.md`（lecture 也叫 SKILL.md，此前被误标「权威」——workbuddy 抓出，判定不受影响但输出不可信）。

**验证**：锚点 78/78 · guard 全绿 · golden 全过 · smoke 14/14 · import 全检 OK · 16 讲 lint 零回归。

---

## 2026-09-15 · v2.4.43 —— 阶段1-2 治理（文档归位 + 引擎清理）

**文档归位（阶段1）**
- SKILL.md 大手术（1205 → 429 行）：删「大纲语法速查（唯一真相源）」内联段、「常见坑」、「强调锚点纪律」、「版本」节；新增「语法唯一源（指针）」与「示意图注入（SVG 协议）」；资源文件导览重写；「坑转做法」精简为「文档纪律」（字段用法段只许 ACTIVE 键、DEAD 键只存注册表与 CHANGELOG、已解决坑一律删除）。
- 示例大纲：删 93 行字段注释菜谱（含 img_pos 教学）、版本戳去重、字段权威指针改 generated/语法速查.md；**迁移 examples/ → engine/generated/**（golden 基线归属生成物目录）。
- **接口约定删除归位**：references/大纲制作接口约定.md 删除；46 处引用（lecture 正文 12 处 + eink 侧）改具体归位点；§2 完整选型表（含 L19-27 通用约定与 P0 数据约束）并入 lecture 第 5 步；§6 SVG 协议并入 eink SKILL「示意图注入」；其余节已在 lecture（互动/防空/三道闸/移交）。
- 生成物精简：gen_syntax_docs.py 只输出**语法速查（含挂载矩阵 §9）**；删除 generated/填空模板.md、版式字段说明.md、挂载矩阵.md；删除 templates/eink_大纲填空模板.md（与 generated 重复）。
- **版本单一源**：注册表删 SYNTAX_VERSION/ENGINE_VERSION/CONTRACT_VERSION；引擎删 __version__ 自报；权威版本 = SKILL.md frontmatter `version`；guard 版本检查改为「被管理文档不维护版本号（无戳=对齐指针式合法），出现版本号必须==权威」；lecture 对齐声明改版本指针。

**引擎清理（阶段2）**
- **figsvg 语法字段彻底删除**（捅到底）：注册表键、解析（render_outline 字段正则/透传/多源检查）、lint（FIGSVG_FIELD_RE/2c/10c 检查）、文档提及全删；L12 版式内部类型名保留（仅走 svg: 内联）；含 figsvg 的旧大纲将报「未登记键」。
- **img_pos 渲染读删除**（彻底）：_eink_template p_imagehero 不再读 img_pos/s.img_pos，object-position 固定 center center；注册表 DEAD 登记保留（lint 锚）；docstring 更新。
- **L24-27 M10 补渲染**：p_statement/p_timeline/p_microcard/p_imagehero 加 body（标题下、内容/图上）；BODY_NATIVE 例外注释删除；16 讲 lint/渲染零回归。

**验证**：guard 全绿（4 文档一致）；锚点 78/78；示例大纲 lint 0 错误；L24-27+M10 渲染实测 4/4 命中；16 讲 lint --strict 零回归（T27 全量复核）。

---

## eink-deck 历史（原 SKILL.md「版本」节，日期倒序）

| 版本 | 日期 | 一句话 |
|---|---|---|
| v2.4.42 | 09-15 | **二期收尾：注册表补录 + 引擎别名/版本自报/死代码清理 + 文档口径修正**：① 注册表 v1.1.0 新增 `MOUNTS` 挂载矩阵（28 版式×渲染层消费字段；核实 L24–L27 **不渲染 M10**——BODY_NATIVE 含但 p_statement/p_timeline/p_microcard/p_imagehero 不读 body）与 `MOUNT_ALL`，补录 `<size=数字>` 倍数/img_pos(DEAD)/title 别名口径/M11 通用语义/M12 img_slot/`图文比例` 别名；② 引擎 `nf` 认「图文比例」并归一化到 grid 键（渲染侧 p_grid2 本就双读）、模块级 `__version__` 自报（import 注册表 ENGINE_VERSION）、删除 src_tag 死透传；③ lint 新增「M12 文件 × svg: 同页共存」警告（引擎 _img_figure 优先 svg、M12 图被静默覆盖）；④ guard 新增版式清单完整性/字段⊆mounts/版本戳完整性三项；⑤ 生成器新增 `挂载矩阵.md` 生成物 + 统一版本戳区；⑥ 接口约定 v1.5.2、lecture 对齐声明、模板规范版式清单（补 L24–L27）同步。 [契约影响:否（无新渲染行为；图文比例别名仅补解析入口）] |
| v2.4.41 | 09-15 | **一期治理：语法唯一源工具链落地**：① 新增 `engine/syntax_registry.py` 语法注册表（三态 ACTIVE/DEPRECATED/DEAD，元数据/页面级键/模块/复合键/版式/枚举全量登记，锚点直指引擎函数），新增 `engine/check_syntax_anchors.py` 锚点自检（78 锚点全命中）；② lint 常量改从注册表导入（LAYOUT_CODES/RECIPES/SPLIT_FIELDS/STEP_OK_FIELDS 杜绝双份维护），MODULE_RE 支持全角冒号，**新增复合键子项前缀检查**（`stats:/steps:/rows:/imgs:/kpis:` 缩进子项缺 `- ` 前缀即报错——2026-09-15 第1-4讲 111 处事故的直接拦截器）、复合键带值检查、L27 img_mode/img.file 检查，清理 `_FIELDS_OK` 死集合，新增 `--strict` 门禁模式；③ 新增 `engine/check_docs_consistency.py` 文档↔注册表一致性 guard（示例大纲为真实语法基准，分级高置信/待确认/废弃提及；首跑清理 SKILL「设计指令」过时小节）；④ 新增 `engine/gen_syntax_docs.py` 文档生成器（语法速查/填空模板/版式字段说明三份生成物，机器生成·勿手改，改语法=改引擎+注册表→重跑）；⑤ 新增 `engine/golden_check.py` golden 门禁（示例大纲 lint --strict+渲染 + 16 讲 lint --strict 零回归）；⑥ **L27 配图建议区间校准 2.5:1～3.2:1 → 2.8:1～3.8:1**（用户实测 3.80:1 宽幅更佳，注册表 ENUMS 与示例 P28 同步）；⑦ 示例大纲行尾 `# 注释` 3 处修正（引擎不剥注释，注释写法不生效——golden 首跑抓到）。 [契约影响:否（不新增大纲语法；工具链与校验层）] |
| v2.4.40 | 09-15 | **L27 新增 fit 信息图模式**：① 新增 `img_mode: fit`——图区高度按图片真实宽高比自适应（`_img_size` 读文件头算 `aspect-ratio`，无留白不裁切不变形），build_lecture 在 `_prepare_local_images` 后解析路径读取；② **contain/fit 为信息图模式**：标题由「悬浮图顶」改为**落下方纸色区**（static，与 cap/KPI 同区，零遮挡），scrim 由 0–56% 渐变压暗弱化为顶部 0–16% 轻渐变（仅保 M01 眉标可读），深浅页标题文字色随所在区（深页纸色、浅页墨色，深页反相修复）；③ cover 悬浮模式行为不变（三档兼容，旧大纲零破坏）；④ 配图建议区间入文档：**横宽幅 2.8:1～3.8:1**（图区占屏约 55%–72%；用户实测 3.80:1 宽幅更佳），示例大纲 P28 加 fit 示例；⑤ SKILL 详解/示例、接口约定 v1.5.1 同步四档语法与配图建议。 [契约影响:是（img_mode 新增 fit + 信息图模式行为）] |
| v2.4.39 | 09-14 | **七项版式对齐修复**：① L27 深色玻璃底标题自动配纸色浅字（底字成套反相，深底不再深字）；② L19 修复条形整体消失（`margin-inline:auto` 在纵向 flex 交叉轴致 1fr 轨道坍缩为 0），改确定宽度 **68%＋居左**（`align-self:flex-start`）、深色页槽改纸色低透明；③ M07 副标题支持 `/` 换行（sub_lines 多行渲染，免复制两次）；④ L12b 链条、L10 引文框默认**标题区以下的内容空间内垂直居中、水平居中**（flex `margin-top:auto;margin-bottom:auto` 上下均分，非贴底、非绝对定位；不硬编码 top 值）；⑤ head-block 改 `flex:0 0 auto;min-height:22vh`——kicker 占空间/内容偏多时自动撑高、正文被推走不重叠；⑥ img-bottom 只作用 figure（`align-self:end`）、frame 恢复 stretch，左列不再被底对齐推下，L05 半幅列标题字号适配（4.5vw）防第二行挤出；⑦ L25 改 `align-items:stretch`＋title 预留两行高，横线平直、year/title/desc 左右对齐。 [契约影响:是（M07 换行 / L19 居左68% / L12b·L10 下半部分居中 / head-block·img-bottom·L25 对齐）] |
| v2.4.38 | 09-14 | **双基线后版式回退修复（8 问题收口）**：① 新增复合选择器 `.frame.center`（特异性高于 `.frame` flex-start），恢复封面/扉页/金句/收束垂直居中；② `_apply_dual` 跳过集合补 `interactive`——L17 不再被误清 center，问题与提示恢复居中、讨论标签缩回内容宽度（不再横向拉长）；③ L27 悬浮标题改**半透明玻璃底**（深浅页自适应 rgba＋背景模糊，替代不透明纸色块）；④ L19 三处：深色页数字自动转纸色、`scale: max` 显式归一化（解决 5.6 万亿小数裸计数被误判成 5.6%）、最长条默认封顶 **72%**＋图表限宽形成右侧留白；⑤ M13/M14 同时存在时合并 `.aux-row`（同一底部行两端对齐、统一虚线，免上下错层）；⑥ L12b 链条、L10 引文框默认贴下部；⑦ SVG 明确 viewBox 按内容包围盒收紧纪律。 [契约影响:是（新增 scale:max / 玻璃底 / aux-row / chain·callout 贴底）] |
| v2.4.37 | 09-14 | **双基线布局全局落地（垂直美学定稿）**：经四档校准（A/C/D→定稿），标题区与正文起线两条固定基线全局生效——① `.frame` `padding-top:3vh`（标题区距眉标）、新增固定高 `.head-block`（22vh，预留两行），标题字号统一 **5.4vw**；② **一行标题在标题区内上下居中（head-1）、两行标题顶对齐上下分布（head-2）**，由统一后处理函数 `_apply_dual` 自动把「kicker＋标题」包进 head-block，全部内页原语一次生效、免逐个改（L05 标题在栏内、单独处理）；③ 正文从标题区下沿约 **42vh** 固定线向下生长、下方自然留白（取代 v2.4.36 的"整组垂直居中"，基线固定、逐页视线零成本）；④ lint 新增「标题三行以上报错」；⑤ 封面/扉页/收束/L07/L24/L27 正确跳过；⑥ SKILL 双基线段、接口约定 v1.4.9、示例大纲、lecture 第5步同步语法用法。 [契约影响:是（新增 head-block 双基线机制 + 标题限两行 lint）] |
| v2.4.36 | 09-14 | **默认垂直平衡 + 页面级纵向/规则线/图对齐**：① 外层 `.frame` 默认 `justify-content:center`——内容在剩余空间垂直居中（少则悬浮留呼吸、填满则贴顶，免白名单）；L14 `.body-fill`、L16、L25 内容容器内部落位统一居中；② 新增页面级 `纵向: 顶/中/底`（离散落位，经 `_apply_frame_mods` 统一注入 frame 类）、`规则线: 是`（标题上方 accent 短横线，仅居左页、全系列一贯）、`图对齐: 底`（L05 坐底，挂 callout 时自动）；③ 补全 L05 页面级 `callout:/callout_src:` 的解析正则与 build_lecture 透传（v2.4.34 加 L05 callout 时白名单遗漏的既有缺口）；④ render_outline 修复 build_lecture 重建 slide 丢弃新键、lint 新增三键取值校验；⑤ SKILL「其它可选字段」、`examples/示例大纲.md` P05/P14、接口约定 v1.4.8 同步语法用法；⑥ 经 6／8vh 两档截图对比，**标题基线定为 `.frame` `padding-top:6vh`**——标题下移约"标题字高的一半"、与页眉留呼吸不顶天，标题位置每页固定成稳定基线，正文仍在标题以下剩余空间居中（不另升版本，并入本版）。 [契约影响:是（新增 纵向/规则线/图对齐 三键 + L05 callout 解析）] |
| v2.4.35 | 09-13 | **L27 图幅主导全出血重构 + side 竖图模式**：① 图改**全出血**铺到页面边缘（内容容器绝对定位、突破 slide padding），眉标白色浮于图顶（图顶渐变 scrim 保可读）、底部 foot 隐藏；② 标题由"通栏不透明纸条压底切断图"改为**居左悬浮纸色小块**；③ 新增 `img_mode: side` **竖图模式**（图占左 40% 全高、contain 不裁，右侧纵向排 title＋KPI），根治人民英雄纪念碑等竖图被横槽截成一小段；④ 新增 `img_pos:`（object-position，默认 center center）；⑤ SKILL 详解/示例、`examples/示例大纲.md`、接口约定 v1.4.7 同步三模式语法与用法。 [契约影响:是（新增 img_mode: side / img_pos 语法）] |
| v2.4.34 | 09-13 | **L24–L27 四版式 + 文档一致性纠错**：① 新增 L24 论断陈述／L25 横向时间轴／L26 微卡矩阵／L27 图幅主导 四个版式（含 yaml 示例与字段口径，吸 S03/S22 设计语言）；② L05 新增 `callout:`/`callout_src:` 页级引文框；③ 资源树示例注释「19 页」纠正为 28 页（覆盖 L01–L27＋L12b）；④「版本」节当前版本与 frontmatter 对齐为 2.4.34、补本条目（此前升号未同步正文/日志，已纠正）；⑤ 命名空间说明去日期闲词、L05 callout 口径去黑话；⑥ 补 L27 图幅主导 `kpis:` 复合子项解析——子项捕获白名单与 parse_compound_item 补 kpis 分支（v/l），修复 KPI 列此前不渲染，接口约定 L24–L27 强调命中规则同步补全。 |
| v2.4.33 | 09-13 | **4b-0 python 探测入执行路径（豆包侧交接单 §一）**：SKILL.md 工作流 4b 前新增「4b-0 · python 探测」小节——直接 `python package_deck.py` 时 PATH 首发常是 WorkBuddy 托管版（无 fonttools）→ 字体静默降级 CDN、产物不自包含；AI/命令行执行打包前必须先探测（`python -c "import fontTools…"`，失败改用系统 python），人工拖拽走 bat（内置探测首行打印 `python [fonttools OK]`）。根因此前只写在「常见坑」排查文档里、未进执行路径，本次补上。 [契约影响:否] |
| v2.4.32 | 09-12 | **bat 解释器钉死（ARC-9，工程审查收口）**：`00拖拽渲染`/`03自检` 原用 `where python` 取 PATH 首发，本机 PATH 首发为 Inkscape 捆绑 3.12.12（无 fontTools/Pillow/python-pptx），03 自检实机显示 `python : 3.12.12`，02 配图/01 打包/00 渲染行为不确定。修法：两 bat 改**优先系统 Python 绝对路径（装全工具链），缺失回落 PATH `python`**（兼顾其它机器），新增 `"%PY%" --version` 预检打印版本。`01交付打包`/`02压缩配图` 经 fontTools/Pillow 能力探测已自护、不取 PATH 首发，**先读码核实后判定无需改动**（修订前未盲目套"同病"假设）。纯 bat 改动，引擎零字节级回归（golden `index.html` 仍 `0cc01e5b3c…`/94096B）。 [契约影响:否] |
| v2.4.31 | 09-12 | **工程审查加固（第三方 AI 工程保障团队主理 + 实机 Python 3.13.15 验证，详见审查报告）**：① 🔴 SEC-1 `sanitize_svg()` 安全闸补强——原 docstring 承诺未兑现，实测 `<svg/onload=…>`/`href="javascript:alert('x')"`/`"java\tscript:"` 等 8 类绕过原样幸存；新增 `<tag/on…`→`<tag on…` 归一化 + 协议名容忍 tab/LF/CR + 双/单引号值改写，修复后 8/8 拦截、合法几何 SVG 与 `data:image/png` 逐字节不变；② ARC-1 `engine/_pptx_build.py` 末补 `__main__` 守卫，消除「exit 0/零输出/零产物」静默空跑（现 rc=2 + 说明）；③ 页面级字段全角冒号支持（批次2，10 处正则 `:`→`[：:]`）；④ 新增回归门禁 `scripts/golden_check.py`（整树逐文件 sha256 基线，示例 deck 零变更锁死）+ `tests/test_smoke.py`（14 用例，零依赖可裸跑，含 5 主题渲染断言）+ `bat/03自检-eink.bat`（双击即跑）；⑤ golden 离线字体子集归一化，跨机可比；⑥ SKILL.md 补 ARC-6 junction 依赖与自检工具说明。全部变更**零渲染回归**（golden `index.html` 仍 `0cc01e5b3c…`/94096B）。 [契约影响:否（仅放宽字段分隔符接受全角，不引入新语法）] |
| v2.4.30 | 09-11 | **新增 5 个版式（L19–L23）+ 动效 recipe 扩展**（老陈裁定，补图表/结构图/多图三处缺口）：① **L19 条形图**（`stats:` label/nb/unit/note，条宽∝nb/max，数字 rAF 递增）；② **L20 KPI 塔**（同单位可比 4 项，柱自底部 scaleY 拉起）；③ **L21 闭环图**（`steps:` 3-5 步，引擎自绘 SVG 环描线+节点序列点亮，🟥 本页禁挂 `svg:`/`figsvg:`）；④ **L22 系统同心圆**（`items:` 严格三层，引擎自绘，🟥 同禁 `svg:`）；⑤ **L23 多图证据墙**（**新开 `imgs:` 复合键** `file= / cap=`，复用单图同一套路径安全校验并逐张拷贝）。配套：新增 recipe `hbar`/`kpitower`/`loop`/`system`/`wall`；`_MOTION` 由单行 4593 字符转义串重构为 `r'''...'''` 多行（纯字面变换，渲染产物逐字节一致）；`render_outline.py` 图片拷贝循环把 `imgs:` 处理**前移**到单图逻辑之前（否则无单图页会被 `continue` 跳过导致一张不拷）；lint 新增 L19–L23 合法码与 L21/L22 同页多源拦截。回归：既有 19 版式 section 逐字节一致。 [契约影响:是] |
| v2.4.29 | 09-11 | **图片溢出裁切根治（影响所有图文同页 deck 宽屏显示）**：`_eink_template.py` 注入 CSS `.img-slot.has-img` 加 `min-height:0;flex-shrink:1`。根因：含图 figure 作 `.slide`（flex 列，100vh+overflow:hidden）子项时，默认 `min-height:auto` 取 img 自然高、阻止压缩，宽屏下「图+标题+说明」总高超 100vh 被 overflow:hidden 裁掉下半（img 本为 object-fit:contain，非裁切）。加后 figure 可在 flex 列内收缩到剩余空间，contain 保证整图完整；窄屏同样完整。修复前第2次课·中国国防历史与启示+现代国防观渲染产物已手工补同款（index.html L535）。 [契约影响:否] |
| v2.4.28 | 09-11 | **文档勘误（引擎代码未动，版本号不抬，wumai v1.1.4 兼容声明仍有效）**：① §687「一页一源」口径按引擎真实行为分两类——侧车/`svg:`/`figsvg:` 任意两个→`SystemExit`；L12b `items:` 与图源同页→引擎不报错但**静默丢弃 svg**、仅 lint 错误级拦截（与 v2.4.27 ②的 lint 行为一致，原文"四源任意两个即 SystemExit"与 `build_lecture()` 实测不符）；② 「一句话速记」"想画图→写 `设计:`"改为"想画图→页内写成品 `- svg:`（单行）"，与现行「写大纲即出图」流程对齐。 |
| v2.4.28 | 09-10 | **§7 改写为「SVG 示意图：两种载体」+ 正文清除废路批注**（老陈裁定「技能正文只写现行做法」）：① §7「设计（SVG 示意图）操作流程」原以"大纲写 `- 设计:` → 渲染前另画 SVG → 注入侧车"为主干，已与实际流程（写大纲即成图）脱节 → 改写为**载体 A 内联 `- svg:`（常规）／载体 B 侧车（不改大纲做临时覆盖时）**，技术细节（键名铁律／原始 SVG 字符串非 base64／加载顺序／配色铁律）全部保留并按载体重排；② 清正文里 8 处否定式/对照式表述（"不再是 `.py`""旧版只从大纲目录加载（事故）""历史通道…旧件兼容""旧版是侧车静默盖掉内联""已停用"等），**变更史归版本日志**；③ 侧车安全口径由"消除旧版 RCE 漏洞"改为正面陈述"**绝不 import/exec 任何 Python**"；④ 画布示例由 640×360 统一为 **640×360（16:9）**（与《接口约定》§6、lecture-outline-design §5b 一致）。 |
| v2.4.27 | 09-10 | **同页多源直接报错 + 一源化**（老陈裁定「同页多源直接报错」，配合上游 lecture-outline-design v1.4.0／接口约定 v1.3.0）：① `build_lecture()` 废除旧"三源优先级 侧车 > `figsvg:` > `svg:`"的**静默二选一**，改为**同页 ≥2 个图源即 `SystemExit`**并逐条列出命中源（侧车键／内联 `svg:`／`figsvg:`）——静默覆盖会让作者以为图已上屏、实则被吞；② `lint_outline.py`：`svg:` 空值/无 `<svg`/同页多条 由警告**升为错误**，新增 `figsvg:` 与 `svg:` 同页错误、**L12b（chain）页挂 `svg:` 错误**（chain 不渲染底部图位，会静默丢弃）；③ L12b 交叉校验改为**整页后置校验**（解决"`svg:` 行在 `- 版式:` 行之前"的顺序依赖漏检）；④ L12 表行的旧 `M12 文件:` 通道移除（历次已不再推荐）。**实测**：用真实输出目录渲染第1讲（侧车仍在）→ 报 `❌ 同页多源：讲次「第1讲」第 P03 页同时有 2 个图源`；第9讲 lint 出 1 条真实的 L12b 冲突（P29 chain + svg），其余 13 份零误报。 |
| v2.4.26 | 09-10 | **通用内联 SVG 字段 `- svg:` + 图注修复**（老陈裁定「图跟页走、零外部依赖」）：① 新增**任意版式通用**的 `- svg: <svg …>`（无 M 前缀），解析后直接进 `svg_inline` 走底部通用图位——与侧车等价但**不依赖外部 JSON**，页号随动；`figsvg:` 仍是 L12 专属。② 确立**三源优先级：侧车 > `figsvg:` > `svg:`**（实测：旧实现下 L12 同页 `figsvg`+`svg` 会让后者覆盖前者）。③ **修复底部通用图位丢图注**：`_bottom_elements` 此前只输出 `<figure>`、不输出 `svg_cap`，故 `L03/L08/L09/L14…` 等非 figure 版式挂图时**图注被静默丢弃**（figsvg / _img_figure 两分支各有 cap 逻辑，此处漏）——现补齐，与既有 `.svg-cap` 同样式。④ `lint_outline.py` 新增 `svg:` 三项校验（空值警告／无 `<svg` 错误／同页多条警告）。**A/B 实测**：既有 13 讲·41 侧车页全部走原生图位，字节级完全一致（改动零回归）；构造用例验证旧版丢图注、新版正确渲染。 |
| v2.4.25 | 09-10 | **L16 `M10 notes:` 分条修复 + 上游接口契约外置**（无破坏性改动）：① `_eink_template.py::p_statnote` 非分步路径此前**漏按 `/` `／` `、` 切分**，文档承诺的「`- M10 notes: 甲 / 乙` → 两块标牌」实际整串上屏（老陈实测发现）→ 补 `re.split`，实测 3 条各成一块；② 新增 `references/大纲制作接口约定.md`（版式选型表含 L08 条数与栅格规则／L06 行上限／L14 防空页、元件学生可见性表、`\|\|\|` 先问后揭、侧车 SVG 协议、移交自检），资源树与工作流 1 加入口，并立「改语法须同步该文档」纪律；③ 顺带纠正 L08 条数旧口径（归档模板写 2–4，现行 **2–6**，以引擎 `p_pillar` 为准） |
| v2.4.24 | 09-09 | **第三方评审修复**：① `02压缩配图-eink.bat` 末步写文件补 `if errorlevel 1` 错误检查（旧版把失败伪装成 Done）；② `prep_images.py` 修 `_trim_borders` 运算符优先级（加显式括号，不再靠 except 吞 None）、`_opt` 容错（`--max-edge` 后缺数值/跟 flag 不再 `int()` 崩溃，改告警用默认） |
| v2.4.24 | 09-09 | **第三方代码评审 + 3 处缺陷修复**（技能体检，v2.4.23→v2.4.24）：`02压缩配图-eink.bat` 末步写文件补 `if errorlevel 1`（失败不再伪装成成功）；`prep_images.py::_opt` 加参数容错（`--max-edge` 后跟 flag 不再 `int('--trim')` 崩）；`_trim_borders` 运算符优先级加显式括号。静态校验 + 关键交互核验 + 修前实测复现。护栏 51/51、19/19、24/24 全绿。 |
| v2.4.23 | 09-09 | **配图预处理脚本 `prep_images.py` + 拖拽 bat**（渲染前可选步骤，老陈裁定落地）：缩长边 ≤1920（只缩不裁）+ 统一转 **WebP**（照片 q80 / 线条图自动无损，更大则退回 q80）+ **同名同目录只换扩展名、原文件绝不删除** + 动图跳过 + **`--dry-run` 先出报告**；**脚本绝不改大纲**，只列出需同步的 `M12 文件:` 行（按「主干名+扩展名」精确匹配，**不误报 `M12 img_slot` 占位行**）。配套 `bat/02压缩配图-eink.bat`：探测带 Pillow 的 python（缺则报错退出，不静默降级）、**先干跑再由用户确认才写**——⚠️ 拖文件夹会处理其中所有图。第2讲实测：妇好钺 PNG 2.9MB → **336KB**（-88.7%），交付稿 2.45 → **2.32MB**。护栏 +T39/T40 |
| v2.4.22 | 09-09 | **交付稿去「大纲」修饰词**：`package_deck.py` 新增 `_delivery_stem()`——目录名去 `_eink` 后再去掉 `_大纲`/`-大纲`，`第2讲_大纲_eink` → **`第2讲.html`**（"大纲"是写作期概念，交付稿不该带）；删空则回退保留修饰词（绝不产出无名 `.html`）。文档写明**交付稿名跟随大纲文件名**，想要更多信息量应改大纲命名而非手改产物。护栏 +T38 |
| v2.4.21 | 09-09 | **字体内嵌静默降级修复**：打包日志原把"fonttools 未装"与"字体缓存为空"合并成一句，无法定位——实测老陈本机 PATH 上第一个 `python` 是 **WorkBuddy 托管版（无 fonttools）**，导致交付稿"中文字体没内嵌"却只给一句模糊提示（且**推翻此前"bat 用的 python = 系统 Python 3.13 有 fonttools"的结论**）。修法：① `package_deck.py` 拆成两种诊断并**打印 python 路径**；② 两个交付 bat 新增 **python 能力探测**——遍历常见安装路径挑第一个能 `import fontTools` 的，首行打印 `python [fonttools OK] : …`，找不到才降级并给修复命令；③ SKILL 4b 补"两个前提 + PATH 陷阱"，常见坑新增"字体没内嵌"排查。实测：探测选中系统 Python 绝对路径，第2讲重打包后四族字体（842KB）成功内嵌、单文件 5.75MB |
| v2.4.20 | 09-09 | **打包器补配图内联（P0 修复）**：`package_deck.py` 新增第 5 步——把产物 `images/` 下的真实配图转成 **data URI**，覆盖 `<img src="images/…">` 与 CSS `url(images/…)`。此前只内联了 JS 与字体，图片仍是相对路径，**交付稿一拷出产物目录就全部开天窗**（老陈实测第2讲：剪切到 E 盘根后车战/妇好钺两张图不显示）——「单文件自包含」的承诺在图片上是破的。顺带：内联步骤**刻意排在字体内嵌之后**（图片 base64 会污染字体子集字符集）；收尾校验新增 images/ 残留检测；单张 >1.5MB 告警建议压缩；仿渲染器做路径穿越防护。端到端验证：PNG/SVG 均内联成功，Edge `file://` 真机测 `naturalWidth>0` 显示正常，缺失图按设计保留并告警 |
| v2.4.19 | 09-09 | **通用拖拽 bat 入册 + bat 括号块纪律**：① 新增 `bat/00拖拽渲染-eink.bat`（拖大纲→渲染，内置 lint 不阻断、无 profile）与 `bat/01交付打包-eink.bat`（拖产物文件夹→单文件交付稿）——**位置无关**（共享目录+junction 兜底定位引擎），可拷到任何工作目录用；§2b 与资源树、工作流表同步；② **新 bat 纪律**：`if (...)` 括号块内 echo 禁未转义圆括号——cmd 整块先解析再判断，裸 `)` 提前闭合块 → `not was unexpected at this time` 闪退零输出（真实事故：交付 bat 第 34 行 `(ends with _eink)`，拖第2/3讲必闪退；修后第3讲端到端打包通过）；重复拖打包已验证幂等（index.html 不动、交付稿覆盖重生成）。护栏 W11/guard 同步 |
| v2.4.18 | 09-09 | **两步打包交付 + 大纲 lint + notes 分步**：① 新增 `engine/package_deck.py`——产物目录打包成单文件 `<大纲名>.html`（内联 motion+lucide 根治 file:// CORS、localStorage 守卫、字体子集内嵌含西文、锚点校验失败即退出），不改 build()；② 新增 `engine/lint_outline.py` 大纲守护（裸强调/`|||`错位/未知版式/缺图等 11 类，只报告不阻断；AI 流程必跑，拖拽渲染 bat 自动跑）；③ `M10 notes:` 支持 `|||` 分步（步内仍 `/` 分条，与正文同约定）；④ 常见坑 file:// 小节按 Edge 实证改写（WebGL/localStorage 不被拦，黑屏=浏览器禁 WebGL）。护栏 27→35 项全绿 |
| v2.4.17 | 09-09 | **离线字体开关（子集内嵌）**：大纲 `字体源: 本地` / `字体: 本地` / CLI `--offline-fonts` / profile `字体源: 本地` 任一触发；构建期用 fonttools 把本 deck 实际用字从本地 Noto SC 源 woff2/ttf 切子集、base64 内嵌进 index.html，产物自包含、断网不豆腐块；源字体缺失或 fonttools 未装则优雅回退 CDN 并告警（不崩）。配套 `engine/eink_assets/get_fonts.py` 一次性取源、`README_fonts.md` 说明。护栏新增离线相关检查（27→约 31 项全绿） |
| v2.4.16 | 09-09 | **行内弱化标记 `<dim>...</dim>`**（映射 `opacity:.5`，不用写死色值以免撞主题）；顺带修复 `<size=大>**粗**</size>` 嵌套丢内层标记的旧 bug（内层递归处理 + 保护区多趟还原）；「依赖全本地化」措辞写实为「**脚本**依赖全本地化」并写明字体实为 CDN 及其真实开销；**恢复丢失的 frontmatter**（WorkBuddy 只认 `name`+`description`，丢了技能即不可见）并新增 T20/T21 护栏锁住它。护栏 17 → 27 项全绿 |
| v2.4.15 | 09-08 | **语法文档重构（无引擎代码改动）**：按「写作者视角」重排大纲语法为 §0速览→§1元数据→§2骨架四角→§3版式与组件（**19 版式逐个全展开**）→§4组件用法→§5通用写法（斜杠/结构化/行内/三控/分步）→§6图片→§7可选字段→§8强调→§9明暗→§10速记；补实测漏项 `字体:` 元数据、`M06 行对齐`、`M10 分步优先于斜杠`、`M12 同页多条 last-wins`、`M12 图片来源已停用`；小节改用**名称锚点**（原编号引用已出现 2 处死链）；常见坑 14 组瘦身至 5 条纯排查；**「坑转做法」立为维护者纪律**；图片节不再重复三控。新增护栏 24 项先红后绿，既有 17/11 项回归全绿 |   |
| v2.4.14 | 09-08 | 文档口径收口（无引擎代码改动）：§工作流 5「转 PPTX」补 **⚠️ 暂不可用、现在勿跑** 并与 §这是什么/§常见坑 对齐（原只写"需 python-pptx"，与同文件三处"暂不可用·勿执行"自相矛盾，已导致派生技能 wumai-eink-engine 抄出可执行命令；实测未装库直接 `ModuleNotFoundError`，装了库也因 HTML→sections 解析器未接入仍不可用）。护栏 17 项仍全绿                                                                                                         |   |
| v2.4.13 | 09-08 | 外部审查收尾（细节项 N2/N3）：示例大纲 L12b 注释统一到裸词 `blank`（原示范 `blank=1`，易被误读为必须写 `=1`）；`validate()` emoji 检测补 U+2B00–2BFF 与零散码位（⭐⬛⭕ 原漏报），并**刻意排除 U+2190–21FF 箭头区**——引擎自用「→」作链条分隔符，纳入会每页误报。护栏扩至 17 项，先红后绿                                                                                                                                   |   |
| v2.4.12 | 09-08 | 外部审查第二轮修复（可观测性专题 R1–R4 + N1）：description 去掉「可转 PPTX」误承诺、三控覆盖面写实；大纲读取改 `utf-8-sig`（根治 BOM→讲次丢失→侧车 SVG 全丢）；侧车 JSON 非法/非字典显式告警（原静默吞异常）；`M10 字号` 显式告警并指路 `<size=大>`（原静默丢弃，与 M06/M08 对齐）；清理 `engine/__pycache__`。护栏 11 项先红后绿                                                                                                      |   |
| v2.4.11 | 09-04 | 第二轮外部审查（老陈裁批次 A/B/C + WebGL 选 A）：L12b 裸 `blank` 生效、M16 中文冒号+https 切分修复、侧车 svg_cap 恢复、`+3vh` 接受、尾随 \`                                                                                                                                                                                                                         |   |   | `剥离；**WebGL 双背景成套恢复**（CSS+canvas+GL 段三件套）；lucide 守卫 + 资产缺失告警；SKILL 措辞 4 处（M13 默认左 /`--serif-zh\` 正名 / M11 三控口径 / kraft emoji 风格约定） |
| v2.4.10 | 09-04 | 外部审查批次3/4/5：M08 方位词误吞、M11 空引文框、SVG 图位「水平」失效、figsvg+设计双渲染、块级数字倍数丢弃、M10 ‖‖‖+「/」告警；body_list 死代码清理、低功耗键去领域残留（含迁移）、补 `<head>`、注释与代码对齐 3 处、SKILL 措辞 3 处                                                                                                                                                                           |   |
| v2.4.9  | 09-04 | 恢复 deck 导航 JS（09-03 修复轮误删、从 09-02 产物抠回，黄金单测锁防再丢）；ratio 默认 auto 落到 4 个调用点；SKILL 四处矛盾修正（M02 范围 / L01 删 M14 / M11 三控限 L10 / 总讲次数=纯元信息）                                                                                                                                                                                          |   |
| v2.4.8  | 09-04 | P2 收敛（带测试锁）：em_html 全文替换、CSS 去重、占位 currentColor、正文溢出阈值实测校准、引擎维护纪律                                                                                                                                                                                                                                                            |   |
| v2.4.0  | 08-29 | 去领域污染（通用化整改）：移除内置词表 / 讲次推断，改 `- 块词表:` 可选、`--profile` 机制                                                                                                                                                                                                                                                                      |   |
| v2.4.6  | 08-23 | M12 maxh/ratio 穿透（竖版图可控 + 底部图位认命令）                                                                                                                                                                                                                                                                                           |   |
| v2.4.5  | 08-23 | 全局图位（路线2）：解除"侧车只在 figure 版式显示"硬限制                                                                                                                                                                                                                                                                                            |   |
| v2.4.4  | 08-22 | 常见坑补：侧车 SVG 只在 figure 版式显示（排查指引）                                                                                                                                                                                                                                                                                             |   |
| v2.4.3  | 08-21 | parse_split NameError 修复（L09 同行内联崩溃）                                                                                                                                                                                                                                                                                         |   |
| v2.4.2  | 08-21 | M12 maxh 失效修复（双拼单位 vhvh bug）                                                                                                                                                                                                                                                                                                 |   |
| v2.4.1  | 08-21 | 第9讲三修复：分步揭示不依赖 motion、L16 notes 缩进子项、模板/示例大补                                                                                                                                                                                                                                                                                 |   |
| v2.4    | 08-21 | 第三方 18 条评审修复（P0+P1）：accent 锚点、斜杠留白、页码回退、三控正则稳健                                                                                                                                                                                                                                                                               |   |
| v2.3    | 08-21 | 对外分发安全加固：侧车改 JSON、白名单、sanitize、路径防护、依赖本地化                                                                                                                                                                                                                                                                                    |   |
| v2.2    | 08-20 | 侧车归属改生成目录（防多讲覆盖）                                                                                                                                                                                                                                                                                                             |   |
| v2.1    | 08-20 | M08 默认两行居左·居右、split_kv 兼容冒号、pid 字母后缀                                                                                                                                                                                                                                                                                         |   |
| v2.0    | 08-19 | 引擎/模板/示例随 skill 分发；M05–M14 三控；M12 auto/contain；M10 分步揭示                                                                                                                                                                                                                                                                      |   |

---

## 接口约定历史（原《大纲制作接口约定》变更日志，2026-09-15 该文件删除归位后收编于此）

| 版本 | 日期 | 要点 |
|---|---|---|
| v1.5.2 | 2026-09-15 | **二期收尾口径修正（配合 eink-deck v2.4.42 / 注册表 v1.1.0）**：① L05 行补 `grid:`/`图文比例:` 双键等价（v2.4.42 起引擎 nf 认别名并归一化到 grid 键，渲染侧 p_grid2 本就双读——半实现别名补齐解析入口）；② L27 行删 `img_pos:`（引擎核实：渲染读但解析侧无入口，写了不生效，注册表登记 DEAD）；③ L19–L27 通用约定改——**L24–L27 不渲染 M10 正文**（BODY_NATIVE 含但原语不读 body，lint 拦截勿写）；④ M11 行改「通用页面级元件」（非 L07/L10 专用）；⑤ 头部三行同步。 [契约影响:否（不改渲染行为，仅口径修正 + 别名补解析）] |
| v1.5.1 | 2026-09-15 | **L27 信息图模式入契约（配合 eink-deck v2.4.40）**：① §2 选型表 L27 行改写——`img_mode` 四档 cover/contain/**fit**（新增·图区高度按图片真实宽高比自适应，无留白不裁切）/side；**contain 与 fit 为信息图模式：标题落下方纸色区（不再悬浮遮挡）、scrim 弱化为仅保顶部眉标可读**；② 新增 L27 fit/contain 配图建议区间 **2.5:1～3.2:1（横宽幅）**，太方（<2:1）图区过高挤没文字区、太宽（>3.5:1）图区过矮——分别改 cover/重构图；③ 头部三行同步。 [契约影响:是（img_mode 新增 fit + 信息图模式行为）] |
| v1.5.0 | 2026-09-14 | **v2.4.39 七项对齐修复入契约（对接面口径更新）**：① M07 副标题支持 `/` 切多行（sub_lines，免复制两次）；② L19 修复条形消失（`margin-inline:auto` 压坍 1fr 轨道）、改**居左宽 68%**、深色槽纸色低透明；③ L12b 链条／L10 引文框默认**标题区以下的内容空间内垂直居中、水平居中**（flex margin auto 上下均分，非贴底、非绝对定位；v2.4.39 PATCH）；④ head-block 改 `flex:0 0 auto;min-height:22vh`（kicker 占空间自动撑高、不重叠）；⑤ img-bottom 只作用 figure（frame 恢复 stretch，左列不再被推下）、L05 半幅列标题字号适配；⑥ L25 改 stretch＋title 预留两行，横线平直、year/title/desc 左右对齐。 [契约影响:是] |
| v1.4.9 | 2026-09-14 | **双基线布局入契约（配合 eink-deck v2.4.37）**：① §5 第一道机制由"默认垂直平衡（整组居中）"升级为**双基线**——标题区距眉标 3vh、固定预留两行高 22vh、字号 5.4vw，一行区内居中/两行顶对齐（引擎 `_apply_dual` 自动）；正文从约 42vh 固定线向下生长、下方自然留白；② 新增硬约束「标题最多两行，三行 lint 报错」；③ 列明不走双基线的版式（L01/L02/L15/L07/L24/L27）；④ 头部三行同步。 [契约影响:是（新增 head-block 双基线机制 + 标题限两行）] |
| v1.4.8 | 2026-09-14 | **默认垂直平衡 + 页面级纵向/规则线/图对齐（配合 eink-deck v2.4.36）**：① §5 新增第一道防空机制——`.frame` 默认 `justify-content:center`，内容在剩余空间垂直居中（少则悬浮、满则贴顶，免白名单）；② 新增页面级 `纵向:顶/中/底`（离散落位）、`规则线:是`（标题上方 accent 短横线，仅居左页、全系列一贯）、`图对齐:底`（L05 坐底，挂 callout 时自动）；③ 补全 L05 页面级 `callout:/callout_src:` 的解析与透传（v2.4.34 加 L05 callout 时解析白名单遗漏的既有缺口）；④ 头部三行同步；旧 `Mxx 垂直:` 数值三控保留微调、不冲突。 [契约影响:是（新增 纵向/规则线/图对齐 三键 + L05 callout 解析）] |
| v1.4.7 | 2026-09-13 | **L27 全出血重构 + side 竖图模式（配合 eink-deck v2.4.35）**：① §2 选型表 L27 行改写——图全出血、标题居左悬浮，`img_mode` 三档 cover/contain/**side（新增竖图模式：图占左 40% 全高不裁、右侧纵向 title＋KPI）**，新增 `img_pos:`（object-position，默认 center center）；② 头部契约版本/最后核验/契约影响三行同步；③ L27 眉标白色浮于图顶、底部 foot 隐藏。 [契约影响:是（新增 img_mode: side / img_pos）] |
| v1.4.6 | 2026-09-13 | **新增 L24–L27 四个版式 + L05/L07/L13/L16/L19 修订（对接面扩展，配合 eink-deck v2.4.34）**：① §2 选型表加 4 行——L24 论断陈述（单句定调，`statement:`＋`sub:`，衬线粗体/强左轴/大留白/发丝线，吸收 S03 之魂但不用瑞士细体）、L25 横向时间轴（`items:` `year/title/desc`，1px 线＋方节点＋等宽年份，轻于 L06/L12b）、L26 微卡矩阵（`items:` `main/sub`，3×2，一处 accent）、L27 图幅主导（`img:`＋`title`＋`cap:`＋`kpis:`，上 60% 图＋纸色标题块＋3 列 KPI）；② L05 增三档比例 `grid:`/`图文比例:`（6:6/7:5/8:4，竖图自动 8:4）＋可挂 `callout:`；L07 默认暗底＋短/标/长三档字号；L13 步骤 `data-anim="step"` 逐个点亮（修复整页压灰）；L16 降级为非衬线/左轴/发丝线、首末 accent；L19 增 `scale:`/`whitespace:` 双留白模式；③ §2「L19–L23 通用约定」扩为「L19–L27」，补 L24–L27 同为自包含原语、登记 `BODY_NATIVE`。 [契约影响:是] |
| v1.4.5 | 2026-09-13 | **真实图入契约 + 移交清单去占位**（配合 lecture-outline-design v1.7.0 新增 §5c，豆包侧交接单 §二）：① §3 元件表 `M12 配图` 行补真实图指引——「真实图流程见 lecture-outline-design §5c（下载→压缩→M12→M14，渲染交付前不得带占位）」；② §7 移交清单「`img_slot` 已补图或标注待补来源」→「🟥 已全部补成真实图（不得残留占位）；真实图均存 images/、经 prep_images 压缩、`M12 文件:` 引用、M14 标信源」；③ 最后核验 eink-deck 前移 v2.4.33。 [契约影响:否（不新增语法，仅口径补全）] |
| v1.4.4 | 2026-09-11 | **新增 L19–L23 五个版式（对接面扩展）**（老陈裁定，补 eink 三处缺口：无真图表 / 缺结构图 / 一页只能一张图）：① §2 选型表加 5 行——L19 条形图（`stats:`，条宽∝nb）、L20 KPI 塔（`stats:`，柱高∝nb）、L21 闭环图（`steps:`，引擎自绘 SVG）、L22 系统同心圆（`items:`，限三层，引擎自绘）、L23 多图证据墙（**新开 `imgs:` 复合键** `file= / cap=`）；② L21/L22 图形由引擎生成，**本页禁挂 `svg:`/`figsvg:`**（同页双图源）；③ 新增 **P0 原则「版式必须匹配内容的数据类型」**——图表版式只承载同单位可比量化数据，严禁给概念列举编造数值；④ 消费方只把「对齐契约」声明行的版本号前移，**不在正文散抄 eink 版本号**。 [契约影响:是] |
| v1.4.3 | 2026-09-11 | **画布标准回归 640×360（16:9）**（老陈裁定，用户主动将武脉千年档案改回 640×360 并改日志）：§6 画布建议由 680×340（2:1）改回 640×360（16:9），与 eink-deck SKILL §7（L241/L957 一贯推荐 640×360）一致；示例大纲 P12 与第1讲大纲 3 处 SVG viewBox 同步改 640×360（`<g transform="scale(0.941,0.941)">` 包裹保形）。此前 680×340 系 09-10 清理口径，非用户本意。 |
| v1.4.2 | 2026-09-11 | **稿2 交叉审查修复**：① §1 元数据补齐必填标记——系列名/总讲次数标(必填)、主题/字体标(可选)，与引擎必填 4 项口径一致；② **同页多源口径按引擎真实行为分两类**（§2 表行、§6 硬规则、§7 移交清单）：侧车/`svg:`/`figsvg:` 任意两个→引擎报错；L12b `items:` 与图源同页→引擎不报错但**静默丢弃 svg**、仅 lint 错误级拦截。 |
| v1.4.1 | 2026-09-11 | **稿1 核对整改（上轮改版未留日志，本行补记）**：§1 顶部元数据补 `总讲次数`；§5 防空页 #4 阈值显式化（同类型页连续不得超 2 页，与 lecture-outline-design v1.5.1 一致）。 |
| v1.4.0 | 2026-09-10 | **第 6 节改名「示意图注入：页面内联 `svg:`」+ 清否定式表述**（配合 eink-deck v2.4.28，老陈裁定「技能正文只写现行做法」）：① 标题与表格不再用"现行／旧件／仅默认"这类对照语，两通道改为「A 内联（常规）／B 侧车（可选）」并直接写各自适用场景；② 删"旧流程已废止""旧三源优先级已废除"等 3 处废路批注（变更史归本表）；③ 画布尺寸统一为 **680×340（2:1）**；④ 第 2 节 L08 行删「旧模板规范写 2–4 根已作废」对照句。 |
| v1.3.0 | 2026-09-10 | **示意图流程改"写大纲即出图"、同页多源直接报错**（配合 eink-deck v2.4.27，老陈裁定）：第 6 节改写为「现行 = 页面内联 `- svg:`」——① **同页多源直接报错**（侧车 / `svg:` / `figsvg:` / L12b `items:`）；② 补 `- svg:` **必须单行**铁律（逐行解析器只取第一行，多行静默截断）；③ 侧车降为可选通道。 |
| v1.2.0 | 2026-09-10 | **新增通用内联 SVG 通道**（配合 eink-deck v2.4.26）：第 6 节由「`设计:` 与侧车协议」改写为「示意图注入：两条通道」——**A 内联 `- svg:`（推荐默认，任意版式通用、零外部依赖、页号随动）／ B 侧车（临时覆盖用）**，并确立**三源优先级 侧车 > `figsvg:` > `svg:`**；第 3 节补图注 `svg_cap:` 现所有版式都渲染。 |
| v1.1.2 | 2026-09-10 | **纠正侧车值口径**（第 6 节）：明确**值是原始 SVG 字符串、不是 base64**（eink-deck SKILL.md 第 7 节的 JSON 示例曾写 base64，系历史遗留错误，2026-09-10 核 `_load_svg_overrides()` 代码后已在两侧同时纠正）。另补两条防坑：画图前须先 grep 该页版式（只对会显示图的页写键），侧车应**在大纲定稿后**再做（键含页号，页号漂移会致 SVG 错位或被吞）。 |
| v1.1.1 | 2026-09-10 | **补元数据护栏**（老陈发现"大纲前面的元数据被清掉"）：第 1 节明确顶部元数据 6 行必须留顶、`讲次=—` 为硬警报、整文件覆盖前须先取回旧头；第 8 节闸三补"整文件覆盖须先存快照 + 写后比对头部/页数/`讲次`"。事故还原：重做大纲时用 `Write` 整文件覆盖，只从 `### P01` 起手，漏带元数据头与"本讲设计说明"引用块，渲染报 `讲次=—` 未被重视。 |
| v1.1.0 | 2026-09-10 | 新增**第 8 节 交付前三道闸**（闸一反向覆盖／闸二顺序单调／闸三技能依赖＋影响面清单）。依据第2讲实跑暴露的三类漏检——整段漏落、时间倒序、联动失配，均为"流程里不存在的步骤"。老陈裁定加固。 |
| v1.0.1 | 2026-09-10 | **纠错**：L08 支柱条数上限原写「4 根」，系抄自 2026-08-29 归档的旧模板规范；核引擎 `p_pillar` 与现行 SKILL.md 确认为 **2–6 根**（4→4 列、2→2 列、其余 3 列自动换行，6 根＝3×2）。同步改 L12b 与 L08 的选型建议（d= 较长者用 L08 而非 L12b）。 |
| v1.0.0 | 2026-09-10 | 首版。版式选型表（L06 行数上限、L14 防空页）、元件可见性表、互动"先问后揭"、侧车协议、移交自检。依据：第2讲实跑三重校验 + 外部二轮审查两稿 + 老陈三项裁定（接口文档放 eink 侧／SVG 侧车选 B／互动放宽）。 |
