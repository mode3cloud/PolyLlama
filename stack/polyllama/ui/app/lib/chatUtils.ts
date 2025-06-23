import { ChatMessage, StreamChunk } from '../types'
import { fetchWithAuth } from './fetchWithAuth'

const API_BASE_URL = '/ui/api/chat'

interface StreamChatOptions {
  messages: ChatMessage[]
  model: string
  sessionId: string
  temperature: number
  signal: AbortSignal
  onChunk: (content: string) => void
  onError: (error: string) => void
  onDone: () => void
}

export async function streamChat({
  messages,
  model,
  sessionId,
  temperature,
  signal,
  onChunk,
  onError,
  onDone
}: StreamChatOptions) {
  const response = await fetchWithAuth(`${API_BASE_URL}/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      messages,
      model,
      session_id: sessionId,
      stream: true,
      temperature
    }),
    signal
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('No response body')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6).trim()
          if (data === '') continue

          try {
            const chunk: StreamChunk = JSON.parse(data)

            if (chunk.type === 'content' && chunk.content) {
              onChunk(chunk.content)
            } else if (chunk.type === 'error') {
              console.error('Stream error:', chunk.error)
              onError(chunk.error || 'Unknown error')
            } else if (chunk.type === 'done') {
              onDone()
              return
            } else if (chunk.type === 'connected') {
              // Connection established
            }
          } catch (parseError) {
            console.error('Failed to parse chunk:', data, parseError)
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

export async function syncSessionMessages(sessionId: string, messages: ChatMessage[]) {
  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/sessions/${sessionId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        messages: messages.map(msg => ({
          role: msg.role,
          content: msg.content,
          timestamp: msg.timestamp
        }))
      })
    })

    if (!response.ok) {
      console.error('Failed to sync messages with backend')
      return false
    }
    return true
  } catch (error) {
    console.error('Error syncing messages with backend:', error)
    return false
  }
}

export function exportChatToMarkdown(messages: ChatMessage[], sessionId: string) {
  const markdown = messages.map(msg => {
    const role = msg.role.charAt(0).toUpperCase() + msg.role.slice(1)
    return `**${role}:** ${msg.content}`
  }).join('\n\n')

  const blob = new Blob([markdown], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `chat-${sessionId}.md`
  a.click()
  URL.revokeObjectURL(url)
}