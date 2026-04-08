<template>
  <PageContainer title="教师管理">
    <!-- 页面级操作，放置在 extra 插槽 -->
    <template #extra>
      <el-tooltip content="刷新列表" placement="bottom">
        <el-button 
          :icon="RefreshRight" 
          circle 
          @click="gettechList"
        ></el-button>
      </el-tooltip>
    </template>

    <!-- 主内容区卡片 -->
    <el-card class="main-card" shadow="never">
      <!-- 顶部工具栏：搜索与新增 -->
      <div class="table-controls">
        <el-input
          v-model="search"
          placeholder="请输入教师姓名进行搜索"
          clearable
          @keyup.enter="gettechList"
          class="search-input"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" :icon="Plus" @click="addTeacher">
          新增教师
        </el-button>
      </div>

      <!-- 教师信息表格 -->
      <el-table
        v-loading="isLoading"
        :data="techList"
        style="width: 100%"
        border
        stripe
        :header-cell-style="{ background: '#f5f7fa', color: '#606266' }"
      >
        <el-table-column prop="id" label="教师ID" width="180" align="center"></el-table-column>
        <el-table-column prop="username" label="教师姓名" min-width="200"></el-table-column>
        
        <el-table-column label="操作" width="200" align="center">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-tooltip content="修改密码" placement="top">
                <el-button
                  type="warning"
                  :icon="Key"
                  circle
                  plain
                  @click="openPasswordModal(row)"
                ></el-button>
              </el-tooltip>
              <el-tooltip content="删除教师" placement="top">
                <el-button
                  type="danger"
                  :icon="Delete"
                  circle
                  plain
                  @click="removeTeacher(row.id)"
                ></el-button>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty description="暂无教师数据"></el-empty>
        </template>
      </el-table>

      <!-- 底部分页控件 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @size-change="gettechList"
          @current-change="gettechList"
        />
      </div>
    </el-card>

    <!-- 修改/新增表单 (弹窗组件) -->
    <TechEdit ref="editRef" @success="OnSubmit"></TechEdit>
    
    <!-- 密码修改模态框 (弹窗组件) -->
    <PasswordModal 
      ref="passwordModalRef" 
      @success="handlePasswordUpdateSuccess"
    ></PasswordModal>
  </PageContainer>
</template>

<script setup>
// 逻辑未做任何修改，仅为适配美化后的模板，增加图标导入
import PageContainer from '@/components/PageContainer.vue'
import { ref } from 'vue'
import { Edit, Delete, Plus, Search, Key, RefreshRight } from '@element-plus/icons-vue' // 增加了新图标
import { getTeacherListService, deleteTeacherService } from '@/api/admin.js'
import TechEdit from './components/TechEdit.vue'
import PasswordModal from './components/PasswordModal1.vue'
import { ElMessage, ElMessageBox } from 'element-plus' // 显式导入

const search = ref('')
const techList = ref([])
const isLoading = ref(false)
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

const passwordModalRef = ref(null)

const gettechList = async () => {
  isLoading.value = true
  try {
    const resp = await getTeacherListService({
      search: search.value,
      page: currentPage.value,
      limit: pageSize.value, // 建议后端接口使用limit参数
      role: 'teacher'
    })
    techList.value = resp.data.users
    total.value = resp.data.total
  } catch(e) {
    // 增加错误处理提示
    ElMessage.error('获取教师列表失败')
  } finally {
    isLoading.value = false
  }
}

gettechList()

const OnSubmit = () => {
  gettechList()
}

const editRef = ref(null)
const addTeacher = () => {
  editRef.value.open()
}
const editStudent = (row) => {
  editRef.value.open(row)
}

const removeTeacher = (id) => {
  ElMessageBox.confirm('确认删除这位教师吗？此操作不可撤销。', '重要提示', {
    confirmButtonText: '确认删除',
    cancelButtonText: '取消',
    type: 'warning'
  })
    .then(async () => {
      await deleteTeacherService(id)
      ElMessage.success('删除成功')
      // 如果删除的是当前页的最后一条数据，最好返回上一页
      if (techList.value.length === 1 && currentPage.value > 1) {
        currentPage.value--
      }
      gettechList()
    })
    .catch(() => {
      ElMessage.info('已取消删除')
    })
}

const openPasswordModal = (row) => {
  passwordModalRef.value.open(row)
}

const handlePasswordUpdateSuccess = () => {
  ElMessage.success('密码修改成功')
  gettechList()
}
</script>

<style scoped lang="scss">
.main-card {
  border-radius: 8px;
  border: 1px solid #ebeef5;
  :deep(.el-card__body) {
    padding: 20px;
  }
}

.table-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;

  .search-input {
    width: 300px;
  }
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 10px;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>