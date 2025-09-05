<template>
  <div
    class="attachment-chip"
    :class="{
      'attachment-chip--pending': state === 'pending',
      'attachment-chip--uploading': state === 'uploading',
      'attachment-chip--sent': state === 'sent',
    }"
  >
    <div class="attachment-chip__left">
      <span class="attachment-chip__icon" v-if="state === 'sent'">
        <span class="attachment-chip__dot"></span>
      </span>
      <span class="attachment-chip__spinner" v-if="state === 'uploading'">
        <!-- 使用项目内已有的转圈动画类名，如无则用此简易 spinner 兜底 -->
        <span class="spinner"></span>
      </span>
      <span class="attachment-chip__name" :title="filename">{{ filename }}</span>
    </div>
    <button
      v-if="closable && state === 'pending'"
      type="button"
      class="attachment-chip__close"
      @click="$emit('close')"
      aria-label="移除附件"
      title="移除附件"
    >
      ×
    </button>
  </div>
</template>

<script>
export default {
  name: 'AttachmentChip',
  props: {
    filename: { type: String, required: true },
    state: { type: String, default: 'pending' }, // 'pending' | 'uploading' | 'sent'
    closable: { type: Boolean, default: false },
  },
}
</script>

<style scoped>
/* 颜色尽量走项目变量；若无变量则使用 fallback */
:root {
  --primary-blue: var(--brand-blue, #3b82f6);
  --success-green: var(--success, #22c55e);
  --chip-bg-sent: var(--chip-sent-bg, var(--primary-blue));
  --chip-fg-on-sent: var(--chip-sent-fg, #ffffff);
}
.attachment-chip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-radius: 8px;
  padding: 6px 10px;
  min-height: 36px;
  max-width: 100%;
  box-sizing: border-box;
  gap: 8px;
}
.attachment-chip__left {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.attachment-chip__name {
  display: inline-block;
  max-width: 420px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 发送前：蓝色描边 */
.attachment-chip--pending,
.attachment-chip--uploading {
  border: 1px solid var(--primary-blue);
  background-color: #fff;
  color: #111827;
}
/* 发送后：蓝底白字 */
.attachment-chip--sent {
  border: 1px solid var(--chip-bg-sent);
  background-color: var(--chip-bg-sent);
  color: var(--chip-fg-on-sent);
}

/* 关闭按钮 */
.attachment-chip__close {
  appearance: none;
  border: none;
  background: transparent;
  color: inherit;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  padding: 0 2px;
}

/* 绿色状态点（发送后） */
.attachment-chip__dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  background: var(--success-green);
  border-radius: 50%;
}

/* 简易 spinner 兜底（若项目已有 spinner 类则自动覆盖） */
.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(59, 130, 246, 0.2);
  border-top-color: var(--primary-blue);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
