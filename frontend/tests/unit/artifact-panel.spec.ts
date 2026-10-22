import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import type { ReviewArtifact } from '../../src/api/types'
import ArtifactPanel from '../../src/components/ArtifactPanel.vue'
import SectionReader from '../../src/components/SectionReader.vue'

const artifacts: ReviewArtifact[] = [
  {
    artifact_id: 1, review_id: 'review-1', ordinal: 0, artifact_type: 'claim', section_type: '摘要',
    char_start: 0, char_end: 12, claim_text: '结果表明有效时长达到 22.4 s。', table_markdown: null, citation_text: null,
  },
  {
    artifact_id: 2, review_id: 'review-1', ordinal: 1, artifact_type: 'table', section_type: '结果',
    char_start: 12, char_end: 40, claim_text: null, table_markdown: '| 项目 | 数值 |\n| --- | --- |\n| A | 22 |', citation_text: null,
  },
  {
    artifact_id: 3, review_id: 'review-1', ordinal: 2, artifact_type: 'citation', section_type: '摘要',
    char_start: 40, char_end: 44, claim_text: null, table_markdown: null, citation_text: '[12]',
  },
]

describe('ArtifactPanel', () => {
  it('分三组显示条数并把 Markdown 表格渲染成表格结构', () => {
    const wrapper = mount(ArtifactPanel, { props: { artifacts } })

    expect(wrapper.get('[data-testid="artifact-group-claim"] h3').text()).toContain('主张 (1)')
    expect(wrapper.get('[data-testid="artifact-group-table"] h3').text()).toContain('表格 (1)')
    expect(wrapper.get('[data-testid="artifact-group-citation"] h3').text()).toContain('引用 (1)')
    expect(wrapper.findAll('table th').map((node) => node.text())).toEqual(['项目', '数值'])
    expect(wrapper.text()).toContain('摘要')
    expect(wrapper.text()).not.toContain('| --- |')
  })

  it('有产物时空类型组显示无', () => {
    const wrapper = mount(ArtifactPanel, { props: { artifacts: [artifacts[0]] } })
    expect(wrapper.get('[data-testid="artifact-group-table"]').text()).toContain('无')
    expect(wrapper.get('[data-testid="artifact-group-citation"]').text()).toContain('无')
  })

  it('空态显示说明并由可用用户发起抽取', async () => {
    const wrapper = mount(ArtifactPanel, { props: { artifacts: [], canExtract: true } })
    expect(wrapper.get('[data-testid="artifact-empty"]').text()).toContain('本篇未抽取到产物')
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('extract')).toHaveLength(1)
  })

  it('点击产物发出定位事件', async () => {
    const wrapper = mount(ArtifactPanel, { props: { artifacts } })
    await wrapper.get('[data-testid="artifact-group-claim"] button').trigger('click')
    expect(wrapper.emitted('locate')?.[0]).toEqual([artifacts[0]])
  })

  it('缺少 section 区间时保留偏移定位降级提示', async () => {
    const wrapper = mount(SectionReader, {
      props: {
        section: { title: '摘要', section_type: '摘要', level: 1, content: '当前正文没有目标片段。' },
        reviewId: 'review-1',
        artifacts: [{ ...artifacts[0], claim_text: '缺失的证据。', char_start: 2, char_end: 8 }],
      },
    })
    await wrapper.get('[data-testid="artifact-group-claim"] button').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="approximate-note"]').text()).toBe('按偏移定位，未精确匹配')
  })

  it('有 section 基准时用全篇偏移换算并精确高亮原文', async () => {
    const paperText = '# 摘要\n结果达到 22.4 s。'
    const section = {
      title: '摘要', section_type: '摘要', level: 1, content: '结果达到 22.4 s。',
      char_start: 0, char_end: paperText.length,
    }
    const claim = {
      ...artifacts[0], char_start: paperText.indexOf('结果'),
      char_end: paperText.length, claim_text: '结果达到 22.4 s。',
    }
    const wrapper = mount(SectionReader, {
      props: { section, sections: [section], paperText, sectionsRanged: true, reviewId: 'review-1', artifacts: [claim] },
    })
    await wrapper.get('[data-testid="artifact-group-claim"] button').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="artifact-mark"]').text()).toBe(claim.claim_text)
    expect(wrapper.find('[data-testid="approximate-note"]').exists()).toBe(false)
  })
})
