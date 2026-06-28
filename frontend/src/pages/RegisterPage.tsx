import { AuthPage } from './AuthPage'

import { register } from '../api/auth'
import { parseApiError } from '../api/client'

// 注册页：
// 1. 只负责提交账号信息并展示后端校验结果。
// 2. 注册成功后跳转登录页，由用户再完成登录获取 token。
// 3. 表单校验覆盖昵称、邮箱和密码的基础规则，复杂唯一性由后端判断。

/** 注册入口，实际由统一认证组件承载。 */
export function RegisterPage() {
  return <AuthPage initialMode="register" />
}
