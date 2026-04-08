// stores/planStore.js
import { defineStore } from 'pinia'

export const usePlanStore = defineStore('plan', {
  state: () => ({
    // 存储当前选中的教案类型和ID
    currentResourceType: '',
    currentId: ''
  }),
  actions: {
    // 设置当前教案的类型和ID
    setPlanInfo(resource_type, id) {
      this.currentResourceType = resource_type
      this.currentId = id
    }
  }
})