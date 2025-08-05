<template>
  <div class="chat-root">
    <div class="chat-main">
      <div class="chat-messages" ref="messagesEl">
        <template v-for="(msg, idx) in messages" :key="msg.id">
          <!-- 用户消息 -->
          <div v-if="msg.from === 'me'" class="message-row user-row">
            <div class="bubble-with-toolbar user-side">
              <div class="user-message-bubble">
                {{ msg.text }}
              </div>
              <div class="bubble-toolbar user-toolbar">
                <el-icon
                  class="toolbar-icon"
                  title="复制"
                  v-if="!msg.copied"
                  @click="copyToClipboard(msg, idx)">
                  <CopyDocument />
                </el-icon>
                <el-icon
                  class="toolbar-icon"
                  title="已复制"
                  v-else
                  style="color: #52c41a">
                  <Check />
                </el-icon>
                <el-icon class="toolbar-icon" title="重新编辑"><EditPen /></el-icon>
              </div>
            </div>
          </div>
          <!-- agent消息：左侧头像，右侧上下两个气泡 -->
          <template v-else-if="msg.from === 'agent'">
            <div class="message-row agent-row">
              <!-- 左侧头像 -->
              <img class="agent-avatar" src="/mu.png" alt="头像" />
              <!-- 右侧气泡堆叠 -->
              <div class="agent-bubble-stack">
                <!-- 顶部过程泡泡 -->
                <button
                  class="thought-toggle-btn-row"
                  @click="toggleThought(msg.id)"
                  v-if="msg.thoughts && msg.thoughts.length > 0"
                >
                  <el-icon class="thought-static-icon"><EditPen /></el-icon>
                  <span class="thought-title-btn">智能体思考</span>
                  <el-icon class="arrow-icon-btn" v-if="thoughtExpanded[msg.id]"><ArrowUp /></el-icon>
                  <el-icon class="arrow-icon-btn" v-else><ArrowDown /></el-icon>
                </button>
                <transition name="fade">
                  <div v-if="thoughtExpanded[msg.id]" class="agent-thought-bubble">
                    <transition-group name="fade-in" tag="div">
                      <div
                        v-for="(t, i) in msg.thoughts"
                        :key="i"
                        class="thought-content-row"
                      >
                        {{ t }}
                      </div>
                    </transition-group>
                  </div>
                </transition>
                <!-- 回复泡泡 -->
                <div class="bubble-with-toolbar agent-side">
                  <div class="agent-message-block">
                    <template v-if="msg.isLoading">
                      <el-icon class="thinking-icon is-loading" style="font-size: 24px;">
                        <Loading />
                      </el-icon>
                      <span style="margin-left: 0.5em;" v-if="msg.text">{{ msg.text }}</span>
                    </template>
                    <transition name="fade-in">
                      <span v-if="!msg.isLoading" v-html="renderMarkdown(msg.text)"></span>
                    </transition>
                  </div>
<div class="bubble-toolbar agent-toolbar">
                    <el-icon
                      class="toolbar-icon"
                      title="复制"
                      v-if="!msg.copied && !msg.isLoading"
                      @click="copyToClipboard(msg, idx)">
                      <CopyDocument />
                    </el-icon>
                    <el-icon
                      class="toolbar-icon"
                      title="已复制"
                      v-else-if="!msg.isLoading"
                      style="color: #52c41a"
                    >
                      <Check />
                    </el-icon>
                    <el-icon v-if="!msg.isLoading" class="toolbar-icon" title="重新生成"><Refresh /></el-icon>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </template>
      </div>
      <!-- 输入区container，分上下两部分 -->
      <div
        class="chat-input-container"
        :class="{ focused: inputFocused }"
      >
        <!-- 上方输入框，单独一行，自适应多行 -->
        <textarea
          v-model="input"
          class="chat-input"
          placeholder="输入消息..."
          autocomplete="off"
          rows="2"
          ref="textareaEl"
          @input="autoResize"
          @focus="inputFocused = true"
          @blur="inputFocused = false"
          @keydown.enter.exact.prevent="sendMessage"
        ></textarea>
        <!-- 下方按钮container -->
        <div class="chat-btns-container">
          <button class="input-btn" @click="onLocalDoc">
            <el-icon class="btn-icon"><Document /></el-icon>
            <span class="btn-text">本地文档</span>
          </button>
          <button
            class="input-btn"
            :class="{ active: useWebSearch }"
            @click="toggleWebSearch"
          >
            <el-icon class="btn-icon"><Search /></el-icon>
            <span class="btn-text">网络搜索</span>
          </button>
          <div class="btns-spacer"></div>
          <button
            class="chat-send-btn"
            :disabled="!canSend"
            :class="{ disabled: !canSend }"
            @click="sendMessage"
            title="发送"
          >
            <el-icon><Promotion /></el-icon>
          </button>
        </div>
      </div>
      <!-- 免责声明应该和输入区平级在 chat-main 内部 -->
      <div class="ai-disclaimer">
        内容由 AI 生成，请仔细甄别
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Check, Document, Search, Promotion, CopyDocument, EditPen, Refresh, Loading, ArrowUp, ArrowDown } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import {   fetchAgentReplyStream } from '@/api/chat.js'
import MarkdownIt from 'markdown-it'
import { computed } from 'vue'

