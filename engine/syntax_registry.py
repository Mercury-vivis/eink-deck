# -*- coding: utf-8 -*-
"""syntax_registry.py —— 大纲语法注册表（引擎语法的显式化快照；版本以 eink-deck/SKILL.md frontmatter 为准）
================================================================================

定位
----
引擎代码是语法的唯一真相源（parse_outline / apply_module / build_lecture /
_eink_template 版式原语）。本文件是这份真相的【显式化快照】，供三类消费方使用：

  1. lint_outline.py —— 常量从本文件导入（LAYOUT_CODES / MODULE_CODES / RECIPES /
                        SPLIT_FIELDS / STEP_OK_FIELDS 等不再双份维护）；
  2. 一致性 guard    —— 文档（示例大纲 / 语法速查 / SKILL / 模板规范）中
                        出现的语法键必须 ∈ 本注册表且状态 ACTIVE；
  3. 文档生成器      —— 从本文件生成语法速查.md
                        （人工文档降级为生成物；生成物标注「机器生成·勿手改」）。

三态定义
--------
  ACTIVE     现行语法：文档生成器输出、guard 要求文档可引用、lint 校验写法。
  DEPRECATED 引擎仍解析但方法论文档禁止/不推荐（仅兼容旧大纲）：guard 允许旧
             文档提及，但新文档生成器不输出为推荐写法。
  DEAD       引擎残留（解析无入口 / 渲染忽略）：文档生成器不输出，guard 检出即报。

更新纪律
--------
  改引擎语法后必须同步本文件；同步动作由 guard 的 --verify-anchors 辅助
  （锚点串须能在引擎文件中检索到；查不到即提醒锚点漂移或引擎已改）。

字段说明
--------
  每个语法项统一携带：status / 锚点 anchor（"文件.函数:分支"）/ 语义 semantics /
  取值约束 constraint（可空）/ 版式范围 layouts（可空，None=全版式可挂）。

派生物（禁手改）
----------------
  MOUNTS（挂载矩阵）与 LAYOUT_TYPES（版式码→type）由 gen_mounts.py 从引擎声明
  自动生成（_generated_mounts.py）。MOUNTS 真源 = _eink_template.py 各 p_* 的
  _MOUNT 声明；LAYOUT_TYPES 真源 = render_outline.py 的 LAYOUT_MAP。
"""
from _generated_mounts import MOUNTS, LAYOUT_TYPES

