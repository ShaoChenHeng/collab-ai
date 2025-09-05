<template>
  <div class="chat-root">
    <div class="chat-main">
      <ChatMessages
        :messages="messages"
        :thought-expanded-map="thoughtExpanded"
        :current-web-links-msg-id="currentWebLinksMsgId"
        :render-markdown="renderMarkdown"
        @toggle-thought="toggleThought"
        @open-web-links="openWebLinksPanel"
        @copy="onCopy"
      />

      <ChatInput
        ref="chatInputRef"
        v-model="input"
        :can-send="canSend"
        :deep-thinking="useDeepThinking"
        :web-search="useWebSearch"
        @send="sendMessage"
        @toggle-web="toggleWebSearch"
        @toggle-deep="toggleDeepThinking"
      />

      <div class="ai-disclaimer">
        内容由 AI 生成，请仔细甄别
      </div>
    </div>

    <div v-if="weblinksPanelVisible" class="weblinks-panel">
      <WebLinksPanel
        :show="weblinksPanelVisible"
        :links="currentWebLinks"
        @close="closeWebLinksPanel"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import MarkdownIt from 'markdown-it'
import { fetchAgentReplyStream } from '@/api/chat.js'
import WebLinksPanel from '@/components/WebLinksPanel.vue'
import { useWebLinksPanel } from '@/hooks/useWebLinksPanel.js'

// 子组件
import ChatMessages from '@/components/ChatMessages.vue'
import ChatInput from '@/components/ChatInput.vue'

// 计算与状态
const messages = ref([])
let idSeed = 1
function genId() {
  return 'msg_' + idSeed++
}
// 初始一条欢迎消息
messages.value = [
  { id: genId(), from: 'agent', text: '你好！我是AI助手，有什么可以帮你的吗？', copied: false, isLoading: false },
]

const input = ref('')
const useWebSearch = ref(false)
const useDeepThinking = ref(false)
const thoughtExpanded = ref({})

// markdown 渲染（维持原状）
const md = new MarkdownIt({
  linkify: true,
  breaks: false,
  typographer: false,
  html: true,
  xhtmlOut: true
})
md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
  const aIndex = tokens[idx].attrIndex('target')
  if (aIndex < 0) tokens[idx].attrPush(['target', '_blank'])
  else tokens[idx].attrs[aIndex][1] = '_blank'
  const relIndex = tokens[idx].attrIndex('rel')
  if (relIndex < 0) tokens[idx].attrPush(['rel', 'noopener noreferrer'])
  else tokens[idx].attrs[relIndex][1] = 'noopener noreferrer'
  return self.renderToken(tokens, idx, options)
}
const renderMarkdown = (text) => md.render(text || '')

// weblinks 面板
const {
  weblinksPanelVisible,
  currentWebLinksMsgId,
  currentWebLinks,
  openWebLinksPanel,
  closeWebLinksPanel,
  setWebLinksToMsg
} = useWebLinksPanel(messages)

// 发送能力控制
const isAgentLoading = computed(() =>
  messages.value.some(m => m.from === 'agent' && m.isLoading)
)
const canSend = computed(() =>
  input.value.trim().length > 0 && !isAgentLoading.value
)

// UI 交互
function toggleWebSearch() { useWebSearch.value = !useWebSearch.value }
function toggleDeepThinking() { useDeepThinking.value = !useDeepThinking.value }
function toggleThought(id) { thoughtExpanded.value[id] = !thoughtExpanded.value[id] }

// 复制
function copyToClipboard(msg, idx) {
  if (!msg.text) return
  navigator.clipboard.writeText(msg.text).then(() => {
    messages.value.forEach((m, i) => { if (i !== idx) m.copied = false })
    msg.copied = true
    setTimeout(() => { msg.copied = false }, 2000)
  }, (err) => {
    ElMessage ? ElMessage.error('复制失败：' + err) : alert('复制失败：' + err);
  })
}
function onCopy({ msg, idx }) {
  copyToClipboard(msg, idx)
}

