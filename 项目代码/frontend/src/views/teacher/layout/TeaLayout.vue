<script setup>
import { ref } from 'vue'
import { useUserStore } from '@/stores/user'
import { logoutService } from '@/api/login.js'
import { useRouter } from 'vue-router'

// 两个需要导入的element组件
import { Promotion } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

// 设置用户名字
const userName = ref('')
const userStore = useUserStore()
userName.value = userStore.userName

// 登出功能
const router = useRouter()
const logout = async () => {
  ElMessage.success('登出成功')
  router.push('/login')
}
</script>

<template>
  <el-container class="layout-container">
    <el-aside width="250px"> <!-- 宽度调整为250px保持一致 -->
      <div class="el-aside__logo"></div>
      <el-menu
        active-text-color="#409EFF"  
        background-color="#ffffff"  
        :default-active="$route.path"
        text-color="#333333"        
        router
        :collapse-transition="false" 
      >
        <el-menu-item index="/teacher/situationassessment">
          <el-icon><Promotion /></el-icon>
          <span>学生学情评估</span>
        </el-menu-item>
        <el-menu-item index="/teacher/aimake">
          <el-icon><Promotion /></el-icon>
          <span>ai制作考核</span>
        </el-menu-item>
        <el-menu-item index="/teacher/PreDesign">
          <el-icon><Promotion /></el-icon>
          <span>备课与设计</span>
        </el-menu-item>
        <el-menu-item index="/teacher/questionfork">
          <el-icon><Promotion /></el-icon>
          <span>题库</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="mainHeader">
          <div class="system-title">教学实训智能体系统</div>
        <div style="display: flex; align-items: center">
          <div></div>
          <div style="margin-left: 10px">
            <el-button type="primary" @click="logout">登出</el-button>
          </div>
        </div>
      </el-header>
      <el-main>
        <router-view></router-view>
      </el-main>
      <el-footer>智能平台 ©2025 Created by 502C组</el-footer>
    </el-container>
  </el-container>
</template>

<style scoped lang="scss">
.layout-container {
  height: 100vh;
  .el-aside {
    background-color: #ffffff; /* 侧边栏背景保持白色 */
    &__logo {
      height: 120px; /* 保持logo区域高度一致 */
    }
    .el-menu {
      border-right: none; /* 去除右侧边框 */
      // 统一菜单按钮样式
      .el-menu-item {
        background-color: #ffffff; // 按钮背景白色
        color: #333333; // 文字黑色
        
        &:hover {
          background-color: #f5f7fa; // 悬停背景色
          color: #409EFF; // 悬停文字蓝色
        }
        
        &.is-active {
          background-color: #ecf5ff; // 激活状态背景色
          color: #409EFF; // 激活文字蓝色
          border-right: 3px solid #409EFF; // 激活状态右侧蓝色标识
        }
      }
    }
  }
  .el-header {
    background-color: rgb(29, 70, 110);
    display: flex;
    align-items: center;
    justify-content: space-between;
    .el-dropdown__box {
      display: flex;
      align-items: center;
      .el-icon {
        color: #999;
        margin-left: 10px;
      }

      &:active,
      &:focus {
        outline: none;
      }
    }
  }
  .el-footer {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    color: #666;
  }
}

.mainHeader {
  display: flex;
  justify-content: space-between;
  background-color: rgb(4, 131, 213);
}

.system-title {
  color: #ffffff;
  font-size: 30px;
  font-weight: bold;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  letter-spacing: 2px;
  transition: all 0.3s ease;
  
  &:hover {
    transform: translateY(-2px);
    text-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
  }
}
</style>