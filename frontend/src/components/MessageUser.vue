<template>
  <div class="message-row user-row">
    <div class="bubble-with-toolbar user-side">
      <div
        v-if="msg.text && msg.text.trim().length"
        class="user-message-bubble">
        {{ msg.text }}
      </div>

      <div class="bubble-toolbar user-toolbar"
        v-if="msg.text && msg.text.trim().length">
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
      </div>
      <div v-if="Array.isArray(msg.files) && msg.files.length" class="sent-files">
        <div class="sent-file-row" v-for="f in msg.files" :key="f.id">
          <FileBubble :filename="f.name" :closable="false" class="sent-variant" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import FileBubble from '@/components/FileBubble.vue'
import { CopyDocument, Check } from '@element-plus/icons-vue'

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
.bubble-with-toolbar.user-side {
  display: inline-flex;        /* 不再占满整行，按内容宽度收缩 */
  flex-direction: column;      /* 竖直堆叠：文本在上，附件在下 */
  align-items: flex-end;       /* 子项（文本泡泡、附件区）都贴右对齐 */
  max-width: 340px;            /* 与用户泡泡最大宽度保持一致 */
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
  display: inline-block;
}
.sent-files {
  display: flex;
  flex-direction: row;      /* 原先 column -> row */
  flex-wrap: wrap;          /* 超过宽度后换行 */
  justify-content: flex-end;
  gap: 6px;
  margin-top: 6px;
  max-width: 100%;
}
.sent-file-row {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
/* [MOD] 还原文件泡泡为白底黑字蓝边框，并为内部小圆点预留右侧空间 */
:deep(.file-bubble.sent-variant) {
  background: #fff;        /* 白底 */
  color: #222;             /* 黑字 */
  border-color: #409eff;   /* 蓝边框 */
  position: relative;      /* 放置内部小圆点 */
  padding-right: 18px;     /* 预留小圆点空间（可按需微调） */
  margin-right: 10px;      /* 与用户泡泡保持一致的右侧间距 */
}
:deep(.file-bubble.sent-variant::after) {
  content: '';
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #52c41a;
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
}
/* 更紧凑 */
:deep(.file-bubble.sent-variant .filename) {
  color: #222;
}
</style>
