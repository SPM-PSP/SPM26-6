<template>
  <div class="assessment-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">学情评估</h1>
      <p class="page-desc">查看您发布的试题及学生答题情况分析</p>
    </div>
    
    <!-- 试题列表区域 -->
    <div class="exam-list-container">
      <div v-loading="isLoading" class="exam-list">
        <div 
          v-for="exam in examList" 
          :key="exam.id" 
          class="exam-card"
          @click.stop="toggleExamDetail(exam.id)"
        >
          <div class="exam-header">
            <h3 class="exam-title">{{ exam.title }}</h3>
            <el-button 
              type="primary" 
              size="small"
              :loading="analysisLoading[exam.id]"
              @click="getExamAnalysis(exam.id)"
            >
              展示学情
            </el-button>
          </div>
          
          <!-- 学情分析内容 (展开/收起) -->
          <div 
            class="analysis-content"
            :class="{ 'expanded': expandedExamIds.includes(exam.id) }"
          >
            <div v-if="analysisLoading[exam.id]" class="loading-skeleton">
              <el-skeleton animated :rows="8" />
            </div>
            
            <!-- 正确展示新结构的学情分析数据 -->
            <div v-else-if="examAnalysis[exam.id]" class="analysis-data">
              <!-- 考核标题 -->
              <h4 class="analysis-title">{{ examAnalysis[exam.id].assessment_title }}</h4>
              
              <!-- 总体评价 -->
              <div class="overall-summary">
                <p><strong>总体评价：</strong>{{ examAnalysis[exam.id].overall_summary }}</p>
              </div>
              
              <!-- 强弱项分析 -->
              <div class="strength-weakness">
                <div class="section">
                  <h5>学生优势</h5>
                  <ul>
                    <li v-for="(point, idx) in examAnalysis[exam.id].strength_points" :key="idx">
                      {{ point }}
                    </li>
                  </ul>
                </div>
                <div class="section">
                  <h5>薄弱环节</h5>
                  <ul>
                    <li v-for="(point, idx) in examAnalysis[exam.id].weakness_points" :key="idx">
                      {{ point }}
                    </li>
                  </ul>
                </div>
              </div>
              
              <!-- 问题题目分析 -->
              <div class="problematic-questions">
                <h5>重点问题分析</h5>
                <div v-for="(question, qIdx) in examAnalysis[exam.id].problematic_questions" :key="qIdx" class="question-item">
                  <div class="question-text">
                    <p><strong>{{ question.question_identifier }}：</strong>{{ question.question_text.split('\n')[0] }}</p>
                    <div class="options">
                      <div v-for="(opt, oIdx) in question.question_text.split('\n').slice(1)" :key="oIdx">
                        {{ opt }}
                      </div>
                    </div>
                  </div>
                  <div class="question-meta">
                    <span class="correct-rate">正确率：{{ question.correct_rate * 100 }}%</span>
                    <span class="knowledge-point">知识点：{{ question.main_knowledge_point }}</span>
                  </div>
                  <div class="error-analysis">
                    <p><strong>错误分析：</strong>{{ question.common_error_analysis }}</p>
                  </div>
                </div>
              </div>
              
              <!-- 教学建议 -->
              <div class="teaching-suggestions">
                <h5>教学建议</h5>
                <ol>
                  <li v-for="(suggestion, sIdx) in examAnalysis[exam.id].teaching_suggestions" :key="sIdx">
                    {{ suggestion }}
                  </li>
                </ol>
              </div>
            </div>
            
            <div v-else-if="!analysisLoading[exam.id]" class="no-analysis-data">
              暂无学生答题数据
            </div>
          </div>
        </div>
      </div>
      
      <!-- 无数据提示 -->
      <div v-if="!isLoading && examList.length === 0" class="no-data-tip">
        <el-empty description="您还没有发布试题" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElEmpty, ElSkeleton } from 'element-plus'
import { getTeacherExamsService, getExamAnalysisService } from '@/api/teacher'
import { useUserStore } from '@/stores/user'

// 响应式数据
const examList = ref([]) // 试题列表
const examAnalysis = ref({}) // 试题分析数据（修改为对象存储，键为examId）
const isLoading = ref(true) // 全局加载状态
const expandedExamIds = ref([]) // 展开的试题ID
const analysisLoading = ref({}) // 学情分析加载状态

// 获取老师发布的试题列表
const fetchTeacherExams = async () => {
  isLoading.value = true
  try {
    const userStore = useUserStore()
    const res = await getTeacherExamsService(userStore.userId )
    examList.value = res.data || []
  } catch (error) {
    ElMessage.error('获取试题列表失败，请稍后重试')
    console.error('获取试题列表失败', error)
  } finally {
    isLoading.value = false
  }
}

