// 文件队列管理：选择、类型/大小校验、去重、数量上限、移除、取出（并清空）
// 仅管理前端队列与用户提示，不负责上传网络请求（后续补充）
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

// 约束：最多 4 个，单文件 ≤ 20MB
export const MAX_FILES = 4
export const MAX_SIZE = 20 * 1024 * 1024 // 20MB

let fileIdSeed = 1
const files = ref([]) // [{ id, name, file }]

// 判重键：同名+同大小+同 lastModified 视为“同一文件”
function keyOf(f) {
  return `${f.name}::${f.size || 0}::${f.lastModified || 0}`
}

  // 允许的类型：.txt / .pdf / .md / .json / .docx（双重校验：扩展名 + MIME）
function isAllowedType(f) {
  const nameOk = /\.(txt|pdf|md|json|docx)$/i.test(f.name)
  const typeOk = [
    'text/plain',
    'application/pdf',
    'text/markdown',
    'application/json',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '', // 某些浏览器未识别 type
  ].includes(f.type || '')
  return nameOk && typeOk
}

export function useFileQueue() {
  // 选择文件入口：附带去重、大小限制、数量限制与用户提示
  function onPickFiles(list) {
    const incoming = Array.from(list || [])
    const invalid = []  // 类型不符合
    const oversize = [] // 超出大小
    const dups = []     // 重复
    let reachedLimit = false

    const existing = new Set(files.value.map(f => keyOf(f.file)))
    const toAdd = []

    for (const f of incoming) {
      if (!isAllowedType(f)) { invalid.push(f.name); continue }
      if (f.size > MAX_SIZE) { oversize.push(f.name); continue }

      const key = keyOf(f)
      if (existing.has(key) || toAdd.some(x => x.key === key)) { dups.push(f.name); continue }

      if (files.value.length + toAdd.length >= MAX_FILES) { reachedLimit = true; break }
      toAdd.push({ key, file: f })
    }

    // 入队
    toAdd.forEach(it => files.value.push({ id: fileIdSeed++, name: it.file.name, file: it.file }))

    // 用户提示（尽量合并，避免打扰）
    if (invalid.length) ElMessage?.warning?.(`仅支持 .txt、.pdf、.md、.json、.docx，已忽略：${invalid.join('、')}`)
    // ...
    if (oversize.length) ElMessage?.warning?.(`超过 20MB 已忽略：${oversize.join('、')}`)
    if (dups.length) ElMessage?.info?.(`已忽略重复文件：${dups.join('、')}`)
    if (reachedLimit) ElMessage?.warning?.(`最多上传 ${MAX_FILES} 个文件，已达上限`)
  }

  // 从队列中移除指定 id
  function removeFileItem(id) {
    const i = files.value.findIndex(f => f.id === id)
    if (i !== -1) files.value.splice(i, 1)
  }

  // 取出全部附件并清空队列（用于“发送时收割”）
  function takeAttachments() {
    const atts = files.value.slice()
    files.value = []
    return atts
  }

  return { files, onPickFiles, removeFileItem, takeAttachments }
}
