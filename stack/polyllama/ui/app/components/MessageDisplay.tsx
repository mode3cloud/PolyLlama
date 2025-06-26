'use client'

import { useState } from 'react'
import { ChatMessage } from '../types'
import UserMessage from './UserMessage'
import ToolMessage from './ToolMessage'
import AssistantMessage from './AssistantMessage'
import SystemMessage from './SystemMessage'

interface MessageDisplayProps {
  message: ChatMessage
  index: number
  onCopy: (content: string, index: number) => void
  onDelete: (index: number) => void
  onResend: (index: number) => void
  copiedMessageId: number | null
  isLoading: boolean
}

export default function MessageDisplay({
  message,
  index,
  onCopy,
  onDelete,
  onResend,
  copiedMessageId,
  isLoading
}: MessageDisplayProps) {
  const [copiedCode, setCopiedCode] = useState<{ [key: string]: boolean }>({})

  const extractText = (node: React.ReactNode): string => {
    if (typeof node === 'string') return node
    if (!node) return ''
    if (typeof node === 'object' && 'props' in node) {
      const nodeWithProps = node as { props: { children?: React.ReactNode } }
      if (nodeWithProps.props?.children) {
        if (Array.isArray(nodeWithProps.props.children)) {
          return nodeWithProps.props.children.map(extractText).join('')
        }
        return extractText(nodeWithProps.props.children)
      }
    }
    return ''
  }

  const handleCodeCopy = (key: string, children: React.ReactNode) => {
    const codeText = extractText(children)
    navigator.clipboard.writeText(codeText)
    setCopiedCode({ ...copiedCode, [key]: true })
    setTimeout(() => setCopiedCode({ ...copiedCode, [key]: false }), 2000)
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const markdownComponents: any = {
    pre: ({ children }: { children: React.ReactNode }) => {
      const key = `pre-${index}-${message.timestamp}`
      const copied = copiedCode[key] || false

      return (
        <div className="relative group my-2">
          <button
            onClick={() => handleCodeCopy(key, children)}
            className="absolute top-2 right-2 flex items-center justify-center w-6 h-6 rounded bg-gray-800 hover:bg-gray-700 opacity-0 group-hover:opacity-100 transition-all"
            title="Copy code"
          >
            {copied ? (
              <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            )}
          </button>
          <pre className="bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto border border-gray-700">
            {children}
          </pre>
        </div>
      )
    },
    code: ({ className, children, ...props }: { className?: string; children: React.ReactNode }) => {
      const match = /language-(\w+)/.exec(className || '')
      const isInline = !match
      return isInline ? (
        <code className="bg-gray-100 text-gray-800 rounded px-1.5 py-0.5 text-sm font-mono" {...props}>
          {children}
        </code>
      ) : (
        <code className="text-gray-100 text-sm font-mono block" {...props}>
          {children}
        </code>
      )
    },
    a: ({ href, children }: { href?: string; children: React.ReactNode }) => (
      <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 underline">
        {children}
      </a>
    ),
    ul: ({ children }: { children: React.ReactNode }) => (
      <ul className="list-disc list-inside space-y-1 my-2">{children}</ul>
    ),
    ol: ({ children }: { children: React.ReactNode }) => (
      <ol className="list-decimal list-inside space-y-1 my-2">{children}</ol>
    ),
    blockquote: ({ children }: { children: React.ReactNode }) => (
      <blockquote className="border-l-4 border-gray-300 pl-4 italic my-2 text-gray-700">{children}</blockquote>
    ),
    h1: ({ children }: { children: React.ReactNode }) => (
      <h1 className="text-2xl font-bold mt-4 mb-2">{children}</h1>
    ),
    h2: ({ children }: { children: React.ReactNode }) => (
      <h2 className="text-xl font-bold mt-3 mb-2">{children}</h2>
    ),
    h3: ({ children }: { children: React.ReactNode }) => (
      <h3 className="text-lg font-bold mt-2 mb-1">{children}</h3>
    ),
    p: ({ children }: { children: React.ReactNode }) => (
      <p className="my-2">{children}</p>
    ),
    table: ({ children }: { children: React.ReactNode }) => (
      <div className="overflow-x-auto my-2">
        <table className="min-w-full border-collapse border border-gray-300">
          {children}
        </table>
      </div>
    ),
    th: ({ children }: { children: React.ReactNode }) => (
      <th className="border border-gray-300 px-4 py-2 bg-gray-100 font-semibold text-left">
        {children}
      </th>
    ),
    td: ({ children }: { children: React.ReactNode }) => (
      <td className="border border-gray-300 px-4 py-2">
        {children}
      </td>
    ),
  }

  const parseMessageContent = () => {
    // Ensure content is a string
    let contentStr = String(message.content || '')

    // If we have tool_calls, filter out the "Preparing to call tool" messages
    if (message.tool_calls && message.tool_calls.length > 0) {
      contentStr = contentStr.replace(/🔧 Preparing to call tool: \*\*[^*]+\*\*\.\.\.\n*/g, '').trim()
    }

    // Check if content contains think/thought/output blocks (complete or incomplete)
    const completeThinkRegex = /<(think|thought)>([\s\S]*?)<\/(think|thought)>/gi
    const incompleteThinkRegex = /<(think|thought)>([\s\S]*?)$/i
    const completeOutputRegex = /<(output)>([\s\S]*?)<\/(output)>/gi
    const incompleteOutputRegex = /<(output)>([\s\S]*?)$/i
    const parts: Array<{ type: 'content' | 'think' | 'output', text: string, incomplete?: boolean }> = []
    let lastIndex = 0
    let match

    // Process content to find all special blocks
    const allMatches: Array<{ type: 'think' | 'output', index: number, length: number, text: string }> = []

    // Find all think/thought blocks
    completeThinkRegex.lastIndex = 0
    while ((match = completeThinkRegex.exec(contentStr)) !== null) {
      allMatches.push({
        type: 'think',
        index: match.index,
        length: match[0].length,
        text: match[2].trim()
      })
    }

    // Find all output blocks
    completeOutputRegex.lastIndex = 0
    while ((match = completeOutputRegex.exec(contentStr)) !== null) {
      allMatches.push({
        type: 'output',
        index: match.index,
        length: match[0].length,
        text: match[2].trim()
      })
    }

    // Sort matches by index
    allMatches.sort((a, b) => a.index - b.index)

    // Build parts array
    for (const matchItem of allMatches) {
      // Add content before this block
      if (matchItem.index > lastIndex) {
        parts.push({
          type: 'content',
          text: contentStr.slice(lastIndex, matchItem.index)
        })
      }

      // Add the block
      parts.push({
        type: matchItem.type,
        text: matchItem.text
      })

      lastIndex = matchItem.index + matchItem.length
    }

    // Check for incomplete blocks at the end
    const remainingContent = contentStr.slice(lastIndex)
    const incompleteThinkMatch = incompleteThinkRegex.exec(remainingContent)
    const incompleteOutputMatch = incompleteOutputRegex.exec(remainingContent)

    if (incompleteThinkMatch) {
      // Add content before the incomplete think/thought block
      if (incompleteThinkMatch.index > 0) {
        parts.push({
          type: 'content',
          text: remainingContent.slice(0, incompleteThinkMatch.index)
        })
      }

      // Add incomplete think/thought block (being streamed)
      parts.push({
        type: 'think',
        text: incompleteThinkMatch[2].trim(),
        incomplete: true
      })
    } else if (incompleteOutputMatch) {
      // Add content before the incomplete output block
      if (incompleteOutputMatch.index > 0) {
        parts.push({
          type: 'content',
          text: remainingContent.slice(0, incompleteOutputMatch.index)
        })
      }

      // Add incomplete output block (being streamed)
      parts.push({
        type: 'output',
        text: incompleteOutputMatch[2].trim(),
        incomplete: true
      })
    } else if (remainingContent) {
      // No incomplete blocks, just regular content
      parts.push({
        type: 'content',
        text: remainingContent
      })
    }

    // If no parts found, treat entire content as regular
    if (parts.length === 0) {
      parts.push({
        type: 'content',
        text: contentStr
      })
    }

    return parts
  }

  const renderMessageContent = () => {
    if (message.role === 'tool') {
      return <ToolMessage message={message} />
    } else if (message.role === 'user') {
      return <UserMessage message={message} />
    } else if (message.role === 'system') {
      return <SystemMessage message={message} />
    } else {
      return (
        <AssistantMessage 
          message={message}
          markdownComponents={markdownComponents}
          parseMessageContent={parseMessageContent}
        />
      )
    }
  }

  // Check if assistant message has only tool calls and no content
  const hasOnlyToolCalls = () => {
    if (message.role !== 'assistant') return false
    const hasToolCalls = message.tool_calls && message.tool_calls.length > 0
    const hasContent = message.content && message.content.trim().length > 0
    return hasToolCalls && !hasContent
  }

  const isAssistantWithOnlyToolCalls = hasOnlyToolCalls()

  // Helper function to handle copy action based on message type
  const handleCopy = () => {
    if (message.role === 'assistant' && message.tool_calls && message.tool_calls.length > 0) {
      const toolCallsText = message.tool_calls
        .map(tc => `Tool: ${tc.function.name}\nArguments: ${tc.function.arguments}`)
        .join('\n\n')
      const fullText = message.content ? `${message.content}\n\n${toolCallsText}` : toolCallsText
      onCopy(fullText, index)
    } else {
      onCopy(message.content, index)
    }
  }

  return (
    <div className={`group flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} mb-6`}>
      <div className="relative max-w-[80%]">
        {isAssistantWithOnlyToolCalls ? (
          // For assistant messages with only tool calls, render without the outer box
          <>
            {renderMessageContent()}
          </>
        ) : (
          // For all other messages, render with the outer box
          <>
            <div
              className={`rounded-lg p-4 ${message.role === 'user'
                ? 'bg-blue-500 text-white'
                : message.role === 'tool'
                  ? 'bg-green-50 border border-green-200 text-gray-900'
                  : message.role === 'system'
                  ? 'bg-gray-100 border border-gray-300 text-gray-800 border-dashed'
                  : 'bg-white border border-gray-200 text-gray-900'
                }`}
            >
              <div className="flex-1">
                {renderMessageContent()}
              </div>
            </div>
          </>
        )}
        
        {/* Action buttons container - shared for all message types */}
        <div className="absolute -bottom-6 right-0 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity z-10">
          {/* Copy button - not shown for system messages */}
          {message.role !== 'system' && (
            <button
              onClick={handleCopy}
              className="group/btn flex items-center justify-center w-6 h-6 rounded bg-gray-700 hover:bg-gray-600 transition-colors"
              title="Copy message"
            >
              {copiedMessageId === index ? (
                <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              )}
            </button>
          )}
          
          {/* Resend button - only for user messages */}
          {message.role === 'user' && (
            <button
              onClick={() => onResend(index)}
              className="group/btn flex items-center justify-center w-6 h-6 rounded bg-gray-700 hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              title="Resend message"
              disabled={isLoading}
            >
              <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          )}
          
          {/* Delete button */}
          <button
            onClick={() => onDelete(index)}
            className="group/btn flex items-center justify-center w-6 h-6 rounded bg-gray-700 hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="Delete message"
            disabled={isLoading}
          >
            <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}