// 获取试题学情分析
const getExamAnalysis = async (examId) => {
  if (analysisLoading.value[examId]) return // 防止重复请求
  
  analysisLoading.value[examId] = true
  try {
    const res = await getExamAnalysisService(examId)
    // 直接存储后端返回的完整分析数据
    examAnalysis.value[examId] = res.data
    
    // 自动展开查看学情
    if (!expandedExamIds.value.includes(examId)) {
      expandedExamIds.value.push(examId)
    }
  } catch (error) {
    ElMessage.error('获取学情分析失败，请稍后重试')
    console.error('获取学情分析失败', error)
  } finally {
    analysisLoading.value[examId] = false
  }
}

// 切换试题详情展开状态
const toggleExamDetail = (examId) => {
  if (expandedExamIds.value.includes(examId)) {
    expandedExamIds.value = expandedExamIds.value.filter(id => id !== examId)
  } else {
    expandedExamIds.value.push(examId)
  }
}

// 初始化加载试题列表
onMounted(() => {
  fetchTeacherExams()
})
</script>

<style scoped>
.assessment-page {
  padding: 30px;
  background-color: #f5f7fa;
  min-height: 100vh;
}

.page-header {
  text-align: center;
  margin-bottom: 30px;
}

.page-title {
  font-size: 28px;
  color: #1f2d3d;
  margin-bottom: 10px;
  font-weight: 600;
}

.page-desc {
  font-size: 16px;
  color: #606266;
  margin: 0;
}

.exam-list-container {
  max-width: 1200px;
  margin: 0 auto;
}

.exam-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(800px, 1fr));
  gap: 20px;
}

.exam-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  overflow: hidden;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.exam-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.12);
}

.exam-header {
  padding: 20px;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.exam-title {
  font-size: 18px;
  color: #1f2d3d;
  font-weight: 600;
  margin: 0;
}

.analysis-content {
  padding: 0;
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.5s ease, padding 0.3s ease;
  background-color: #f9fafc;
}

.analysis-content.expanded {
  max-height: 1500px;
  padding: 20px;
}

.analysis-title {
  font-size: 18px;
  color: #303133;
  font-weight: 600;
  margin: 0 0 20px 0;
  padding-bottom: 10px;
  border-bottom: 2px solid #42b983;
}

.overall-summary {
  background-color: #f0f9f0;
  padding: 15px;
  border-radius: 8px;
  margin-bottom: 20px;
  font-size: 15px;
  line-height: 1.6;
}

.strength-weakness {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
}

.strength-weakness .section {
  flex: 1;
  background-color: #fff;
  padding: 15px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.strength-weakness h5 {
  margin-top: 0;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid #eee;
}

.strength-weakness .section:first-child h5 {
  color: #42b983;
}

.strength-weakness .section:last-child h5 {
  color: #e74c3c;
}

.strength-weakness ul {
  padding-left: 20px;
  margin-bottom: 0;
}

.strength-weakness li {
  margin-bottom: 8px;
  line-height: 1.5;
}

.problematic-questions {
  margin-bottom: 20px;
}

.problematic-questions h5 {
  font-size: 16px;
  color: #303133;
  margin-top: 0;
  margin-bottom: 15px;
}

.question-item {
  background: #fff;
  border-radius: 8px;
  padding: 15px;
  margin-bottom: 15px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.question-text {
  margin-bottom: 10px;
}

.question-text p {
  margin: 0 0 10px 0;
  line-height: 1.6;
}

.options {
  padding-left: 20px;
  margin-bottom: 10px;
}

.options div {
  margin-bottom: 5px;
}

.question-meta {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
  font-size: 14px;
}

.correct-rate {
  color: #e74c3c;
  font-weight: 500;
}

.knowledge-point {
  color: #2c3e50;
}

.error-analysis {
  background-color: #fff8e6;
  padding: 12px;
  border-radius: 6px;
  font-size: 14px;
}

.teaching-suggestions {
  background-color: #f0f7ff;
  padding: 15px;
  border-radius: 8px;
}

.teaching-suggestions h5 {
  margin-top: 0;
  margin-bottom: 10px;
  color: #2c3e50;
}

.teaching-suggestions ol {
  padding-left: 20px;
  margin-bottom: 0;
}

.teaching-suggestions li {
  margin-bottom: 10px;
  line-height: 1.6;
}

.no-analysis-data {
  font-size: 14px;
  color: #909399;
  padding: 15px 0;
  text-align: center;
}

.no-data-tip {
  text-align: center;
  padding: 40px 0;
}

.loading-skeleton {
  padding: 15px 0;
}
</style>