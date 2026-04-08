<template>
  <PageContainer title="教学资源管理">
    <!-- 右上角添加刷新功能 -->
    <template #extra>
      <el-tooltip content="刷新列表" placement="bottom">
        <el-button 
          :icon="Refresh" 
          circle 
          @click="getSubjectList"
        ></el-button>
      </el-tooltip>
    </template>

    <!-- 使用卡片包裹表格，提升质感 -->
    <el-card class="table-card" shadow="never">
      <!-- 学科列表表格 -->
      <el-table
        v-loading="isLoading"
        :data="subjectList"
        style="width: 100%"
        stripe
        border
        :header-cell-style="{ 
          background: '#f5f7fa', 
          color: '#606266', 
          fontWeight: 'bold' 
        }"
      >
        <el-table-column label="学科名称" min-width="300">
          <template #default="{ row }">
            <div class="subject-name-cell">
              <el-icon :size="18"><Collection /></el-icon>
              <span>{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="180" align="center">
          <template #default="{ row }">
            <el-button
              type="primary"
              :icon="View"
              class="detail-button"
              @click="goToDetail(row.name)"
            >
              查看详情
            </el-button>
          </template>
        </el-table-column>

        <!-- 优化空状态提示 -->
        <template #empty>
          <el-empty description="暂无学科数据">
            <el-button type="primary" @click="getSubjectList">重新加载</el-button>
          </el-empty>
        </template>
      </el-table>
    </el-card>
  </PageContainer>
</template>

<script setup>
// 逻辑代码完全不变，仅为美化需要增加图标导入和ElMessage
import PageContainer from '@/components/PageContainer.vue'
import { ref } from 'vue'
import { View, Refresh, Collection } from '@element-plus/icons-vue' // 增加了新图标
import { getSubjectListService } from '@/api/admin.js'
import { useRouter } from 'vue-router'
import { useSubjectStore } from '@/stores/subjectStore'
import { ElMessage } from 'element-plus' // 增加消息提示

// 状态管理
const subjectList = ref([])
const isLoading = ref(false)
const router = useRouter()
const subjectStore = useSubjectStore()

// 获取学科列表数据时，格式化数据
const getSubjectList = async () => {
  isLoading.value = true
  try {
    const resp = await getSubjectListService()
    subjectList.value = resp.data.map((subjectName) => ({
      name: subjectName
    }))
  } catch (error) {
    // 优化：给用户一个失败的反馈
    ElMessage.error('获取学科列表失败，请稍后重试')
    console.error('获取学科列表失败:', error)
  } finally {
    isLoading.value = false
  }
}

// 初始化加载数据
getSubjectList()

// 点击详情跳转
const goToDetail = (name) => {
  subjectStore.setSubject(name)
  console.log(name) // 保留您原有的 console.log
  router.push('/admin/detail')
}
</script>

<style scoped lang="scss">
// 表格卡片容器样式
.table-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);

  :deep(.el-card__body) {
    padding: 20px;
  }
}

// 学科名称单元格样式
.subject-name-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 500;
  color: #333;

  .el-icon {
    color: var(--el-color-primary);
  }
}

// 详情按钮样式与悬浮效果
.detail-button {
  transition: all 0.25s ease-out;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 10px rgba(64, 158, 255, 0.2);
  }
}
</style>