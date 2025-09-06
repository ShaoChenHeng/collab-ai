<template>
  <div class="file-bubble">
    <span class="filename" :title="filename">{{ filename }}</span>
    <button
      v-if="closable"
      type="button"
      class="close-btn"
      title="移除文件"
      @click="$emit('close')"
    >
      <el-icon class="close-icon"><Close /></el-icon>
    </button>
  </div>
</template>

<script setup>
import { Close } from '@element-plus/icons-vue'

defineProps({
  filename: { type: String, default: '测试文件.txt' },
  closable: { type: Boolean, default: true }
})
defineEmits(['close'])
</script>

<style scoped>
.file-bubble {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px 6px 12px;
  border: 1.5px solid #409eff; /* 外围蓝色边框 */
  border-radius: 8px;           /* 与页面设计一致的圆角 */
  background: #fff;             /* 白底 */
  color: #222;                  /* 黑字（深灰） */
  max-width: 100%;
}

.filename {
  font-size: 13px;
  line-height: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.close-btn {
  appearance: none;
  border: none;
  background: transparent;
  padding: 2px;
  margin: 0;
  cursor: pointer;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.close-btn:hover {
  background: #f2f6fc;
}
.close-icon {
  font-size: 14px;
  color: #409eff;
}
.close-btn:hover .close-icon {
  color: #1976d2;
}
</style>
