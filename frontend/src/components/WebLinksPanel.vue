<template>
  <div class="weblinks-panel" v-if="show">
    <div class="weblinks-panel-header">
      <span>网络搜索结果
        <span class="search-count" v-if="links && links.length">（{{ links.length }}）</span>
      </span>
      <el-icon class="close-icon" @click="$emit('close')"><Close /></el-icon>
    </div>
    <div class="weblinks-list">
      <div
        v-for="(item, i) in links"
        :key="i"
        class="weblink-item"
        @click="openLink(item.link)"
        tabindex="0"
        role="button"
      >
        <div class="weblink-title-row">
          <img
            v-if="item.favicon"
            :src="item.favicon"
            alt="网站图标"
            class="weblink-favicon"
            loading="lazy"
            width="20"
            height="20"
          />
          <div class="weblink-title" :title="item.title">{{ item.title }}</div>
        </div>
        <div class="weblink-snippet">{{ item.snippet }}</div>
      </div>
      <div v-if="!links || links.length === 0" class="no-links">暂无搜索结果</div>
    </div>
  </div>
</template>

<script setup>
import { Close } from '@element-plus/icons-vue'
defineProps({
  show: Boolean,
  links: {
    type: Array,
    default: () => []
  }
})
defineEmits(['close'])

// 新标签页打开链接
function openLink(url) {
  if (!url) return
  window.open(url, '_blank', 'noopener')
}
</script>

<style scoped>
.weblinks-panel {
  width: 100%;
  height: 100%;
  background: #fff;
  box-shadow: -2px 0 12px rgba(0,0,0,0.07);
  border-left: 1px solid #e4e8ef;
  z-index: 100;
  display: flex;
  flex-direction: column;
  padding: 0;
  animation: fadeIn 0.22s;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateX(40px);}
  to { opacity: 1; transform: none;}
}
.weblinks-panel-header {
  height: 48px;
  background: #f6f8fb;
  border-bottom: 1px solid #e4e8ef;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px 0 20px;
  font-weight: 600;
  font-size: 16px;
  border-radius: 0;
  text-align: left;
}
.close-icon {
  font-size: 19px;
  color: #8a8a8a;
  cursor: pointer;
  transition: color 0.18s;
}
.close-icon:hover {
  color: #ff4d4f;
}
.weblinks-list {
  padding: 18px 18px 12px 18px;
  overflow-y: auto;
  flex: 1;
  text-align: left;
}
.weblink-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 18px;
  border-bottom: 1px solid #f0f2f7;
  padding-bottom: 11px;
  word-break: break-all;
  text-align: left;
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.12s;
}
.weblink-item:active,
.weblink-item:focus,
.weblink-item:hover {
  background: #f2f6fc;
}
.weblink-title-row {
  display: flex;
  align-items: center;
  gap: 0;
}
.weblink-favicon {
  width: 20px;
  height: 20px;
  border-radius: 3px;
  background: #f3f5f8;
  box-shadow: 0 0 2px #e0e4ea;
  flex-shrink: 0;
  margin-right: 10px;
  vertical-align: middle;
}
.weblink-title {
  color: #212121;
  font-size: 15px;
  font-weight: 500;
  line-height: 1.2;
  margin-bottom: 2px;
  margin-left: 2px;
  max-width: calc(100% - 32px);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-align: left;
  vertical-align: middle;
  display: inline-block;
}
.search-count {
  display: inline-block;
  transition: transform 0.8s cubic-bezier(.5,1.7,.4,.8), color 0.8s;
}

.search-count.animated {
  transform: scale(1.4);
  color: #409EFF; /* Element Plus 主色 */
}
.weblink-snippet {
  color: #444f6e;
  font-size: 13px;
  line-height: 1.5;
  margin-top: 1.5px;
  text-align: left;
}
.no-links {
  color: #8a8a8a;
  font-size: 14px;
  text-align: left;
  margin-top: 30px;
}
</style>
