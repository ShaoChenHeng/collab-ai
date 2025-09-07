<template>
  <div class="chat-root">
    <div class="chat-main">
      <!-- 聊天消息列表 -->
      <ChatMessages
        :messages="messages"
        :thought-expanded-map="thoughtExpanded"
        :current-web-links-msg-id="currentWebLinksMsgId"
        :render-markdown="renderMarkdown"
        @toggle-thought="toggleThought"
        @open-web-links="openWebLinksPanel"
        @copy="onCopy"
      />
      <!-- 文件气泡列表 -->
      <div class="file-bubbles-row" v-if="fileItems.length">
        <FileBubble
          v-for="f in fileItems"
          :key="f.id"
          :filename="f.name"
          @close="removeFileItem(f.id)"
        />
      </div>
      <!-- 输入框 -->
      <ChatInput
        ref="chatInputRef"
        v-model="input"
        :can-send="canSend"
        :deep-thinking="useDeepThinking"
        :web-search="useWebSearch"
        @send="sendMessage"
        @toggle-web="toggleWebSearch"
        @toggle-deep="toggleDeepThinking"
        @pick-files="onPickFiles"
      />
      <!-- AI 免责声明 -->
      <div class="ai-disclaimer">
        {{ aiDisclaimer }}
      </div>
    </div>
    <!-- 侧边栏：网页链接面板 -->
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
import { ref } from 'vue'
import { fetchAgentReplyStream, uploadFile } from '@/api/chat.js'

import WebLinksPanel from '@/components/WebLinksPanel.vue'
import ChatMessages from '@/components/ChatMessages.vue'
import ChatInput from '@/components/ChatInput.vue'
import FileBubble from '@/components/FileBubble.vue'

import { useWebLinksPanel } from '@/hooks/useWebLinksPanel.js'
import { useFileQueue } from '@/hooks/useFileQueue.js'
import { useChatMessages } from '@/hooks/useChatMessages.js'
import { useAgentStream } from '@/hooks/useAgentStream.js'
import { useMarkdown } from '@/hooks/useMarkdown.js'
import { useSendMessage } from '@/hooks/useSendMessage.js'

// 基本输入/开关
const input = ref('')
const useWebSearch = ref(false)
const useDeepThinking = ref(false)
// 文件队列（选择、去重、校验、移除、取出发送）
const { files: fileItems, onPickFiles, removeFileItem, takeAttachments } = useFileQueue()
// 聊天消息（列表、加载状态、思考展开、添加用户消息、添加AI占位、切换思考、复制）
const { messages, thoughtExpanded, isAgentLoading, pushUserMessage, pushAgentPlaceholder, toggleThought, copyToClipboard } = useChatMessages()
// Markdown 渲染
const { renderMarkdown } = useMarkdown()
// 网页链接面板（显示、隐藏、设置当前消息的链接）
const {
  weblinksPanelVisible,
  currentWebLinksMsgId,
  currentWebLinks,
  openWebLinksPanel,
  closeWebLinksPanel,
  setWebLinksToMsg
} = useWebLinksPanel(messages)
const { sendWithStream } = useAgentStream({ messages, pushAgentPlaceholder, setWebLinksToMsg, fetchAgentReplyStream })

// AI 免责声明仅渲染
const aiDisclaimer = '内容由 AI 生成，请仔细甄别'

// 初始欢迎消息
messages.value.push({
  id: 'msg_welcome',
  from: 'agent',
  text: '你好！我是AI助手，有什么可以帮你的吗？',
  copied: false,
  isLoading: false }
)

const chatInputRef = ref(null)

// 使用抽象后的发送逻辑
const { sendMessage, canSend } = useSendMessage({
  input,
  fileItems,
  takeAttachments,
  pushUserMessage,
  uploadFile,
  sendWithStream,
  useWebSearch,
  useDeepThinking,
  chatInputRef,
  isAgentLoading,
})

function onCopy({ msg, idx }) { copyToClipboard(msg, idx) }
function toggleWebSearch() { useWebSearch.value = !useWebSearch.value }
function toggleDeepThinking() { useDeepThinking.value = !useDeepThinking.value }
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
.file-bubbles-row {
  width: 98%;
  margin: 8px auto 4px auto;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
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
