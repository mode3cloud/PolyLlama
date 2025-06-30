'use client'

import { useState, useEffect, useRef } from 'react'
import { EmailMessage, ChatMessage } from '../types'
import { sanitizeHtml } from '../lib/emailUtils'
import LLMOutput from './LLMOutput'

interface EmailDetailModalProps {
  email: EmailMessage
  isOpen: boolean
  onClose: () => void
  onArchive: () => void
  onDelete: () => void
  onSummarize: () => void
  onDraft: (type: 'reply' | 'replyAll' | 'forward', context?: string) => void
  isSummarizing: boolean
  isDrafting: boolean
  currentSummary: string
  currentDraft: string
  onStopGeneration: () => void
  hasModel: boolean
  selectedModel: string
  onSendConversationMessage: (message: string, messages: ChatMessage[]) => void
  conversationMessages: ChatMessage[]
  isConversationLoading: boolean
}

export default function EmailDetailModal({
  email,
  isOpen,
  onClose,
  onArchive,
  onDelete,
  onSummarize,
  onDraft,
  isSummarizing,
  isDrafting,
  currentSummary,
  currentDraft,
  onStopGeneration,
  hasModel,
  selectedModel,
  onSendConversationMessage,
  conversationMessages,
  isConversationLoading
}: EmailDetailModalProps) {
  const [activeTab, setActiveTab] = useState<'email' | 'summary' | 'draft'>('email')
  const [draftContext, setDraftContext] = useState('')
  const [draftType, setDraftType] = useState<'reply' | 'replyAll' | 'forward'>('reply')
  const [conversationInput, setConversationInput] = useState('')
  const modalRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (currentSummary) setActiveTab('summary')
    if (currentDraft) setActiveTab('draft')
  }, [currentSummary, currentDraft])

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [conversationMessages])

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    if (isOpen) {
      document.addEventListener('keydown', handleEscape)
      return () => document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen, onClose])

  if (!isOpen) return null

  const handleDraftSubmit = () => {
    onDraft(draftType, draftContext)
    setDraftContext('')
  }

  const handleSendConversationMessage = () => {
    if (!conversationInput.trim() || isConversationLoading) return
    
    onSendConversationMessage(conversationInput.trim(), conversationMessages)
    setConversationInput('')
  }

  const handleConversationKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendConversationMessage()
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div 
        ref={modalRef}
        className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] flex flex-col"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b flex items-center justify-between">
          <h2 className="text-xl font-semibold truncate flex-1 mr-4">
            {email.subject}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl"
          >
            ✕
          </button>
        </div>

        {/* Tabs */}
        <div className="border-b px-6">
          <div className="flex space-x-6">
            <button
              onClick={() => setActiveTab('email')}
              className={`py-2 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === 'email'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              Email
            </button>
            <button
              onClick={() => setActiveTab('summary')}
              className={`py-2 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === 'summary'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
              disabled={!currentSummary && !isSummarizing}
            >
              Summary {isSummarizing && '⏳'}
            </button>
            <button
              onClick={() => setActiveTab('draft')}
              className={`py-2 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === 'draft'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
              disabled={!currentDraft && !isDrafting}
            >
              Draft Reply {isDrafting && '⏳'}
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'email' && (
            <div>
              {/* Email metadata */}
              <div className="space-y-2 mb-6 text-sm">
                <div className="flex">
                  <span className="font-medium w-20">From:</span>
                  <span>{email.from.emailAddress.name || email.from.emailAddress.address}</span>
                </div>
                <div className="flex">
                  <span className="font-medium w-20">To:</span>
                  <span>
                    {email.toRecipients.map(r => r.emailAddress.name || r.emailAddress.address).join(', ')}
                  </span>
                </div>
                {email.ccRecipients && email.ccRecipients.length > 0 && (
                  <div className="flex">
                    <span className="font-medium w-20">Cc:</span>
                    <span>
                      {email.ccRecipients.map(r => r.emailAddress.name || r.emailAddress.address).join(', ')}
                    </span>
                  </div>
                )}
                <div className="flex">
                  <span className="font-medium w-20">Date:</span>
                  <span>{new Date(email.receivedDateTime).toLocaleString()}</span>
                </div>
              </div>

              {/* Email body */}
              {email.body?.contentType === 'html' ? (
                <div 
                  className="prose max-w-none"
                  dangerouslySetInnerHTML={{ 
                    __html: sanitizeHtml(email.body.content) 
                  }}
                />
              ) : (
                <div className="whitespace-pre-wrap">
                  {email.body?.content || email.bodyPreview}
                </div>
              )}
            </div>
          )}

          {activeTab === 'summary' && (
            <div className="flex flex-col h-full">
              {/* Messages area */}
              <div className="flex-1 overflow-y-auto mb-4 space-y-4">
                {/* Initial summary */}
                {currentSummary && (
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                    <div className="text-sm font-medium text-blue-700 mb-2">
                      📧 Email Summary
                    </div>
                    <LLMOutput 
                      content={currentSummary}
                      isStreaming={isSummarizing}
                      messageIndex={0}
                      timestamp={email.receivedDateTime}
                    />
                  </div>
                )}

                {/* Conversation messages */}
                {conversationMessages.map((message, index) => (
                  <div
                    key={`${message.timestamp}-${index}`}
                    className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[80%] rounded-lg p-3 ${
                        message.role === 'user'
                          ? 'bg-blue-500 text-white'
                          : message.role === 'tool'
                            ? 'bg-green-50 border border-green-200 text-gray-900'
                            : 'bg-white border border-gray-200 text-gray-900'
                      }`}
                    >
                      {message.role === 'assistant' ? (
                        <LLMOutput
                          content={message.content}
                          isStreaming={isConversationLoading && index === conversationMessages.length - 1}
                          messageIndex={index + 1}
                          timestamp={message.timestamp}
                        />
                      ) : (
                        <div className="whitespace-pre-wrap">
                          {message.content}
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {/* No summary generated state */}
                {!currentSummary && !isSummarizing && conversationMessages.length === 0 && (
                  <div className="text-center py-8 text-gray-500">
                    <p>No summary generated yet.</p>
                    <button
                      onClick={onSummarize}
                      disabled={!hasModel}
                      className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Generate Summary
                    </button>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>

              {/* Input area - only show if we have a summary or conversation */}
              {(currentSummary || conversationMessages.length > 0) && (
                <div className="border-t pt-4">
                  <div className="flex space-x-2">
                    <textarea
                      value={conversationInput}
                      onChange={(e) => setConversationInput(e.target.value)}
                      onKeyDown={handleConversationKeyPress}
                      placeholder="Ask follow-up questions, request actions, or tell me to remember something..."
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                      rows={2}
                      disabled={isConversationLoading}
                    />
                    <button
                      onClick={handleSendConversationMessage}
                      disabled={!conversationInput.trim() || isConversationLoading || !selectedModel}
                      className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                    >
                      {isConversationLoading ? (
                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      ) : (
                        'Send'
                      )}
                    </button>
                  </div>
                  <div className="text-xs text-gray-500 mt-2">
                    💡 I can help you remember information, search for related content, or take actions using available tools.
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'draft' && (
            <div>
              {!currentDraft && !isDrafting && (
                <div className="space-y-4 mb-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Reply Type
                    </label>
                    <select
                      value={draftType}
                      onChange={(e) => setDraftType(e.target.value as 'reply' | 'replyAll' | 'forward')}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="reply">Reply</option>
                      <option value="replyAll">Reply All</option>
                      <option value="forward">Forward</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Additional Context (optional)
                    </label>
                    <textarea
                      value={draftContext}
                      onChange={(e) => setDraftContext(e.target.value)}
                      placeholder="Add any specific points or context for the AI to consider..."
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      rows={3}
                    />
                  </div>
                  <button
                    onClick={handleDraftSubmit}
                    disabled={!hasModel || isDrafting}
                    className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Generate Draft
                  </button>
                </div>
              )}

              {currentDraft && (
                <div>
                  <div className="mb-4 p-4 bg-gray-50 rounded-lg">
                    <div className="text-sm font-medium text-gray-700 mb-2">
                      Generated {draftType === 'forward' ? 'Forward' : 'Reply'}:
                    </div>
                    <LLMOutput 
                      content={currentDraft}
                      isStreaming={isDrafting}
                      messageIndex={1}
                      timestamp={email.receivedDateTime}
                    />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="px-6 py-4 border-t flex items-center justify-between">
          <div className="flex space-x-2">
            <button
              onClick={onArchive}
              className="px-4 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
            >
              📥 Archive
            </button>
            <button
              onClick={onDelete}
              className="px-4 py-2 text-sm bg-red-100 hover:bg-red-200 text-red-700 rounded-md transition-colors"
            >
              🗑️ Delete
            </button>
          </div>

          <div className="flex space-x-2">
            {(isSummarizing || isDrafting) && (
              <button
                onClick={onStopGeneration}
                className="px-4 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
              >
                Stop
              </button>
            )}
            {!isSummarizing && !currentSummary && activeTab === 'email' && (
              <button
                onClick={onSummarize}
                disabled={!hasModel}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                🤖 Summarize
              </button>
            )}
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm bg-gray-200 hover:bg-gray-300 rounded-md transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}