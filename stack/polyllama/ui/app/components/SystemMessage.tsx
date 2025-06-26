'use client'

import { ChatMessage } from '../types'

interface SystemMessageProps {
  message: ChatMessage
}

export default function SystemMessage({ message }: SystemMessageProps) {
  return (
    <>
      <div>
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm font-semibold text-gray-600">⚙️ System</span>
          {message.timestamp && (
            <span className="text-xs text-gray-500">{new Date(message.timestamp).toLocaleTimeString()}</span>
          )}
        </div>
        <div className="text-sm text-gray-700 whitespace-pre-wrap font-mono">
          {String(message.content || '')}
        </div>
      </div>
    </>
  )
}