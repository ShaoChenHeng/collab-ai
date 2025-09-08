<template>
  <div class="chat-input-container" :class="{ focused: focused }">
    <textarea
      v-model="localInput"
      class="chat-input"
      placeholder="输入消息..."
      autocomplete="off"
      rows="2"
      ref="textareaEl"
      @input="autoResize"
      @focus="focused = true"
      @blur="focused = false"
      @keydown.enter.exact.prevent="onSend"
    ></textarea>

    <div class="chat-btns-container">
      <button class="input-btn" :class="{ active: deepThinking }" @click="$emit('toggle-deep')">
        <el-icon class="btn-icon"><Cpu /></el-icon>
        <span class="btn-text">深度思考</span>
      </button>
      <button
        class="input-btn"
        :class="webSearchBtnClass()"
        @click="$emit('toggle-web')"
        :title="webSearchBtnTooltip()">
        <el-icon class="btn-icon"><Search /></el-icon>
        <span class="btn-text">网络搜索</span>
      </button>
      <div class="btns-spacer"></div>
      <button
        class="chat-upload-btn"
        title="上传文件"
        @click="triggerPickFiles"
      >
        <el-icon><Upload /></el-icon>
      </button>
      <input
        ref="fileInputEl"
        type="file"
        accept="
             .txt, .pdf,
             .md, .json,
             .docx
        "
        multiple
        style="display:none"
        @change="onFilesPicked"
      />
      <button
        class="chat-send-btn"
        :disabled="!canSend"
        :class="{ disabled: !canSend }"
        @click="onSend"
        title="发送"
      >
        <el-icon><Promotion /></el-icon>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { Cpu, Search, Promotion, Upload } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  canSend: { type: Boolean, default: false },
  deepThinking: { type: Boolean, default: false },
  webSearchMode: { type: String, default: 'auto' }
})
const emits = defineEmits(['update:modelValue', 'send', 'toggle-web', 'toggle-deep', 'pick-files'])

const localInput = ref(props.modelValue || '')
watch(() => props.modelValue, v => {
  if (v !== localInput.value) {
    localInput.value = v
    nextTick(() => autoResize())
  }
})
watch(localInput, v => emits('update:modelValue', v))

const textareaEl = ref(null)
const focused = ref(false)
function webSearchBtnClass() {
  if (props.webSearchMode === 'on') return 'active'
  if (props.webSearchMode === 'off') return 'forbid'
  return ''
}
function webSearchBtnTooltip() {
  if (props.webSearchMode === 'on') return '强制开启网络搜索'
  if (props.webSearchMode === 'off') return '已禁用网络搜索'
  return '自动网络搜索'
}
function autoResize() {
  if (textareaEl.value) {
    textareaEl.value.style.height = 'auto'
    textareaEl.value.style.height = textareaEl.value.scrollHeight + 'px'
  }
}
function onSend() { emits('send') }
// [MOD] 新增：文件选择逻辑
const fileInputEl = ref(null)
function triggerPickFiles() {
  fileInputEl.value?.click()
}
function onFilesPicked(e) {
  const files = Array.from(e.target?.files || [])
  if (files.length > 0) {
    emits('pick-files', files)
  }
  // 允许重复选择同一文件
  e.target.value = ''
}

defineExpose({ autoResize })
</script>

<style scoped>
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
.input-btn.forbid {
  background: #F6575F;
  color: #fff;
}
.input-btn.forbid .btn-icon { color: #fff; }
.input-btn:hover { background: #f2f6fc; }
.input-btn.active {
  background: #409eff;
  color: #fff;
}
.input-btn.active .btn-icon { color: #fff; }
.input-btn.active:hover {
  background: #73b8ff;
  color: #fff;
}
.input-btn.forbid:hover {
  background: #fa8c92;
  color: #fff;
}
.btn-icon { font-size: 15px; display: flex; align-items: center; }
.btn-text { margin-left: 7px; font-size: 13px; }
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
.chat-send-btn:hover { background: #1976d2; }
.chat-send-btn:disabled,
.chat-send-btn.disabled {
  background: #d7dde5;
  color: #fff;
  cursor: not-allowed;
  opacity: 0.7;
}
.chat-send-btn:disabled:hover,
.chat-send-btn.disabled:hover { background: #d7dde5; }
.chat-upload-btn {
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
  margin: 0;
  padding: 0 0;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}
.chat-upload-btn:hover { background: #1976d2; }

.btns-spacer { flex: 1; }
</style>
