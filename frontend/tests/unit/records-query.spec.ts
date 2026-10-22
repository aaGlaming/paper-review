import ElementPlus from 'element-plus'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { expect, it, vi } from 'vitest'
import * as api from '../../src/api'
import RecordsView from '../../src/views/记录总览.vue'

vi.mock('../../src/api', async (original) => {
  const actual=await original<typeof import('../../src/api')>()
  return {...actual,listContests:vi.fn().mockResolvedValue({contests:[]}),listReviews:vi.fn().mockResolvedValue({reviews:[],total:0,page:1,page_size:20,scope:'all'}),getReview:vi.fn().mockResolvedValue({review_id:'r1',contest_id:'c',rubric_id:null,rubric_version:null,model_name:'m',created_at:null,dimensions:[],change_list:[],change_list_note:null}),getReviewArtifacts:vi.fn().mockResolvedValue([])}
})
it('review 查询参数打开对应抽屉，关闭后清掉参数', async () => {
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/records',component:RecordsView}]})
  await router.push('/records?review=r1'); await router.isReady()
  const wrapper=mount(RecordsView,{global:{plugins:[ElementPlus,router],stubs:{ElDrawer:{props:['modelValue'],emits:['update:modelValue'],template:'<section v-if="modelValue" class="el-drawer"><button class="test-close" @click="$emit(\'update:modelValue\',false)"></button><slot /></section>'}}}}); await flushPromises()
  expect(api.getReview).toHaveBeenCalledWith('r1')
  expect(wrapper.find('.el-drawer').exists()).toBe(true)
  await wrapper.find('.test-close').trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.query.review).toBeUndefined()
})
