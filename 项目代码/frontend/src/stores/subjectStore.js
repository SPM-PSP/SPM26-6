import { defineStore } from 'pinia'

export const useSubjectStore = defineStore('subjectStore', {
  state: () => ({
    currentSubject: null // 存储当前选中的学科名称
  }),
  actions: {
    // 设置当前学科
    setSubject(name) {
      this.currentSubject = name
    },
    // 清空当前学科（可选）
    clearSubject() {
      this.currentSubject = null
    }
  }
})