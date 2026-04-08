<template>
  <PageContainer title="学生学习效果分析" class="analysis-page">
    <template #extra>
      <el-button 
        type="primary" 
        @click="handleRefresh"
        :loading="isLoading"
        :icon="Refresh"
      >
        刷新数据
      </el-button>
    </template>

    <div class="content-layout">
      <!-- 图表容器 -->
      <el-card class="stat-card" shadow="never">
        <template #header>
          <div class="card-header">
            <h3 class="header-title">学习效果趋势与薄弱知识点</h3>
            <p class="header-desc">学生答题准确率变化及掌握薄弱的知识点分析</p>
          </div>
        </template>
        
        <div class="charts-wrapper">
          <!-- 左侧：准确率趋势折线图 -->
          <div class="chart-item">
            <h4 class="chart-title">准确率趋势</h4>
            <div class="chart-placeholder">
              <el-skeleton v-if="loadingTrend" :rows="5" animated />
              <el-empty v-else-if="accuracyTrend.length === 0" description="暂无准确率趋势数据" />
              <LineChart 
                v-else
                :data="lineChartData" 
                :options="lineChartOptions"
              />
            </div>
          </div>

          <!-- 右侧：薄弱知识点雷达图 -->
          <div class="chart-item">
            <h4 class="chart-title">薄弱知识点掌握度</h4>
            <div class="chart-placeholder">
              <el-skeleton v-if="loadingConcepts" animated>
                <template #template>
                  <el-skeleton-item variant="circle" style="width: 150px; height: 150px;" />
                </template>
              </el-skeleton>
              <el-empty v-else-if="weakestConcepts.length === 0" description="暂无薄弱知识点数据" />
              <RadarChart 
                v-else
                :data="radarChartData" 
                :options="radarChartOptions"
              />
            </div>
          </div>
        </div>
      </el-card>

      <!-- 详细数据表格 -->
      <el-card class="stat-card" shadow="never">
        <template #header>
          <div class="card-header">
            <h3 class="header-title">薄弱知识点详情</h3>
            <p class="header-desc">各知识点的具体掌握率及答题情况</p>
          </div>
        </template>
        
        <div class="table-container">
          <el-skeleton v-if="loadingConcepts" :rows="5" animated />
          <el-table 
            v-else
            :data="weakestConcepts" 
            border 
            style="width: 100%;"
            :header-cell-style="{ backgroundColor: '#f5f7fa', color: '#606266', fontWeight: 'bold' }"
          >
            <el-table-column prop="concept" label="知识点" min-width="180" />
            <el-table-column 
              prop="mastery_rate" 
              label="掌握率" 
              align="center"
              width="120"
              :formatter="(row) => `${row.mastery_rate}%`"
            />
            <el-table-column prop="total_attempts" label="总答题数" align="center" width="120" />
            <el-table-column prop="incorrect_attempts" label="错误次数" align="center" width="120" />
          </el-table>
        </div>
      </el-card>
    </div>
  </PageContainer>
</template>

<script setup>
// 所有业务逻辑、数据请求和处理方式均与您提供的原始代码完全一致
import PageContainer from '@/components/PageContainer.vue'
import { ref, onMounted, computed, nextTick } from 'vue'
import { Line, Radar } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement,
  LineElement, RadarController, ArcElement, Tooltip, Legend,
  Filler, RadialLinearScale
} from 'chart.js'
import { getLearningEffectService } from '@/api/admin.js'
import { ElMessage, ElTable, ElTableColumn, ElSkeleton, ElEmpty } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement, RadarController,
  ArcElement, Tooltip, Legend, Filler, RadialLinearScale
)

const LineChart = Line
const RadarChart = Radar

const accuracyTrend = ref([])
const weakestConcepts = ref([])
const isLoading = ref(false)
const loadingTrend = ref(true)
const loadingConcepts = ref(true)

const lineChartData = computed(() => ({
  labels: accuracyTrend.value.map(item => item.date),
  datasets: [{
    label: '平均准确率（%）',
    data: accuracyTrend.value.map(item => item.average_accuracy),
    borderColor: '#4096ff',
    backgroundColor: 'rgba(64, 150, 255, 0.1)',
    fill: true,
    tension: 0.4,
    pointBackgroundColor: '#4096ff',
    pointRadius: 4,
    pointHoverRadius: 6
  }]
}))

