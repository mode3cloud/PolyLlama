'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { ChatMessage, ChatModel, StreamChunk } from '../types'
import { fetchWithAuth } from '../lib/fetchWithAuth'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// Use relative URLs to hit our Next.js API routes
const API_BASE_URL = '/ui/api/chat'

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
  const [copiedMessageId, setCopiedMessageId] = useState<number | null>(null)

  // Fetch available models
  const fetchModels = useCallback(async () => {
    try {
      const response = await fetchWithAuth(`${API_BASE_URL}/models`)
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
      const response = await fetchWithAuth(`${API_BASE_URL}/completions`, {
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
                <div className="relative group">
                  <div className="flex-1">
                    {message.role === 'user' ? (
                      <div className="whitespace-pre-wrap">{message.content}</div>
                    ) : (
                      <div>
                        {(() => {
                          // Check if content contains think blocks (complete or incomplete)
                          const completeThinkRegex = /<think>([\s\S]*?)<\/think>/g
                          const incompleteThinkRegex = /<think>([\s\S]*?)$/
                          const parts: Array<{type: 'content' | 'think', text: string, incomplete?: boolean}> = []
                          let lastIndex = 0
                          let match
                          
                          // First, find all complete think blocks
                          while ((match = completeThinkRegex.exec(message.content)) !== null) {
                            // Add content before think block
                            if (match.index > lastIndex) {
                              parts.push({
                                type: 'content',
                                text: message.content.slice(lastIndex, match.index)
                              })
                            }
                            
                            // Add complete think block
                            parts.push({
                              type: 'think',
                              text: match[1].trim()
                            })
                            
                            lastIndex = match.index + match[0].length
                          }
                          
                          // Check for incomplete think block at the end
                          const remainingContent = message.content.slice(lastIndex)
                          const incompleteMatch = incompleteThinkRegex.exec(remainingContent)
                          
                          if (incompleteMatch) {
                            // Add content before the incomplete think block
                            if (incompleteMatch.index > 0) {
                              parts.push({
                                type: 'content',
                                text: remainingContent.slice(0, incompleteMatch.index)
                              })
                            }
                            
                            // Add incomplete think block (being streamed)
                            parts.push({
                              type: 'think',
                              text: incompleteMatch[1].trim(),
                              incomplete: true
                            })
                          } else if (remainingContent) {
                            // No incomplete think block, just regular content
                            parts.push({
                              type: 'content',
                              text: remainingContent
                            })
                          }
                          
                          // If no parts found, treat entire content as regular
                          if (parts.length === 0) {
                            parts.push({
                              type: 'content',
                              text: message.content
                            })
                          }
                          
                          return parts.map((part, index) => {
                            if (part.type === 'think') {
                              return (
                                <div key={index} className="my-4 p-4 bg-purple-50 border border-purple-200 rounded-lg">
                                  <div className="flex items-center gap-2 mb-2 text-purple-700">
                                    <span className="text-sm font-semibold">💭 Thinking Process</span>
                                    {part.incomplete && (
                                      <span className="text-xs text-purple-600 animate-pulse">● Streaming...</span>
                                    )}
                                  </div>
                                  <div className="text-sm text-purple-900 whitespace-pre-wrap">
                                    {part.text}
                                  </div>
                                </div>
                              )
                            }
                            
                            return (
                              <div key={index} className="prose prose-sm max-w-none prose-gray [&>*]:text-gray-900">
                                <ReactMarkdown
                                  remarkPlugins={[remarkGfm]}
                                  components={{
                          pre: ({ children }) => {
                            const [copied, setCopied] = useState(false)
                            
                            const extractText = (node: any): string => {
                              if (typeof node === 'string') return node
                              if (!node) return ''
                              if (node.props?.children) {
                                if (Array.isArray(node.props.children)) {
                                  return node.props.children.map(extractText).join('')
                                }
                                return extractText(node.props.children)
                              }
                              return ''
                            }
                            
                            const handleCopy = () => {
                              const codeText = extractText(children)
                              navigator.clipboard.writeText(codeText)
                              setCopied(true)
                              setTimeout(() => setCopied(false), 2000)
                            }
                            
                            return (
                              <div className="relative group my-2">
                                <button
                                  onClick={handleCopy}
                                  className="absolute top-2 right-2 px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                                  title="Copy code"
                                >
                                  {copied ? '✓ Copied' : '📋 Copy'}
                                </button>
                                <pre className="bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto border border-gray-700">
                                  {children}
                                </pre>
                              </div>
                            )
                          },
                          code: ({ className, children, ...props }) => {
                            const match = /language-(\w+)/.exec(className || '')
                            const isInline = !match
                            return isInline ? (
                              <code className="bg-gray-100 text-gray-800 rounded px-1.5 py-0.5 text-sm font-mono" {...props}>
                                {children}
                              </code>
                            ) : (
                              <code className="text-gray-100 text-sm font-mono block" {...props}>
                                {children}
                              </code>
                            )
                          },
                          a: ({ href, children }) => (
                            <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 underline">
                              {children}
                            </a>
                          ),
                          ul: ({ children }) => (
                            <ul className="list-disc list-inside space-y-1 my-2">{children}</ul>
                          ),
                          ol: ({ children }) => (
                            <ol className="list-decimal list-inside space-y-1 my-2">{children}</ol>
                          ),
                          blockquote: ({ children }) => (
                            <blockquote className="border-l-4 border-gray-300 pl-4 italic my-2 text-gray-700">{children}</blockquote>
                          ),
                          h1: ({ children }) => (
                            <h1 className="text-2xl font-bold mt-4 mb-2">{children}</h1>
                          ),
                          h2: ({ children }) => (
                            <h2 className="text-xl font-bold mt-3 mb-2">{children}</h2>
                          ),
                          h3: ({ children }) => (
                            <h3 className="text-lg font-bold mt-2 mb-1">{children}</h3>
                          ),
                          p: ({ children }) => (
                            <p className="my-2">{children}</p>
                          ),
                          table: ({ children }) => (
                            <div className="overflow-x-auto my-2">
                              <table className="min-w-full border-collapse border border-gray-300">
                                {children}
                              </table>
                            </div>
                          ),
                          th: ({ children }) => (
                            <th className="border border-gray-300 px-4 py-2 bg-gray-100 font-semibold text-left">
                              {children}
                            </th>
                          ),
                          td: ({ children }) => (
                            <td className="border border-gray-300 px-4 py-2">
                              {children}
                            </td>
                          ),
                                }}
                                >
                                  {part.text}
                                </ReactMarkdown>
                              </div>
                            )
                          })
                        })()}
                      </div>
                    )}
                  </div>
                  {message.role === 'assistant' && (
                    <button
                      onClick={() => {
                        copyMessage(message.content)
                        setCopiedMessageId(index)
                        setTimeout(() => setCopiedMessageId(null), 2000)
                      }}
                      className="absolute top-2 right-2 px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                      title="Copy message"
                    >
                      {copiedMessageId === index ? '✓ Copied' : '📋 Copy'}
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