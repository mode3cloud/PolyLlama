'use client'

import { useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { createMarkdownComponents } from '../lib/markdownComponents'

interface LLMOutputProps {
  content: string
  className?: string
  isStreaming?: boolean
  messageIndex?: number
  timestamp?: string
}

export default function LLMOutput({
  content,
  className = '',
  isStreaming = false,
  messageIndex = 0,
  timestamp = new Date().toISOString()
}: LLMOutputProps) {
  const [copiedCode, setCopiedCode] = useState<{ [key: string]: boolean }>({})
  
  // Create markdown components with proper context
  const markdownComponents = useMemo(
    () => createMarkdownComponents({ 
      messageIndex, 
      timestamp,
      copiedCode,
      setCopiedCode
    }),
    [messageIndex, timestamp, copiedCode]
  )

  // Parse content for special blocks (think/thought/output)
  const parseContent = () => {
    // Ensure content is a string
    const contentStr = String(content || '')

    // Check if content contains think/thought/output blocks
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

    // Check for incomplete blocks at the end (only if streaming)
    const remainingContent = contentStr.slice(lastIndex)
    if (isStreaming) {
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

        // Add incomplete think/thought block
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

        // Add incomplete output block
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
    } else if (remainingContent) {
      // Not streaming, just add remaining content
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

  const renderContent = () => {
    const parts = parseContent()

    return parts.map((part, partIndex) => {
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
    })
  }

  return (
    <div className={`llm-output ${className}`}>
      {renderContent()}
      {isStreaming && (
        <span className="inline-block w-2 h-4 bg-gray-600 animate-pulse ml-1" />
      )}
    </div>
  )
}