import { AuthPage } from './AuthPage'

// 登录页：
// 1. 登录成功后把 token 和用户信息写入 authStore。
// 2. 如果用户是从受保护路由跳转而来，优先回到原路径。
// 3. 认证错误码会转成更友好的中文提示。
// 4. 页面不直接操作 localStorage，持久化由 authStore 统一处理。

/** 登录入口，实际由统一认证组件承载。 */
export function LoginPage() {
  return <AuthPage initialMode="login" />
}
