'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { EmailMessage, ChatModel, ChatMessage } from '../types'
import { fetchWithAuth } from '../lib/fetchWithAuth'
import { GraphClient } from '../lib/graphClient'
import { streamEmailSummarize, streamEmailDraft } from '../lib/emailUtils'
import EmailHeader from './EmailHeader'
import EmailList from './EmailList'
import EmailDetailModal from './EmailDetailModal'
import EmailActionButtons from './EmailActionButtons'
import FolderTree from './FolderTree'

export default function EmailInterface() {
  const [emails, setEmails] = useState<EmailMessage[]>([])
  const [selectedEmails, setSelectedEmails] = useState<Set<string>>(new Set())
  const [isLoading, setIsLoading] = useState(false)
  const [models, setModels] = useState<ChatModel[]>([])
  const [selectedModel, setSelectedModel] = useState<string>(() => {
    // Initialize from localStorage
    if (typeof window !== 'undefined') {
      return localStorage.getItem('email-selected-model') || ''
    }
    return ''
  })
  const [, setCurrentPage] = useState(1)
  const [nextPageToken, setNextPageToken] = useState<string | undefined>()
  const [selectedEmail, setSelectedEmail] = useState<EmailMessage | null>(null)
  const [showDetailModal, setShowDetailModal] = useState(false)
  const [isSummarizing, setIsSummarizing] = useState(false)
  const [isDrafting, setIsDrafting] = useState(false)
  const [currentSummary, setCurrentSummary] = useState<string>('')
  const [currentDraft, setCurrentDraft] = useState<string>('')
  const [conversationMessages, setConversationMessages] = useState<ChatMessage[]>([])
  const [isConversationLoading, setIsConversationLoading] = useState(false)
  const [folders, setFolders] = useState<any[]>([])
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null)
  const [isFoldersLoading, setIsFoldersLoading] = useState(false)
  const [showFolderTree, setShowFolderTree] = useState(true)
  const graphClientRef = useRef<GraphClient | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const conversationAbortControllerRef = useRef<AbortController | null>(null)

  // Fetch available models
  const fetchModels = useCallback(async () => {
    try {
      const response = await fetchWithAuth('/ui/api/chat/models')
      if (response.ok) {
        const data = await response.json()
        setModels(data.models || [])

        // Check if saved model still exists
        const savedModel = localStorage.getItem('email-selected-model')
        if (savedModel && data.models?.some((m: ChatModel) => m.id === savedModel)) {
          // Saved model is still available, keep it
          return
        }

        // Otherwise set default if no model selected
        if (data.models?.length > 0 && !selectedModel) {
          // Default to first Ollama model if available
          const ollamaModel = data.models.find((m: ChatModel) => m.provider === 'ollama')
          const defaultModel = ollamaModel?.id || data.models[0].id
          setSelectedModel(defaultModel)
          localStorage.setItem('email-selected-model', defaultModel)
        }
      }
    } catch (error) {
      console.error('Failed to fetch models:', error)
    }
  }, [selectedModel])

  // Initialize Graph client
  const initGraphClient = useCallback(async () => {
    try {
      // Get access token from auth endpoint
      const response = await fetchWithAuth('/ui/api/auth/me')
      if (response.ok) {
        const data = await response.json()
        if (data.accessToken) {
          graphClientRef.current = new GraphClient(data.accessToken)
          return true
        }
      }
      return false
    } catch (error) {
      console.error('Failed to initialize Graph client:', error)
      return false
    }
  }, [])

  // Fetch folders
  const fetchFolders = useCallback(async () => {
    if (!graphClientRef.current) {
      const initialized = await initGraphClient()
      if (!initialized) return
    }

    setIsFoldersLoading(true)
    try {
      const folderData = await graphClientRef.current!.getMailFolders()
      setFolders(folderData)
    } catch (error) {
      console.error('Failed to fetch folders:', error)
    } finally {
      setIsFoldersLoading(false)
    }
  }, [initGraphClient])

  // Fetch emails
  const fetchEmails = useCallback(async (pageToken?: string) => {
    if (!graphClientRef.current) {
      const initialized = await initGraphClient()
      if (!initialized) return
    }

    setIsLoading(true)
    try {
      const response = await graphClientRef.current!.getEmails(20, pageToken, undefined, selectedFolderId || undefined)
      if (pageToken) {
        setEmails(prev => [...prev, ...response.messages])
      } else {
        setEmails(response.messages)
      }
      setNextPageToken(response.nextPageToken)
    } catch (error) {
      console.error('Failed to fetch emails:', error)
    } finally {
      setIsLoading(false)
    }
  }, [initGraphClient, selectedFolderId])

  useEffect(() => {
    fetchModels()
    const init = async () => {
      await fetchEmails()
      await fetchFolders()
    }
    init()
  }, [])

  // Refetch emails when folder selection changes
  useEffect(() => {
    if (graphClientRef.current && selectedFolderId !== undefined) {
      setEmails([])
      setNextPageToken(undefined)
      setCurrentPage(1)
      fetchEmails()
    }
  }, [selectedFolderId, fetchEmails])

  const handleSelectEmail = (emailId: string) => {
    setSelectedEmails(prev => {
      const newSet = new Set(prev)
      if (newSet.has(emailId)) {
        newSet.delete(emailId)
      } else {
        newSet.add(emailId)
      }
      return newSet
    })
  }

  const handleSelectAll = () => {
    if (selectedEmails.size === emails.length) {
      setSelectedEmails(new Set())
    } else {
      setSelectedEmails(new Set(emails.map(e => e.id)))
    }
  }

  const handleViewEmail = async (email: EmailMessage) => {
    if (!graphClientRef.current) return

    // Stop any ongoing generation
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    if (conversationAbortControllerRef.current) {
      conversationAbortControllerRef.current.abort()
    }

    // Reset states for new email
    setCurrentSummary('')
    setCurrentDraft('')
    setIsSummarizing(false)
    setIsDrafting(false)
    setConversationMessages([])
    setIsConversationLoading(false)

    try {
      // Fetch full email details including body
      const fullEmail = await graphClientRef.current.getEmailById(email.id)
      setSelectedEmail(fullEmail)
      setShowDetailModal(true)

      // Mark as read
      if (!fullEmail.isRead) {
        await graphClientRef.current.markAsRead(email.id)
        setEmails(prev => prev.map(e =>
          e.id === email.id ? { ...e, isRead: true } : e
        ))
      }
    } catch (error) {
      console.error('Failed to fetch email details:', error)
    }
  }

  const handleArchive = async (emailIds?: string[]) => {
    if (!graphClientRef.current) return

    const ids = emailIds || Array.from(selectedEmails)
    if (ids.length === 0) return

    try {
      if (ids.length === 1) {
        await graphClientRef.current.archiveEmail(ids[0])
      } else {
        await graphClientRef.current.batchArchiveEmails(ids)
      }

      // Remove from list
      setEmails(prev => prev.filter(e => !ids.includes(e.id)))
      setSelectedEmails(new Set())
      setShowDetailModal(false)
    } catch (error) {
      console.error('Failed to archive emails:', error)
    }
  }

  const handleDelete = async (emailIds?: string[]) => {
    if (!graphClientRef.current) return

    const ids = emailIds || Array.from(selectedEmails)
    if (ids.length === 0) return

    if (!confirm(`Are you sure you want to delete ${ids.length} email(s)?`)) return

    try {
      if (ids.length === 1) {
        await graphClientRef.current.deleteEmail(ids[0])
      } else {
        await graphClientRef.current.batchDeleteEmails(ids)
      }

      // Remove from list
      setEmails(prev => prev.filter(e => !ids.includes(e.id)))
      setSelectedEmails(new Set())
      setShowDetailModal(false)
    } catch (error) {
      console.error('Failed to delete emails:', error)
    }
  }

  const handleSummarize = async (email: EmailMessage) => {
    if (!selectedModel || isSummarizing) return

    setIsSummarizing(true)
    setCurrentSummary('')

    // Create abort controller
    abortControllerRef.current = new AbortController()

    await streamEmailSummarize(email, selectedModel, {
      onChunk: (content) => {
        setCurrentSummary(prev => prev + content)
      },
      onError: (error) => {
        console.error('Summarize error:', error)
        setCurrentSummary(prev => prev + '\n\nError: ' + error)
      },
      onDone: () => {
        setIsSummarizing(false)
      },
      signal: abortControllerRef.current.signal
    })
  }

  const handleDraft = async (
    email: EmailMessage,
    replyType: 'reply' | 'replyAll' | 'forward',
    context?: string
  ) => {
    if (!selectedModel || isDrafting) return

    setIsDrafting(true)
    setCurrentDraft('')

    // Create abort controller
    abortControllerRef.current = new AbortController()

    await streamEmailDraft(email, selectedModel, replyType, context, {
      onChunk: (content) => {
        setCurrentDraft(prev => prev + content)
      },
      onError: (error) => {
        console.error('Draft error:', error)
        setCurrentDraft(prev => prev + '\n\nError: ' + error)
      },
      onDone: () => {
        setIsDrafting(false)
      },
      signal: abortControllerRef.current.signal
    })
  }

  const handleLoadMore = () => {
    if (nextPageToken && !isLoading) {
      fetchEmails(nextPageToken)
    }
  }

  const handleRefresh = () => {
    setCurrentPage(1)
    setSelectedEmails(new Set())
    fetchEmails()
  }

  const stopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    if (conversationAbortControllerRef.current) {
      conversationAbortControllerRef.current.abort()
    }
    // Reset the loading states
    setIsSummarizing(false)
    setIsDrafting(false)
    setIsConversationLoading(false)
  }

  const handleModelChange = (model: string) => {
    setSelectedModel(model)
    // Save to localStorage
    if (typeof window !== 'undefined') {
      localStorage.setItem('email-selected-model', model)
    }
  }

  const handleSendConversationMessage = async (message: string, messages: ChatMessage[]) => {
    if (!selectedEmail || !selectedModel || isConversationLoading) return

    setIsConversationLoading(true)

    // Add user message to conversation
    const userMessage: ChatMessage = {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString()
    }
    setConversationMessages(prev => [...prev, userMessage])

    // Create abort controller for conversation
    conversationAbortControllerRef.current = new AbortController()

    try {
      const response = await fetchWithAuth('/ui/api/email/conversation', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: selectedEmail,
          model: selectedModel,
          messages,
          message,
          sessionId: selectedEmail.id, // Use email ID as session ID
          stream: true
        }),
        signal: conversationAbortControllerRef.current.signal
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      let assistantContent = ''
      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString()
      }

      // Add assistant message placeholder
      setConversationMessages(prev => [...prev, assistantMessage])

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.trim() === '') continue
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            if (data === '[DONE]') {
              break
            }

            try {
              const chunk = JSON.parse(data)
              const content = chunk.choices?.[0]?.delta?.content
              if (content) {
                assistantContent += content
                // Update the last message (assistant) with new content
                setConversationMessages(prev => {
                  const updated = [...prev]
                  updated[updated.length - 1] = {
                    ...updated[updated.length - 1],
                    content: assistantContent
                  }
                  return updated
                })
              }
            } catch (e) {
              console.error('Error parsing chunk:', e)
            }
          }
        }
      }
    } catch (error: unknown) {
      const err = error as Error
      if (err.name === 'AbortError') {
        console.log('Conversation stream aborted')
      } else {
        console.error('Conversation error:', error)
        // Add error message to conversation
        const errorMessage: ChatMessage = {
          role: 'assistant',
          content: `Error: ${err.message || 'Unknown error occurred'}`,
          timestamp: new Date().toISOString()
        }
        setConversationMessages(prev => [...prev, errorMessage])
      }
    } finally {
      setIsConversationLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      <EmailHeader
        selectedModel={selectedModel}
        models={models}
        isLoading={isLoading}
        onModelChange={handleModelChange}
        onRefresh={handleRefresh}
        selectedCount={selectedEmails.size}
      />

      <div className="flex-1 overflow-hidden flex">
        {/* Folder tree sidebar */}
        {showFolderTree && (
          <div className="w-64 border-r bg-gray-50 overflow-y-auto">
            <div className="p-4 border-b bg-white flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-700">Folders</h2>
              <button
                onClick={() => setShowFolderTree(false)}
                className="text-gray-400 hover:text-gray-600"
                title="Hide folders"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
                </svg>
              </button>
            </div>
            <FolderTree
              folders={folders}
              selectedFolderId={selectedFolderId}
              onFolderSelect={setSelectedFolderId}
              isLoading={isFoldersLoading}
            />
          </div>
        )}

        {/* Email list */}
        <div className="flex-1 overflow-hidden">
          <div className="h-full flex flex-col">
            {/* Show folders button when hidden */}
            {!showFolderTree && (
              <div className="px-4 py-2 border-b">
                <button
                  onClick={() => setShowFolderTree(true)}
                  className="text-sm text-gray-600 hover:text-gray-900 flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                  Show folders
                </button>
              </div>
            )}

            {/* Action buttons for bulk operations */}
            <EmailActionButtons
              selectedCount={selectedEmails.size}
              onArchive={() => handleArchive()}
              onDelete={() => handleDelete()}
              disabled={isLoading || selectedEmails.size === 0}
            />

            {/* Email list */}
            <EmailList
              emails={emails}
              selectedEmails={selectedEmails}
              isLoading={isLoading}
              onSelectEmail={handleSelectEmail}
              onSelectAll={handleSelectAll}
              onViewEmail={handleViewEmail}
              onLoadMore={handleLoadMore}
              hasMore={!!nextPageToken}
            />
          </div>
        </div>
      </div>

      {/* Email detail modal */}
      {selectedEmail && showDetailModal && (
        <EmailDetailModal
          email={selectedEmail}
          isOpen={showDetailModal}
          onClose={() => {
            setShowDetailModal(false)
            setCurrentSummary('')
            setCurrentDraft('')
            setConversationMessages([])
          }}
          onArchive={() => handleArchive([selectedEmail.id])}
          onDelete={() => handleDelete([selectedEmail.id])}
          onSummarize={() => handleSummarize(selectedEmail)}
          onDraft={(type, context) => handleDraft(selectedEmail, type, context)}
          isSummarizing={isSummarizing}
          isDrafting={isDrafting}
          currentSummary={currentSummary}
          currentDraft={currentDraft}
          onStopGeneration={stopGeneration}
          hasModel={!!selectedModel}
          selectedModel={selectedModel}
          onSendConversationMessage={handleSendConversationMessage}
          conversationMessages={conversationMessages}
          isConversationLoading={isConversationLoading}
        />
      )}
    </div>
  )
}