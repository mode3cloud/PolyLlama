'use client'

import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ChatMessage } from '../types'

interface AssistantMessageProps {
  message: ChatMessage
  markdownComponents: any
  parseMessageContent: () => Array<{ type: 'content' | 'think' | 'output', text: string, incomplete?: boolean }>
}

export default function AssistantMessage({
  message,
  markdownComponents,
  parseMessageContent
}: AssistantMessageProps) {
  const [expandedTools, setExpandedTools] = useState<{ [key: string]: boolean }>({})

  // Render tool calls if present
  const renderToolCalls = () => {
    if (!message.tool_calls || message.tool_calls.length === 0) return null

    return (
      <div className="">
        <div className="p-3 bg-orange-50 border border-orange-200 rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-orange-700">🔧 Tool Calls</span>
              <span className="text-xs text-orange-600">({message.tool_calls.length} tool{message.tool_calls.length > 1 ? 's' : ''})</span>
            </div>
          </div>
          {message.tool_calls.map((toolCall, toolCallIndex) => (
            <div key={toolCall.id || toolCallIndex} className="mb-2 last:mb-0">
              <div className="flex items-center justify-between">
                <span className="text-xs bg-orange-200 px-2 py-1 rounded">{toolCall.function.name}</span>
                <button
                  onClick={() => {
                    const key = `${toolCall.id || toolCallIndex}`;
                    setExpandedTools({ ...expandedTools, [key]: !expandedTools[key] });
                  }}
                  className="text-xs text-orange-600 hover:text-orange-800 flex items-center gap-1"
                >
                  {expandedTools[`${toolCall.id || toolCallIndex}`] ? (
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
              {expandedTools[`${toolCall.id || toolCallIndex}`] && (
                <div className="mt-1 text-xs text-gray-600 font-mono bg-white p-2 rounded border border-gray-200 overflow-x-auto">
                  <pre>{(() => {
                    try {
                      return JSON.stringify(JSON.parse(toolCall.function.arguments), null, 2);
                    } catch {
                      return toolCall.function.arguments;
                    }
                  })()}</pre>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    )
  }

  // Render message content
  const renderContent = () => {
    const parts = parseMessageContent()

    return parts.map((part, partIndex) => {
      if (part.type === 'think') {
        return (
          <div key={partIndex} className="my- p-4 bg-purple-50 border border-purple-200 rounded-lg">
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

      if (part.type === 'output') {
        return (
          <div key={partIndex} className="my-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex items-center gap-2 mb-2 text-blue-700">
              <span className="text-sm font-semibold">📤 Output</span>
              {part.incomplete && (
                <span className="text-xs text-blue-600 animate-pulse">● Streaming...</span>
              )}
            </div>
            <div className="prose prose-sm max-w-none prose-gray [&>*]:text-gray-900">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={markdownComponents}
              >
                {part.text}
              </ReactMarkdown>
            </div>
          </div>
        )
      }

      return (
        <div key={partIndex} className="prose prose-sm max-w-none prose-gray [&>*]:text-gray-900 pb-2">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={markdownComponents}
          >
            {part.text}
          </ReactMarkdown>
        </div>
      )
    })
  }

  return (
    <>
      <div className="gap-y-4">
        {renderContent()}
        {renderToolCalls()}
      </div>
    </>
  )
}