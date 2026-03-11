# AI 学伴 - 轻量化团队 AI 辅助学习平台

## 项目简介
面向学生/小团队的 AI 辅助学习工具集，无需自研 AI 模型（调用大厂开放 API），核心功能聚焦 "AI 问答、AI 笔记总结、AI 错题分析"，技术门槛低，但软件开发流程完整，5 人分工明确，2 个月能做完。

## 项目目标
1. 开发 Web 端（学生端 + 教师端 + 管理员端）AI 辅助学习平台；
2. 核心功能覆盖 "AI 批改作业、AI 出题、AI 答疑、教案管理、试题管理"；
3. 保证系统稳定、界面友好、操作简单，满足师生日常教学需求；
4. 完成完整的项目开发流程（需求→设计→开发→测试→部署→文档），适配高校软件实践课程要求。

## 核心功能
### 学生端
#### 1. AI 答疑
- 智能问答系统，支持学科知识查询
- 多轮对话交互，深入理解问题
- 答案质量评价与反馈

#### 2. AI 笔记总结
- 上传课堂笔记或学习资料
- AI 自动生成知识点总结
- 重点难点标注与提取

#### 3. AI 错题分析
- 上传错题图片或题目
- AI 分析错误原因与解题思路
- 生成个性化错题本与练习推荐

#### 4. 作业提交与批改
- 在线提交作业
- 查看 AI 批改结果与评分
- 错误解析与改进建议

### 教师端
#### 1. AI 出题
- 根据知识点自动生成试题
- 支持多种题型（选择题、填空题、简答题等）
- 难度级别自定义调整
- 试题质量评估与筛选

#### 2. 教案管理
- 创建与编辑教学教案
- AI 辅助教案内容生成
- 教案模板管理与复用
- 教案分享与协作

#### 3. 试题管理
- 试题库管理与分类
- 试题标签与知识点关联
- 试卷自动组卷
- 试题导入导出

#### 4. 学生管理
- 学生信息管理
- 学习进度跟踪
- 作业批改与反馈
- 学习数据分析

### 管理员端
#### 1. 用户管理
- 用户注册审核
- 角色权限分配（学生/教师/管理员）
- 用户信息编辑与删除
- 账号状态管理

#### 2. 系统配置
- AI 接口配置与管理
- 系统参数设置
- 日志监控与管理
- 数据备份与恢复

#### 3. 数据统计
- 平台使用情况统计
- 用户活跃度分析
- AI 调用量统计
- 教学效果数据分析

## 技术栈
- 前端：Vue 3 + TypeScript + Vite
- 后端：Node.js + Express
- 数据库：MongoDB
- AI 接口：OpenAI API / 百度文心一言 / 阿里通义千问
- 实时通信：Socket.io
- 样式框架：Tailwind CSS
- 文件处理：Multer / Sharp

## 安装与运行
### 前置要求
- Node.js >= 18.0.0
- MongoDB >= 5.0.0
- AI API Key（OpenAI / 百度 / 阿里等）

### 安装步骤
1. 克隆项目
```bash
git clone https://github.com/SPM-PSP/SPM26-6.git
cd SPM26-6
```

2. 安装依赖
```bash
# 前端依赖
cd frontend
npm install

# 后端依赖
cd ../backend
npm install
```

3. 配置环境变量
- 在 `backend/.env` 中配置：
  ```
  MONGODB_URI=mongodb://localhost:27017/ai-learning
  PORT=3000
  JWT_SECRET=your-jwt-secret
  OPENAI_API_KEY=your-openai-api-key
  BAIYUN_API_KEY=your-baidu-api-key
  QWEN_API_KEY=your-qwen-api-key
  ```
- 在 `frontend/.env` 中配置：
  ```
  VITE_API_URL=http://localhost:3000/api
  ```

4. 启动项目
```bash
# 启动后端服务
cd backend
npm run dev

# 启动前端服务
cd ../frontend
npm run dev
```

## 项目结构
```
SPM26-6/
├── frontend/          # 前端代码
│   ├── src/
│   │   ├── components/  # 公共组件
│   │   ├── views/       # 页面组件
│   │   │   ├── student/  # 学生端页面
│   │   │   ├── teacher/  # 教师端页面
│   │   │   └── admin/    # 管理员端页面
│   │   ├── router/      # 路由配置
│   │   ├── store/       # 状态管理
│   │   └── utils/       # 工具函数
│   └── package.json
├── backend/           # 后端代码
│   ├── src/
│   │   ├── controllers/  # 控制器
│   │   ├── models/       # 数据模型
│   │   ├── routes/       # 路由配置
│   │   ├── middleware/   # 中间件
│   │   └── services/     # AI 服务
│   └── package.json
└── README.md
```

## 开发流程
1. 需求分析与设计
2. 前端页面开发（学生端/教师端/管理员端）
3. 后端接口开发
4. AI 功能集成与测试
5. 联调测试
6. 部署上线

## 贡献指南
1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 许可证
MIT License

## 联系方式
如有问题或建议，请通过以下方式联系：
- 邮箱：3555670675@qq.com
- 项目地址：https://github.com/SPM-PSP/SPM26-6.git

## 项目成员
- 项目负责人：陈城
- 开发人员：黄星宇
- 开发人员：杜晟
- 开发人员：马子恒
- 开发人员：张伟绅
- 开发人员：钮天宸
