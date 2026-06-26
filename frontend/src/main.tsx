import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider } from 'antd'

import { WelcomeGate } from './components/WelcomeGate'
import { AppRouter } from './router'
import './monaco/config'
import { useAuthStore } from './stores/authStore'
import './styles/global.css'

const queryClient = new QueryClient()

useAuthStore.getState().hydrate()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#37b85a',
          colorSuccess: '#2dbb4f',
          colorInfo: '#37b85a',
          colorLink: '#1f8f46',
          colorBgLayout: '#eff8ec',
          colorBorder: '#d8ecd5',
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
            headerBg: '#16351f',
            bodyBg: '#eff8ec',
            siderBg: '#f5fbf2',
          },
          Menu: {
            itemSelectedBg: '#e4f6df',
            itemSelectedColor: '#1f7a3b',
            itemHoverColor: '#1f7a3b',
          },
        },
      }}
    >
      <QueryClientProvider client={queryClient}>
        <WelcomeGate />
        <AppRouter />
      </QueryClientProvider>
    </ConfigProvider>
  </React.StrictMode>,
)
