<template>
  <button class="toggle-btn-row" @click="onClick" :class="{ active }">
    <el-icon class="static-icon">
      <component :is="icon" />
    </el-icon>
    <span class="title-btn">{{ label }}</span>
    <el-icon class="arrow-icon-btn">
      <component :is="arrowIcon" />
    </el-icon>
  </button>
</template>

<script setup>
import { defineProps, defineEmits } from 'vue'

defineProps({
  icon: { type: [Object, Function], required: true },
  label: { type: String, required: true },
  arrowIcon: { type: [Object, Function], required: true },
  active: { type: Boolean, default: false },
})
const emit = defineEmits(['click'])

function onClick(e) {
  emit('click', e)
}
</script>

<style scoped>
.toggle-btn-row {
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
.title-btn {
  font-size: 13px;
}
.arrow-icon-btn {
  font-size: 13px;
  margin-left: 2px;
  color: #b0b3ba;
  transition: color 0.2s;
}
.toggle-btn-row:hover {
  background: #f0f6ff;
  border-color: #2563eb;
}
.arrow-icon-btn:hover {
  color: #409eff;
}
</style>
