/**
 * 评审流程里的词表：章节类型与六个预审步骤。
 *
 * **章节类型必须与后端 `backend/app/graph/review_graph.py` 的 `SECTION_TYPES` 一致。**
 * 后端没有「取词表」的接口，而 P8 不许改后端，所以只能在这里镜像一份。
 * 这份镜像**只准有一处定义**（用例锁死：恰好六个类型 + 未分类、顺序一致）——
 * 分叉的后果是用户能选出一个后端不认识的类型。
 */

/** 后端 `SECTION_TYPES` 的镜像，顺序一致。 */
export const SECTION_TYPES = ['假设', '模型', '求解', '结果', '检验', '参考文献'] as const

/** 判不出类型时的兜底：后端 `UNCLASSIFIED_SECTION_TYPE` 的镜像。 */
export const UNCLASSIFIED_SECTION_TYPE = '未分类'

/** 章节类型下拉的全部合法值：六个类型 + 兜底的未分类。 */
export const SECTION_TYPE_OPTIONS: readonly string[] = [...SECTION_TYPES, UNCLASSIFIED_SECTION_TYPE]

/**
 * 预审的六个步骤（任务文档 §14 任务 9）。
 *
 * 步骤指示器只按**真实观测到**的时点点亮，不补中间态：`resume` 是同步接口，
 * 后端一次跑完这六步，中间态拿不到。详见 `StageTracker`。
 */
export const REVIEW_STAGES = ['赛题对齐', '按维检索', '选档', '规则审查', '原句校验', '生成报告'] as const

/**
 * 页面唯一能真实区分出来的几个时点：
 * - `idle` 未开始；`running` 有请求在飞（不确定态）；`parsed` 章节树已产出、待确认；
 * - `done` 报告已收到；`failed` 请求失败或超时（停在等待服务返回）。
 */
export type StagePhase = 'idle' | 'running' | 'parsed' | 'done' | 'failed'
