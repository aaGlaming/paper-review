import ElementPlus from 'element-plus'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { expect, it, vi } from 'vitest'
import * as api from '../../src/api'
import type { AnalyticsResponse, ContestSummary } from '../../src/api/types'
import ChatView from '../../src/views/AI问询.vue'

vi.mock('../../src/api', async (original) => {
  const actual = await original<typeof import('../../src/api')>()
  return { ...actual, askQuestion:vi.fn(), createChatSession:vi.fn(), deleteChatSession:vi.fn(), generateSummary:vi.fn(), listChatMessages:vi.fn(), listChatSessions:vi.fn(), listContests:vi.fn(), listReviews:vi.fn(), runAnalytics:vi.fn() }
})
it('三个聚合入口调用指定接口，展示服务端表格行与摘要证据提示', async () => {
  const contest: ContestSummary = { contest_id:'contest-test', year:2026, problem_code:'X', title:'练习', statement:'', status:'published', rubric:null, constraints:[], pitfall_count:0, exemplar_count:0 }
  vi.mocked(api.listContests).mockResolvedValue({ contests:[contest] })
  vi.mocked(api.listReviews).mockResolvedValue({ reviews:[], total:0, page:1, page_size:1, scope:'all' })
  vi.mocked(api.listChatSessions).mockResolvedValue({ sessions:[{ session_id:'s1', title:'当前会话', created_at:'now', updated_at:'now', message_count:0 }] })
  vi.mocked(api.listChatMessages).mockResolvedValue({ session_id:'s1', messages:[] })
  vi.mocked(api.runAnalytics).mockImplementation(async ({kind}): Promise<AnalyticsResponse> => {
    if (kind === 'bands') return { kind, result:{ contest_id:'contest-test', reviews:1, students:1, orphan_reviews:0, insufficient_total:1, bands:[{ dimension_code:'assumption', counts:{'证据不足':1}, insufficient:1, reviews:1 },{ dimension_code:'evidence', counts:{'充分':2}, insufficient:0, reviews:2 }] } }
    return { kind, result:{ contest_id:'contest-test', reviews_with_changes:1, kinds:{}, hotspots:[], finding_total:0, unparsable:0 } }
  })
  vi.mocked(api.generateSummary).mockResolvedValue({ content:'摘要', refs:[], model_name:'m', notes:{ rejected:0, evidence_short:2 } })
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/chat',component:ChatView}]}); await router.push('/chat')
  const wrapper=mount(ChatView,{global:{plugins:[ElementPlus,router]}}); await flushPromises()
  await wrapper.findAll('button').find((button)=>button.text()==='档位汇总')!.trigger('click'); await flushPromises()
  expect(api.runAnalytics).toHaveBeenCalledWith({contestId:'contest-test',kind:'bands'})
  expect(wrapper.findAll('.el-table__row')).toHaveLength(2)
  await wrapper.findAll('button').find((button)=>button.text()==='冲突汇总')!.trigger('click'); await flushPromises()
  expect(api.runAnalytics).toHaveBeenCalledWith({contestId:'contest-test',kind:'conflicts'})
  await wrapper.findAll('button').find((button)=>button.text()==='生成摘要')!.trigger('click'); await flushPromises()
  expect(api.generateSummary).toHaveBeenCalled()
  expect(wrapper.text()).toContain('可用证据少于 3 条')
  expect(wrapper.findAll('[data-message-id]')).toHaveLength(0)
})
