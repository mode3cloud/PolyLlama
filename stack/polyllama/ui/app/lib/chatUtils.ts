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
  onToolCall?: (toolCall: { id: string; name: string; arguments: any }) => void
  onToolResult?: (name: string, result: string, toolCallId?: string) => void
  onToolError?: (name: string, error: string, toolCallId?: string) => void
  onToolCallStreaming?: (toolCall: { id: string; name: string; status?: 'started' | 'completed' }) => void
}

interface StreamChatAudioOptions extends StreamChatOptions {
  voice?: string
  speechSpeed?: number
  speechLang?: string
  onAudio?: (audioData: { audio: string; sample_rate: number; text: string; format: string }) => void
}

export async function streamChat({
  messages,
  model,
  sessionId,
  temperature,
  signal,
  onChunk,
  onError,
  onDone,
  onToolCall,
  onToolResult,
  onToolError,
  onToolCallStreaming
}: StreamChatOptions) {
  // Convert messages to include attachments for images
  const processedMessages = messages.map(msg => {
    const processedMsg: {
      role: string;
      content: string;
      timestamp: string;
      attachments?: string[];
    } = {
      role: msg.role,
      content: msg.content,
      timestamp: msg.timestamp || new Date().toISOString()
    }
    
    // Add attachments if message has images
    if (msg.images && msg.images.length > 0) {
      processedMsg.attachments = msg.images.map(img => img.url)
    }
    
    return processedMsg
  })

  const response = await fetchWithAuth(`${API_BASE_URL}/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      messages: processedMessages,
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
            
            // Debug logging for tool-related events
            if (chunk.type && chunk.type.includes('tool')) {
              console.log(`[Chat Stream] Received ${chunk.type} event:`, chunk)
            }

            if (chunk.type === 'content' && chunk.content) {
              onChunk(chunk.content)
            } else if (chunk.type === 'tool_call' && chunk.tool_call && onToolCall) {
              // Ensure arguments is present before calling onToolCall
              if (chunk.tool_call.arguments !== undefined) {
                onToolCall(chunk.tool_call as { id: string; name: string; arguments: any })
              }
            } else if (chunk.type === 'tool_call_streaming' && chunk.tool_call && onToolCallStreaming) {
              onToolCallStreaming(chunk.tool_call)
            } else if (chunk.type === 'tool_result' && chunk.name && chunk.result && onToolResult) {
              onToolResult(chunk.name, chunk.result, chunk.tool_call_id)
            } else if (chunk.type === 'tool_error' && chunk.name && chunk.error && onToolError) {
              onToolError(chunk.name, chunk.error, chunk.tool_call_id)
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

export async function streamChatWithAudio({
  messages,
  model,
  sessionId,
  temperature,
  signal,
  onChunk,
  onError,
  onDone,
  voice,
  speechSpeed,
  speechLang,
  onAudio,
  onToolCall,
  onToolResult,
  onToolError,
  onToolCallStreaming
}: StreamChatAudioOptions) {
  // Convert messages to include attachments for images
  const processedMessages = messages.map(msg => {
    const processedMsg: {
      role: string;
      content: string;
      timestamp: string;
      attachments?: string[];
    } = {
      role: msg.role,
      content: msg.content,
      timestamp: msg.timestamp || new Date().toISOString()
    }
    
    // Add attachments if message has images
    if (msg.images && msg.images.length > 0) {
      processedMsg.attachments = msg.images.map(img => img.url)
    }
    
    return processedMsg
  })

  const response = await fetchWithAuth(`${API_BASE_URL}/completions_audio`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      messages: processedMessages,
      model,
      session_id: sessionId,
      stream: true,
      temperature,
      voice,
      speech_speed: speechSpeed,
      speech_lang: speechLang
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
            const event = JSON.parse(data)

            if (event.type === 'text') {
              // Handle text chunks same as before
              const chunk = event.data
              if (chunk.type === 'content' && chunk.content) {
                onChunk(chunk.content)
              } else if (chunk.type === 'tool_call' && chunk.tool_call && onToolCall) {
                // Ensure arguments is present before calling onToolCall
                if (chunk.tool_call.arguments !== undefined) {
                  onToolCall(chunk.tool_call as { id: string; name: string; arguments: any })
                }
              } else if (chunk.type === 'tool_call_streaming' && chunk.tool_call && onToolCallStreaming) {
                onToolCallStreaming(chunk.tool_call)
              } else if (chunk.type === 'tool_result' && chunk.name && chunk.result && onToolResult) {
                onToolResult(chunk.name, chunk.result)
              } else if (chunk.type === 'tool_error' && chunk.name && chunk.error && onToolError) {
                onToolError(chunk.name, chunk.error)
              } else if (chunk.type === 'error') {
                console.error('Stream error:', chunk.error)
                onError(chunk.error || 'Unknown error')
              }
            } else if (event.type === 'audio' && event.data && onAudio) {
              // Handle audio chunks
              onAudio(event.data)
            } else if (event.type === 'error') {
              console.error('Stream error:', event.error)
              onError(event.error || 'Unknown error')
            } else if (event.type === 'done') {
              onDone()
              return
            } else if (event.type === 'connected') {
              // Connection established
            }
          } catch (parseError) {
            console.error('Failed to parse event:', data, parseError)
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
          timestamp: msg.timestamp || new Date().toISOString(),
          images: msg.images,
          tool_calls: msg.tool_calls,
          tool_name: msg.tool_name,
          tool_call_id: msg.tool_call_id
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