# =====================================================================
# A. 顶部元数据（meta）
# =====================================================================
# required: True = lint/渲染必需；False = 可选
META_KEYS = {
    "讲次": {
        "status": "ACTIVE", "required": True,
        "anchor": "render_outline.build_lecture:讲次",
        "semantics": "讲次编号（第X讲）。参与侧车复合键「讲次/页号」；缺失时渲染行显示 讲次=— 且侧车退化为纯页号键。",
        "constraint": "含数字即可；推荐「第N讲」",
    },
    "讲稿题目(M02)": {
        "status": "ACTIVE", "required": True,
        "anchor": "render_outline.build_lecture:讲稿题目",
        "semantics": "讲稿题目（正文页右上眉标；M02 是题目专用号）。",
        "constraint": "标题文本；勿与 M01（逐页运行眉标）混淆",
    },
    "系列名": {
        "status": "ACTIVE", "required": True,
        "anchor": "render_outline.build_lecture:系列名",
        "semantics": "系列课程名（生成 series_name）。",
    },
    "总讲次数": {
        "status": "ACTIVE", "required": True,
        "anchor": "render_outline.build_lecture:总讲次数",
        "semantics": "本系列总讲数（series_total）；缺省回退为实际页数。",
        "constraint": "正整数",
    },
    "主题": {
        "status": "ACTIVE", "required": False,
        "anchor": "render_outline.build_lecture:主题",
        "semantics": "主题预设（theme；可被 --profile 覆盖）。",
        "constraint": "5 套主题名之一，见 eink SKILL 主题节",
    },
    "字体": {
        "status": "ACTIVE", "required": False,
        "anchor": "render_outline.build_lecture:字体",
        "semantics": "字体基调 serif/sans，或快捷写法 本地/离线 触发离线嵌入（回落默认衬线）。",
        "constraint": "serif | sans | 无衬线 | 本地 | 离线 | local | offline",
    },
    "字体源": {
        "status": "ACTIVE", "required": False,
        "anchor": "render_outline.build_lecture:字体源",
        "semantics": "独立触发离线嵌入（不干扰基调）。",
        "constraint": "本地 | 离线 | local | offline",
    },
    "字体本地": {
        "status": "DEPRECATED", "required": False,
        "anchor": "render_outline.build_lecture:字体本地",
        "semantics": "旧写法兼容：engine meta.get 兜底消费（`字体源` 缺失时回落）；新大纲写「字体: 本地/离线」或「字体源:」。",
        "constraint": "本地 | 离线 | local | offline",
    },
    "字体基调": {
        "status": "ACTIVE", "required": False,
        "anchor": "render_outline.build_lecture:字体基调",
        "semantics": "离线时另指定基调。",
        "constraint": "serif | sans",
    },
    "讲次类型": {
        "status": "ACTIVE", "required": False,
        "anchor": "render_outline.__main__块:讲次类型",
        "semantics": "讲次性质描述（仅在渲染日志显示）。",
    },
    "块词表": {
        "status": "ACTIVE", "required": False,
        "anchor": "render_outline.build_lecture:块词表",
        "semantics": "M03 前段受控校验词表（以 /、顿号等分隔）；不写则不校验。通用引擎不内置任何系列专属词表。",
    },
    # 兼容别名（历史大纲可用，新大纲不推荐）
    "讲稿题目": {"status": "DEPRECATED", "anchor": "render_outline.build_lecture:讲稿题目", "semantics": "旧写法（未带 M02 后缀），仍兼容。"},
    "系列名(M02)": {"status": "DEPRECATED", "anchor": "render_outline.build_lecture:系列名", "semantics": "旧写法，仍兼容。"},
    "讲稿题目(M01)": {"status": "DEPRECATED", "anchor": "render_outline.build_lecture:讲稿题目", "semantics": "旧写法，仍兼容。"},
    "font": {"status": "DEPRECATED", "anchor": "render_outline.build_lecture:字体", "semantics": "字体 的英文别名，仍兼容。"},
    "theme": {"status": "DEPRECATED", "anchor": "render_outline.build_lecture:主题", "semantics": "主题 的英文别名，仍兼容。"},
}

