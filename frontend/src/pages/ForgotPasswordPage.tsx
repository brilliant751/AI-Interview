import { AuthPage } from './AuthPage'

/** 找回密码入口，实际由统一认证组件承载。 */
export function ForgotPasswordPage() {
  return <AuthPage initialMode="forgot" />
}
