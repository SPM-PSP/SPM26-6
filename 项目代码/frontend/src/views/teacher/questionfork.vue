<script setup>
import 'element-plus/es/components/loading/style/css'
import { useUserStore } from '@/stores/user'
import { ref, onMounted, computed } from 'vue'
import { getQuestionBanks, publishQuestionBank } from '@/api/teacher'
import { ElMessage, ElEmpty } from 'element-plus'
import { formatTime } from '@/utils/format' // 假设已有时间格式化工具
import PageContainer from '@/components/PageContainer.vue'

// 状态管理
const banks = ref([])
const loading = ref(true)
const publishingIds = ref([])
const userStore = useUserStore()
// 按创建时间倒序排序
const sortedBanks = computed(() => {
  return [...banks.value].sort((a, b) => {
    return new Date(b.create_time) - new Date(a.create_time)
  })
})

// 获取题库列表
const fetchBanks = async () => {
  try {
    loading.value = true
    const response = await getQuestionBanks(userStore.userId)
    banks.value = response.data.assessments || []
  } catch (error) {
    ElMessage.error('获取题库失败：' + (error.message || '网络错误'))
    banks.value = []
  } finally {
    loading.value = false
  }
}

// 发布题库
const handlePublish = async (assessmentId) => {
  try {
    publishingIds.value.push(assessmentId)
    await publishQuestionBank(assessmentId,userStore.userId)
    ElMessage.success('发布成功')
    // 可选择刷新列表或更新当前项状态
    fetchBanks()
  } catch (error) {
    ElMessage.error('发布失败：' + (error.message || '操作失败'))
  } finally {
    publishingIds.value = publishingIds.value.filter(
      (id) => id !== assessmentId
    )
  }
}

// 页面加载时获取数据
onMounted(() => {
  fetchBanks()
})
</script>

<template>
  <PageContainer title="题库管理">
    <div class="question-bank-container">
      <!-- 题库卡片列表 -->
      <div class="bank-card" v-for="bank in sortedBanks" :key="bank.id">

        <div class="bank-info">
          <div class="bank-header">
            <h3 class="bank-title">{{ bank.title }}</h3>
            <span class="bank-id">题库ID: {{ bank.id }}</span>
          </div>
          <div class="bank-meta">
            <span class="bank-subject"
              ><i class="el-icon-notebook-2"></i> {{ bank.subject }}</span
            >
            <span class="bank-time"
              ><i class="el-icon-clock"></i>
              {{ formatTime(bank.create_time) }}</span
            >
          </div>
        </div>
        <el-button
          type="primary"
          class="publish-btn"
          @click="handlePublish(bank.id)"
          :loading="publishingIds.includes(bank.id)"
        >
          发布
        </el-button>
      </div>

      <!-- 空状态提示 -->
      <div v-if="sortedBanks.length === 0 && !loading" class="empty-state">
        <el-empty description="暂无题库数据"></el-empty>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading" class="loading-state">
        <el-loading size="large"></el-loading>
        <p>加载题库中...</p>
      </div>
    </div>
  </PageContainer>
</template>

<style scoped lang="scss">
.question-bank-container {
  padding: 20px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(600px, 1fr));
  gap: 20px;
}

.bank-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease;

  &:hover {
    transform: translateY(-3px);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  }
}

.bank-info {
  flex: 1;
}

.bank-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.bank-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}

.bank-id {
  font-size: 14px;
  color: #909399;
  background: #f5f7fa;
  padding: 2px 8px;
  border-radius: 12px;
}

.bank-meta {
  display: flex;
  gap: 20px;
  color: #606266;
  font-size: 14px;
}

.bank-subject,
.bank-time {
  display: flex;
  align-items: center;
  gap: 6px;
}

.publish-btn {
  min-width: 100px;
  height: 40px;
  border-radius: 8px;
}

.empty-state,
.loading-state {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
}

.loading-state {
  color: #606266;
  gap: 16px;
}
</style>