# =====================================================================
# B. 页面级键（顶层 `- 键:`，无 M 前缀）
# =====================================================================
# layouts: 受限版式列表；None = 任意版式可挂
PAGE_KEYS = {
    "版式": {
        "status": "ACTIVE", "required": True,
        "anchor": "render_outline.parse_outline:版式",
        "semantics": "声明本页版式（28 选 1）；未写/写错按 raw 兜底渲染。",
        "constraint": "L01–L27 或 L12b（见 LAYOUTS）",
    },
    "强调": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_outline:强调",
        "semantics": "强调锚点词（[ ] 内逗号分隔）；正文命中即套 accent 色。裸短语缺方括号会被整行静默丢弃。",
        "constraint": "必须 [词1, 词2] 形式；锚点词须出现在当页可见文字中；单页 ≤3 处",
    },
    "data_animate": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_outline:data_animate",
        "semantics": "局部动效覆盖（覆盖版式默认 recipe）。拼错/带连字符会静默退化为无入场动画。",
        "constraint": "10 选 1：cascade/hero/quote/directional/pipeline/hbar/kpitower/loop/system/wall（见 ENUMS.recipes）",
    },
    "数据_animate": {"status": "ACTIVE", "anchor": "render_outline.parse_outline:data_animate", "semantics": "data_animate 的中文别名，等价。"},
    "数据animate": {"status": "ACTIVE", "anchor": "render_outline.parse_outline:data_animate", "semantics": "data_animate 的中文别名，等价。"},
    "tag": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_outline:tag",
        "semantics": "L17 互动标签（学生可见提示，如「猜一猜」）。禁写「互动 ①」等内部编号。",
        "layouts": ["L17"],
    },
    "center": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_outline:center",
        "semantics": "L21 闭环图环中心词（省略默认「闭环」）。",
        "layouts": ["L21"],
    },
    "left(M09+body)": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_outline:left",
        "semantics": "L09 左栏（M09 栏标题 + body 要点；同行内联或空值+缩进子项）。裸 left:/right: 整行被忽略。",
        "layouts": ["L09"],
        "constraint": "同行写 title / 要点；或空值 + 缩进 `- M09 h_md:` 与 `- body:` 子项",
    },
    "right(M09+body)": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_outline:right",
        "semantics": "L09 右栏，同上。",
        "layouts": ["L09"],
        "constraint": "同行写 title / 要点；或空值 + 缩进子项",
    },
    "svg": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_outline:svg",
        "semantics": "通用内联示意图（唯一推荐通道）。值必须是单行完整 <svg …>…</svg> 字符串；多行会被逐行解析器截断静默丢弃。",
        "constraint": "单行；值以 <svg 开头；一页一源（与侧车共存即 SystemExit）；画布上限 640×360；配色 currentColor / var(--accent)",
    },
    "svg_cap": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_outline:svg_cap",
        "semantics": "示意图图注（所有版式都渲染）。示意类配「概念示意 · 非精确」。",
    },
    "meta-row": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_outline:meta-row",
        "semantics": "封面元信息行（以 · 分隔多项）。",
    },
    # —— 新版式字段（L24–L27 + L05 grid + L19 scale/whitespace） ——
    "statement": {"status": "ACTIVE", "anchor": "render_outline.parse_outline:nf", "semantics": "L24 论断正文。", "layouts": ["L24"]},
    "text": {"status": "ACTIVE", "anchor": "render_outline.parse_outline:nf", "semantics": "L24 论断正文别名（与 statement 等价）。", "layouts": ["L24"]},
    "sub": {"status": "ACTIVE", "anchor": "render_outline.parse_outline:nf", "semantics": "L24 论断下方补充行。", "layouts": ["L24"]},
    "lead": {"status": "ACTIVE", "anchor": "render_outline.parse_outline:nf", "semantics": "L24 补充行别名（与 sub 等价）。", "layouts": ["L24"]},
    "cap": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_outline:nf",
        "semantics": "图注（L27 图注 / L12 svg 图注共用字段）。",
        "layouts": ["L27", "L12"],
    },
    "grid": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_outline:nf",
        "semantics": "L05 三档比例（6:6/7:5/8:4，竖图自动 8:4）。中文别名「图文比例」引擎 nf 认（渲染侧 p_grid2 双读 grid/图文比例）。",
        "layouts": ["L05"],
    },
    "图文比例": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_outline:nf",
        "semantics": "grid 的中文别名（渲染侧 p_grid2 双读 grid/图文比例；解析侧 nf 归一化到 grid 键）。",
        "layouts": ["L05"],
    },
    "scale": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_outline:nf",
        "semantics": "L19 显式归一化（scale: max 解决小数裸计数被误判为百分比）。",
        "layouts": ["L19"],
        "constraint": "max（小数裸计数/最大值≤100 非百分比时必写）",
    },
    "whitespace": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_outline:nf",
        "semantics": "L19 留白控制（N 调、0 顶满）。禁用 margin-inline:auto（会压坍 1fr 轨道致条消失）。",
        "layouts": ["L19"],
    },
    "img_mode": {
        "status": "ACTIVE",
        "anchor": "render_outline.build_lecture:img_mode",
        "semantics": "L27 图适配模式：cover=裁切填满·标题悬浮；contain=不裁·标题落下方；fit=图区按图片真实宽高比自适应·标题落下方；side=竖图占左 40%。",
        "layouts": ["L27"],
        "constraint": "cover | contain | fit | side（见 ENUMS.img_mode）；fit/contain 配图建议横宽幅 2.8:1–3.8:1",
    },
    "title": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_outline:nf",
        "semantics": "L27 标题（cover 悬浮 / contain·fit 落下方）。别名口径：裸 `- title:` 与 `- M08 h_xl:` 等价（nf/M08 都写 cur「title」，build_lecture 统一取用）。",
        "layouts": ["L27"],
    },
    "callout": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_outline:nf",
        "semantics": "L05 页级引文框（左栏挂 callout 时右图自动坐底）。",
        "layouts": ["L05"],
    },
    "callout_src": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_outline:nf",
        "semantics": "L05 引文框出处。",
        "layouts": ["L05"],
    },
    # —— 页面级落位 ——
    "纵向": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_outline:纵向",
        "semantics": "页面内容垂直落位（覆盖双基线默认）。非法值静默沿用默认居中。",
        "constraint": "顶 | 中 | 底",
    },
    "规则线": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_outline:纵向",
        "semantics": "标题上方 accent 短横线（仅居左页、全系列一贯）。",
        "constraint": "是 | 否",
    },
    "图对齐": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_outline:纵向",
        "semantics": "L05 图垂直对齐（默认顶对齐）。",
        "layouts": ["L05"],
        "constraint": "底 | 顶",
    },
    "img.file": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_outline:img.file",
        "semantics": "L27 配图路径（点号键，进 img 字典；与 M12 文件 同语义但走 L27 原语）。",
        "layouts": ["L27"],
        "constraint": "images/ 相对路径（安全校验：拒绝对路径与目录穿越）",
    },
    # —— 复合键 ——
    "items": {"status": "ACTIVE", "anchor": "render_outline.parse_outline:复合字段", "semantics": "复合子项列表（L08 支柱/L12b 链/L18 字源/L25 时间轴/L26 微卡）。空值 + 缩进子项；带值会被静默忽略。"},
    "stats": {"status": "ACTIVE", "anchor": "render_outline.parse_outline:复合字段", "semantics": "复合子项列表（L04 数据大字报/L19 条形图/L20 KPI 塔）。空值 + 缩进子项。"},
    "steps": {"status": "ACTIVE", "anchor": "render_outline.parse_outline:复合字段", "semantics": "复合子项列表（L13 进程/L21 闭环图）。空值 + 缩进子项。"},
    "rows": {"status": "ACTIVE", "anchor": "render_outline.parse_outline:复合字段", "semantics": "复合子项列表（L06 年表）。空值 + 缩进子项。"},
    "imgs": {"status": "ACTIVE", "anchor": "render_outline.parse_outline:复合字段", "semantics": "复合子项列表（L23 多图证据墙）。空值 + 缩进子项；逐张安全校验并拷贝。"},
    "kpis": {"status": "ACTIVE", "anchor": "render_outline.parse_outline:复合字段", "semantics": "复合子项列表（L27 KPI，最多 3 个）。空值 + 缩进子项。"},
    # —— DEPRECATED / DEAD 页面级键 ——
    "设计": {
        "status": "DEPRECATED",
        "anchor": "render_outline.parse_outline:设计",
        "semantics": "给画图助手的指令占位（渲染为待设计占位）。lecture 方法论已禁止页面内写占位行；新流程写大纲即出图。",
    },
    "示意": {"status": "DEPRECATED", "anchor": "render_outline.parse_outline:设计", "semantics": "设计 的别名。"},
    "::design": {"status": "DEPRECATED", "anchor": "render_outline.parse_outline:设计", "semantics": "设计 的别名。"},
    "信源": {
        "status": "DEAD",
        "anchor": "render_outline.parse_outline:信源",
        "semantics": "页脚信源 tag 已停用；引擎安全忽略该行。",
    },
    "src_tag": {
        "status": "DEAD",
        "anchor": "render_outline.build_lecture:src_tag",
        "semantics": "无入口的引擎残留（2026-09-15 二期已从 build_lecture 删除透传）；文档不得引用。",
    },
    "img_pos": {
        "status": "DEAD",
        "anchor": "_eink_template.p_imagehero:img_pos",
        "semantics": "L27 object-position 微调：解析侧 nf/vmk/cmp/mf 均无入口；渲染读已于 2026-09-15 阶段2 删除（彻底）——写了不生效（DEAD；文档不得引用）。",
    },
}

