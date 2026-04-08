<script setup>
import { ref } from 'vue'
import { useUserStore } from '@/stores/user'
import { logoutService } from '@/api/login.js'
import { useRouter } from 'vue-router'

// 新增：导入大屏相关图标（使用更贴合的图标）
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
    <el-aside width="250px">
      <div class="el-aside__logo"></div>
      <el-menu
        active-text-color="#409EFF"
        background-color="#ffffff"
        :default-active="$route.path"
        text-color="#333333"
        router
        :collapse-transition="false" 
      >
        <!-- 新增：大屏概览（父菜单） -->
        <el-sub-menu index="/admin/overview">  <!-- 父菜单唯一标识 -->
          <template #title>
            <el-icon><Promotion /></el-icon>  <!-- 大屏图标 -->
            <span>大屏概览</span>
          </template>
          
          <!-- 子菜单1：用户活跃度 -->
          <el-menu-item index="/admin/overview/userActivity">
            <el-icon><Promotion /></el-icon>  <!-- 活跃度图标 -->
            <span>用户活跃度</span>
          </el-menu-item>
          
          <!-- 子菜单2：教学效率 -->
          <el-menu-item index="/admin/overview/teachingEfficiency">
            <el-icon><Promotion /></el-icon>  <!-- 效率图标 -->
            <span>教学效率</span>
          </el-menu-item>
          
          <!-- 子菜单3：学习效果 -->
          <el-menu-item index="/admin/overview/learningEffect">
            <el-icon><Promotion /></el-icon>  <!-- 效果图标 -->
            <span>学习效果</span>
          </el-menu-item>
        </el-sub-menu>

        <!-- 原有菜单保持不变 -->
        <el-menu-item index="/admin/stuManage">
          <el-icon><Promotion /></el-icon>
          <span>学生管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/teaManage">
          <el-icon><Promotion /></el-icon>
          <span>教师管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/resourcesManage">
          <el-icon><Promotion /></el-icon>
          <span>教学资源管理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <!-- 头部、内容区、底部保持不变 -->
      <el-header class="mainHeader">
        <div>
          <div class="system-title">教学实训智能体系统</div>
        </div>

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
/* 原有样式保持不变，新增子菜单样式优化 */
.layout-container {
  height: 100vh;
  .el-aside {
    background-color: #ffffff; // 修改为白色背景
    &__logo {
      height: 120px;
    }
    .el-menu {
      border-right: none;
      // 子菜单缩进优化
      .el-sub-menu__title {
        padding-left: 30px !important;  /* 父菜单标题缩进 */
      }
      .el-menu-item {
        padding-left: 20px !important;  /* 子菜单标题缩进，与父菜单区分 */
        background-color: #ffffff; // 按钮背景为白色
        color: #333333; // 文字为黑色
        
        &:hover {
          background-color: #f5f7fa; // 悬停背景色
          color: #409EFF; // 悬停文字颜色
        }
        
        &.is-active {
          background-color: #ecf5ff; // 激活背景色
          color: #409EFF; // 激活文字颜色
          border-right: 3px solid #409EFF; // 激活状态右边框
        }
      }
    }
  }
  /* 其他原有样式保持不变 */
  .el-header {
    background-color: rgb(29, 70, 110);
    display: flex;
    align-items: center;
    justify-content: space-between;
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