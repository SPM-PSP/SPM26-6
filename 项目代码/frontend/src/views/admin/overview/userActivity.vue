<template>
  <PageContainer title="用户操作行为统计">
    <template #extra>
      <el-button 
        type="primary" 
        @click="getActivityData"
        :loading="isLoading"
      >
        <Refresh :size="16" style="margin-right: 5px;" />
        刷新数据
      </el-button>
    </template>

    <div class="stats-container">
      <!-- 日统计模块 -->
      <el-card class="stat-card">
        <div class="card-header">
          <h3>当日操作统计</h3>
          <p class="card-desc">老师与学生的当日系统操作分布</p>
        </div>
        <div class="chart-wrapper">
          <!-- 空数据提示 -->
          <div v-if="dailyChartData.labels.length === 0" class="empty-data">
            暂无当日操作数据
          </div>
          <Bar 
            v-else
            :data="dailyChartData" 
            :options="chartOptions"
            :height="400"
          />
        </div>
      </el-card>

      <!-- 周统计模块 -->
      <el-card class="stat-card">
        <div class="card-header">
          <h3>本周操作统计</h3>
          <p class="card-desc">老师与学生的本周系统操作分布</p>
        </div>
        <div class="chart-wrapper">
          <div v-if="weeklyChartData.labels.length === 0" class="empty-data">
            暂无本周操作数据
          </div>
          <Bar 
            v-else
            :data="weeklyChartData" 
            :options="chartOptions"
            :height="400"
          />
        </div>
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
import { getActivityDataService } from '@/api/admin.js' 
import { ElMessage } from 'element-plus'
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
const dailyTeacherData = ref([]) 
const dailyStudentData = ref([]) 
const weeklyTeacherData = ref([]) 
const weeklyStudentData = ref([]) 
const isLoading = ref(false)

// 格式化图表数据（核心修改：合并老师和学生的操作类型，确保数据长度一致）
const formatChartData = (teacherData, studentData) => {
  // 合并所有操作类型（去重）
  const allActivityTypes = [
    ...teacherData.map(item => item.name),
    ...studentData.map(item => item.name)
  ].filter((item, index, self) => self.indexOf(item) === index) // 去重

  // 为每种操作类型匹配对应的数据（没有数据则补0）
  const getDataset = (data) => {
    return allActivityTypes.map(type => {
      const item = data.find(i => i.name === type)
      return item ? item.value : 0
    })
  }

  return {
    labels: allActivityTypes, // 所有操作类型（x轴）
    datasets: [
      {
        label: '老师',
        data: getDataset(teacherData),
        backgroundColor: '#4096ff',
        borderRadius: 6,
        barThickness: 20
      },
      {
        label: '学生',
        data: getDataset(studentData),
        backgroundColor: '#67c23a',
        borderRadius: 6,
        barThickness: 20
      }
    ]
  }
}

// 日统计图表数据
const dailyChartData = computed(() => {
  return formatChartData(dailyTeacherData.value, dailyStudentData.value)
})

// 周统计图表数据
const weeklyChartData = computed(() => {
  return formatChartData(weeklyTeacherData.value, weeklyStudentData.value)
})

// 图表配置项
const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    y: {
      beginAtZero: true,
      grid: {
        color: 'rgba(0, 0, 0, 0.05)',
        borderDash: [3, 3]
      },
      ticks: {
        precision: 0 // 确保Y轴只显示整数（次数不能为小数）
      }
    },
    x: {
      grid: {
        display: false
      },
      ticks: {
        // 操作类型文本过长时自动换行
        callback: function(value) {
          const label = this.getLabelForValue(value)
          return label.length > 10 ? label.slice(0, 10) + '...' : label
        }
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
          return `${context.dataset.label}：${context.raw}次`
        },
        title: function(context) {
          // 显示完整的操作类型名称
          return context[0].label
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

// 处理接口数据（保持不变，仅提取原始数据）
const formatData = (rawData) => {
  const formatUserTypeData = (userTypeData) => 
    userTypeData.map(item => ({ 
      name: item.activity_type, 
      value: item.count 
    }))

  return {
    dailyTeacher: formatUserTypeData(rawData.daily.teacher),
    dailyStudent: formatUserTypeData(rawData.daily.student),
    weeklyTeacher: formatUserTypeData(rawData.weekly.teacher),
    weeklyStudent: formatUserTypeData(rawData.weekly.student)
  }
}

// 获取数据
const getActivityData = async () => {
  isLoading.value = true
  try {
    const resp = await getActivityDataService()
    const formatted = formatData(resp.data)
    dailyTeacherData.value = formatted.dailyTeacher
    dailyStudentData.value = formatted.dailyStudent
    weeklyTeacherData.value = formatted.weeklyTeacher
    weeklyStudentData.value = formatted.weeklyStudent
  } catch (error) {
    ElMessage.error('获取数据失败')
    console.error('错误:', error)
  } finally {
    isLoading.value = false
  }
}

// 初始化
onMounted(() => {
  getActivityData()
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

  .chart-wrapper {
    width: 100%;
    padding: 24px;
    position: relative;

    .empty-data {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      color: #86909c;
      font-size: 14px;
    }
  }
}

@media (min-width: 1200px) {
  .stats-container {
    grid-template-columns: 1fr 1fr;
  }
}

:deep(.legend-item) {
  margin-right: 24px !important;
  font-size: 14px;
}

:deep(.axis-label) {
  font-size: 14px;
  color: #666;
}
</style>