const isAgentLoading = computed(() => messages.value.some(m => m.from === 'agent' && m.isLoading));
const canSend = computed(() => input.value.trim().length > 0 && !isAgentLoading.value);
// 简单ID生成器
let idSeed = 1
function genId() {
  return 'msg_' + idSeed++
}
const useWebSearch = ref(false)
const thoughtExpanded = ref({})
const md = new MarkdownIt({
  linkify: true,
  breaks: false,
  typographer: false,
  html: true,
  xhtmlOut: true
})
const messages = ref([
  { id: genId(), from: 'agent', text: '你好！我是AI助手，有什么可以帮你的吗？', copied: false, isLoading: false },
])
const input = ref('')
const messagesEl = ref(null)
const textareaEl = ref(null)
const inputFocused = ref(false)
const renderMarkdown = (text) => {
  return md.render(text || '')
}
function toggleThought(id) {
  thoughtExpanded.value[id] = !thoughtExpanded.value[id]
}
async function sendMessage(e) {
  if (e) e.preventDefault?.()
  if (!canSend.value) return
  if (!input.value.trim()) return

  let userText = input.value.trim()
  // 如果选中了网络搜索，加前缀
  if (useWebSearch.value) {
    userText = '请你使用网络搜索，' + userText
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
  autoResize()

  // 占位的Agent消息，为流式过程做准备
  const agentMsgId = genId()
  messages.value.push({
    id: agentMsgId,
    from: 'agent',
    isLoading: true,
    copied: false,
    thoughts: []  // 用于展示中间过程
  })
  thoughtExpanded.value[agentMsgId] = true

  fetchAgentReplyStream(userText, (entry) => {
    // 忽略掉 content 为空的 entry
    if (!entry.content || entry.content.trim() === '') return;

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
        const n = Array.isArray(results) ? results.length : 0
        let str = `调用“google_search”工具，得到了${n}个搜索结果：`
        if (n > 0) {
          // 只取前三项
          const showResults = results.slice(0, 3)
          str += "\n"
          showResults.forEach((item, i) => {
            str += `【${i+1}】标题：${item.title} 是一个与问题高度相关的搜索结果。\n主要内容：${item.snippet}\n访问链接：${item.link}${item.displayLink ? `（来自：${item.displayLink}）` : ''}\n`
          })
        }
        msg.thoughts.push(str.trim())
      } else if (entry.tool === "url_summary") {
        // 去掉所有换行
        const cleanContent = entry.content.replace(/\r?\n/g, '')
        // 截取前60字
        const preview = cleanContent.length > 60 ? cleanContent.slice(0, 60) + '……' : cleanContent
        msg.thoughts.push(`调用“url_summary”工具对相关网页内容爬取，该网页介绍了：${preview}`)
      } else {
        msg.thoughts.push(`调用“${entry.tool}”工具，得到结果：${entry.content}`)
      }
    } else if (entry.type === "intermediate_step") {
      msg.thoughts.push(entry.content)
    } else if (entry.type === "chat") {
      msg.text = entry.content
      msg.isLoading = false
    }
  })
}
function copyToClipboard(msg, idx) {
  if (!msg.text) return;
  navigator.clipboard.writeText(msg.text).then(() => {
    // 先把所有消息的copied设为false，然后只标记当前为true
    messages.value.forEach((m, i) => { if (i !== idx) m.copied = false })
    msg.copied = true;
    // 2秒后自动恢复为CopyDocument
    setTimeout(() => { msg.copied = false }, 2000)
  }, (err) => {
    ElMessage ? ElMessage.error('复制失败：' + err) : alert('复制失败：' + err);
  });
}
function autoResize() {
  if (textareaEl.value) {
    textareaEl.value.style.height = 'auto'
    textareaEl.value.style.height = textareaEl.value.scrollHeight + 'px'
  }
}
function toggleWebSearch() {
  useWebSearch.value = !useWebSearch.value
}
function onLocalDoc() {
  alert('本地文档功能待实现')
}
</script>