// 发送消息（逻辑保持不变，未调整 webSearch 传参的原始行为）
const chatInputRef = ref(null)
async function sendMessage(e) {
  if (e) e.preventDefault?.()
  if (!canSend.value) return
  if (!input.value.trim()) return

  let userText = input.value.trim()
  if (useWebSearch.value) {
    userText = '请你网络搜索相关关键字后回答：' + userText
    useWebSearch.value = false // 发送后自动关闭高亮
  }

  // 用户消息入队
  messages.value.push({
    id: genId(),
    from: 'me',
    text: input.value.trim(),
    copied: false,
    isLoading: false
  })
  input.value = ''
  chatInputRef.value?.autoResize?.()

  // 占位的Agent消息
  const agentMsgId = genId()
  messages.value.push({
    id: agentMsgId,
    from: 'agent',
    text: '',
    isLoading: true,
    copied: false,
    thoughts: [],
    weblinks: []
  })
  thoughtExpanded.value[agentMsgId] = true

  const options = {
    deepThinking: useDeepThinking.value,
    webSearch: useWebSearch.value
  }

  fetchAgentReplyStream(userText, options, (entry) => {
    if (!entry.content || entry.content.trim() === '') return
    const msg = messages.value.find(m => m.id === agentMsgId)
    if (!msg) return

    if (entry.type === "tool_result" && entry.tool) {
      if (entry.tool === "today_date") {
        msg.thoughts.push(`调用today_date工具，得到当前日期：${entry.content}`)
      } else if (entry.tool === "google_search") {
        let results
        try {
          results = JSON.parse(entry.content)
        } catch {
          results = []
        }
        setWebLinksToMsg(agentMsgId, results)
        const n = Array.isArray(results) ? results.length : 0
        let str = `调用“google_search”工具，搜索关键词为：“${msg.searchQuery || ''}”，得到了${n}个搜索结果：`
        if (n > 0) {
          const showResults = results.slice(0, 3)
          str += "\n"
          showResults.forEach((item, i) => {
            str += `【${i+1}】标题：${item.title} 是一个与问题高度相关的搜索结果。\n主要内容：${item.snippet}\n访问链接：${item.link}${item.displayLink ? `（来自：${item.displayLink}）` : ''}\n`
          })
        }
        msg.thoughts.push(str.trim())
      } else if (entry.tool === "url_summary") {
        const cleanContent = entry.content.replace(/\r?\n/g, '')
        const preview = cleanContent.length > 60 ? cleanContent.slice(0, 60) + '……' : cleanContent
        msg.thoughts.push(`调用“url_summary”工具对相关网页内容爬取，该网页介绍了：${preview}`)
      } else {
        msg.thoughts.push(`调用“${entry.tool}”工具，得到结果：${entry.content}`)
      }
    } else if (entry.type === "intermediate_step") {
      msg.thoughts.push(entry.content)
      if (entry.query) msg.searchQuery = entry.query
    } else if (entry.type === "chat") {
      msg.text = entry.content
      msg.isLoading = false
    }
  })
}
</script>

<style scoped>
.chat-root {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: row;
  justify-content: center;
  align-items: stretch;
  position: relative;
  overflow: hidden;
}
.chat-main {
  width: 60vw;
  height: 100vh;
  z-index: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
}
.ai-disclaimer {
  width: 98%;
  margin: 8px auto 0 auto;
  text-align: center;
  font-size: 11px;
  color: #aaa;
  letter-spacing: 0.02em;
  user-select: none;
  z-index: 1;
}
.weblinks-panel {
  flex:1;
  position: absolute;
  top: 0;
  right: 0;
  width: 20vw;
  height: 100vh;
  background: #fff;
  border-left: 1px solid #e4e8ef;
  box-shadow: -2px 0 12px rgba(0,0,0,0.07);
  z-index: 10;
  display: flex;
  flex-direction: column;
}
</style>
