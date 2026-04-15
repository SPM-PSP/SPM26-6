<script setup>
import PageContainer from '@/components/PageContainer.vue'
import { ref, onMounted, nextTick } from 'vue'
import { useUserStore } from '@/stores/user'
import { getAIAnswerService, getAIAnswerServicemore } from '@/api/teacher.js'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue' // 导入加载图标
import { ElIcon } from 'element-plus' // 导入图标组件

// 获取当前时间（HH:MM格式）
const getCurrentTime = () => {
  const time = new Date().toTimeString().slice(0, 5)
  return time
}

// 消息列表
const messages = ref([
  {
    role: 'assistant',
    content: '你好！我是你的智能助手，有什么可以帮你解答的？',
    time: ''
  }
])

// 输入框内容
const inputText = ref('')
let qa_id = ref(null)
// 消息容器引用
const chatContainer = ref(null)

// 组件挂载时设置初始消息时间并滚动到底部
onMounted(() => {
  messages.value[0].time = getCurrentTime()
  scrollToBottom()
})

// 发送消息
const sendMessage = async () => {
  if (!inputText.value.trim()) {
    ElMessage.warning('请输入消息内容')
    return
  }

  const userQuestion = inputText.value.trim()

  // 添加用户消息
  messages.value.push({
    role: 'user',
    content: userQuestion,
    time: getCurrentTime()
  })

  // 添加加载中的临时消息
  const thinkingMsgId = messages.value.length // 记录临时消息位置
  messages.value.push({
    role: 'assistant',
    content: '正在为您思考如何解决…………',
    time: getCurrentTime(),
    isLoading: true // 标记为加载状态
  })
  isThinking.value = true

  try {
    const userStore = useUserStore()
    let response

    if (qaHistory.value.length === 0) {
      response = await getAIAnswerService(userStore.userId, userQuestion)
    } else {
      response = await getAIAnswerServicemore(
        userStore.userId,
        qaHistory.value,
        userQuestion,
        qa_id.value
      )
    }
    qa_id.value = response.data.teaching_plan_id
    const aiAnswer = response.data.generated_plan_content

    // 替换临时消息为实际回答
    messages.value[thinkingMsgId] = {
      role: 'assistant',
      content: '回答如下:' + aiAnswer,
      time: getCurrentTime()
    }

    // 维护历史问答
    qaHistory.value.push({
      role: 'user',
      content: userQuestion
    })
    qaHistory.value.push({
      role: 'assistant',
      content: aiAnswer
    })
  } catch (error) {
    console.error('获取回答失败', error)
    ElMessage.error('获取回答失败，请重试')
    // 替换临时消息为错误提示
    messages.value[thinkingMsgId] = {
      role: 'assistant',
      content: '抱歉，当前回答遇到问题，请重试',
      time: getCurrentTime()
    }
  } finally {
    inputText.value = ''
    isThinking.value = false
    await nextTick()
    scrollToBottom()
  }
}

// 滚动到底部
const scrollToBottom = () => {
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

// 存储历史问答对
const qaHistory = ref([])

// 新增：加载状态（思考中）
const isThinking = ref(false)
</script>

<template>
  <PageContainer title="智能学习助手小C">
    <!-- 消息显示区域 -->
    <div ref="chatContainer" class="chat-container">
      <div class="messages" v-for="(msg, index) in messages" :key="index">
        <!-- AI回复消息 -->
        <div v-if="msg.role === 'assistant'" class="message ai-message">
          <div class="avatar">
            <img
              src="@/assets/ai.png"
              alt="AI头像"
              style="width: 100%; height: 100%; border-radius: 50%"
            />
          </div>
          <div class="content">
            <!-- 加载状态时显示图标 -->
            <div v-if="msg.isLoading" class="text flex items-center gap-2">
              <el-icon><Loading /></el-icon>
              <span>{{ msg.content }}</span>
            </div>
            <div v-else class="text">
              {{ msg.content }}
            </div>
            <div class="time">{{ msg.time }}</div>
          </div>
        </div>

        <!-- 用户消息 -->
        <div v-else class="message user-message">
          <div class="content">
            <div class="text">{{ msg.content }}</div>
            <div class="time">{{ msg.time }}</div>
          </div>
          <div class="avatar">👤</div>
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="input-area">
      <el-input
        v-model="inputText"
        type="textarea"
        placeholder="输入消息并回车发送"
        @keyup.enter="sendMessage"
        class="input"
      ></el-input>
      <el-button type="primary" @click="sendMessage" class="send-btn"
        >发送</el-button
      >
    </div>
  </PageContainer>
</template>

<style scoped lang="scss">
.chat-container {
  height: calc(70vh - 180px);
  overflow-y: auto;
  padding: 20px;
  background: #f5f7fa;
}
.messages {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.message {
  display: flex;
  align-items: flex-start;
  max-width: 70%;
}

.ai-message {
  justify-content: flex-start;
}

.user-message {
  justify-content: flex-end;
  margin-left: auto;
}

.avatar {
  width: 32px;
  height: 32px;
  flex-shrink: 0; /* 防止头像因父容器收缩被压缩 */
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 10px;
}

.ai-message .avatar {
  background: #e6f4ff;
  color: #1677ff;
}

.user-message .avatar {
  background: #f0f9eb;
  color: #52c41a;
}

.content {
  background: white;
  padding: 12px 16px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  flex-grow: 1;
}

.user-message .content {
  background: #e6f4ff;
}

.text {
  font-size: 14px;
  line-height: 1.5;
  margin-bottom: 4px;
  white-space: pre-line;
}

.time {
  font-size: 12px;
  color: #909399;
  text-align: right;
}

.input-area {
  display: flex;
  gap: 10px;
  padding: 20px;
  background: white;
  border-top: 1px solid #ebedf0;
}

.input {
  flex-grow: 1;
  height: auto;
  min-height: 40px;
  .el-input__inner {
    border-radius: 20px;
    padding: 10px 20px;
    font-size: 14px;
    white-space: pre-wrap !important;
    word-wrap: break-word !important;
    overflow: auto !important;
    resize: none;
  }
}

.send-btn {
  white-space: nowrap;
  height: 40px; /* 与输入框高度一致 */
  padding: 0 24px; /* 增加按钮内边距 */
  border-radius: 20px; /* 按钮圆角 */
  background: #1677ff; /* 主色背景 */
  border: none;
  &:hover {
    background: #4096ff; /* 悬停颜色 */
  }
}
</style>