const radarChartData = computed(() => ({
  labels: weakestConcepts.value.map(item => item.concept),
  datasets: [{
    label: '掌握率（%）',
    data: weakestConcepts.value.map(item => item.mastery_rate),
    backgroundColor: 'rgba(237, 100, 166, 0.2)',
    borderColor: '#ed64a6',
    pointBackgroundColor: '#ed64a6',
    pointBorderColor: '#fff',
    pointHoverBackgroundColor: '#fff',
    pointHoverBorderColor: '#ed64a6'
  }]
}))

const lineChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { position: 'top', labels: { usePointStyle: true, padding: 20 } },
    tooltip: {
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      titleColor: '#333',
      bodyColor: '#666',
      borderColor: '#eee',
      borderWidth: 1,
      padding: 10,
      callbacks: { label: (context) => `准确率: ${context.raw}%` }
    }
  },
  scales: {
    y: {
      beginAtZero: true,
      max: 100,
      ticks: { callback: (value) => `${value}%` },
      grid: { color: 'rgba(0, 0, 0, 0.05)' }
    },
    x: { grid: { display: false } }
  }
}

const radarChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { position: 'top', labels: { usePointStyle: true, padding: 20 } },
    tooltip: {
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      titleColor: '#333',
      bodyColor: '#666',
      borderColor: '#eee',
      borderWidth: 1,
      padding: 10,
      callbacks: { label: (context) => `掌握率: ${context.raw}%` }
    }
  },
  scales: {
    r: {
      angleLines: { color: 'rgba(0, 0, 0, 0.05)' },
      suggestedMin: 0,
      suggestedMax: 100,
      pointLabels: { font: { size: 12 }, color: '#606266' },
      ticks: { display: false, backdropPadding: 0 }
    }
  }
}

const getLearningData = async () => {
  isLoading.value = true
  loadingTrend.value = true
  loadingConcepts.value = true
  try {
    const resp = await getLearningEffectService()
    setTimeout(() => {
      accuracyTrend.value = resp.data.accuracy_trend || []
      weakestConcepts.value = resp.data.weakest_concepts || []
      nextTick(() => {
        loadingTrend.value = false
        loadingConcepts.value = false
      })
    }, 300)
  } catch (error) {
    ElMessage.error('获取数据失败')
    console.error(error)
    loadingTrend.value = false
    loadingConcepts.value = false
  } finally {
    isLoading.value = false
  }
}

const handleRefresh = () => getLearningData()

onMounted(() => getLearningData())
</script>

<style scoped lang="scss">
// 页面级背景和布局
.analysis-page {
  :deep(.page-main) {
    background-color: #f0f2f5;
  }
}

.content-layout {
  display: grid;
  gap: 20px;
}

// 卡片统一样式
.stat-card {
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  
  // 移除卡片头部的默认下边框和内边距，以便自定义
  :deep(.el-card__header) {
    padding: 0;
    border-bottom: none;
  }
}

// 自定义卡片头
.card-header {
  padding: 16px 24px;
  border-bottom: 1px solid #f0f2f5;
  .header-title {
    font-size: 18px;
    font-weight: 600;
    color: #303133;
    margin: 0;
  }
  .header-desc {
    font-size: 14px;
    color: #909399;
    margin: 4px 0 0;
  }
}

// 图表网格布局
.charts-wrapper {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 32px;
  padding: 24px;
}

.chart-item {
  display: flex;
  flex-direction: column;
}

// 图表标题
.chart-title {
  font-size: 16px;
  font-weight: 500;
  color: #606266;
  margin: 0 0 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0f2f5;
}

// 图表占位符容器
.chart-placeholder {
  flex-grow: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 320px;
}

// 表格容器
.table-container {
  padding: 0 24px 24px;
  
  :deep(.el-table tr) {
    transition: background-color 0.2s;
  }
  :deep(.el-table tr:hover > td) {
    background-color: #f5f7fa !important;
  }
}

// 响应式布局
@media (max-width: 1200px) {
  .charts-wrapper {
    grid-template-columns: 1fr;
    gap: 40px;
  }
  .chart-placeholder {
    min-height: 280px;
  }
}
</style>