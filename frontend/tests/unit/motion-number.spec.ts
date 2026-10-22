import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import MotionNumber from '../../src/components/MotionNumber.vue'

describe('MotionNumber', () => {
  it('reduced-motion 开启时直接落到真实终值，并提供非动画读屏文本', () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true, media: '', onchange: null, addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn() }))
    const wrapper = mount(MotionNumber, { props: { value: 42 } })
    expect(wrapper.text()).toContain('42')
    expect(wrapper.find('.motion-number__accessible').text()).toBe('42')
    wrapper.unmount()
    vi.unstubAllGlobals()
  })

  it('数据变化时从旧值过渡到新值并在完成后稳定', async () => {
    let timestamp = 1000
    vi.spyOn(performance, 'now').mockImplementation(() => timestamp)
    const callbacks: FrameRequestCallback[] = []
    vi.stubGlobal('matchMedia', () => ({ matches: false }))
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      callbacks.push(callback)
      return callbacks.length
    })
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    const wrapper = mount(MotionNumber, { props: { value: 10, duration: 100 } })
    callbacks.shift()?.(1100)
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('10')

    await wrapper.setProps({ value: 20 })
    timestamp = 1100
    callbacks.shift()?.(1200)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.motion-number__accessible').text()).toBe('20')
    expect(wrapper.text()).toContain('20')
    wrapper.unmount()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })
})
