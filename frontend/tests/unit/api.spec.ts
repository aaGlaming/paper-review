import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as api from '../../src/api'

type Recorded = { url: string; init: RequestInit | undefined }

let calls: Recorded[] = []

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function stubFetch(handler: () => Response = () => jsonResponse({ ok: true })): void {
  calls = []
  const impl = (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    calls.push({ url: String(input), init })
    return Promise.resolve(handler())
  }
  vi.stubGlobal('fetch', vi.fn(impl))
}

function lastCall(): Recorded {
  const call = calls.at(-1)
  if (!call) {
    throw new Error('这一条接口函数没有发出任何请求')
  }
  return call
}

type Case = {
  label: string
  call: () => Promise<unknown>
  url: string
  method: 'GET' | 'POST'
}

const CASES: Case[] = [
  { label: '赛题列表', call: () => api.listContests(), url: '/api/contests', method: 'GET' },
  {
    label: '赛题列表带草稿与归档',
    call: () => api.listContests(true, true),
    url: '/api/contests?include_archived=true&include_drafts=true',
    method: 'GET',
  },
  { label: '创建评审', call: () => api.createReview({ paper_text: '正文' }), url: '/api/reviews', method: 'POST' },
  {
    label: '确认章节树后继续',
    call: () => api.resumeReview('review-1', []),
    url: '/api/reviews/review-1/resume',
    method: 'POST',
  },
  { label: '读取评审', call: () => api.getReview('review-1'), url: '/api/reviews/review-1', method: 'GET' },
  { label: '样例列表', call: () => api.listSamples(), url: '/api/samples', method: 'GET' },
  { label: '只看演示样例', call: () => api.listSamples(true), url: '/api/samples?is_demo=true', method: 'GET' },
  { label: '评测汇总', call: () => api.getEvalSummary(), url: '/api/eval/summary', method: 'GET' },
  {
    label: '导入数据包',
    call: () => api.importPackage('data/contests/demo'),
    url: '/api/imports',
    method: 'POST',
  },
  {
    label: '发布赛题',
    call: () => api.publishContest('contest-demo'),
    url: '/api/contests/contest-demo/publish',
    method: 'POST',
  },
  {
    label: '归档赛题',
    call: () => api.archiveContest('contest-demo'),
    url: '/api/contests/contest-demo/archive',
    method: 'POST',
  },
  {
    label: '复制下一版量规',
    call: () => api.copyRubricAsDraft('contest-demo'),
    url: '/api/contests/contest-demo/rubrics',
    method: 'POST',
  },
  {
    label: '发布量规',
    call: () => api.publishRubric('contest-demo-v1'),
    url: '/api/rubrics/contest-demo-v1/publish',
    method: 'POST',
  },
]

beforeEach(() => {
  stubFetch()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('api 层', () => {
  it('十一条已冻结接口各有一个函数，且请求路径与方法都对', async () => {
    const names = [
      'listContests',
      'createReview',
      'resumeReview',
      'getReview',
      'listSamples',
      'getEvalSummary',
      'importPackage',
      'publishContest',
      'archiveContest',
      'copyRubricAsDraft',
      'publishRubric',
    ] as const
    for (const name of names) {
      expect(typeof api[name], name).toBe('function')
    }

    for (const item of CASES) {
      stubFetch()
      await item.call()
      expect(lastCall().url, item.label).toBe(item.url)
      expect(lastCall().init?.method ?? 'GET', item.label).toBe(item.method)
    }
  })

  it('请求路径一律是相对路径，不以 http:// 或 https:// 开头', async () => {
    // 这里不给每条重置记录，要一次看全 13 次调用的路径（11 个函数 + 两个带查询参数/无参数的变体）。
    for (const item of CASES) {
      await item.call()
    }

    expect(calls).toHaveLength(CASES.length)
    for (const call of calls) {
      expect(call.url.startsWith('/api/'), call.url).toBe(true)
      expect(call.url.startsWith('http://'), call.url).toBe(false)
      expect(call.url.startsWith('https://'), call.url).toBe(false)
    }
  })

  it('非 2xx 时抛错，错误信息里带上响应体的 detail', async () => {
    stubFetch(() => jsonResponse({ filename: 'rubric.json', field: 'dimensions[0].weight', detail: '五个维度权重合计为 95，必须为 100' }, 400))

    const error = await api.importPackage('data/contests/demo').catch((reason: unknown) => reason)

    expect(error).toBeInstanceOf(api.ApiError)
    const apiError = error as api.ApiError
    expect(apiError.status).toBe(400)
    expect(apiError.message).toContain('五个维度权重合计为 95')
    expect(apiError.field).toBe('dimensions[0].weight')
    expect(apiError.filename).toBe('rubric.json')
  })

  it('参数校验失败时 detail 是数组，也要进错误信息', async () => {
    stubFetch(() => jsonResponse({ detail: [{ type: 'json_invalid', loc: ['body', 1], msg: 'JSON decode error' }] }, 422))

    const error = await api.createReview({ paper_text: '正文' }).catch((reason: unknown) => reason)

    expect(error).toBeInstanceOf(api.ApiError)
    expect((error as api.ApiError).message).toContain('json_invalid')
    expect((error as api.ApiError).status).toBe(422)
  })

  it('响应体不是 JSON 时也不崩，错误信息退回状态码', async () => {
    stubFetch(() => new Response('<html>502 Bad Gateway</html>', { status: 502 }))

    const error = await api.getEvalSummary().catch((reason: unknown) => reason)

    expect(error).toBeInstanceOf(api.ApiError)
    expect((error as api.ApiError).status).toBe(502)
    expect((error as api.ApiError).message).toContain('502')
  })
})
