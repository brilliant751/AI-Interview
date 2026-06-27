import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider } from 'antd'

import { AppRouter } from './router'
import './monaco/config'
import { useAuthStore } from './stores/authStore'
import './styles/global.css'

// 前端应用入口：
// 1. 先 hydrate 认证状态，让路由首屏能判断用户是否已登录。
// 2. QueryClientProvider 提供 React Query 缓存和请求状态管理。
// 3. Ant Design ConfigProvider 统一组件上下文。
// 4. Monaco 配置在入口导入一次即可，被编程练习页面复用。
// 5. StrictMode 用于开发期发现副作用问题，生产构建不会改变业务逻辑。

/** 全局 QueryClient 实例。 */
const queryClient = new QueryClient()

/** 启动时恢复本地会话状态。 */
useAuthStore.getState().hydrate()

/** 渲染前端应用根节点。 */
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider>
      <QueryClientProvider client={queryClient}>
        <AppRouter />
      </QueryClientProvider>
    </ConfigProvider>
  </React.StrictMode>,
)
