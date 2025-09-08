import { computed } from 'vue'

export function useSendMessage({
  input,
  fileItems,
  takeAttachments,
  pushUserMessage,
  uploadFile,
  sendWithStream,
  webSearchMode,
  useDeepThinking,
  chatInputRef,
  isAgentLoading
}) {
  // 用户输入预处理
  function prepareUserText(text, webFlag, webSearchMode) {
    if (webSearchMode === 'off' && text) {
    return '本次对话禁止使用网络搜索。' + text
  }
  return webFlag && text ? '请你网络搜索相关关键字后回答：' + text : text
  }

  // 构造 docs_use 指令 prompt
  function buildDocsPrompt(userText, paths) {
    const header = '我已在工作区上传了以下文件（相对路径）：\n' + paths.map(p => `- ${p}`).join('\n')
    if (userText && userText.trim()) {
      return `${header}\n请在需要时使用 docs_use 工具读取上述文件，并结合其内容回答我的问题：\n${userText}`
    }
    return `${header}\n请使用 docs_use 工具依次读取这些文件，先给出一个中文概览与要点提要；如内容较长可按需多次调用 docs_use 续读。`
  }

  // 顺序上传所有附件，失败抛错
  async function uploadAllOrFail(attachments) {
    for (const f of attachments) {
      const resp = await uploadFile(f.file)
      f.serverFilename = resp.filename
      f.serverPath = resp.path
    }
    return attachments
  }

  // 是否可发送
  const canSend = computed(() =>
    (input.value.trim().length > 0 || fileItems.value.length > 0) && !isAgentLoading.value
  )

  // 发送消息（文本 + 附件）
  async function sendMessage(e) {
    e?.preventDefault?.()
    const textRaw = input.value.trim()
    const hasText = !!textRaw
    const hasFiles = fileItems.value.length > 0
    if ((!hasText && !hasFiles) || !canSend.value) return

    // 是否启用网页搜索（只在on时强制提示，auto和off不提示）
    const webFlag = webSearchMode.value === 'on'

    // 取出并清空待发送附件；用户消息入队（展示端）
    const attachments = takeAttachments()
    input.value = ''
    chatInputRef.value?.autoResize?.()

    // 如有附件：先上传；失败则终止，不发消息
    if (attachments.length > 0) {
      try {
        await uploadAllOrFail(attachments)
      } catch (err) {
        console.error('上传失败：', err)
        return
      }
    }

    // 入队用户侧消息（展示端）
    if (hasText) {
      // 有输入 + 可有文件：显示文字泡泡 + 文件泡泡
      pushUserMessage({ text: textRaw, files: attachments })
    } else if (attachments.length > 0) {
      // 无输入 + 有文件：仅显示文件泡泡（组件在 text 为空时隐藏文字泡泡）
      pushUserMessage({ text: '', files: attachments })
    }

    // 构造最终发给后端的 message
    const serverPaths = attachments.map(a => a.serverPath).filter(Boolean)
    let messageToSend
    if (serverPaths.length > 0) {
      const prepared = prepareUserText(textRaw, webFlag, webSearchMode.value)
      messageToSend = buildDocsPrompt(prepared, serverPaths)
    } else {
      // 无文件：沿用原逻辑
      messageToSend = prepareUserText(textRaw, webFlag, webSearchMode.value)
    }

    // 流式 Agent 回复
    sendWithStream(messageToSend, {
      deepThinking: useDeepThinking.value,
      webSearchMode: webSearchMode.value // 用新的三态变量
    })
  }

  return {
    sendMessage,
    canSend,
  }
}
