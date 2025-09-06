// Agent 流式回复管理：创建占位、处理分片回调、落盘思维与工具调用结果
// 依赖：messages（响应式）、pushAgentPlaceholder、setWebLinksToMsg、fetchAgentReplyStream
export function useAgentStream({ messages, pushAgentPlaceholder, setWebLinksToMsg, fetchAgentReplyStream }) {
  // 工具调用结果的格式化入库
  function handleToolResult(msg, entry) {
    const { tool, content } = entry
    if (tool === 'today_date') {
      msg.thoughts.push(`调用today_date工具，得到当前日期：${content}`)
      return
    }
    if (tool === 'google_search') {
      let results = []
      try {
        results = JSON.parse(content)
      } catch (e) {
        // ESLint: 避免空 catch（no-empty），并保证 results 为数组
        results = []
      }
      setWebLinksToMsg(msg.id, results)
      const n = Array.isArray(results) ? results.length : 0
      let str = `调用“google_search”工具，搜索关键词为：“${msg.searchQuery || ''}”，得到了${n}个搜索结果：`
      if (n > 0) {
        str += '\n' + results.slice(0, 3).map((item, i) =>
          `【${i+1}】标题：${item.title} 是一个与问题高度相关的搜索结果。\n主要内容：${item.snippet}\n访问链接：${item.link}${item.displayLink ? `（来自：${item.displayLink}）` : ''}`
        ).join('\n')
      }
      msg.thoughts.push(str.trim())
      return
    }
    if (tool === 'url_summary') {
      const clean = String(content).replace(/\r?\n/g, '')
      const preview = clean.length > 60 ? clean.slice(0, 60) + '……' : clean
      msg.thoughts.push(`调用“url_summary”工具对相关网页内容爬取，该网页介绍了：${preview}`)
      return
    }
    // 其它工具统一降级为原文展示
    msg.thoughts.push(`调用“${tool}”工具，得到结果：${content}`)
  }

  // 处理每个流式分片（工具结果 / 中间思维 / 最终聊天文本）
  function handleEntry(agentMsgId, entry) {
    if (!entry.content || entry.content.trim() === '') return
    const msg = messages.value.find(m => m.id === agentMsgId)
    if (!msg) return

    if (entry.type === 'tool_result' && entry.tool) {
      handleToolResult(msg, entry)
      return
    }
    if (entry.type === 'intermediate_step') {
      msg.thoughts.push(entry.content)
      if (entry.query) msg.searchQuery = entry.query
      return
    }
    if (entry.type === 'chat') {
      msg.text = entry.content
      msg.isLoading = false
    }
  }

  // 对外发送接口：封装占位与回调绑定
  function sendWithStream(userText, options) {
    const agentMsgId = pushAgentPlaceholder()
    fetchAgentReplyStream(userText, options, (entry) => handleEntry(agentMsgId, entry))
  }

  return { sendWithStream }
}
