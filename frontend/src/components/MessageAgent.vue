<template>
  <div class="message-row agent-row">
    <img class="agent-avatar" src="/mu.png" alt="头像" />
    <div class="agent-bubble-stack">
      <div class="toggle-btn-row-group">
        <ChatPanelToggleBtn
          class="toggle-btn-row"
          :icon="EditPen"
          label="智能体思考"
          :arrowIcon="thoughtExpanded ? ArrowUp : ArrowDown"
          :active="thoughtExpanded"
          @click="$emit('toggle-thought', msg.id)"
          v-if="msg.thoughts && msg.thoughts.length > 0"
        />
        <ChatPanelToggleBtn
          class="toggle-btn-row"
          :icon="Link"
          label="相关链接"
          :arrowIcon="ArrowRight"
          :active="currentWebLinksMsgId === msg.id"
          @click="$emit('open-web-links', msg.id)"
          v-if="msg.weblinks && msg.weblinks.length > 0"
        />
      </div>

      <transition name="fade">
        <div v-if="thoughtExpanded" class="agent-thought-bubble">
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
            @click="$emit('copy', { msg, idx: index })">
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

<script setup>
import { CopyDocument, Check, Refresh, Loading, ArrowUp, ArrowDown, ArrowRight, Link, EditPen } from '@element-plus/icons-vue'
import ChatPanelToggleBtn from '@/components/ChatPanelToggleBtn.vue'

defineProps({
  msg: { type: Object, required: true },
  index: { type: Number, required: true },
  thoughtExpanded: { type: Boolean, default: false },
  currentWebLinksMsgId: { type: String, default: '' },
  renderMarkdown: { type: Function, required: true },
})
defineEmits(['copy', 'toggle-thought', 'open-web-links'])
</script>

<style scoped>
.message-row { display: flex; width: 100%; }
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
.toggle-btn-row-group {
  display: flex;
  flex-direction: row;
  gap: 4px;
}

/* 补回按钮激活态的样式（使用 :deep 穿透到子组件） */
:deep(.toggle-btn-row.active) {
  background: #3b82f6;
  color: #fff;
  border-color: #3b82f6;
}
:deep(.toggle-btn-row.active .arrow-icon-btn),
:deep(.toggle-btn-row.active .static-icon) {
  color: #fff;
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
.agent-toolbar { justify-content: flex-start; margin-left: 0; }
.toolbar-icon { font-size: 15px; color: #b0b3ba; cursor: pointer; transition: color 0.18s; }
.toolbar-icon:hover { color: #409eff; }
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
  margin: 2px 0 2px 0;
  padding: 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-shadow: none;
  display: block;
}
.fade-enter-active,
.fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from,
.fade-leave-to { opacity: 0; }
.fade-in-enter-active {
  transition: opacity 0.8s cubic-bezier(.4,0,.2,1), transform 0.8s cubic-bezier(.4,0,.2,1);
}
.fade-in-leave-active {
  transition: opacity 0.5s cubic-bezier(.4,0,.2,1), transform 0.5s cubic-bezier(.4,0,.2,1);
}
.fade-in-enter-from, .fade-in-leave-to { opacity: 0; transform: translateY(18px); }
.fade-in-enter-to, .fade-in-leave-from { opacity: 1; transform: translateY(0); }
</style>
