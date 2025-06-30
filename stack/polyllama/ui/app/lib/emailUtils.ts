import { fetchWithAuth } from './fetchWithAuth'
import { EmailMessage } from '../types'
import { EmailSummary, EmailDraft } from '../types'

interface StreamEmailOptions {
  onChunk: (content: string) => void
  onError: (error: string) => void
  onDone: () => void
  onSummary?: (summary: EmailSummary) => void
  onDraft?: (draft: EmailDraft) => void
  signal?: AbortSignal
}

export async function streamEmailSummarize(
  email: EmailMessage,
  model: string,
  options: StreamEmailOptions
): Promise<void> {
  try {
    const response = await fetchWithAuth('/ui/api/email/summarize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, model, stream: true }),
      signal: options.signal,
    })

    if (!response.ok) {
      const error = await response.text()
      options.onError(error)
      return
    }

    const reader = response.body?.getReader()
    if (!reader) {
      options.onError('No response body')
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6).trim()
          if (data === '[DONE]') {
            options.onDone()
            return
          }

          try {
            // Handle [DONE] signal
            if (data === '[DONE]') {
              return
            }
            
            const json = JSON.parse(data)
            
            // Handle OpenAI format
            if (json.choices?.[0]?.delta?.content) {
              options.onChunk(json.choices[0].delta.content)
            }
            
            // Check if summary was saved (custom field)
            if (json.summary_id && options.onSummary) {
              // Fetch the saved summary
              const summaryResponse = await fetchWithAuth(
                `/ui/api/email/sessions?emailId=${email.id}`
              )
              if (summaryResponse.ok) {
                const { session } = await summaryResponse.json()
                const latestSummary = session?.summaries[session.summaries.length - 1]
                if (latestSummary) {
                  options.onSummary(latestSummary)
                }
              }
            }
          } catch (e) {
            console.error('Error parsing SSE data:', e, 'Raw data:', data)
          }
        }
      }
    }
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      console.log('Stream aborted')
    } else {
      options.onError(error instanceof Error ? error.message : 'Unknown error')
    }
  }
}

export async function streamEmailDraft(
  email: EmailMessage,
  model: string,
  replyType: 'reply' | 'replyAll' | 'forward',
  context: string | undefined,
  options: StreamEmailOptions
): Promise<void> {
  try {
    const response = await fetchWithAuth('/ui/api/email/draft', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, model, replyType, context, stream: true }),
      signal: options.signal,
    })

    if (!response.ok) {
      const error = await response.text()
      options.onError(error)
      return
    }

    const reader = response.body?.getReader()
    if (!reader) {
      options.onError('No response body')
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6).trim()
          if (data === '[DONE]') {
            options.onDone()
            return
          }

          try {
            // Handle [DONE] signal
            if (data === '[DONE]') {
              return
            }
            
            const json = JSON.parse(data)
            
            // Handle OpenAI format
            if (json.choices?.[0]?.delta?.content) {
              options.onChunk(json.choices[0].delta.content)
            }
            
            // Check if draft was saved (custom field)
            if (json.draft_id && options.onDraft) {
              // Fetch the saved draft
              const draftResponse = await fetchWithAuth(
                `/ui/api/email/sessions?emailId=${email.id}`
              )
              if (draftResponse.ok) {
                const { session } = await draftResponse.json()
                const latestDraft = session?.drafts[session.drafts.length - 1]
                if (latestDraft) {
                  options.onDraft(latestDraft)
                }
              }
            }
          } catch (e) {
            console.error('Error parsing SSE data:', e, 'Raw data:', data)
          }
        }
      }
    }
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      console.log('Stream aborted')
    } else {
      options.onError(error instanceof Error ? error.message : 'Unknown error')
    }
  }
}

// Helper to format email date
export function formatEmailDate(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffHours = diffMs / (1000 * 60 * 60)
  const diffDays = diffMs / (1000 * 60 * 60 * 24)

  if (diffHours < 1) {
    const diffMinutes = Math.floor(diffMs / (1000 * 60))
    return `${diffMinutes}m ago`
  } else if (diffHours < 24) {
    return `${Math.floor(diffHours)}h ago`
  } else if (diffDays < 7) {
    return `${Math.floor(diffDays)}d ago`
  } else {
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric',
      year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
    })
  }
}

// Helper to sanitize HTML content
export function sanitizeHtml(html: string): string {
  // This is a basic implementation. In production, use DOMPurify
  return html
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
    .replace(/<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>/gi, '')
    .replace(/on\w+\s*=\s*["'][^"']*["']/gi, '')
    .replace(/javascript:/gi, '')
}