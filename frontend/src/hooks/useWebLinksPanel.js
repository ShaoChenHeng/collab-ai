import { ref, computed } from 'vue'

/**
 * 聊天相关链接弹窗管理
 * - 支持多条消息，每条消息独立相关链接
 */
export function useWebLinksPanel(messages) {
  // 当前面板是否显示
  const weblinksPanelVisible = ref(false)
  // 当前打开哪条消息的weblinks
  const currentWebLinksMsgId = ref(null)
  // 计算当前消息的 weblinks
  const currentWebLinks = computed(() => {
    const msg = messages.value.find(m => m.id === currentWebLinksMsgId.value)
    return msg?.weblinks || []
  })

  // 打开某条消息的相关链接面板
  function openWebLinksPanel(msgId) {
    if (weblinksPanelVisible.value && currentWebLinksMsgId.value === msgId) {
      // 如果已经打开并且就是当前消息，再点一下就收起
      weblinksPanelVisible.value = false
      currentWebLinksMsgId.value = null
    } else {
      // 其它情况就切换显示
      currentWebLinksMsgId.value = msgId
      weblinksPanelVisible.value = true
    }
  }
  // 关闭面板
  function closeWebLinksPanel() {
    weblinksPanelVisible.value = false
    currentWebLinksMsgId.value = null
  }

  // 给某条消息设置搜索结果
  function setWebLinksToMsg(msgId, links) {
    const msg = messages.value.find(m => m.id === msgId)
    if (!msg) return
    if (!Array.isArray(msg.weblinks)) msg.weblinks = []
    if (!Array.isArray(links)) links = []
    // 合并去重：以 link 字段唯一
    const combined = [...msg.weblinks, ...links]
    const uniqMap = new Map()
    combined.forEach(item => {
      if (item && item.link) uniqMap.set(item.link, item)
    })
    msg.weblinks = Array.from(uniqMap.values())
  }

  return {
    weblinksPanelVisible,
    currentWebLinksMsgId,
    currentWebLinks,
    openWebLinksPanel,
    closeWebLinksPanel,
    setWebLinksToMsg
  }
}
