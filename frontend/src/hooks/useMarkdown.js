// Markdown 渲染配置：统一开启 linkify、允许 HTML，并强制外链新窗口打开 + 安全 rel
import MarkdownIt from 'markdown-it'

export function useMarkdown() {
  const md = new MarkdownIt({
    linkify: true,
    breaks: false,
    typographer: false,
    html: false,
    xhtmlOut: true
  })

  // 所有链接 target=_blank 且 rel=noopener noreferrer
  md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
    const aIndex = tokens[idx].attrIndex('target')
    if (aIndex < 0) tokens[idx].attrPush(['target', '_blank'])
    else tokens[idx].attrs[aIndex][1] = '_blank'
    const relIndex = tokens[idx].attrIndex('rel')
    if (relIndex < 0) tokens[idx].attrPush(['rel', 'noopener noreferrer'])
    else tokens[idx].attrs[relIndex][1] = 'noopener noreferrer'
    return self.renderToken(tokens, idx, options)
  }

  const renderMarkdown = (text) => md.render(text || '')
  return { renderMarkdown }
}
