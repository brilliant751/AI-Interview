import { loader } from '@monaco-editor/react'
import * as monaco from 'monaco-editor'
import editorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'
import jsonWorker from 'monaco-editor/esm/vs/language/json/json.worker?worker'
import cssWorker from 'monaco-editor/esm/vs/language/css/css.worker?worker'
import htmlWorker from 'monaco-editor/esm/vs/language/html/html.worker?worker'
import tsWorker from 'monaco-editor/esm/vs/language/typescript/ts.worker?worker'

// Monaco 在 Vite 中需要显式配置各语言 worker：
// 1. 不同语言的语法服务由不同 worker 处理，避免主线程解析代码。
// 2. 编程练习主要使用 cpp/java/javascript，但保留 json/css/html worker 兼容编辑器默认能力。
// 3. 未匹配语言回退 editorWorker，保证基础编辑功能可用。
// 4. loader.config({ monaco }) 让 @monaco-editor/react 使用当前打包后的 monaco 实例。

self.MonacoEnvironment = {
  getWorker(_: string, label: string) {
    if (label === 'json') {
      return new jsonWorker()
    }
    if (label === 'css' || label === 'scss' || label === 'less') {
      return new cssWorker()
    }
    if (label === 'html' || label === 'handlebars' || label === 'razor') {
      return new htmlWorker()
    }
    if (label === 'typescript' || label === 'javascript') {
      return new tsWorker()
    }
    return new editorWorker()
  },
}

loader.config({ monaco })
