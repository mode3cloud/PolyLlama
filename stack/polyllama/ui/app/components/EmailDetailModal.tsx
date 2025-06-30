'use client'

import { useState, useEffect, useRef } from 'react'
import { EmailMessage } from '../types'
import { formatEmailDate, sanitizeHtml } from '../lib/emailUtils'

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
  hasModel
}: EmailDetailModalProps) {
  const [activeTab, setActiveTab] = useState<'email' | 'summary' | 'draft'>('email')
  const [draftContext, setDraftContext] = useState('')
  const [draftType, setDraftType] = useState<'reply' | 'replyAll' | 'forward'>('reply')
  const modalRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (currentSummary) setActiveTab('summary')
    if (currentDraft) setActiveTab('draft')
  }, [currentSummary, currentDraft])

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
            <div>
              {currentSummary ? (
                <div className="prose max-w-none">
                  <pre className="whitespace-pre-wrap font-sans">
                    {currentSummary}
                  </pre>
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <p>No summary generated yet.</p>
                  <button
                    onClick={onSummarize}
                    disabled={!hasModel || isSummarizing}
                    className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Generate Summary
                  </button>
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
                      onChange={(e) => setDraftType(e.target.value as any)}
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
                <div className="prose max-w-none">
                  <div className="mb-4 p-4 bg-gray-50 rounded-lg">
                    <div className="text-sm font-medium text-gray-700 mb-2">
                      Generated {draftType === 'forward' ? 'Forward' : 'Reply'}:
                    </div>
                    <pre className="whitespace-pre-wrap font-sans">
                      {currentDraft}
                    </pre>
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