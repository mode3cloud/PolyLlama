'use client'

import { useState } from 'react'
import { ChatMessage } from '../types'

interface ToolMessageProps {
  message: ChatMessage
}

export default function ToolMessage({ message }: ToolMessageProps) {
  const [expandedToolResults, setExpandedToolResults] = useState<boolean>(false)

  return (
    <>
      <div>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-green-700">✅ Tool Result</span>
            {message.tool_name && (
              <span className="text-xs bg-green-200 px-2 py-1 rounded">{message.tool_name}</span>
            )}
          </div>
          <button
            onClick={() => setExpandedToolResults(!expandedToolResults)}
            className="text-xs text-green-600 hover:text-green-800 flex items-center gap-1"
          >
            {expandedToolResults ? (
              <>
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
                Collapse
              </>
            ) : (
              <>
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                Expand
              </>
            )}
          </button>
        </div>
        {expandedToolResults && (
          <div className="text-xs text-gray-600 font-mono bg-white p-2 rounded border border-gray-200 overflow-x-auto">
            <pre>{(() => {
              // Handle different types of content
              const content = message.content;
              if (typeof content === 'string') {
                // Try to parse and format JSON
                try {
                  const parsed = JSON.parse(content);
                  return JSON.stringify(parsed, null, 2);
                } catch {
                  return content;
                }
              } else if (content && typeof content === 'object') {
                return JSON.stringify(content, null, 2);
              } else {
                return String(content || '');
              }
            })()}</pre>
          </div>
        )}
      </div>
    </>
  )
}