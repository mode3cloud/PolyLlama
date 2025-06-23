'use client'

import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { ChatMessage, ChatModel, ChatImage } from '../types'
import { fetchWithAuth } from '../lib/fetchWithAuth'
import { streamChat, syncSessionMessages, exportChatToMarkdown } from '../lib/chatUtils'
import SessionSidebar from './SessionSidebar'
import ChatHeader from './ChatHeader'
import ChatInput from './ChatInput'
import MessageDisplay from './MessageDisplay'

// Use relative URLs to hit our Next.js API routes
const API_BASE_URL = '/ui/api/chat'

export default function ChatInterface() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingSession, setIsLoadingSession] = useState(false)
  const [models, setModels] = useState<ChatModel[]>([])
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [sessionId, setSessionId] = useState(() => `session-${Date.now()}`)
  const [showSidebar, setShowSidebar] = useState(true)
  const [refreshTrigger, setRefreshTrigger] = useState(0)
  const [pendingModelSelection, setPendingModelSelection] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const [copiedMessageId, setCopiedMessageId] = useState<number | null>(null)
  const [temperature, setTemperature] = useState(0.2)

  // Fetch available models
  const fetchModels = useCallback(async () => {
    try {
      const response = await fetchWithAuth(`${API_BASE_URL}/models`)
      if (response.ok) {
        const data = await response.json()
        setModels(data.models || [])
        if (data.models?.length > 0 && !selectedModel && !pendingModelSelection) {
          // Default to first Ollama model if available, otherwise first model
          const ollamaModel = data.models.find((m: ChatModel) => m.provider === 'ollama')
          setSelectedModel(ollamaModel?.id || data.models[0].id)
        }
      }
    } catch (error) {
      console.error('Failed to fetch models:', error)
    }
  }, [pendingModelSelection, selectedModel])

  // Load session messages
  const loadSession = useCallback(async (sessionId: string) => {
    try {
      setIsLoadingSession(true)
      const response = await fetchWithAuth(`${API_BASE_URL}/sessions/${sessionId}`)
      if (response.ok) {
        const data = await response.json()
        // Filter to only show user and assistant messages in the UI
        const sessionMessages = data.messages
          .filter((msg: { role: string }) => msg.role === 'user' || msg.role === 'assistant')
          .map((msg: { role: string; content: string; timestamp: string }) => ({
            role: msg.role,
            content: msg.content,
            timestamp: msg.timestamp
          }))
        setMessages(sessionMessages)

        // Store model selection for restoration when models are loaded
        if (data.metadata?.model) {
          if (models.length > 0) {
            const modelExists = models.some(m => m.id === data.metadata.model)
            if (modelExists) {
              setSelectedModel(data.metadata.model)
            }
          } else {
            // Models not loaded yet, store for later
            setPendingModelSelection(data.metadata.model)
          }
        }
      }
    } catch (error) {
      console.error('Failed to load session:', error)
    } finally {
      setIsLoadingSession(false)
    }
  }, [models])

  // Handle session selection
  const handleSessionSelect = useCallback((newSessionId: string) => {
    if (newSessionId === sessionId) return

    // Stop any ongoing generation for current session
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    setSessionId(newSessionId)
    loadSession(newSessionId)
  }, [sessionId, loadSession])

  // Handle new session
  const handleNewSession = useCallback(() => {
    // Stop any ongoing generation
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    const newSessionId = `session-${Date.now()}`
    setSessionId(newSessionId)
    setMessages([])
  }, [])

  useEffect(() => {
    fetchModels()
  }, [fetchModels])

  // Apply pending model selection when models are loaded
  useEffect(() => {
    if (pendingModelSelection && models.length > 0) {
      const modelExists = models.some(m => m.id === pendingModelSelection)
      if (modelExists) {
        setSelectedModel(pendingModelSelection)
      }
      setPendingModelSelection(null)
    }
  }, [models, pendingModelSelection])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async (images?: ChatImage[]) => {
    if ((!input.trim() && !images?.length) || isLoading || !selectedModel) return

    const userMessage: ChatMessage = {
      role: 'user',
      content: input.trim(),
      timestamp: new Date().toISOString(),
      images: images
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    // Create abort controller for this request
    abortControllerRef.current = new AbortController()

    // Trigger sidebar refresh after first message
    if (messages.length === 0) {
      setTimeout(() => setRefreshTrigger(Date.now()), 500)
    }

    const assistantMessage: ChatMessage = {
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString()
    }

    setMessages(prev => [...prev, assistantMessage])

    try {
      await streamChat({
        messages: [...messages, userMessage],
        model: selectedModel,
        sessionId: sessionId,
        temperature: temperature,
        signal: abortControllerRef.current.signal,
        onChunk: (content) => {
          assistantMessage.content += content
          setMessages(prev =>
            prev.map((msg, idx) =>
              idx === prev.length - 1 ? { ...assistantMessage } : msg
            )
          )
        },
        onError: (error) => {
          assistantMessage.content += `\n\n*Error: ${error}*`
          setMessages(prev =>
            prev.map((msg, idx) =>
              idx === prev.length - 1 ? { ...assistantMessage } : msg
            )
          )
        },
        onDone: () => {
          // Stream completed
        }
      })
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        console.log('Request aborted')
      } else {
        console.error('Chat error:', error)
        const errorMessage: ChatMessage = {
          role: 'assistant',
          content: `*Error: ${(error as Error).message}*`,
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
    if (confirm('Are you sure you want to clear the current chat? This will start a new session.')) {
      handleNewSession()
    }
  }

  const copyMessage = (content: string) => {
    navigator.clipboard.writeText(content)
  }

  const deleteMessage = async (index: number) => {
    const newMessages = messages.filter((_, i) => i !== index)
    setMessages(newMessages)

    // Sync with backend
    await syncSessionMessages(sessionId, newMessages)
  }

  const resendMessage = async (index: number) => {
    // Only allow resending user messages or tool results
    const message = messages[index]
    if (message.role !== 'user' && message.role !== 'tool') return

    // Truncate messages after this one
    const truncatedMessages = messages.slice(0, index)
    setMessages(truncatedMessages)

    // Sync truncated messages with backend before resending
    await syncSessionMessages(sessionId, truncatedMessages)

    // Resend the message
    const userMessage: ChatMessage = {
      role: 'user',
      content: message.content,
      timestamp: new Date().toISOString()
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    // Create abort controller for this request
    abortControllerRef.current = new AbortController()

    // Trigger sidebar refresh after first message
    if (truncatedMessages.length === 0) {
      setTimeout(() => setRefreshTrigger(Date.now()), 500)
    }

    const assistantMessage: ChatMessage = {
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString()
    }

    setMessages(prev => [...prev, assistantMessage])

    try {
      await streamChat({
        messages: [...truncatedMessages, userMessage],
        model: selectedModel,
        sessionId: sessionId,
        temperature: temperature,
        signal: abortControllerRef.current.signal,
        onChunk: (content) => {
          assistantMessage.content += content
          setMessages(prev =>
            prev.map((msg, idx) =>
              idx === prev.length - 1 ? { ...assistantMessage } : msg
            )
          )
        },
        onError: (error) => {
          assistantMessage.content += `\n\n*Error: ${error}*`
          setMessages(prev =>
            prev.map((msg, idx) =>
              idx === prev.length - 1 ? { ...assistantMessage } : msg
            )
          )
        },
        onDone: () => {
          // Stream completed
        }
      })
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        console.log('Request aborted')
      } else {
        console.error('Chat error:', error)
        const errorMessage: ChatMessage = {
          role: 'assistant',
          content: `*Error: ${(error as Error).message}*`,
          timestamp: new Date().toISOString()
        }
        setMessages(prev => [...prev, errorMessage])
      }
    } finally {
      setIsLoading(false)
      abortControllerRef.current = null
    }
  }

  const exportChat = () => {
    exportChatToMarkdown(messages, sessionId)
  }

  const copyMessageWithFeedback = (content: string, index: number) => {
    copyMessage(content)
    setCopiedMessageId(index)
    setTimeout(() => setCopiedMessageId(null), 2000)
  }

  // Compute supportsVision based on current selectedModel
  const supportsVision = useMemo(() => {
    if (!selectedModel || models.length === 0) return false
    const model = models.find(m => m.id === selectedModel)
    return model?.supports_vision || false
  }, [selectedModel, models])

  return (
    <div className="flex h-full">
      {/* Session Sidebar */}
      {showSidebar && (
        <SessionSidebar
          currentSessionId={sessionId}
          onSessionSelect={handleSessionSelect}
          onNewSession={handleNewSession}
          refreshTrigger={refreshTrigger}
        />
      )}

      {/* Main Chat Area */}
      <div className="flex flex-col flex-1 bg-gray-50">
        <ChatHeader
          selectedModel={selectedModel}
          models={models}
          isLoading={isLoading}
          showSidebar={showSidebar}
          temperature={temperature}
          onModelChange={setSelectedModel}
          onToggleSidebar={() => setShowSidebar(!showSidebar)}
          onClearChat={clearChat}
          onExportChat={exportChat}
          onTemperatureChange={setTemperature}
          hasMessages={messages.length > 0}
        />

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4">
          <div className="max-w-4xl mx-auto space-y-4 transition-opacity duration-200">
            {isLoadingSession ? (
              <div className="text-center text-gray-500 py-8">
                <p className="text-lg">Loading session...</p>
              </div>
            ) : messages.length === 0 ? (
              <div className="text-center text-gray-500 py-8">
                <p className="text-lg">Welcome to PolyLlama Chat!</p>
                <p className="text-sm mt-2">Select a model and start chatting with your AI assistant.</p>
              </div>
            ) : null}

            {!isLoadingSession && messages.map((message, index) => (
              <MessageDisplay
                key={index}
                message={message}
                index={index}
                onCopy={copyMessageWithFeedback}
                onDelete={deleteMessage}
                onResend={resendMessage}
                copiedMessageId={copiedMessageId}
                isLoading={isLoading}
              />
            ))}
            <div ref={messagesEndRef} />
          </div>
        </div>

        <ChatInput
          input={input}
          isLoading={isLoading}
          selectedModel={selectedModel}
          supportsVision={supportsVision}
          onInputChange={setInput}
          onSendMessage={sendMessage}
          onStopGeneration={stopGeneration}
        />
      </div>
    </div>
  )
}