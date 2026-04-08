<template>
  <PageContainer :title="`${subjectName} - 教案详情`" class="plan-detail-container">
    <!-- #extra 插槽，用于放置页面右上角的操作按钮和分页 -->
    <template #extra>
      <div class="header-extra">
        <!-- 返回按钮 (优化: 添加图标，调整样式) -->
        <el-button type="default" @click="goBack" class="back-btn">
          <el-icon><ArrowLeft /></el-icon>
          返回列表
        </el-button>

        <!-- 顶部简易分页控件 (优化: 调整尺寸和间距) -->
        <div class="pagination-controls">
          <el-button
            type="primary"
            plain
            @click="handlePrevPage"
            :disabled="currentPage === 1"
            size="small"
          >
            上一页
          </el-button>
          <span class="page-info">
            第 {{ currentPage }} 页 / 共 {{ totalPages }} 页
          </span>
          <el-button
            type="primary"
            plain
            @click="handleNextPage"
            :disabled="currentPage >= totalPages"
            size="small"
          >
            下一页
          </el-button>
        </div>
      </div>
    </template>

    <!-- 使用卡片包裹主要内容，提升视觉效果 (优化: 增加hover阴影和边框) -->
    <el-card shadow="hover" class="main-card">
      <!-- 教案列表表格 (优化: 调整表头、单元格样式) -->
      <el-table
        v-loading="isLoading"
        :data="planList"
        style="width: 100%"
        stripe
        :header-cell-style="{ 
          background: '#f5f7fa', 
          color: '#606266',
          fontWeight: '600',
          fontSize: '14px'
        }"
        :cell-style="{ padding: '12px 0' }"
      >
        <el-table-column label="资源名称" min-width="300">
          <template #default="{ row }">
            <!-- 优化: 增加图标样式和文字样式 -->
            <div class="resource-title">
              <el-icon class="document-icon"><Document /></el-icon>
              <span class="resource-name">{{ row.title }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="250" align="center">
          <template #default="{ row }">
            <!-- 优化: 调整按钮尺寸、间距和悬停效果 -->
            <div class="action-buttons">
              <el-tooltip content="查看内容详情" placement="top" effect="light">
                <el-button
                  type="primary"
                  :icon="Document"
                  circle
                  plain
                  @click="goToPlanDetail(row.resource_type, row.id)"
                  class="action-btn detail-btn"
                />
              </el-tooltip>
              <el-tooltip content="导出该文件" placement="top" effect="light">
                <el-button
                  type="success"
                  :icon="Download"
                  circle
                  plain
                  @click="exportSinglePlan(row.resource_type, row.id)"
                  class="action-btn export-btn"
                />
              </el-tooltip>
            </div>
          </template>
        </el-table-column>

        <!-- 空状态显示 (优化: 增加刷新按钮) -->
        <template #empty>
          <el-empty description="暂无教案数据" :image-size="120">
            <el-button type="primary" @click="getPlanList">刷新试试</el-button>
          </el-empty>
        </template>
      </el-table>

      <!-- 底部分页控件 (优化: 增加分隔线和间距) -->
      <div class="footer-pagination">
        <div class="pagination-controls">
          <el-button
            type="primary"
            plain
            @click="handlePrevPage"
            :disabled="currentPage === 1"
          >
            上一页
          </el-button>
          <span class="page-info detailed">
            第 {{ currentPage }} 页 / 共 {{ totalPages }} 页 (总计 {{ total }} 条)
          </span>
          <el-button
            type="primary"
            plain
            @click="handleNextPage"
            :disabled="currentPage >= totalPages"
          >
            下一页
          </el-button>
        </div>
      </div>
    </el-card>
  </PageContainer>
</template>

<script setup>
// 脚本部分的逻辑完全没有改动
import PageContainer from '@/components/PageContainer.vue'
import { ref, onMounted, computed } from 'vue'
import { Download, Document, ArrowLeft } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { getTeachingPlansService, exportwenjian } from '@/api/admin.js'
import { ElMessage, ElLoading } from 'element-plus'
import { useSubjectStore } from '@/stores/subjectStore'
import { usePlanStore } from '@/stores/planStore'

const subjectStore = useSubjectStore()
const subjectName = subjectStore.currentSubject

const router = useRouter()
const planStore = usePlanStore()

const planList = ref([])
const isLoading = ref(false)
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

const totalPages = computed(() => {
  return total.value > 0 ? Math.ceil(total.value / pageSize.value) : 1
})

const getPlanList = async () => {
  isLoading.value = true
  try {
    const resp = await getTeachingPlansService(
      subjectName,
      currentPage.value,
      pageSize.value
    )
    planList.value = resp.data.resources
    total.value = resp.data.total
  } catch (error) {
    ElMessage.error('获取教案列表失败')
    console.error('获取失败:', error)
  } finally {
    isLoading.value = false
  }
}

const handlePrevPage = () => {
  if (currentPage.value > 1) {
    currentPage.value--
    getPlanList()
  }
}

const handleNextPage = () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
    getPlanList()
  }
}

