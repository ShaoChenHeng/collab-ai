<template>
  <div class="message-row user-row">
    <div class="bubble-with-toolbar user-side">
      <div class="user-message-bubble">
        {{ msg.text }}
      </div>
      <div class="bubble-toolbar user-toolbar">
        <el-icon
          class="toolbar-icon"
          title="复制"
          v-if="!msg.copied"
          @click="$emit('copy', { msg, idx: index })">
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
</template>

<script setup>
import { CopyDocument, Check, EditPen } from '@element-plus/icons-vue'

defineProps({
  msg: { type: Object, required: true },
  index: { type: Number, required: true }
})
defineEmits(['copy'])
</script>

<style scoped>
.message-row { display: flex; width: 100%; }
.user-row { justify-content: flex-end; padding-right: 40px; }
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
.user-toolbar { justify-content: flex-end; margin-right: 10px; }
.toolbar-icon { font-size: 15px; color: #b0b3ba; cursor: pointer; transition: color 0.18s; }
.toolbar-icon:hover { color: #409eff; }
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
</style>
