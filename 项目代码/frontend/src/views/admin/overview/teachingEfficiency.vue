<template>
  <PageContainer title="教学效率分析">
    <template #extra>
      <el-button 
        type="primary" 
        @click="handleRefresh"
        :loading="isLoading"
      >
        <Refresh :size="16" style="margin-right: 5px;" />
        刷新数据
      </el-button>
    </template>

    <div class="stats-container">
      <!-- 主内容区：柱状图 + 低表现科目表格 -->
      <el-card class="stat-card">
        <div class="card-header">
          <h3>教师效率指标与低表现科目</h3>
          <p class="card-desc">教师效率指数对比及表现不佳的科目统计</p>
        </div>
        
        <div class="content-wrapper">
          <!-- 左侧柱状图区域 -->
          <div class="chart-container">
            <div v-if="chartData.labels.length === 0" class="empty-data">
              暂无教学效率数据
            </div>
            <Bar 
              v-else
              :data="chartData" 
              :options="chartOptions"
              :height="400"
            />
          </div>

          <!-- 右侧低表现科目表格 -->
          <div class="table-container">
            <h4 class="table-title">低表现科目列表</h4>
            <div v-if="lowSubjects.length === 0" class="empty-table">
              暂无低表现科目数据
            </div>
            <el-table 
              v-else
              :data="lowSubjects" 
              border 
              style="width: 100%"
              :header-cell-style="{ backgroundColor: '#f5f7fa' }"
            >
              <el-table-column 
                prop="subject" 
                label="科目名称" 
                align="center" 
                width="180"
              />
              <el-table-column 
                prop="average_score" 
                label="平均分数" 
                align="center"
                width="120"
                :formatter="(row) => row.average_score + '分'"
              />
            </el-table>
          </div>
        </div>
      </el-card>

      <!-- 教师详细数据表格 -->
      <el-card class="stat-card">
        <div class="card-header">
          <h3>教师详细数据统计</h3>
          <p class="card-desc">各教师的教学计划与测评创建/优化数量</p>
        </div>
        <el-table 
          :data="teacherData" 
          border 
          style="width: 100%; margin-top: 16px"
          :header-cell-style="{ backgroundColor: '#f5f7fa' }"
        >
          <el-table-column prop="teacher_name" label="教师姓名" align="center" />
          <el-table-column prop="plans_created" label="教学计划创建数" align="center" />
          <el-table-column prop="plans_refined" label="教学计划优化数" align="center" />
          <el-table-column prop="assessments_created" label="测评创建数" align="center" />
          <el-table-column prop="assessments_refined" label="测评优化数" align="center" />
          <el-table-column 
            prop="plan_efficiency_index" 
            label="计划效率指数" 
            align="center"
            :formatter="(row) => `${row.plan_efficiency_index}%`"
          />
          <el-table-column 
            prop="assessment_efficiency_index" 
            label="测评效率指数" 
            align="center"
            :formatter="(row) => `${row.assessment_efficiency_index}%`"
          />
        </el-table>
      </el-card>
    </div>
  </PageContainer>
</template>

<script setup>
import PageContainer from '@/components/PageContainer.vue'
import { ref, onMounted, computed } from 'vue'
import { Bar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js'
import { getTeachEffectDataService } from '@/api/admin.js'
import { getlowperformingsubjectsService } from '@/api/admin.js' // 新增低表现科目接口
import { ElMessage, ElTable, ElTableColumn } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

// 注册 Chart.js 组件
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
)

// 数据状态
const teacherData = ref([])
const lowSubjects = ref([]) // 低表现科目数据
const isLoading = ref(false)

// 格式化图表数据
const chartData = computed(() => ({
  labels: teacherData.value.map(item => item.teacher_name),
  datasets: [
    {
      label: '计划效率指数（%）',
      data: teacherData.value.map(item => item.plan_efficiency_index),
      backgroundColor: '#4096ff',
      borderRadius: 6,
      barThickness: 30
    },
    {
      label: '测评效率指数（%）',
      data: teacherData.value.map(item => item.assessment_efficiency_index),
      backgroundColor: '#722ed1',
      borderRadius: 6,
      barThickness: 30
    }
  ]
}))

