# -*- coding: utf-8 -*-
# _theme_default.py —— eink 默认主题名的单一真相源
#
# 背景：`_eink_template.py`（引擎）与 `templates.py`（eink2pptx 的 PPTX 侧）都各写一遍
#       `DEFAULT_THEME = "ink-classic"`。eink2pptx 的设计契约是「视觉继承 eink 主题」，
#       默认值一旦只改一边，PPTX 默认主题就会与 HTML 默认主题分叉——而且分叉是静默的：
#       get_theme() 有兜底，不报错，只是产出与预期不同的配色。
#
# 收编于此：eink 引擎直接 import；eink2pptx 在运行时按目录结构相对定位读取
# （_eink_template.py 的写法不跨技能可用），两者共用同一个值。

DEFAULT_THEME = "ink-classic"