<style scoped>
.chat-root {
  width: 100vw;
  height: 100vh;
  background: #fff;
  display: flex;
  justify-content: center;
  align-items: center;
}
.chat-main {
  width: 60vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #fff;
}
.chat-input-container {
  width: 98%;
  margin: 0 auto 0 auto;
  background: #f4f6fa;
  border: 1.5px solid #e0e0e0;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  box-shadow: 0 1px 8px rgba(0,0,0,0.04);
  transition: border-color 0.2s, box-shadow 0.2s;
  position: relative;
  z-index: 2;
  border-radius: 8px;
}
.chat-input-container.focused {
  border-color: #409eff;
  box-shadow: 0 2px 16px rgba(64,158,255,0.10);
}
.chat-input {
  width: 100%;
  min-height: 70px;
  max-height: 320px;
  border: none;
  border-radius: 18px 18px 0 0;
  outline: none;
  font-size: 13px;
  line-height: 1.4;
  padding: 13px 12px 7px 12px;
  background: #f4f6fa;
  margin: 0;
  box-sizing: border-box;
  resize: none;
  overflow-y: auto;
  transition: box-shadow 0.2s;
  color: #222;
  vertical-align: top;
}
.chat-input::placeholder {
  color: #b0b3ba;
  font-size: 14px;
  line-height: 1.4;
  text-align: left;
  vertical-align: top;
}
.chat-btns-container {
  display: flex;
  align-items: flex-end;
  width: 100%;
  gap: 10px;
  background: #f4f6fa;
  padding: 0 10px 13px 10px;
  margin: 0;
  min-height: 36px;
  box-sizing: border-box;
  border-radius: 0 0 18px 18px;
}
.input-btn {
  height: 30px;
  background: #fff;
  color: #333;
  border: none;
  border-radius: 8px;
  padding: 0 5px 0 5px;
  font-size: 13px;
  cursor: pointer;
  transition: background .2s;
  display: flex;
  align-items: center;
  line-height: 1;
  margin: 0;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
.input-btn:hover {
  background: #f2f6fc;
}
.input-btn.active {
  background: #409eff;
  color: #fff;
}
.input-btn.active .btn-icon {
  color: #fff;
}
.btn-icon {
  font-size: 15px;
  display: flex;
  align-items: center;
}
.btn-text {
  margin-left: 7px;
  font-size: 13px;
}
.chat-send-btn {
  background: #409eff;
  color: #fff;
  border: none;
  height: 30px;
  width: 48px;
  border-radius: 8px;
  font-size: 22px;
  cursor: pointer;
  transition: background 0.2s;
  align-self: flex-end;
  margin-left: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  margin: 0;
  padding: 0;
}
.chat-send-btn:hover {
  background: #1976d2;
}
.chat-send-btn:disabled,
.chat-send-btn.disabled {
  background: #d7dde5;
  color: #fff;
  cursor: not-allowed;
  opacity: 0.7;
}
.chat-send-btn:disabled:hover,
.chat-send-btn.disabled:hover {
  background: #d7dde5;
}
.btns-spacer {
  flex: 1;
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
.chat-messages {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 22px 0 12px 0;
  display: flex;
  flex-direction: column;
  gap: 18px;
  scrollbar-width: thin;
  scrollbar-color: #c2c6cc #f2f3f8;
}
.chat-messages::-webkit-scrollbar {
  width: 6px;
  background: #f2f3f8;
  border-radius: 6px;
}
.chat-messages::-webkit-scrollbar-thumb {
  background: #c2c6cc;
  border-radius: 6px;
}
.chat-messages::-webkit-scrollbar-thumb:hover {
  background: #a6adb8;
}
.message-row {
  display: flex;
  width: 100%;
}
.user-row {
  justify-content: flex-end;
  padding-right: 40px;
}
.agent-row {
  justify-content: flex-start;
  padding-left: 40px;
  max-width: 100%;
  box-sizing: border-box;
  gap: 10px;
  align-items: flex-start;
}
.agent-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  object-fit: cover;
  align-self: flex-start;
  flex-shrink: 0;
  background: #e6f1fc;
}
.agent-bubble-stack {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  width: 100%;
  max-width: 100%;
}
.user-message-bubble {
  background: #409eff;
  color: #fff;
  padding: 10px 10px;
  border-radius: 8px;
  max-width: 340px;
  font-size: 15px;
  word-break: break-word;
  box-shadow: 0 2px 8px rgba(64,158,255,0.08);
  display: block;
  text-align: left;
  white-space: pre-wrap;
  margin-right: 10px;
}
.agent-message-block {
  background: #fff;
  color: #222;
  border: none;
  box-shadow: none;
  max-width: 100%;
  min-width: 0;
  white-space: normal;
  word-wrap: break-word;
  overflow-wrap: anywhere;
  text-align: left;
  font-size: 15px;
  line-height: 1.5;
  hyphens: auto;
  display: block;
}
.agent-message-block :deep(*:last-child) {
  margin-bottom: 0 !important;
  padding-bottom: 0 !important;
}
.bubble-toolbar {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 28px;
  padding: 0 2px;
  margin-bottom: 2px;
  background: #fff;
  border-radius: 0;
  font-size: 0;
  user-select: none;
}
.user-toolbar {
  justify-content: flex-end;
  margin-right: 10px;
}
.agent-toolbar {
  justify-content: flex-start;
  margin-left: 0;
}
.toolbar-icon {
  font-size: 15px;
  color: #b0b3ba;
  cursor: pointer;
  transition: color 0.18s;
}
.toolbar-icon:hover {
  color: #409eff;
}
.chat-input::-webkit-scrollbar {
  width: 4px;
  background: transparent;
}
.chat-input::-webkit-scrollbar-thumb {
  background: #e0e4ea;
  border-radius: 3px;
}
.chat-input::-webkit-scrollbar-thumb:hover {
  background: #d0d4da;
}
.chat-input {
  scrollbar-width: thin;
  scrollbar-color: #e0e4ea transparent;
}
.thought-toggle-btn-row {
  background: #fff;
  border: 1.5px solid #3b82f6;
  border-radius: 8px;
  color: #3b82f6;
  font-weight: 600;
  font-size: 15px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 5px 5px 10px;
  margin-bottom: 2px;
  min-width: 0;
  max-width: 60vw;
  cursor: pointer;
  outline: none;
  transition: background 0.18s, border-color 0.18s;
}
.thought-toggle-btn-row:hover {
  background: #f0f6ff;
  border-color: #2563eb;
}
.thought-title-btn {
  font-size: 13px;
}
.arrow-icon-btn {
  font-size: 13px;
  margin-left: 2px;
  color: #b0b3ba;
  transition: color 0.2s;
}
.arrow-icon-btn:hover {
  color: #409eff;
}
@keyframes spin {
  0% {transform: rotate(0deg);}
  100% {transform: rotate(360deg);}
}
.thought-content-row {
  font-size: 13px;
  color: #888;
  line-height: 1.7;
  background: none;
  border: none;
  padding: 10px 16px 10px 14px;
  position: relative;
  white-space: pre-line;
  border-left: 3px solid #3183f6;
  text-align: left;
}
.agent-thought-bubble {
  background: #fff;
  border: none;
  border-radius: 10px;
  margin: 2px 0 8px 0;
  padding: 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-shadow: none;
  display: block;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
.fade-in-enter-active {
  transition: opacity 0.8s cubic-bezier(.4,0,.2,1), transform 0.8s cubic-bezier(.4,0,.2,1);
}
.fade-in-leave-active {
  transition: opacity 0.5s cubic-bezier(.4,0,.2,1), transform 0.5s cubic-bezier(.4,0,.2,1);
}
.fade-in-enter-from, .fade-in-leave-to {
  opacity: 0;
  transform: translateY(18px);
}
.fade-in-enter-to, .fade-in-leave-from {
  opacity: 1;
  transform: translateY(0);
}
</style>