# =====================================================================
# C. 模块字段 M01–M16
# =====================================================================
# fields: {子字段前缀: {status, semantics, constraint}}；"" = 裸字段（`- Mxx: 值`）
# 三控（字号/垂直/水平）由 _three_ctrl 统一消费，不逐项登记
MODULE_FIELDS = {
    "M01": {"desc": "顶左眉标（逐页运行标签）", "fields": {"": "本页运行眉标：封面=第X讲·讲题／扉页=第X块·块名／内页=本页短标签；不填隐藏"}},
    "M02": {"desc": "讲稿题目（元数据层专用）", "fields": {}, "note": "仅在顶部元数据出现（讲稿题目(M02)），页面内无 M02 字段。"},
    "M03": {
        "desc": "底左块标签", "fields": {
            "": "[块名] · [本页概括]；简写 `- M03: 块·内容` 亦通；前段可被 块词表 受控校验。禁写「本讲结论一」等内部批注",
        }},
    "M04": {"desc": "右下页码", "fields": {}, "note": "引擎自动生成 位置/总页数，不写。"},
    "M05": {
        "desc": "内容区眉标 kicker", "fields": {
            "": "kicker 文本（通常空）；勿放系列名或顶左眉标",
        }, "controls": "字号/垂直/水平", "anchor": "render_outline.apply_module:M05"},
    "M06": {
        "desc": "主标题 h_hero（L01/L02/L15）", "fields": {
            "": "大字主标题；含「/」拆多行（title_lines）",
            "行对齐": "逐行对齐（如 居左·居右）",
            "对齐": "逐行对齐别名",
            "垂直": "垂直平移",
            "水平": "水平平移",
        },
        "controls": "垂直/水平（字号不支持，写了告警并忽略）", "anchor": "render_outline.apply_module:M06"},
    "M07": {
        "desc": "副标题 h_sub", "fields": {"": "副标题；含「/」拆多行（sub_lines）"},
        "controls": "字号/垂直/水平", "anchor": "render_outline.apply_module:M07"},
    "M08": {
        "desc": "内页主题句 h_xl", "fields": {
            "": "结论句；含「/」拆多行；裸字段值若为对齐词（居中/居左/居右/中/左/右）按对齐指令处理",
            "行对齐": "逐行对齐（如 居左·居右）",
            "行大小": "逐行字号（如 小·大）",
            "行字号": "行大小 别名",
            "对齐": "整体对齐 token",
            "垂直": "垂直平移",
            "水平": "水平平移",
        },
        "controls": "垂直/水平/行大小/行对齐（整体字号不支持，写了告警并忽略）",
        "anchor": "render_outline.apply_module:M08",
        "constraint": "标题最多两行（三行溢出标题区，lint 报错）"},
    "M09": {
        "desc": "L09 对比页栏小标题 h_md", "fields": {"": "作用于两栏（left/right 共用）"},
        "controls": "字号/垂直/水平", "layouts": ["L09"], "anchor": "render_outline.apply_module:M09"},
    "M10": {
        "desc": "正文（多段多行）", "fields": {
            "": "正文块；多行=多条；支持 ||| 分步、<size=> 整段/局部放大、<align=> 整段对齐、**加粗**、<ico=> 图标",
            "列表": "行内列表（甲 / 乙 / 丙）",
            "notes": "L16 标牌内容（学生可见，非教师备注）；支持 ||| 分步与缩进子项",
        },
        "controls": "垂直/水平（字号不支持，写了告警并指路 <size=> 行内标记）",
        "anchor": "render_outline.apply_module:M10",
        "constraint": "||| 只在此字段（正文/notes/列表）生效；「/」须两侧带空白才分行"},
    "M11": {
        "desc": "引文 callout + 出处", "fields": {
            "": "引文正文（L07 金句页原生；**其余版式作为页面级固定引文框挂底部**——通用元件，非 L07/L10 专用）",
            "callout_src": "引文出处（L07 显示为 src；其余版式挂 cite）",
        },
        "controls": "字号/垂直/水平", "anchor": "render_outline.apply_module:M11"},
    "M12": {
        "desc": "配图", "fields": {
            "文件": "本地配图路径 images/xx（渲染拷到输出目录）；同页多条仅最后生效",
            "ratio": "配图框纵横比（4x3/1x1/3x4；auto=按原图）",
            "比例": "ratio 别名",
            "maxh": "图框最大高度占屏 vh（默认 62）",
            "高度": "maxh 别名",
            "对齐": "图在框内水平位置（贴左/居中/贴右）",
            "垂直": "图片整体上下平移（vh，负上正下）",
            "水平": "图片整体左右平移（vw，负左正右）",
            "来源": "已停用（图下不再显示来源）；引擎安全忽略",
            "caption": "已停用；引擎安全忽略",
            "img_slot": "占位（待补·说明）：无文件时渲染虚线占位框 + label 文本；交付前必须补成真实图（lecture §5c）",
            "": "其余裸值 → img.label（alt 文本）",
        },
        "anchor": "render_outline.apply_module:M12",
        "constraint": "真实图流程见 lecture §5c：下载→压缩→M12→M14，交付前不得带 img_slot 占位"},
    "M13": {
        "desc": "注释（页面级小注）", "fields": {"": "注释正文；与 M14 同存时合并 .aux-row 两端对齐"},
        "controls": "字号（大/小）/垂直/水平；「对齐」控 左/中/右",
        "anchor": "render_outline.apply_module:M13"},
    "M14": {
        "desc": "下标/出处", "fields": {"": "出处/史料层级标签；默认右对齐"},
        "controls": "字号（大/小）/垂直/水平；「对齐」控 左/中/右",
        "anchor": "render_outline.apply_module:M14"},
    "M15": {
        "desc": "强调（引擎按 `- 强调:` 解析；`- M15:` 写法无分支）",
        "fields": {}, "note": "文档 M15 = `强调: [词]`（见 PAGE_KEYS.强调）。`- M15:` 前缀写法引擎无 apply 分支，会打印未知模块警告。",
    },
    "M16": {
        "desc": "参考链接", "fields": {
            "链接": "显示文字 | URL；空值 + 缩进子项（每条 `- 文字 | URL`）",
            "link": "链接 别名",
        },
        "anchor": "render_outline.apply_module:M16",
        "constraint": "协议白名单 http/https/mailto；新标签打开"},
}

