import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import MetricCard from '../../src/components/MetricCard.vue'

describe('MetricCard 小样本呈现', () => {
  it('low_sample 时隐藏百分比、保留分数、说明分母并且不画折线', () => {
    const wrapper = mount(MetricCard, {
      props: {
        code: 'insufficient_evidence_hit',
        name: '证据不足命中情况',
        metric: {
          matched: 2,
          total: 2,
          rate: 1,
          low_sample: true,
          caliber: '证据不足命中口径',
        },
      },
    })

    expect(wrapper.get('[data-testid="metric-rate"]').text()).toBe('样本过少')
    expect(wrapper.get('[data-testid="metric-rate"]').text()).not.toContain('%')
    expect(wrapper.get('[data-testid="metric-fraction"]').text()).toBe('2 / 2')
    expect(wrapper.get('[data-testid="metric-low-sample-note"]').text()).toBe(
      '本指标分母仅 2 个维度，不足以支撑结论',
    )
    expect(wrapper.find('.metric__chart').exists()).toBe(false)
  })

  it('非 low_sample 指标仍显示百分比与折线，不显示小样本说明', () => {
    const wrapper = mount(MetricCard, {
      props: {
        code: 'band_agreement',
        name: '档位一致率',
        metric: {
          matched: 26,
          total: 60,
          rate: 26 / 60,
          low_sample: false,
          caliber: '档位一致率口径',
        },
      },
    })

    expect(wrapper.get('[data-testid="metric-rate"]').text()).toBe('43.3%')
    expect(wrapper.get('[data-testid="metric-fraction"]').text()).toBe('26 / 60')
    expect(wrapper.find('.metric__chart').exists()).toBe(true)
    expect(wrapper.find('[data-testid="metric-low-sample-note"]').exists()).toBe(false)
  })
})
