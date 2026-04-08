<script setup>
import PageContainer from '@/components/PageContainer.vue'
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getPlanContentService } from '@/api/admin.js'
import { ElMessage } from 'element-plus'
import { usePlanStore } from '@/stores/planStore'
const planStore = usePlanStore()
const route = useRoute()
const router = useRouter()
// 解码路由参数
const { currentResourceType, currentId } = planStore
// 教案内容数据
const planContent = ref('')
const isLoading = ref(false)

// 获取教案详情内容
const getPlanContent = async () => {
  isLoading.value = true
  try {
    const resp = await getPlanContentService(
      currentResourceType,
      currentId
    )
    planContent.value = resp.data.full_content 
  } catch (error) {
    ElMessage.error('获取教案内容失败')
    console.error('获取失败:', error)
  } finally {
    isLoading.value = false
  }
}

// 返回教案列表页
const goBack = () => {
  router.push(`/admin/detail`)
}

onMounted(() => {
  getPlanContent()
})
</script>

<template>
  <PageContainer :title="`${planName} - 内容详情`">
    <template #extra>
      <el-button
        type="default"
        @click="goBack"
      >
        返回教案列表
      </el-button>
    </template>

    <el-card v-loading="isLoading" style="margin-top: 16px;">
      <template #header>
        <div>
          <h3>{{ planName }}</h3>
          <p style="color: #666; margin-top: 8px;">所属学科：{{ subjectName }}</p>
        </div>
      </template>
      
      <div class="plan-content">
        <!-- 教案内容展示（根据实际格式调整，示例为文本） -->
        <pre v-if="planContent">{{ planContent }}</pre>
        <div v-else-if="!isLoading" class="empty-content">
          暂无教案内容
        </div>
      </div>
    </el-card>
  </PageContainer>
</template>

<style scoped>
.plan-content {
  padding: 20px;
  line-height: 1.8;
}

.empty-content {
  text-align: center;
  padding: 50px 0;
  color: #999;
}
</style>