# =====================================================================
# D. 复合键子项
# =====================================================================
COMPOUND_KEYS = {
    "items": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_compound_item:items",
        "subitems": {
            "ic": "L08 图标（Lucide 名，不用 emoji）",
            "t": "主词/标题",
            "d": "说明",
            "ch": "L12b 链节点名",
            "form": "L18 字形",
            "mean": "L18 释义",
            "blank": "L12b 留白（裸词 blank，无等号）",
            "year": "L25 年份",
            "title": "L25 节点标题",
            "desc": "L25 描述",
            "main": "L26 主词",
            "sub": "L26 副词",
            "accent": "是否 accent（是/否）",
        },
        "layouts": ["L08", "L12b", "L18", "L25", "L26"],
        "rule": "空值 + 缩进子项 `- k=v / k2=v2`；主行带值会被静默忽略",
    },
    "stats": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_compound_item:stats",
        "subitems": {
            "label": "标签",
            "nb": "数值（L19 决定条宽 / L20 决定柱高）",
            "unit": "单位",
            "note": "备注",
            "accent": "显式上色（是/否/红/关）；缺省由强调锚点推导",
        },
        "layouts": ["L04", "L19", "L20"],
        "rule": "空值 + 缩进子项；L19/L20 须同单位可比",
    },
    "steps": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_compound_item:steps",
        "subitems": {"title": "步骤名（L21 环上节点）", "desc": "步骤说明"},
        "layouts": ["L13", "L21"],
        "rule": "空值 + 缩进子项；L13 序号引擎自动（nb= 不生效）",
    },
    "rows": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_compound_item:rows",
        "subitems": {"k": "年份/键", "v": "内容", "m": "备注"},
        "layouts": ["L06"],
        "rule": "空值 + 缩进子项；行 >6 或 v= 过长会压字",
    },
    "imgs": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_compound_item:imgs",
        "subitems": {"file": "图片路径", "cap": "图注"},
        "layouts": ["L23"],
        "rule": "空值 + 缩进子项；同组图须同类、同比例；路径走与单图相同的安全校验",
    },
    "kpis": {
        "status": "ACTIVE",
        "anchor": "render_outline.parse_compound_item:kpis",
        "subitems": {"v": "数值", "l": "标签"},
        "layouts": ["L27"],
        "rule": "空值 + 缩进子项；最多 3 个",
    },
}