// 图表配置项
const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    y: {
      beginAtZero: true,
      max: 100,
      grid: {
        color: 'rgba(0, 0, 0, 0.05)',
        borderDash: [3, 3]
      },
      ticks: {
        callback: function(value) {
          return value + '%'
        }
      }
    },
    x: {
      grid: {
        display: false
      }
    }
  },
  plugins: {
    legend: {
      position: 'top',
      labels: {
        boxWidth: 12,
        padding: 20
      }
    },
    tooltip: {
      callbacks: {
        label: function(context) {
          return `${context.dataset.label}: ${context.raw}%`
        },
        afterLabel: function(context) {
          const teacher = teacherData.value[context.dataIndex]
          return [
            `教学计划创建: ${teacher.plans_created}个`,
            `教学计划优化: ${teacher.plans_refined}个`,
            `测评创建: ${teacher.assessments_created}个`,
            `测评优化: ${teacher.assessments_refined}个`
          ]
        }
      },
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      titleColor: '#333',
      bodyColor: '#666',
      borderColor: '#eee',
      borderWidth: 1,
      padding: 10,
      boxPadding: 5
    }
  }
}

// 获取教师效率数据
const getTeachingData = async () => {
  try {
    const resp = await getTeachEffectDataService()
    teacherData.value = resp.data || []
  } catch (error) {
    ElMessage.error('获取教学效率数据失败')
    console.error('错误:', error)
  }
}

// 新增：获取低表现科目数据
const getLowPerformingSubjects = async () => {
  try {
    const resp = await getlowperformingsubjectsService()
    lowSubjects.value = resp.data || []
  } catch (error) {
    ElMessage.error('获取低表现科目数据失败')
    console.error('错误:', error)
  }
}

// 统一刷新方法
const handleRefresh = async () => {
  isLoading.value = true
  try {
    await Promise.all([
      getTeachingData(),
      getLowPerformingSubjects()
    ])
  } finally {
    isLoading.value = false
  }
}

// 初始化
onMounted(() => {
  handleRefresh()
})
</script>

<style scoped lang="scss">
.stats-container {
  display: grid;
  grid-template-columns: 1fr;
  gap: 24px;
  padding: 20px;
}

.stat-card {
  border-radius: 10px;
  box-shadow: 0 2px 14px rgba(0, 0, 0, 0.04);
  overflow: hidden;

  .card-header {
    padding: 18px 24px;
    border-bottom: 1px solid #f5f7fa;

    h3 {
      margin: 0;
      font-size: 18px;
      font-weight: 500;
      color: #1d2129;
    }

    .card-desc {
      margin: 6px 0 0;
      font-size: 14px;
      color: #86909c;
    }
  }
}

// 新增：主内容区布局（柱状图 + 表格）
.content-wrapper {
  display: grid;
  grid-template-columns: 2fr 1fr; /* 柱状图占2份，表格占1份 */
  gap: 24px;
  padding: 24px;
}

.chart-container {
  width: 100%;
  position: relative;
}

.table-container {
  width: 100%;
  padding: 20px;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);

  .table-title {
    margin: 0 0 16px;
    font-size: 16px;
    color: #1d2129;
    font-weight: 500;
    padding-bottom: 8px;
    border-bottom: 1px solid #f5f7fa;
  }
}

.empty-data, .empty-table {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #86909c;
  font-size: 14px;
}

.empty-table {
  position: static;
  transform: none;
  text-align: center;
  padding: 40px 0;
}

// 表格样式
:deep(.el-table) {
  border-radius: 6px;
  overflow: hidden;
}

:deep(.el-table th) {
  background-color: #f5f7fa;
  font-weight: 500;
}

// 响应式适配
@media (max-width: 1200px) {
  .content-wrapper {
    grid-template-columns: 1fr; /* 小屏幕下堆叠显示 */
  }
  
  .table-container {
    margin-top: 20px;
  }
}

:deep(.legend-item) {
  margin-right: 24px !important;
  font-size: 14px;
}
</style>