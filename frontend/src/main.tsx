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

useAuthStore.getState().hydrate()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#4A9BE8',
          colorSuccess: '#4A9BE8',
          colorInfo: '#4A9BE8',
          colorLink: '#357ABD',
          colorBgLayout: '#F2F7FC',
          colorBorder: '#D6E5F2',
          borderRadius: 12,
          fontFamily: '"PingFang SC", "Noto Sans SC", "Microsoft YaHei", sans-serif',
        },
        components: {
          Button: {
            controlHeightLG: 46,
            borderRadius: 13,
          },
          Card: {
            borderRadiusLG: 18,
          },
          Layout: {
            headerBg: '#1A3A5C',
            bodyBg: '#F2F7FC',
            siderBg: '#F5F9FD',
          },
          Menu: {
            itemSelectedBg: '#E3F0FA',
            itemSelectedColor: '#357ABD',
            itemHoverColor: '#357ABD',
          },
        },
      }}
    >
      <QueryClientProvider client={queryClient}>
        <AppRouter />
      </QueryClientProvider>
    </ConfigProvider>
  </React.StrictMode>,
)