# =====================================================================
# E. 版式注册（LAYOUT_TYPES 派生物 + 版式名/主字段/约束）
# =====================================================================
# type: 唯一源 = render_outline.LAYOUT_MAP（经 gen_mounts.py 派生为 LAYOUT_TYPES，
#       禁手改）；primary: 主内容字段；skip_dual: 是否走双基线；constraint: 方法论约束
_LAYOUT_META = {
    "L01": {"name": "封面", "primary": ["M06 h_hero", "M07 h_sub", "meta-row"], "skip_dual": True},
    "L02": {"name": "扉页", "primary": ["M06 h_hero", "M07 h_sub"], "skip_dual": True},
    "L03": {"name": "引言", "primary": ["M08", "M10"]},
    "L04": {"name": "数据大字报", "primary": ["stats:"]},
    "L05": {"name": "图文", "primary": ["M08", "M10", "M12", "grid:", "callout:"]},
    "L06": {"name": "年表", "primary": ["rows:"]},
    "L07": {"name": "名句", "primary": ["M11 callout:", "M11 callout_src:"], "skip_dual": True},
    "L08": {"name": "支柱", "primary": ["items:"], "constraint": "2–6 根（4→4 列、2→2 列、其余 3 列）"},
    "L09": {"name": "对比", "primary": ["left(M09+body):", "right(M09+body):"], "constraint": "裸 left:/right: 整行被忽略"},
    "L10": {"name": "引文", "primary": ["M11 callout:"]},
    "L11": {"name": "配图", "primary": ["M12"]},
    "L12": {"name": "手绘示意", "primary": ["svg:（推荐）", "svg_cap:"]},
    "L12b": {"name": "链条", "primary": ["items:"], "constraint": "横向单排；节点 >4 时 d= 要短；与 svg: 同页静默丢图"},
    "L13": {"name": "进程", "primary": ["steps:"]},
    "L14": {"name": "正文", "primary": ["M08", "M10"], "constraint": "单行正文=大半页留空，见防空页规则"},
    "L15": {"name": "收束", "primary": ["M06 h_hero", "M07 h_sub"], "skip_dual": True},
    "L16": {"name": "标牌", "primary": ["M10 notes:"]},
    "L17": {"name": "互动", "primary": ["M08", "M10", "tag:"], "skip_dual": True},
    "L18": {"name": "字源卡", "primary": ["items:"]},
    "L19": {"name": "条形图", "primary": ["stats:", "scale:", "whitespace:"], "constraint": "须同单位可比；小数裸计数写 scale:max"},
    "L20": {"name": "KPI 塔", "primary": ["stats:"], "constraint": "建议正好 4 项；数值须可比"},
    "L21": {"name": "闭环图", "primary": ["steps:", "center:"], "constraint": "3–5 步；引擎自绘，禁挂 svg:"},
    "L22": {"name": "系统同心圆", "primary": ["items:"], "constraint": "严格 3 层；引擎自绘，禁挂 svg:"},
    "L23": {"name": "多图证据墙", "primary": ["imgs:"]},
    "L24": {"name": "论断陈述", "primary": ["statement:", "sub:"], "skip_dual": True},
    "L25": {"name": "横向时间轴", "primary": ["items:"]},
    "L26": {"name": "微卡矩阵", "primary": ["items:"]},
    "L27": {"name": "图幅主导", "primary": ["img.file:", "img_mode:", "title:", "cap:", "kpis:"], "skip_dual": True},
}

