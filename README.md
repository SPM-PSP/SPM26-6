# Fish 团队协作交流平台

## 项目简介
针对高校实验室、小型创业团队、课程项目组等小团队的协作痛点（任务分配混乱、进度不透明、文件分散、沟通无闭环），开发一款轻量化、易操作的团队协作交流平台 “Fish”，聚焦 “任务管理 + 团队沟通 + 文件共享” 核心场景，替代零散的微信群、Excel、网盘等工具，实现协作全流程一体化。

## 项目目标
1. 开发 Web 端（用户端 + 管理员端）协作平台，支持 5-20 人小团队使用；
2. 核心功能覆盖 “团队管理、任务流转、文件共享、基础沟通、数据统计”；
3. 保证系统稳定、界面友好、操作简单，满足小团队日常协作需求；
4. 完成完整的项目开发流程（需求→设计→开发→测试→部署→文档），适配高校软件实践课程要求。

## 核心功能
### 1. 团队管理
- 团队创建与成员邀请
- 角色权限分配（管理员/普通成员）
- 团队信息编辑与解散

### 2. 任务流转
- 任务创建与分配
- 任务状态跟踪（待办/进行中/已完成/已取消）
- 任务优先级设置
- 任务评论与附件上传
- 任务进度统计

### 3. 文件共享
- 团队文件库管理
- 文件上传/下载/预览
- 文件版本控制
- 文件夹分类管理

### 4. 基础沟通
- 团队群聊与私信
- 消息通知与已读状态
- 消息附件发送

### 5. 数据统计
- 任务完成情况统计
- 团队成员工作量统计
- 文件共享活跃度统计

## 技术栈
- 前端：Vue 3 + TypeScript + Vite
- 后端：Node.js + Express
- 数据库：MongoDB
- 实时通信：Socket.io
- 样式框架：Tailwind CSS

## 安装与运行
### 前置要求
- Node.js >= 18.0.0
- MongoDB >= 5.0.0

### 安装步骤
1. 克隆项目
```bash
git clone <仓库地址>
cd fish
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
- 在 `backend/.env` 中配置 MongoDB 连接字符串、端口号等
- 在 `frontend/.env` 中配置后端接口地址

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
fish/
├── frontend/          # 前端代码
│   ├── src/
│   │   ├── components/  # 公共组件
│   │   ├── views/       # 页面组件
│   │   ├── router/      # 路由配置
│   │   ├── store/       # 状态管理
│   │   └── utils/       # 工具函数
│   └── package.json
├── backend/           # 后端代码
│   ├── src/
│   │   ├── controllers/  # 控制器
│   │   ├── models/       # 数据模型
│   │   ├── routes/       # 路由配置
│   │   └── middleware/   # 中间件
│   └── package.json
└── README.md
```

## 开发流程
1. 需求分析与设计
2. 前端页面开发
3. 后端接口开发
4. 联调测试
5. 部署上线

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
## 项目成员
- 项目负责人：陈城
- 开发人员：黄星宇
- 开发人员：杜晟
- 开发人员：马子恒
- 开发人员：张伟绅
- 开发人员：钮天宸
