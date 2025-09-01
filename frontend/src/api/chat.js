// src/api/chat.js
export async function fetchAgentReply(message, options = {}) {
  try {
    const payload = { message, options }
    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    if (!res.ok) throw new Error('网络异常')
    const data = await res.json()
    console.log('后端原始响应', data)
    // 避免 undefined 渲染空内容
    return typeof data.result === 'string' && data.result.trim()
      ? data.result
      : '[AI 没有返回内容]'
  } catch (e) {
    console.error('fetchAgentReply error', e)
    return '网络错误，无法获取AI响应。'
  }
}
export async function fetchAgentReplyStream(message, options = {}, onData) {
  const controller = new AbortController()
  const payload = { message, options }
  const resp = await fetch('http://localhost:8000/chat/stream', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'Content-Type': 'application/json' },
    signal: controller.signal
  })
  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  // eslint-disable-next-line no-constant-condition
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const chunk = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      if (chunk.startsWith('data: ')) {
        const line = chunk.slice(6)
        try {
          console.log('收到流式数据:', line) // 直接打印原始字符串
          const parsed = JSON.parse(line)
          console.log('解析后的对象:', parsed) // 打印解析后的对象
          onData(parsed)
        } catch (err) {
          console.warn('JSON parse error:', err, line)
        }
      }
    }
  }
  // 返回 controller 以便后续中断流式（可选）
  return controller
}