# type 注入（唯一源 LAYOUT_TYPES；键集合一致性硬校验：缺/多即启动失败）
_extra = set(_LAYOUT_META) - set(LAYOUT_TYPES)
_missing = set(LAYOUT_TYPES) - set(_LAYOUT_META)
if _extra or _missing:
    raise SystemExit(
        "[syntax_registry] LAYOUTS 与 LAYOUT_TYPES 键不一致 —— 缺：%s；多：%s。"
        "改版式码请在 render_outline.LAYOUT_MAP 与 _LAYOUT_META 同步。"
        % ("/".join(sorted(_missing)), "/".join(sorted(_extra))))
LAYOUTS = {code: {"type": LAYOUT_TYPES[code], **meta}
           for code, meta in _LAYOUT_META.items()}

# =====================================================================
# E2. 挂载矩阵（渲染层版式原语实际消费的内容字段；2026-09-15 二期治理）
# MOUNTS（挂载矩阵）与 LAYOUT_TYPES（版式码→type）均为派生物（阶段3c-3 路线 A +
# 阶段 X 扩展，2026-09-15）：唯一真相源 = _eink_template.py 各 p_* 函数头部的
# `_MOUNT` 声明 + render_outline.py 的 `LAYOUT_MAP`；本文件顶部 import
# gen_mounts.py 生成的 _generated_mounts.py —— 禁止手改 MOUNTS/LAYOUT_TYPES，
# 改字段 = 改对应声明 → 重跑 python gen_mounts.py。

# svg 挂载例外集（lint/guard 共用）：L21/L22 引擎自绘禁挂（lint 拦截）、L12b 静默丢图。
SVG_MOUNT_EXCEPT = {"L21", "L22", "L12b"}

# 通用元件（guard「字段 ⊆ mounts」放行集）：全版式消费，不逐版式登记。
#   · M05 kicker / M01 / M03 / M13 / M14 / M16 链接：所有 p_* 原语或固定元件渲染；
#   · M11 引文：L07 原生、callout 页原生、其余版式挂底部引文框（build_lecture L840）——全版式消费；
#   · M10 正文：BODY_NATIVE 全版式原生渲染（L24-L27 已于 2026-09-15 阶段2 补上）——M10 不进此集，
#     由各版式 mounts 显式声明（L04/L06/L13 等补挂渲染的版式已含 M10）。
MOUNT_ALL = {"M01", "M03", "M05", "M11", "M13", "M14", "M16",
             "强调", "data_animate", "数据_animate", "数据animate", "纵向", "规则线"}


