import { NextRequest, NextResponse } from 'next/server'
import { verifyAuth } from '../../auth-utils'
import { EmailMessage, ChatMessage } from '../../../types'

export async function POST(request: NextRequest) {
  // Verify authentication
  const auth = verifyAuth(request)
  if (!auth.valid) {
    return NextResponse.json(
      { error: 'Authentication required' },
      { status: 401 }
    )
  }

  try {
    const body = await request.json()
    const { 
      email, 
      model, 
      messages,
      message,
      sessionId,
      stream = true 
    } = body as {
      email: EmailMessage
      model: string
      messages: ChatMessage[]
      message: string
      sessionId: string
      stream?: boolean
    }

    if (!email || !model || !message || !sessionId) {
      return NextResponse.json(
        { error: 'Email, model, message, and sessionId are required' },
        { status: 400 }
      )
    }

    // Prepare the system prompt that includes email context
    const systemPrompt = `You are an AI assistant helping with email analysis and management. You have access to tools that can help you remember information, search data, and perform actions.

Original Email Context:
From: ${email.from.emailAddress.name || email.from.emailAddress.address}
To: ${email.toRecipients.map(r => r.emailAddress.name || r.emailAddress.address).join(', ')}
Subject: ${email.subject}
Date: ${new Date(email.receivedDateTime).toLocaleString()}

Email Body:
${email.body?.content || email.bodyPreview}

---

You can use available tools to:
- Remember important information from this email
- Search for related information
- Take actions in external systems
- Answer follow-up questions about this email

Be helpful and use tools when appropriate to provide comprehensive assistance.`

    // Build the conversation messages including the system prompt
    const conversationMessages = [
      { role: 'system', content: systemPrompt },
      ...messages,
      { role: 'user', content: message }
    ]

    // Prepare the request to LLM proxy with tool support
    const llmRequest = {
      model,
      messages: conversationMessages,
      stream,
      temperature: 0.7,
      session_id: sessionId
    }

    // Add API key if configured for Ollama models
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    
    if (process.env.POLYLLAMA_API_KEY && model.startsWith('ollama/')) {
      headers['Authorization'] = `Bearer ${process.env.POLYLLAMA_API_KEY}`
    }

    // Proxy to LLM proxy service with tool support
    const response = await fetch('http://llm-proxy:11435/api/chat/completions', {
      method: 'POST',
      headers,
      body: JSON.stringify(llmRequest),
    })

    if (!response.ok) {
      const error = await response.text()
      return NextResponse.json(
        { error: `LLM proxy error: ${error}` },
        { status: response.status }
      )
    }

    // Handle streaming response - pass through directly like chat route
    if (stream && response.body) {
      return new NextResponse(response.body, {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      })
    } else {
      // Handle non-streaming response
      const data = await response.json()
      return NextResponse.json(data)
    }
  } catch (error) {
    console.error('Error in email conversation:', error)
    return NextResponse.json(
      { error: 'Failed to process conversation' },
      { status: 500 }
    )
  }
}