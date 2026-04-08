import axios from 'axios'
import { useUserStore } from '@/stores/user'
import router from '@/router/index.js'

//配置地址
const baseURL = 'http://localhost:8080/'
//允许跨域
axios.defaults.withCredentials = true

const instance = axios.create({
  baseURL,
  timeout: 5000
})

// 在发送请求之前修改token
instance.interceptors.request.use(
  function (config) {
    // 在发送请求之前修改token
    const userStore = useUserStore()
    if (userStore.token) {
      config.headers.Authorization = userStore.token
    }

    return config
  },
  function (error) {
    // 对请求错误做些什么
    return Promise.reject(error)
  }
)

// 添加响应拦截器
instance.interceptors.response.use(
  function (response) {
    // 2xx 范围内的状态码都会触发该函数。
    
    // --- 正确的逻辑 ---
    // 只要HTTP状态码是2xx，就认为请求是成功的。
    // 我们直接返回后端发送的数据体 (response.data)。
    // 具体的业务逻辑（比如token是否存在）应该在调用API的页面组件中处理。
    return response;
  },
  function (err) {
    // 超出 2xx 范围的状态码都会触发该函数。
    
    // 错误的默认情况，只给提示
    // 从err.response.data.detail中获取FastAPI返回的错误信息
    ElMessage({
      message: err.response?.data?.detail || '服务异常，请稍后重试',
      type: 'error'
    });

    // 错误的特殊情况，如果是401未授权，则跳转到登录页
    if (err.response?.status === 401) {
      // 清除本地的用户信息（如果存在）
      // const userStore = useUserStore();
      // userStore.logout(); 
      router.push('/login');
    }
    
    // 将错误继续抛出，让页面组件的catch块也能捕获到
    return Promise.reject(err);
  
  },
  function (err) {
    //错误的默认情况，只给提示
    ElMessage({
      message: err.response.data.message || '服务异常',
      type: 'error'
    })

    //错误的特殊情况，拦截到登录
    if (err.response?.status === 401) {
      router.push('/login')
    }
    return Promise.reject(err)
  }
)

export default instance
export { baseURL }
