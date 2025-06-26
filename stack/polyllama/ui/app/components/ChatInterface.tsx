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
import MCPStatus from './MCPStatus'

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
  const [hasLoadedSession, setHasLoadedSession] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const [copiedMessageId, setCopiedMessageId] = useState<number | null>(null)
  const [temperature, setTemperature] = useState(0.2)
  const [audioEnabled, setAudioEnabled] = useState(false)
  const { playAudio, stopAudio, isPlaying: isAudioPlaying } = useAudioPlayer()

  // Fetch available models
  const fetchModels = useCallback(async () => {
    try {
      const response = await fetchWithAuth(`${API_BASE_URL}/models`)
      if (response.ok) {
        const data = await response.json()
        setModels(data.models || [])
        // Only set default model if:
        // 1. No model is currently selected
        // 2. No pending model selection from a loaded session
        // 3. We haven't loaded a session with saved preferences
        if (data.models?.length > 0 && !selectedModel && !pendingModelSelection && !hasLoadedSession) {
          // Only set default for new sessions without any messages
          if (messages.length === 0) {
            // Default to first Ollama model if available, otherwise first model
            const ollamaModel = data.models.find((m: ChatModel) => m.provider === 'ollama')
            setSelectedModel(ollamaModel?.id || data.models[0].id)
          }
        }
      }
    } catch (error) {
      console.error('Failed to fetch models:', error)
    }
  }, [pendingModelSelection, selectedModel, hasLoadedSession, messages.length])

  // Load session messages
  const loadSession = useCallback(async (sessionId: string) => {
    try {
      setIsLoadingSession(true)
      const response = await fetchWithAuth(`${API_BASE_URL}/sessions/${sessionId}`)
      if (response.ok) {
        const data = await response.json()
        // Include user, assistant, tool, and system messages
        const sessionMessages = data.messages
          .filter((msg: { role: string }) => msg.role === 'user' || msg.role === 'assistant' || msg.role === 'tool' || msg.role === 'system')
          .map((msg: { role: string; content: unknown; timestamp: string; images?: unknown[]; tool_calls?: any; tool_name?: string; tool_call_id?: string }) => {
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
            }
          } else {
            // Models not loaded yet, store for later
            setPendingModelSelection(data.metadata.model)
          }
        }
        // Mark that we've loaded a session with data
        setHasLoadedSession(true)
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

    // Clear current model to allow session's saved model to be loaded
    setSelectedModel('')
    setPendingModelSelection(null)
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

    // Don't create assistant message upfront - let the streaming handlers create it

    try {
      if (audioEnabled) {
        // Use audio streaming
        await streamChatWithAudio({
          messages: [...messages, userMessage],
          model: selectedModel,
          sessionId: sessionId,
          temperature: temperature,
          signal: abortControllerRef.current.signal,
          onChunk: (content) => {
            setMessages(prev => {
              // Check if we need a new assistant message after tool results
              const lastMessage = prev[prev.length - 1];
              const needNewMessage = !lastMessage || 
                                   lastMessage.role === 'tool' || 
                                   lastMessage.role === 'user' ||
                                   (lastMessage.role === 'assistant' && lastMessage.tool_calls && lastMessage.tool_calls.length > 0);
              
              if (needNewMessage) {
                // Create a new assistant message after tool results or if no assistant message exists
                const newAssistantMessage: ChatMessage = {
                  role: 'assistant',
                  content: content,
                  timestamp: new Date().toISOString()
                };
                return [...prev, newAssistantMessage];
              } else {
                // Update the last assistant message (that doesn't have tool_calls)
                const updatedMessages = [...prev];
                const lastIdx = prev.length - 1;
                updatedMessages[lastIdx] = {
                  ...updatedMessages[lastIdx],
                  content: updatedMessages[lastIdx].content + content
                };
                return updatedMessages;
              }
            });
          },
          onError: (error) => {
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
            // Stream completed
          },
          onAudio: (audioData) => {
            // Play audio chunk
            playAudio(audioData.audio, audioData.sample_rate)
          },
          onToolCallStreaming: (toolCall) => {
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
          onToolCall: (toolCall) => {
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
          onToolResult: (name, result, toolCallId) => {
            // Handle result which might be an array or string
            let formattedResult = result;
            
            // If result is an array, extract text content
            if (Array.isArray(result)) {
              // Extract text from array format [{type: "text", text: "..."}]
              const textContent = result
                .filter(item => item.type === 'text')
                .map(item => item.text)
                .join('\n');
              formattedResult = textContent || JSON.stringify(result, null, 2);
            } else if (typeof result === 'string') {
              // Try to parse as JSON for better display
              try {
                const parsed = JSON.parse(result);
                formattedResult = '```json\n' + JSON.stringify(parsed, null, 2) + '\n```';
              } catch {
                // Not JSON, use as-is
                formattedResult = result;
              }
            } else {
              // For any other type, stringify it
              formattedResult = JSON.stringify(result, null, 2);
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
          onToolError: (name, error, toolCallId) => {
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
        })
      } else {
        // Use regular text streaming
        await streamChat({
          messages: [...messages, userMessage],
          model: selectedModel,
          sessionId: sessionId,
          temperature: temperature,
          signal: abortControllerRef.current.signal,
          onChunk: (content) => {
            setMessages(prev => {
              // Check if we need a new assistant message after tool results
              const lastMessage = prev[prev.length - 1];
              const needNewMessage = !lastMessage || 
                                   lastMessage.role === 'tool' || 
                                   lastMessage.role === 'user' ||
                                   (lastMessage.role === 'assistant' && lastMessage.tool_calls && lastMessage.tool_calls.length > 0);
              
              if (needNewMessage) {
                // Create a new assistant message after tool results or if no assistant message exists
                const newAssistantMessage: ChatMessage = {
                  role: 'assistant',
                  content: content,
                  timestamp: new Date().toISOString()
                };
                return [...prev, newAssistantMessage];
              } else {
                // Update the last assistant message (that doesn't have tool_calls)
                const updatedMessages = [...prev];
                const lastIdx = prev.length - 1;
                updatedMessages[lastIdx] = {
                  ...updatedMessages[lastIdx],
                  content: updatedMessages[lastIdx].content + content
                };
                return updatedMessages;
              }
            });
          },
          onError: (error) => {
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
            // Stream completed
          },
          onToolCallStreaming: (toolCall) => {
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
          onToolCall: (toolCall) => {
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
          onToolResult: (name, result, toolCallId) => {
            // Handle result which might be an array or string
            let formattedResult = result;
            
            // If result is an array, extract text content
            if (Array.isArray(result)) {
              // Extract text from array format [{type: "text", text: "..."}]
              const textContent = result
                .filter(item => item.type === 'text')
                .map(item => item.text)
                .join('\n');
              formattedResult = textContent || JSON.stringify(result, null, 2);
            } else if (typeof result === 'string') {
              // Try to parse as JSON for better display
              try {
                const parsed = JSON.parse(result);
                formattedResult = '```json\n' + JSON.stringify(parsed, null, 2) + '\n```';
              } catch {
                // Not JSON, use as-is
                formattedResult = result;
              }
            } else {
              // For any other type, stringify it
              formattedResult = JSON.stringify(result, null, 2);
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
          onToolError: (name, error, toolCallId) => {
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

    try {
      if (audioEnabled) {
        // Use audio streaming
        await streamChatWithAudio({
          messages: [...truncatedMessages, userMessage],
          model: selectedModel,
          sessionId: sessionId,
          temperature: temperature,
          signal: abortControllerRef.current.signal,
          onChunk: (content) => {
            setMessages(prev => {
              // Check if we need a new assistant message after tool results
              const lastMessage = prev[prev.length - 1];
              const needNewMessage = !lastMessage || 
                                   lastMessage.role === 'tool' || 
                                   lastMessage.role === 'user' ||
                                   (lastMessage.role === 'assistant' && lastMessage.tool_calls && lastMessage.tool_calls.length > 0);
              
              if (needNewMessage) {
                // Create a new assistant message after tool results or if no assistant message exists
                const newAssistantMessage: ChatMessage = {
                  role: 'assistant',
                  content: content,
                  timestamp: new Date().toISOString()
                };
                return [...prev, newAssistantMessage];
              } else {
                // Update the last assistant message (that doesn't have tool_calls)
                const updatedMessages = [...prev];
                const lastIdx = prev.length - 1;
                updatedMessages[lastIdx] = {
                  ...updatedMessages[lastIdx],
                  content: updatedMessages[lastIdx].content + content
                };
                return updatedMessages;
              }
            });
          },
          onError: (error) => {
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
            // Stream completed
          },
          onAudio: (audioData) => {
            // Play audio chunk
            playAudio(audioData.audio, audioData.sample_rate)
          }
        })
      } else {
        // Use regular text streaming
        await streamChat({
          messages: [...truncatedMessages, userMessage],
          model: selectedModel,
          sessionId: sessionId,
          temperature: temperature,
          signal: abortControllerRef.current.signal,
          onChunk: (content) => {
            setMessages(prev => {
              // Check if we need a new assistant message after tool results
              const lastMessage = prev[prev.length - 1];
              const needNewMessage = !lastMessage || 
                                   lastMessage.role === 'tool' || 
                                   lastMessage.role === 'user' ||
                                   (lastMessage.role === 'assistant' && lastMessage.tool_calls && lastMessage.tool_calls.length > 0);
              
              if (needNewMessage) {
                // Create a new assistant message after tool results or if no assistant message exists
                const newAssistantMessage: ChatMessage = {
                  role: 'assistant',
                  content: content,
                  timestamp: new Date().toISOString()
                };
                return [...prev, newAssistantMessage];
              } else {
                // Update the last assistant message (that doesn't have tool_calls)
                const updatedMessages = [...prev];
                const lastIdx = prev.length - 1;
                updatedMessages[lastIdx] = {
                  ...updatedMessages[lastIdx],
                  content: updatedMessages[lastIdx].content + content
                };
                return updatedMessages;
              }
            });
          },
          onError: (error) => {
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
            // Stream completed
          }
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
          onModelChange={setSelectedModel}
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
            <MCPStatus />
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