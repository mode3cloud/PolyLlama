'use client'

import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { ChatMessage, ChatModel, ChatImage } from '../types'
import { fetchWithAuth } from '../lib/fetchWithAuth'
import { streamChat, streamChatWithAudio, syncSessionMessages, exportChatToMarkdown } from '../lib/chatUtils'
import { useAudioPlayer } from '../hooks/useAudioPlayer'
import SessionSidebar from './SessionSidebar'
import ChatHeader from './ChatHeader'
import ChatInput from './ChatInput'
import MessageDisplay from './MessageDisplay'
import MCPStatus, { ToolSelection } from './MCPStatus'

// Use relative URLs to hit our Next.js API routes
const API_BASE_URL = '/ui/api/chat'

export default function ChatInterface() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingSession, setIsLoadingSession] = useState(false)
  const [models, setModels] = useState<ChatModel[]>([])
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [sessionId, setSessionId] = useState<string>('')
  const [showSidebar, setShowSidebar] = useState(true)
  const [refreshTrigger, setRefreshTrigger] = useState(0)
  const [pendingModelSelection, setPendingModelSelection] = useState<string | null>(null)
  const [hasLoadedSession, setHasLoadedSession] = useState(false)
  const [isLoadingSessionData, setIsLoadingSessionData] = useState(false)
  const [hasInitializedSession, setHasInitializedSession] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const [copiedMessageId, setCopiedMessageId] = useState<number | null>(null)
  const selectedModelRef = useRef<string>('')
  const [temperature, setTemperature] = useState(0.2)
  const [audioEnabled, setAudioEnabled] = useState(false)
  const { playAudio, stopAudio, isPlaying: isAudioPlaying } = useAudioPlayer()
  const isStreamingRef = useRef(false)
  const currentStreamIdRef = useRef<string | null>(null)
  const streamingContentRef = useRef<{ [messageIndex: number]: string }>({})
  const lastMessageIndexRef = useRef<number>(-1)
  const [toolSelection, setToolSelection] = useState<ToolSelection>({})
  const [hasInitializedToolSelection, setHasInitializedToolSelection] = useState(false)

  // Fetch available models
  const fetchModels = useCallback(async () => {
    try {
      const response = await fetchWithAuth(`${API_BASE_URL}/models`)
      if (response.ok) {
        const data = await response.json()
        setModels(data.models || [])
      }
    } catch (error) {
      console.error('Failed to fetch models:', error)
    }
  }, [])


  // Tool priority scoring (same as MCPStatus)
  const getToolPriority = (tool: any): number => {
    let score = 0
    
    // Shorter names often indicate more common tools
    score += Math.max(0, 50 - tool.name.length)
    
    // Prioritize certain keywords
    const highPriorityWords = ['search', 'get', 'list', 'read', 'fetch', 'query', 'find']
    const mediumPriorityWords = ['create', 'update', 'delete', 'write', 'execute', 'run']
    
    const name = tool.name.toLowerCase()
    if (highPriorityWords.some(word => name.includes(word))) score += 20
    if (mediumPriorityWords.some(word => name.includes(word))) score += 10
    
    return score
  }

  // Initialize tool selection with smart defaults when MCP status is available
  const initializeToolSelection = useCallback(async () => {
    if (hasInitializedToolSelection) return
    
    try {
      const response = await fetchWithAuth('/ui/api/mcp/proxy-status?includeTools=true')
      if (response.ok) {
        const data = await response.json()
        if (data.servers && data.total_tools > 128) {
          // Auto-select first 128 tools using smart selection logic
          const allTools: Array<{ serverName: string; toolName: string; tool: any }> = []
          
          Object.entries(data.servers).forEach(([serverName, serverData]: [string, any]) => {
            if (serverData.tools) {
              serverData.tools.forEach((tool: any) => {
                allTools.push({ serverName, toolName: tool.name, tool })
              })
            }
          })
          
          // Sort by priority (same logic as MCPStatus)
          allTools.sort((a, b) => {
            const aScore = getToolPriority(a.tool)
            const bScore = getToolPriority(b.tool)
            return bScore - aScore
          })
          
          // Select top 128 tools
          const selectedTools = allTools.slice(0, 128)
          
          const newSelection: ToolSelection = {}
          selectedTools.forEach(({ serverName, toolName }) => {
            if (!newSelection[serverName]) {
              newSelection[serverName] = {}
            }
            newSelection[serverName][toolName] = true
          })
          
          // Validate the selection count
          const selectedCount = Object.values(newSelection).reduce((total, serverTools) => {
            return total + Object.values(serverTools).filter(Boolean).length
          }, 0)
          
          console.log(`Initialized tool selection with ${selectedCount} tools (limit: 128)`)
          setToolSelection(newSelection)
        }
        setHasInitializedToolSelection(true)
      }
    } catch (error) {
      console.error('Failed to initialize tool selection:', error)
    }
  }, [hasInitializedToolSelection])

  // Load session messages
  const loadSession = useCallback(async (sessionId: string) => {
    try {
      setIsLoadingSession(true)
      setIsLoadingSessionData(true)
      const response = await fetchWithAuth(`${API_BASE_URL}/sessions/${sessionId}`)
      if (response.ok) {
        const data = await response.json()
        // Include user, assistant, tool, and system messages
        const sessionMessages = data.messages
          .filter((msg: { role: string }) => msg.role === 'user' || msg.role === 'assistant' || msg.role === 'tool' || msg.role === 'system')
          .map((msg: { role: string; content: unknown; timestamp: string; images?: unknown[]; tool_calls?: Array<{ id: string; type: string; function: { name: string; arguments: string } }>; tool_name?: string; tool_call_id?: string }) => {
            // Handle content that might be an array with image objects
            let messageContent = msg.content
            let images = msg.images

            // If content is an array, extract text and images
            if (Array.isArray(msg.content)) {
              const textContent = msg.content.find((item: { type: string; text?: string }) => item.type === 'text') as { text?: string } | undefined
              const imageContent = msg.content.filter((item: { type: string }) => item.type === 'image_url')
              
              messageContent = textContent?.text || ''
              
              // Convert image_url format to our ChatImage format
              if (imageContent.length > 0 && !images) {
                images = imageContent.map((img: { image_url?: { url?: string; detail?: string } | string }) => {
                  const imageUrl = img.image_url
                  if (typeof imageUrl === 'string') {
                    return { url: imageUrl }
                  }
                  return {
                    url: imageUrl?.url || '',
                    name: imageUrl?.detail || undefined
                  }
                })
              }
            } else if (typeof msg.content !== 'string') {
              // If content is not a string and not an array, convert to string
              messageContent = String(msg.content || '')
            }

            return {
              role: msg.role,
              content: messageContent,
              timestamp: msg.timestamp,
              images: images,
              tool_calls: msg.tool_calls,
              tool_name: msg.tool_name,
              tool_call_id: msg.tool_call_id
            }
          })
        setMessages(sessionMessages)

        // Store model selection for restoration when models are loaded
        if (data.metadata?.model) {
          if (models.length > 0) {
            const modelExists = models.some(m => m.id === data.metadata.model)
            if (modelExists) {
              setSelectedModel(data.metadata.model)
              selectedModelRef.current = data.metadata.model
            }
          } else {
            // Models not loaded yet, store for later
            setPendingModelSelection(data.metadata.model)
          }
        }
        
        // Load tool selection for this session if it exists
        try {
          const toolResponse = await fetchWithAuth(`${API_BASE_URL}/sessions/${sessionId}/tool-selection`)
          if (toolResponse.ok) {
            const toolData = await toolResponse.json()
            if (toolData.tool_selection && Object.keys(toolData.tool_selection).length > 0) {
              setToolSelection(toolData.tool_selection)
              console.log(`Loaded tool selection for session ${sessionId}:`, toolData.tool_selection)
            } else {
              // If no tool selection saved, initialize with defaults
              await initializeToolSelection()
            }
          }
        } catch (toolError) {
          console.warn('Failed to load tool selection for session:', toolError)
          // Fall back to default tool selection
          await initializeToolSelection()
        }
        
        // Mark that we've loaded a session with data
        setHasLoadedSession(true)
      }
    } catch (error) {
      console.error('Failed to load session:', error)
    } finally {
      setIsLoadingSession(false)
      setIsLoadingSessionData(false)
    }
  }, [models, API_BASE_URL, initializeToolSelection])

  // Initialize session - fetch most recent session or create new one
  const initializeSession = useCallback(async () => {
    if (hasInitializedSession) return
    
    try {
      setIsLoadingSession(true)
      const response = await fetchWithAuth(`${API_BASE_URL}/sessions`)
      if (response.ok) {
        const data = await response.json()
        const sessions = data.sessions || []
        
        if (sessions.length > 0) {
          // Sort sessions by creation date (most recent first)
          const sortedSessions = sessions.sort((a: any, b: any) => 
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
          )
          const mostRecentSession = sortedSessions[0]
          
          // Load the most recent session
          setSessionId(mostRecentSession.id)
          await loadSession(mostRecentSession.id)
        } else {
          // No existing sessions, create a new one
          const newSessionId = `session-${Date.now()}`
          setSessionId(newSessionId)
          setMessages([])
        }
      } else {
        // Fallback to new session if fetch fails
        const newSessionId = `session-${Date.now()}`
        setSessionId(newSessionId)
        setMessages([])
      }
    } catch (error) {
      console.error('Failed to initialize session:', error)
      // Fallback to new session
      const newSessionId = `session-${Date.now()}`
      setSessionId(newSessionId)
      setMessages([])
    } finally {
      setIsLoadingSession(false)
      setHasInitializedSession(true)
    }
  }, [hasInitializedSession, loadSession])

  // Handle session selection
  const handleSessionSelect = useCallback((newSessionId: string) => {
    if (newSessionId === sessionId) return

    // Stop any ongoing generation for current session
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    // Clear current model to allow session's saved model to be loaded
    setSelectedModel('')
    setPendingModelSelection(null)
    setHasLoadedSession(false) // Reset this flag before loading new session
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
    setHasLoadedSession(false) // Reset this flag for new session
    // Clear tool selection for new session - let it initialize with defaults
    setToolSelection({})
    setHasInitializedToolSelection(false)
    // Re-initialize tool selection for new session
    setTimeout(() => initializeToolSelection(), 100)
  }, [initializeToolSelection])



  // Save tool selection to session
  const saveToolSelection = useCallback(async (selection: ToolSelection) => {
    if (!sessionId) return
    
    try {
      const response = await fetchWithAuth(`${API_BASE_URL}/sessions/${sessionId}/tool-selection`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ tool_selection: selection })
      })
      
      if (response.ok) {
        console.log(`Saved tool selection for session ${sessionId}`)
      } else {
        const errorText = await response.text()
        console.warn(`Failed to save tool selection for session ${sessionId}:`, errorText)
        
        // If it's a new session, the backend might not have created it yet
        // This is normal behavior and we can safely ignore it
        if (errorText.includes('Not Found')) {
          console.log('Session not created yet, tool selection will be saved when session is created')
        }
      }
    } catch (error) {
      console.warn('Error saving tool selection (this is normal for new sessions):', error)
    }
  }, [sessionId])

  // Save tool selection whenever it changes (with debounce)
  useEffect(() => {
    if (Object.keys(toolSelection).length > 0 && sessionId) {
      // Debounce saves to avoid excessive API calls
      const timeoutId = setTimeout(() => {
        saveToolSelection(toolSelection)
      }, 500)
      
      return () => clearTimeout(timeoutId)
    }
  }, [toolSelection, sessionId, saveToolSelection])

  useEffect(() => {
    fetchModels()
    initializeToolSelection()
    initializeSession()
  }, [fetchModels, initializeToolSelection, initializeSession])

  // Apply pending model selection when models are loaded
  useEffect(() => {
    if (pendingModelSelection && models.length > 0) {
      const modelExists = models.some(m => m.id === pendingModelSelection)
      if (modelExists) {
        setSelectedModel(pendingModelSelection)
        selectedModelRef.current = pendingModelSelection
      }
      setPendingModelSelection(null)
    }
  }, [models, pendingModelSelection])

  // Set default model only for new sessions
  useEffect(() => {
    if (models.length > 0 && 
        !selectedModel && 
        !pendingModelSelection && 
        !hasLoadedSession &&
        !isLoadingSessionData &&
        hasInitializedSession &&
        messages.length === 0) {
      // Default to gpt-4o-mini if available, otherwise first Ollama model, otherwise first model
      const gpt4oMini = models.find((m: ChatModel) => m.id === 'openai/gpt-4o-mini')
      const ollamaModel = models.find((m: ChatModel) => m.provider === 'ollama')
      const defaultModel = gpt4oMini?.id || ollamaModel?.id || models[0].id
      setSelectedModel(defaultModel)
      selectedModelRef.current = defaultModel
    }
  }, [models, selectedModel, pendingModelSelection, hasLoadedSession, isLoadingSessionData, hasInitializedSession, messages.length])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Create shared handlers for streaming that can be reused
  const createStreamHandlers = useCallback(() => ({
    onChunk: (content: string) => {
      const timestamp = Date.now();
      console.log(`[onChunk ${timestamp}] Called with: "${content}"`);
      
      setMessages(prev => {
        console.log(`[onChunk ${timestamp}] State update - current messages count: ${prev.length}`);
        
        // Check if we need a new assistant message after tool results
        const lastMessage = prev[prev.length - 1];
        const needNewMessage = !lastMessage || 
                             lastMessage.role === 'tool' || 
                             lastMessage.role === 'user' ||
                             (lastMessage.role === 'assistant' && lastMessage.tool_calls && lastMessage.tool_calls.length > 0);
        
        if (needNewMessage) {
          // Create a new assistant message after tool results or if no assistant message exists
          const messageIndex = prev.length;
          lastMessageIndexRef.current = messageIndex;
          streamingContentRef.current[messageIndex] = content;
          
          console.log(`[onChunk ${timestamp}] NEW MESSAGE: content="${content}"`);
          
          const newAssistantMessage: ChatMessage = {
            role: 'assistant',
            content: content,
            timestamp: new Date().toISOString()
          };
          return [...prev, newAssistantMessage];
        } else {
          // Update the last assistant message - SIMPLIFIED APPROACH
          const updatedMessages = [...prev];
          const lastIdx = prev.length - 1;
          const currentContent = updatedMessages[lastIdx].content;
          
          console.log(`[onChunk ${timestamp}] UPDATE: currentContent="${currentContent}", adding="${content}"`);
          
          // Simply append to the existing content
          updatedMessages[lastIdx] = {
            ...updatedMessages[lastIdx],
            content: currentContent + content
          };
          
          console.log(`[onChunk ${timestamp}] RESULT: "${updatedMessages[lastIdx].content}"`);
          return updatedMessages;
        }
      });
    },
    onError: (error: string) => {
      setMessages(prev => {
        const lastAssistantIdx = prev.findLastIndex(msg => msg.role === 'assistant');
        if (lastAssistantIdx >= 0) {
          const updatedMessages = [...prev];
          updatedMessages[lastAssistantIdx] = {
            ...updatedMessages[lastAssistantIdx],
            content: updatedMessages[lastAssistantIdx].content + `\n\n*Error: ${error}*`
          };
          return updatedMessages;
        }
        // If no assistant message, add error as new message
        return [...prev, {
          role: 'assistant',
          content: `*Error: ${error}*`,
          timestamp: new Date().toISOString()
        }];
      })
    },
    onDone: () => {
      // Stream completed - clear refs
      streamingContentRef.current = {};
      lastMessageIndexRef.current = -1;
    },
    onToolCallStreaming: (toolCall: { id: string; name: string; status?: 'started' | 'completed' }) => {
      // Show tool is being prepared
      if (toolCall.status === 'started') {
        setMessages(prev => {
          // Check if we need to create a new assistant message
          const lastMessage = prev[prev.length - 1];
          const needNewMessage = !lastMessage || 
                               lastMessage.role !== 'assistant' ||
                               (lastMessage.tool_calls && lastMessage.tool_calls.length > 0);
          
          if (needNewMessage) {
            // Create new assistant message for tool preparation
            const toolStreamMessage: ChatMessage = {
              role: 'assistant',
              content: `🔧 Preparing to call tool: **${toolCall.name}**...`,
              timestamp: new Date().toISOString()
            };
            return [...prev, toolStreamMessage];
          } else {
            // Update existing assistant message
            const updatedMessages = [...prev];
            const lastIdx = prev.length - 1;
            const toolInfo = `🔧 Preparing to call tool: **${toolCall.name}**...\n`;
            
            if (updatedMessages[lastIdx].content && !updatedMessages[lastIdx].content.includes(toolInfo)) {
              updatedMessages[lastIdx] = {
                ...updatedMessages[lastIdx],
                content: updatedMessages[lastIdx].content + '\n\n' + toolInfo
              };
            } else if (!updatedMessages[lastIdx].content) {
              updatedMessages[lastIdx] = {
                ...updatedMessages[lastIdx],
                content: toolInfo
              };
            }
            return updatedMessages;
          }
        });
      }
    },
    onToolCall: (toolCall: { id: string; name: string; arguments: Record<string, unknown> }) => {
      // Update the current assistant message to include tool_calls
      setMessages(prev => {
        // Find the last assistant message that doesn't already have completed tool_calls
        const lastMessage = prev[prev.length - 1];
        if (lastMessage && lastMessage.role === 'assistant') {
          const updatedMessages = [...prev];
          const lastIdx = prev.length - 1;
          
          // Add or append to tool_calls array
          const newToolCall = {
            id: toolCall.id,
            type: 'function' as const,
            function: {
              name: toolCall.name,
              arguments: JSON.stringify(toolCall.arguments)
            }
          };
          
          if (updatedMessages[lastIdx].tool_calls) {
            // Append to existing tool_calls
            updatedMessages[lastIdx] = {
              ...updatedMessages[lastIdx],
              tool_calls: [...updatedMessages[lastIdx].tool_calls!, newToolCall]
            };
          } else {
            // Create new tool_calls array
            updatedMessages[lastIdx] = {
              ...updatedMessages[lastIdx],
              tool_calls: [newToolCall]
            };
          }
          return updatedMessages;
        }
        return prev;
      });
    },
    onToolResult: (name: string, result: string, toolCallId?: string) => {
      let formattedResult = result;
      // Check if the result looks like JSON array from MCP
      if (result.trim().startsWith('[') && result.trim().endsWith(']')) {
        try {
          const parsed = JSON.parse(result);
          if (Array.isArray(parsed) && parsed.length > 0 && parsed[0].type === 'text') {
            // Extract text content from MCP response format
            formattedResult = parsed.map((item: any) => item.text || '').join('\n\n');
          }
        } catch (e) {
          // Not JSON or parsing failed, use as-is
        }
      }
      
      // Add a tool result message
      const toolResultMessage: ChatMessage = {
        role: 'tool',
        content: formattedResult,
        tool_name: name,
        tool_call_id: toolCallId,
        timestamp: new Date().toISOString()
      }
      setMessages(prev => [...prev, toolResultMessage])
      
      // The onChunk handler will create a new assistant message when needed
    },
    onToolError: (name: string, error: string, toolCallId?: string) => {
      // Add a tool error message
      const toolErrorMessage: ChatMessage = {
        role: 'tool',
        content: `Error executing tool ${name}: ${error}`,
        tool_name: name,
        tool_call_id: toolCallId,
        timestamp: new Date().toISOString()
      }
      setMessages(prev => [...prev, toolErrorMessage])
    }
  }), [])

  const sendMessage = async (images?: ChatImage[]) => {
    if ((!input.trim() && !images?.length) || isLoading || !selectedModel || isStreamingRef.current) return
    
    // Abort any existing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    
    // Generate a unique stream ID for this request
    const streamId = `${sessionId}_${Date.now()}_${Math.random()}`;
    currentStreamIdRef.current = streamId;
    
    // Set streaming flag
    isStreamingRef.current = true;

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

    // Trigger sidebar refresh and save tool selection after first message
    if (messages.length === 0) {
      setTimeout(() => setRefreshTrigger(Date.now()), 500)
      // Save tool selection now that session will be created with first message
      if (Object.keys(toolSelection).length > 0) {
        setTimeout(() => saveToolSelection(toolSelection), 1000)
      }
    }

    // Don't create assistant message upfront - let the streaming handlers create it
    
    // Clear streaming content ref for new stream
    streamingContentRef.current = {};
    
    // Get shared handlers
    const sharedHandlers = createStreamHandlers();

    try {
      
      if (audioEnabled) {
        // Use audio streaming with shared handlers
        await streamChatWithAudio({
          messages: [...messages, userMessage],
          model: selectedModel,
          sessionId: sessionId,
          temperature: temperature,
          signal: abortControllerRef.current.signal,
          ...sharedHandlers,
          onAudio: (audioData) => {
            // Play audio chunk
            playAudio(audioData.audio, audioData.sample_rate)
          },
          toolSelection: toolSelection
        })
      } else {
        // Use regular text streaming
        await streamChat({
          messages: [...messages, userMessage],
          model: selectedModel,
          sessionId: sessionId,
          temperature: temperature,
          signal: abortControllerRef.current.signal,
          ...sharedHandlers,
          toolSelection: toolSelection
        })
      }
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
      isStreamingRef.current = false
      currentStreamIdRef.current = null
    }
  }

  const stopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    if (audioEnabled) {
      stopAudio()
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

    // Resend the message with images if present
    const userMessage: ChatMessage = {
      role: 'user',
      content: message.content,
      timestamp: new Date().toISOString(),
      images: message.images
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

    // Don't create assistant message upfront - let the streaming handlers create it
    
    // Clear streaming content ref for new stream
    streamingContentRef.current = {};
    
    // Get shared handlers
    const sharedHandlers = createStreamHandlers();

    try {
      
      if (audioEnabled) {
        // Use audio streaming
        await streamChatWithAudio({
          messages: [...truncatedMessages, userMessage],
          model: selectedModel,
          sessionId: sessionId,
          temperature: temperature,
          signal: abortControllerRef.current.signal,
          ...sharedHandlers,
          onAudio: (audioData) => {
            // Play audio chunk
            playAudio(audioData.audio, audioData.sample_rate)
          },
          toolSelection: toolSelection
        })
      } else {
        // Use regular text streaming
        await streamChat({
          messages: [...truncatedMessages, userMessage],
          model: selectedModel,
          sessionId: sessionId,
          temperature: temperature,
          signal: abortControllerRef.current.signal,
          ...sharedHandlers,
          toolSelection: toolSelection
        })
      }
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
      isStreamingRef.current = false
      currentStreamIdRef.current = null
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
          audioEnabled={audioEnabled}
          onModelChange={(model: string) => {
            setSelectedModel(model)
            selectedModelRef.current = model
          }}
          onToggleSidebar={() => setShowSidebar(!showSidebar)}
          onClearChat={clearChat}
          onExportChat={exportChat}
          onTemperatureChange={setTemperature}
          onToggleAudio={() => setAudioEnabled(!audioEnabled)}
          hasMessages={messages.length > 0}
        />

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4">
          <div className="max-w-4xl mx-auto space-y-4 transition-opacity duration-200">
            {/* MCP Status */}
            <MCPStatus 
              toolSelection={toolSelection}
              onToolSelectionChange={setToolSelection}
              maxTools={128}
            />
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
                key={`${message.timestamp}-${index}-${message.role}`}
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
          isAudioPlaying={isAudioPlaying}
          audioEnabled={audioEnabled}
          onInputChange={setInput}
          onSendMessage={sendMessage}
          onStopGeneration={stopGeneration}
          onStopAudio={stopAudio}
        />
      </div>
    </div>
  )
}
