import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider } from 'antd'

import { AppRouter } from './router'
import { useAuthStore } from './stores/authStore'
import './styles/global.css'

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
