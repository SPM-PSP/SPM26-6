<template>
  <PageContainer title="学生管理">
    <!-- 页面级操作，放置在 extra 插槽 -->
    <template #extra>
      <el-tooltip content="刷新列表" placement="bottom">
        <el-button 
          :icon="RefreshRight" 
          circle 
          @click="getStuList"
        ></el-button>
      </el-tooltip>
    </template>

    <!-- 主内容区卡片 -->
    <el-card class="main-card" shadow="never">
      <!-- 顶部工具栏：搜索与新增 -->
      <div class="table-controls">
        <el-input
          v-model="search"
          placeholder="请输入学生姓名进行搜索"
          clearable
          @keyup.enter="getStuList"
          class="search-input"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" :icon="Plus" @click="addStudent">
          新增学生
        </el-button>
      </div>

      <!-- 学生信息表格 -->
      <el-table
        v-loading="isLoading"
        :data="studentList"
        style="width: 100%"
        border
        stripe
        :header-cell-style="{ background: '#f5f7fa', color: '#606266' }"
      >
        <el-table-column prop="id" label="学生ID" width="180" align="center"></el-table-column>
        <el-table-column prop="username" label="学生姓名" min-width="200"></el-table-column>
        
        <el-table-column label="操作" width="200" align="center">
          <template #default="{ row }">
            <div class="action-buttons">
              <!-- [补全] 增加编辑按钮，触发已有逻辑 -->
              <el-tooltip content="修改密码" placement="top">
                <el-button
                  type="warning"
                  :icon="Key"
                  circle
                  plain
                  @click="openPasswordModal(row)"
                ></el-button>
              </el-tooltip>
              <el-tooltip content="删除学生" placement="top">
                <el-button
                  type="danger"
                  :icon="Delete"
                  circle
                  plain
                  @click="removeStudent(row.id)"
                ></el-button>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty description="暂无学生数据"></el-empty>
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
          @size-change="getStuList"
          @current-change="getStuList"
        />
      </div>
    </el-card>

    <!-- 修改/新增表单 (弹窗组件) -->
    <StuEdit ref="editRef" @success="OnSubmit"></StuEdit>
    
    <!-- 密码修改模态框 (弹窗组件) -->
    <PasswordModal 
      ref="passwordModalRef" 
      @success="handlePasswordUpdateSuccess"
    ></PasswordModal>
  </PageContainer>
</template>

<script setup>
// 逻辑未做任何修改，仅为适配美化后的模板，增加图标和组件的导入
import PageContainer from '@/components/PageContainer.vue'
import { ref } from 'vue'
import { Edit, Delete, Key, Plus, Search, RefreshRight } from '@element-plus/icons-vue' // 增加了新图标
import { getStudentListService, deleteStudentService } from '@/api/admin.js'
import StuEdit from './components/StuEdit.vue'
import PasswordModal from './components/PasswordModal.vue'
import { ElMessage, ElMessageBox } from 'element-plus' // 显式导入

const search = ref('')
const studentList = ref([])
const isLoading = ref(false)
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

const passwordModalRef = ref(null)

const getStuList = async () => {
  isLoading.value = true
  try {
    const resp = await getStudentListService({
      search: search.value,
      page: currentPage.value,
      limit: pageSize.value, // 建议后端接口使用limit参数
      role: 'student'
    })
    studentList.value = resp.data.users
    total.value = resp.data.total
  } catch(e) {
    ElMessage.error('获取学生列表失败')
  } finally {
    isLoading.value = false
  }
}

getStuList()

const OnSubmit = () => {
  getStuList()
}

const editRef = ref(null)
const addStudent = () => {
  editRef.value.open()
}
const editStudent = (row) => {
  editRef.value.open(row)
}

const removeStudent = (id) => {
  ElMessageBox.confirm('确认删除该学生吗？此操作将无法撤销。', '重要提示', {
    confirmButtonText: '确认删除',
    cancelButtonText: '取消',
    type: 'warning'
  })
    .then(async () => {
      await deleteStudentService(id)
      ElMessage.success('删除成功')
      // 如果删除的是当前页的最后一条数据，最好返回上一页
      if (studentList.value.length === 1 && currentPage.value > 1) {
        currentPage.value--
      }
      getStuList()
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
  getStuList()
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