LAYOUT_CODES = set(LAYOUTS.keys())          # lint 常量真源
# （2026-09-15 阶段X 收尾：删除 LAYOUT_TYPES 集合赋值——该名已由顶部 import 的
#   派生物字典（code→type）占用，此处覆盖为集合属死代码，无任何消费者）

# =====================================================================
# F. 取值枚举
# =====================================================================
ENUMS = {
    "recipes": ["cascade", "hero", "quote", "directional", "pipeline",
                "hbar", "kpitower", "loop", "system", "wall"],
    "img_mode": ["cover", "contain", "fit", "side"],
    "纵向": ["顶", "中", "底"],
    "规则线": ["是", "否"],
    "图对齐": ["底", "顶"],
    "grid": ["6:6", "7:5", "8:4"],
    "强调值": ["是", "否", "红", "关", "true", "false", "1", "0", "yes", "no", "开", "on", "off"],
}

# lint 常量真源（供 lint import，杜绝双份维护）
RECIPES = set(ENUMS["recipes"])
SPLIT_FIELDS = {"正文", "notes", "列表", "h_hero", "h_xl", "kicker", "callout",
                "img_slot", "对齐", "行对齐", "链接"}   # 与 lint 现口径一致（从 lint L52-53 迁移）
STEP_OK_FIELDS = {"正文", "notes", "列表"}              # 允许 ||| 分步的字段（lint L50 迁移）

# =====================================================================
# G. 行内标记（M10 正文内）
# =====================================================================
INLINE_MARKS = {
    "size": {"status": "ACTIVE", "anchor": "render_outline._m10_block", "semantics": "字号标记。命名档位 大/中/小（未闭合=整段、成对=局部）；**显式数字倍数 <size=1.5> 亦支持**（float 成功 → font-size:Xem，_size_span L1147-1160，局部与整段均可）。"},
    "align": {"status": "ACTIVE", "anchor": "render_outline._m10_block", "semantics": "整段对齐 <align=居中/居左/居右>（未闭合）。"},
    "bold": {"status": "ACTIVE", "anchor": "_eink_template._inline_rich", "semantics": "**加粗**。"},
    "ico": {"status": "ACTIVE", "anchor": "_eink_template._inline_rich", "semantics": "行内图标 <ico=名>（Lucide）。"},
    "step": {"status": "ACTIVE", "anchor": "render_outline._m10_block", "semantics": "分步揭示 |||（先问后揭；仅 M10 正文/notes/列表）。"},
}

# =====================================================================
# H. 斜杠规则（全引擎唯一分隔原语）
# =====================================================================
SLASH_RULE = {
    "status": "ACTIVE",
    "anchor": "render_outline._split_struct",
    "semantics": "两侧带空白的 / 或 ／ 才是分行/分项符；贴字斜杠（唐/突厥）是内容不切；保护 </xxx> 结束标签内斜杠。",
}

# —— 供 guard 快速枚举 ——
ALL_ACTIVE_KEYS = (set(META_KEYS) | set(PAGE_KEYS) | set(MODULE_FIELDS) | set(COMPOUND_KEYS))
ALL_DEPRECATED_KEYS = {k for k, v in META_KEYS.items() if v["status"] == "DEPRECATED"} \
                      | {k for k, v in PAGE_KEYS.items() if v["status"] == "DEPRECATED"}
ALL_DEAD_KEYS = {k for k, v in PAGE_KEYS.items() if v["status"] == "DEAD"}


def is_active(key):
    """key ∈ ACTIVE 语法（元数据/页面级/模块/复合键任一）。"""
    return key in META_KEYS or key in PAGE_KEYS or key in MODULE_FIELDS or key in COMPOUND_KEYS


if __name__ == "__main__":
    import sys
    print("syntax_registry: 版本以 eink-deck/SKILL.md frontmatter 为准（版本单一源，见 references/CHANGELOG.md）")
    print("元数据键 %d / 页面级键 %d（其中 DEAD %d）/ 模块 %d / 复合键 %d / 版式 %d"
          % (len(META_KEYS), len(PAGE_KEYS), len(ALL_DEAD_KEYS), len(MODULE_FIELDS), len(COMPOUND_KEYS), len(LAYOUTS)))
