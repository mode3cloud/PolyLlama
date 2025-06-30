'use client'

import { EmailMessage } from '../types'
import { formatEmailDate } from '../lib/emailUtils'

interface EmailListProps {
  emails: EmailMessage[]
  selectedEmails: Set<string>
  isLoading: boolean
  onSelectEmail: (emailId: string) => void
  onSelectAll: () => void
  onViewEmail: (email: EmailMessage) => void
  onLoadMore: () => void
  hasMore: boolean
}

export default function EmailList({
  emails,
  selectedEmails,
  isLoading,
  onSelectEmail,
  onSelectAll,
  onViewEmail,
  onLoadMore,
  hasMore
}: EmailListProps) {
  const allSelected = emails.length > 0 && selectedEmails.size === emails.length

  return (
    <div className="flex-1 overflow-y-auto">
      {emails.length === 0 && !isLoading ? (
        <div className="flex items-center justify-center h-full text-gray-500">
          <p>No emails found</p>
        </div>
      ) : (
        <div className="divide-y divide-gray-200">
          {/* Select all header */}
          {emails.length > 0 && (
            <div className="px-4 py-2 bg-gray-50 border-b sticky top-0 z-10">
              <label className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={onSelectAll}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-600">
                  Select all
                </span>
              </label>
            </div>
          )}

          {/* Email items */}
          {emails.map((email) => (
            <div
              key={email.id}
              className={`flex items-start p-4 hover:bg-gray-50 cursor-pointer transition-colors ${
                !email.isRead ? 'bg-blue-50' : ''
              }`}
            >
              <input
                type="checkbox"
                checked={selectedEmails.has(email.id)}
                onChange={(e) => {
                  e.stopPropagation()
                  onSelectEmail(email.id)
                }}
                onClick={(e) => e.stopPropagation()}
                className="mt-1 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              
              <div 
                className="flex-1 ml-3 min-w-0"
                onClick={() => onViewEmail(email)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-2">
                      <span className={`text-sm ${!email.isRead ? 'font-semibold' : ''}`}>
                        {email.from.emailAddress.name || email.from.emailAddress.address}
                      </span>
                      {email.hasAttachments && (
                        <span className="text-gray-400" title="Has attachments">📎</span>
                      )}
                      {email.importance === 'high' && (
                        <span className="text-red-500" title="High importance">❗</span>
                      )}
                    </div>
                    <div className={`text-sm mt-1 ${!email.isRead ? 'font-medium' : 'text-gray-900'}`}>
                      {email.subject}
                    </div>
                    <div className="text-sm text-gray-600 mt-1 truncate">
                      {email.bodyPreview}
                    </div>
                  </div>
                  <div className="ml-4 flex-shrink-0 text-xs text-gray-500">
                    {formatEmailDate(email.receivedDateTime)}
                  </div>
                </div>
              </div>
            </div>
          ))}

          {/* Load more button */}
          {hasMore && (
            <div className="p-4 text-center">
              <button
                onClick={onLoadMore}
                disabled={isLoading}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? 'Loading...' : 'Load More'}
              </button>
            </div>
          )}
        </div>
      )}

      {isLoading && emails.length === 0 && (
        <div className="flex items-center justify-center h-full">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading emails...</p>
          </div>
        </div>
      )}
    </div>
  )
}