const goToPlanDetail = (resource_type, id) => {
  planStore.setPlanInfo(resource_type, id)
  router.push(`/admin/plan`)
}

const goBack = () => {
  router.push('/admin/resourcesManage')
}

const exportSinglePlan = async (resource_type, resource_id) => {
  const loading = ElLoading.service({
    lock: true,
    text: '正在导出教案...',
    background: 'rgba(0, 0, 0, 0.1)'
  })

  try {
    const response = await exportwenjian(resource_type, resource_id, {
      responseType: 'blob'
    })

    const contentDisposition = response.headers['content-disposition']
    if (!contentDisposition) {
      throw new Error('未获取到文件名信息')
    }

    const filenameMatch = contentDisposition.match(/filename\*=UTF-8''(.*)/)
    if (!filenameMatch) {
      throw new Error('文件名格式解析失败')
    }
    const fileName = decodeURIComponent(filenameMatch[1])

    const blob = new Blob([response.data], {
      type: response.headers['content-type'] || 'application/octet-stream'
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = fileName

    document.body.appendChild(link)
    link.click()

    setTimeout(() => {
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    }, 100)

    ElMessage.success('教案导出成功')
  } catch (error) {
    console.error('导出失败:', error)
    ElMessage.error(error.message || '教案导出失败，请重试')
  } finally {
    loading.close()
  }
}

onMounted(() => {
  getPlanList()
})
</script>

<style scoped lang="scss">
/* 优化头部 #extra 插槽的布局 */
.header-extra {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding-right: 12px;
  
  .back-btn {
    display: flex;
    align-items: center;
    .el-icon {
      margin-right: 6px;
    }
  }
}

/* 主卡片样式，增加边框和更柔和的阴影 */
.main-card {
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.04);
  
  :deep(.el-card__body) {
    padding: 8px 20px 20px 20px;
  }
}

/* 分页控件的通用样式 */
.pagination-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  
  .page-info {
    font-size: 13px;
    color: #606266;
    user-select: none;
    
    &.detailed {
      font-size: 14px;
    }
  }
}

/* 资源名称列的样式 */
.resource-title {
  display: flex;
  align-items: center;
  gap: 10px;

  .document-icon {
    color: var(--el-color-primary);
    font-size: 18px;
    flex-shrink: 0;
  }

  .resource-name {
    font-size: 14px;
    font-weight: 500;
    color: #333;
    line-height: 1.5;
    
    /* [修正] 使用标准CSS实现单行文本溢出省略 */
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

/* 操作按钮列的样式 */
.action-buttons {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  
  .action-btn {
    width: 32px;
    height: 32px;
    transition: all 0.2s ease-in-out;
    
    /* 悬停效果 */
    &:hover {
      transform: scale(1.1);
    }

    &.detail-btn:hover {
      background-color: var(--el-color-primary-light-9);
    }
    
    &.export-btn:hover {
      background-color: var(--el-color-success-light-9);
    }
  }
}

/* 底部页脚分页的容器样式，增加分隔线 */
.footer-pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid #f0f2f5;
}
</style>