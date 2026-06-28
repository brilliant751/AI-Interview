import { AuthPage } from './AuthPage'

/** 登录入口，实际由统一认证组件承载。 */
export function LoginPage() {
  return <AuthPage initialMode="login" />
}
