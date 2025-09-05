<template>
  <div class="chat-messages">
    <template v-for="(msg, idx) in messages" :key="msg.id">
      <MessageUser
        v-if="msg.from === 'me'"
        :msg="msg"
        :index="idx"
        @copy="(p) => $emit('copy', p)"
      />
      <MessageAgent
        v-else
        :msg="msg"
        :index="idx"
        :thought-expanded="!!thoughtExpandedMap[msg.id]"
        :current-web-links-msg-id="currentWebLinksMsgId"
        :render-markdown="renderMarkdown"
        @toggle-thought="(id) => $emit('toggle-thought', id)"
        @open-web-links="(id) => $emit('open-web-links', id)"
        @copy="(p) => $emit('copy', p)"
      />
    </template>
  </div>
</template>

<script setup>
import MessageUser from './MessageUser.vue'
import MessageAgent from './MessageAgent.vue'

defineProps({
  messages: { type: Array, required: true },
  thoughtExpandedMap: { type: Object, required: true },
  currentWebLinksMsgId: { type: String, default: '' },
  renderMarkdown: { type: Function, required: true },
})

defineEmits(['copy', 'toggle-thought', 'open-web-links'])
</script>

<style scoped>
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
</style>
