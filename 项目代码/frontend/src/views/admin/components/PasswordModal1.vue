<template>
  <!-- 修改密码弹窗 -->
  <el-dialog
    v-model="dialogFormVisible"  
    title="修改密码"
    width="400px"
  >
    <!-- 表单结构，参考你之前的成功格式 -->
    <el-form
      ref="form"
      :rules="rules"
      :model="formData"
      class="form-inline"  
    >
      <!-- 学生ID（只读） -->
      <el-form-item label="教师ID" prop="id">
        <el-input
          v-model="formData.id"
          disabled
        ></el-input>
      </el-form-item>

      <!-- 学生姓名（只读） -->
      <el-form-item label="教师姓名" prop="username">
        <el-input
          v-model="formData.username"
          disabled
        ></el-input>
      </el-form-item>

      <!-- 新密码 -->
      <el-form-item label="新密码" prop="password">
        <el-input
          v-model="formData.password"
          type="password"
          placeholder="请输入新密码"
        ></el-input>
      </el-form-item>

      <!-- 确认密码 -->
      <el-form-item label="确认密码" prop="confirmPassword">
        <el-input
          v-model="formData.confirmPassword"
          type="password"
          placeholder="请确认新密码"
        ></el-input>
      </el-form-item>
    </el-form>

    <!-- 底部按钮，与你之前的格式一致 -->
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="dialogFormVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确认修改</el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { updateTeacherPasswordService } from '@/api/admin.js'

// 控制弹窗显示（与你之前的变量名保持一致）
const dialogFormVisible = ref(false)
// 表单数据（与你之前的格式一致）
const formData = reactive({
  id: '',
  username: '',
  password: '',
  confirmPassword: ''
})
// 表单规则（与你之前的验证逻辑一致）
const rules = reactive({
  password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { 
      validator: (rule, value, callback) => {
        if (value !== formData.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      }, 
      trigger: 'blur' 
    }
  ]
})
// 表单引用（与你之前的ref命名一致）
const form = ref(null)

// 打开弹窗的方法（暴露给父组件）
const open = (row) => {
  // 填充数据（与你之前的赋值逻辑一致）
  formData.id = row.id
  formData.username = row.username
  formData.password = ''
  formData.confirmPassword = ''
  // 显示弹窗
  dialogFormVisible.value = true
}

// 提交表单（与你之前的提交逻辑一致）
const submitForm = async () => {
  await form.value.validate()
  try {
    // 调用修改密码接口
    await updateTeacherPasswordService(formData.id, formData.password)
    ElMessage.success('密码修改成功')
    dialogFormVisible.value = false
    // 通知父组件刷新列表
    emit('success')
  } catch (error) {
    ElMessage.error(error.message || '密码修改失败')
  }
}

// 定义事件和暴露方法（与你之前的组件通信方式一致）
const emit = defineEmits(['success'])
defineExpose({ open })
</script>

<style scoped lang="scss">
// 保持与你之前表单相同的样式
.form-inline .el-input {
  --el-input-width: 220px;
}
// 增加表单项间距，避免拥挤
.el-form-item {
  margin-bottom: 15px;
}
</style>