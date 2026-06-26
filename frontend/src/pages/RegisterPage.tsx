import { AuthPage } from './AuthPage'

/** 注册入口，实际由统一认证组件承载。 */
export function RegisterPage() {
  return <AuthPage initialMode="register" />
}
