# 手稿线稿 SVG 资产

应用当前使用的 SVG 统一保存在本目录，文件名遵循 `sketch-<语义>.svg`。前端组件直接引用这里的文件；`frontend/src/assets/sketch/` 仅保留页面底图照片，不再保留 SVG 副本。

## 资产清单

| 用途 | 文件 |
| --- | --- |
| 流程与章节 | `sketch-arrow-down.svg`、`sketch-arrow-right.svg`、`sketch-doc-tree.svg`、`sketch-flow-dots.svg` |
| 评审核查 | `sketch-check-list.svg`、`sketch-circle.svg`、`sketch-magnifier.svg`、`sketch-quote.svg` |
| 图表与标记 | `sketch-chart.svg`、`sketch-corner-mark.svg`、`sketch-underline.svg` |
| 页面主题插图 | `sketch-bg-consistency.svg`、`sketch-bg-eval.svg`、`sketch-bg-parse.svg`、`sketch-bg-scoring.svg`、`sketch-bg-suggestions.svg` |
| 主题点缀 | `sketch-card-border.svg`、`sketch-margin-draft.svg`、`sketch-paper-grain.svg`、`sketch-spot-consistency.svg`、`sketch-spot-eval.svg`、`sketch-spot-parse.svg`、`sketch-spot-scoring.svg`、`sketch-spot-suggestions.svg` |
| 文具与主题控件 | `sketch-pencil.svg`、`sketch-tape.svg`、`sketch-moon.svg`、`sketch-sun.svg` |
| 登录开场 | `sketch-review-desk-intro.svg` |

## 本次调整

- 统一 28 张既有 SVG 的存放目录，组件与样式引用改为本目录，避免前端源码与设计文档各留一份同名资产。
- 优化 `sketch-doc-tree.svg`：改成居中的父章节向左右子章节分支，父子层级和阅读方向更明确。
- 优化 `sketch-check-list.svg`：补齐每项的方框，前两项勾选、最后一项留空，完成状态不再只靠悬空对勾表达。
- 统一所有资产根节点的 `width`、`height` 与 `viewBox` 尺寸，避免内联或图片使用时尺寸不确定。
- 新增 `sketch-review-desk-intro.svg`：以校样纸、章节线、边注、勾记和铅笔组成登录成功后的工作台开场；动画可由系统减少动态效果设置关闭。

所有图形保持当前色继承、克制线稿、语义色令牌和小尺寸圆角风格，不引入外部图标库或新动效依赖。
