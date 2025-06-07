'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { ChatMessage, ChatModel, StreamChunk } from '../types'

const LLM_PROXY_URL = process.env.NODE_ENV === 'production'
  ? 'http://llm-proxy:11435'
  : 'http://localhost:11435'

console.log('LLM Proxy URL:', LLM_PROXY_URL, 'Environment:', process.env.NODE_ENV)

interface ChatInterfaceProps {
  onRefresh: () => void
}

export default function ChatInterface({ onRefresh }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [models, setModels] = useState<ChatModel[]>([])
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [sessionId] = useState(() => `session-${Date.now()}`)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  // Fetch available models
  const fetchModels = useCallback(async () => {
    try {
      const response = await fetch(`${LLM_PROXY_URL}/api/models`)
      if (response.ok) {
        const data = await response.json()
        setModels(data.models || [])
        if (data.models?.length > 0 && !selectedModel) {
          // Default to first Ollama model if available, otherwise first model
          const ollamaModel = data.models.find((m: ChatModel) => m.provider === 'ollama')
          setSelectedModel(ollamaModel?.id || data.models[0].id)
        }
      }
    } catch (error) {
      console.error('Failed to fetch models:', error)
    }
  }, [selectedModel])

  useEffect(() => {
    fetchModels()
  }, [fetchModels])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim() || isLoading || !selectedModel) return

    const userMessage: ChatMessage = {
      role: 'user',
      content: input.trim(),
      timestamp: new Date().toISOString()
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    // Create abort controller for this request
    abortControllerRef.current = new AbortController()

    try {
      const response = await fetch(`${LLM_PROXY_URL}/api/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          messages: [...messages, userMessage],
          model: selectedModel,
          session_id: sessionId,
          stream: true,
          temperature: 0.7
        }),
        signal: abortControllerRef.current.signal
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      let assistantMessage: ChatMessage = {
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString()
      }

      setMessages(prev => [...prev, assistantMessage])

      const decoder = new TextDecoder()
      let buffer = ''

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

              console.log('Received chunk:', chunk)

              if (chunk.type === 'content' && chunk.content) {
                assistantMessage.content += chunk.content
                setMessages(prev =>
                  prev.map((msg, idx) =>
                    idx === prev.length - 1 ? { ...assistantMessage } : msg
                  )
                )
              } else if (chunk.type === 'error') {
                console.error('Stream error:', chunk.error)
                assistantMessage.content += `\n\n*Error: ${chunk.error}*`
                setMessages(prev =>
                  prev.map((msg, idx) =>
                    idx === prev.length - 1 ? { ...assistantMessage } : msg
                  )
                )
              } else if (chunk.type === 'done') {
                break
              } else if (chunk.type === 'connected') {
                console.log('Stream connected')
              }
            } catch (parseError) {
              console.error('Failed to parse chunk:', data, parseError)
            }
          }
        }
      }

    } catch (error: any) {
      if (error.name === 'AbortError') {
        console.log('Request aborted')
      } else {
        console.error('Chat error:', error)
        const errorMessage: ChatMessage = {
          role: 'assistant',
          content: `*Error: ${error.message}*`,
          timestamp: new Date().toISOString()
        }
        setMessages(prev => [...prev, errorMessage])
      }
    } finally {
      setIsLoading(false)
      abortControllerRef.current = null
    }
  }

  const stopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
  }

  const clearChat = () => {
    setMessages([])
  }

  const copyMessage = (content: string) => {
    navigator.clipboard.writeText(content)
  }

  const exportChat = () => {
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

  const groupedModels = models.reduce((acc, model) => {
    if (!acc[model.provider]) acc[model.provider] = []
    acc[model.provider].push(model)
    return acc
  }, {} as Record<string, ChatModel[]>)

  const getProviderIcon = (provider: string) => {
    switch (provider) {
      case 'ollama': return '🦙'
      case 'openai': return '🤖'
      case 'anthropic': return '🧠'
      case 'google': return '🔷'
      case 'groq': return '⚡'
      default: return '🔗'
    }
  }

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 p-4 flex-shrink-0">
        <div className="flex items-center justify-between max-w-4xl mx-auto">
          <div className="flex items-center gap-4">
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg bg-white text-sm min-w-[200px]"
              disabled={isLoading}
            >
              <option value="">Select a model...</option>
              {Object.entries(groupedModels).map(([provider, providerModels]) => (
                <optgroup key={provider} label={`${getProviderIcon(provider)} ${provider.charAt(0).toUpperCase() + provider.slice(1)}`}>
                  {providerModels.map(model => (
                    <option key={model.id} value={model.id}>
                      {model.name}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>

            {selectedModel && (
              <span className="text-sm text-gray-600">
                Provider: {models.find(m => m.id === selectedModel)?.provider || 'Unknown'}
              </span>
            )}
          </div>

          <div className="flex gap-2">
            <button
              onClick={clearChat}
              className="px-3 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
              disabled={isLoading}
            >
              Clear
            </button>
            <button
              onClick={exportChat}
              className="px-3 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
              disabled={messages.length === 0}
            >
              Export
            </button>
            <button
              onClick={onRefresh}
              className="px-3 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
            >
              ↻
            </button>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 min-h-0">
        <div className="max-w-4xl mx-auto space-y-4">
          {messages.length === 0 && (
            <div className="text-center text-gray-500 py-8">
              <p className="text-lg">Welcome to PolyLlama Chat!</p>
              <p className="text-sm mt-2">Select a model and start chatting with your AI assistant.</p>
            </div>
          )}

          {messages.map((message, index) => (
            <div
              key={index}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-lg p-4 ${message.role === 'user'
                  ? 'bg-blue-500 text-white'
                  : 'bg-white border border-gray-200 text-gray-900'
                  }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 whitespace-pre-wrap">{message.content}</div>
                  {message.role === 'assistant' && (
                    <button
                      onClick={() => copyMessage(message.content)}
                      className="text-gray-400 hover:text-gray-600 p-1 rounded"
                      title="Copy message"
                    >
                      📋
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className="bg-white border-t border-gray-200 p-4 flex-shrink-0">
        <div className="max-w-4xl mx-auto">
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
              placeholder={selectedModel ? "Type your message..." : "Select a model to start chatting"}
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={isLoading || !selectedModel}
            />
            {isLoading ? (
              <button
                onClick={stopGeneration}
                className="px-6 py-3 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
              >
                Stop
              </button>
            ) : (
              <button
                onClick={sendMessage}
                disabled={!input.trim() || !selectedModel}
                className="px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                Send
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}