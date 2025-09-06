// 消息状态与通用操作：push 用户/Agent、复制、思维展开、Agent 加载态聚合
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'

let idSeed = 1
const messages = ref([])         // 核心消息列表
const thoughtExpanded = ref({})  // { msgId: bool }

// 简单 id 生成（页面级别即可）
function genId() { return 'msg_' + idSeed++ }

// 入队：用户消息
function pushUserMessage({ text = '', files = [] }) {
  const id = genId()
  messages.value.push({ id, from: 'me', text, files, copied: false, isLoading: false })
  return id
}

// 入队：Agent 占位（用于流式更新）
function pushAgentPlaceholder() {
  const id = genId()
  messages.value.push({ id, from: 'agent', text: '', isLoading: true, copied: false, thoughts: [], weblinks: [] })
  thoughtExpanded.value[id] = true
  return id
}

// 是否存在进行中的 Agent 回复（用于禁用发送按钮）
const isAgentLoading = computed(() =>
  messages.value.some(m => m.from === 'agent' && m.isLoading)
)

// 切换“思维过程”展开
function toggleThought(id) { thoughtExpanded.value[id] = !thoughtExpanded.value[id] }

// 复制消息文本到剪贴板，并设置 2 秒的“已复制”状态
function copyToClipboard(msg, idx) {
  if (!msg.text) return
  navigator.clipboard.writeText(msg.text).then(() => {
    messages.value.forEach((m, i) => { if (i !== idx) m.copied = false })
    msg.copied = true
    setTimeout(() => { msg.copied = false }, 2000)
  }, (err) => {
    // 失败兜底：在 Element Plus 不存在时用 alert
    ElMessage ? ElMessage.error('复制失败：' + err) : alert('复制失败：' + err)
  })
}

export function useChatMessages() {
  return {
    messages,
    thoughtExpanded,
    isAgentLoading,
    pushUserMessage,
    pushAgentPlaceholder,
    toggleThought,
    copyToClipboard
  }
}
