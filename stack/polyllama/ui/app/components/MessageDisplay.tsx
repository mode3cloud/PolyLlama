'use client'

import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ChatMessage } from '../types'

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

  const extractText = (node: any): string => {
    if (typeof node === 'string') return node
    if (!node) return ''
    if (node.props?.children) {
      if (Array.isArray(node.props.children)) {
        return node.props.children.map(extractText).join('')
      }
      return extractText(node.props.children)
    }
    return ''
  }

  const handleCodeCopy = (key: string, children: any) => {
    const codeText = extractText(children)
    navigator.clipboard.writeText(codeText)
    setCopiedCode({ ...copiedCode, [key]: true })
    setTimeout(() => setCopiedCode({ ...copiedCode, [key]: false }), 2000)
  }

  const markdownComponents = {
    pre: ({ children }: any) => {
      const key = `pre-${index}-${Date.now()}`
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
    code: ({ className, children, ...props }: any) => {
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
    a: ({ href, children }: any) => (
      <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 underline">
        {children}
      </a>
    ),
    ul: ({ children }: any) => (
      <ul className="list-disc list-inside space-y-1 my-2">{children}</ul>
    ),
    ol: ({ children }: any) => (
      <ol className="list-decimal list-inside space-y-1 my-2">{children}</ol>
    ),
    blockquote: ({ children }: any) => (
      <blockquote className="border-l-4 border-gray-300 pl-4 italic my-2 text-gray-700">{children}</blockquote>
    ),
    h1: ({ children }: any) => (
      <h1 className="text-2xl font-bold mt-4 mb-2">{children}</h1>
    ),
    h2: ({ children }: any) => (
      <h2 className="text-xl font-bold mt-3 mb-2">{children}</h2>
    ),
    h3: ({ children }: any) => (
      <h3 className="text-lg font-bold mt-2 mb-1">{children}</h3>
    ),
    p: ({ children }: any) => (
      <p className="my-2">{children}</p>
    ),
    table: ({ children }: any) => (
      <div className="overflow-x-auto my-2">
        <table className="min-w-full border-collapse border border-gray-300">
          {children}
        </table>
      </div>
    ),
    th: ({ children }: any) => (
      <th className="border border-gray-300 px-4 py-2 bg-gray-100 font-semibold text-left">
        {children}
      </th>
    ),
    td: ({ children }: any) => (
      <td className="border border-gray-300 px-4 py-2">
        {children}
      </td>
    ),
  }

  const parseMessageContent = () => {
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
    while ((match = completeThinkRegex.exec(message.content)) !== null) {
      allMatches.push({
        type: 'think',
        index: match.index,
        length: match[0].length,
        text: match[2].trim()
      })
    }

    // Find all output blocks
    completeOutputRegex.lastIndex = 0
    while ((match = completeOutputRegex.exec(message.content)) !== null) {
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
          text: message.content.slice(lastIndex, matchItem.index)
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
    const remainingContent = message.content.slice(lastIndex)
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
        text: message.content
      })
    }

    return parts
  }

  return (
    <div className={`group flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} mb-6`}>
      <div className="relative max-w-[80%]">
        <div
          className={`rounded-lg p-4 ${message.role === 'user'
            ? 'bg-blue-500 text-white'
            : 'bg-white border border-gray-200 text-gray-900'
            }`}
        >
          <div className="flex-1">
            {message.role === 'user' ? (
              <div className="whitespace-pre-wrap">{message.content}</div>
            ) : (
              <div>
                {parseMessageContent().map((part, partIndex) => {
                  if (part.type === 'think') {
                    return (
                      <div key={partIndex} className="my-4 p-4 bg-purple-50 border border-purple-200 rounded-lg">
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
                    <div key={partIndex} className="prose prose-sm max-w-none prose-gray [&>*]:text-gray-900">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={markdownComponents}
                      >
                        {part.text}
                      </ReactMarkdown>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
        {/* Action buttons positioned below the message box */}
        <div className={`absolute -bottom-6 ${message.role === 'user' ? 'left-0' : 'right-0'} flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity`}>
          {/* Copy button for assistant messages */}
          {message.role === 'assistant' && (
            <button
              onClick={() => onCopy(message.content, index)}
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

          {/* Resend button for user messages */}
          {message.role === 'user' && (
            <button
              onClick={() => onResend(index)}
              className="group/btn flex items-center justify-center w-6 h-6 rounded bg-gray-700 hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              title="Resend message"
              disabled={isLoading}
            >
              <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          )}

          {/* Delete button for all messages */}
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