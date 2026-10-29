import { afterEach, expect, it, vi } from 'vitest'
import { askQuestion, createChatSession, deleteChatSession, generateSummary, listChatMessages, listChatSessions, listReviews, runAnalytics } from '../../src/api'

afterEach(() => { vi.unstubAllGlobals() })
it('七个问询 API 使用相对 URL 与 snake_case 请求字段', async () => {
  const fetchMock=vi.fn(async (input:RequestInfo|URL, init?:RequestInit) => {
    const url=String(input)
    if (url.endsWith('/sessions') && init?.method==='POST') return new Response(JSON.stringify({session_id:'s1',title:'新会话',created_at:'now'}),{status:201})
    if (init?.method==='DELETE') return new Response(null,{status:204})
    if (url.endsWith('/analytics')) return new Response(JSON.stringify({kind:'bands',result:{}}),{status:200})
    if (url.endsWith('/summary')) return new Response(JSON.stringify({content:'',refs:[],model_name:'',notes:{rejected:0}}),{status:200})
    if (url.endsWith('/messages') && init?.method==='POST') return new Response(JSON.stringify({message_id:'m',content:'',refs:[],model_name:'',notifications:{rejected:0,unused:0}}),{status:200})
    if (url.includes('/messages')) return new Response(JSON.stringify({session_id:'s 1',messages:[]}),{status:200})
    if (url.endsWith('/sessions')) return new Response(JSON.stringify({sessions:[]}),{status:200})
    return new Response('{}',{status:200})
  })
  vi.stubGlobal('fetch',fetchMock)
  await listChatSessions(); await createChatSession('标题'); await deleteChatSession('s/1'); await listChatMessages('s 1')
  await askQuestion('s1',{question:'问题',contestId:'contest-test'})
  await runAnalytics({contestId:'contest-test',kind:'gaps',dimensionCode:'modeling'})
  await generateSummary({contestId:'contest-test',top:3,sessionId:'s1'})
  await listReviews({contestId:'contest-test',pageSize:1})
  const calls=fetchMock.mock.calls
  expect(calls.map(([url])=>String(url))).toEqual([
    '/api/chat/sessions','/api/chat/sessions','/api/chat/sessions/s%2F1','/api/chat/sessions/s%201/messages',
    '/api/chat/sessions/s1/messages','/api/chat/analytics','/api/chat/summary','/api/reviews?contest_id=contest-test&page_size=1',
  ])
  expect(JSON.parse(String(calls[1]?.[1]?.body))).toEqual({title:'标题'})
  expect(JSON.parse(String(calls[4]?.[1]?.body))).toEqual({question:'问题',contest_id:'contest-test'})
  expect(JSON.parse(String(calls[5]?.[1]?.body))).toEqual({contest_id:'contest-test',kind:'gaps',dimension_code:'modeling'})
  expect(JSON.parse(String(calls[6]?.[1]?.body))).toEqual({contest_id:'contest-test',top:3,session_id:'s1'})
})
