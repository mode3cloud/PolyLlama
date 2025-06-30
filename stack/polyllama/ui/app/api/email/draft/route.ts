import { NextRequest, NextResponse } from 'next/server'
import { verifyAuth } from '../../auth-utils'
import { saveEmailDraft } from '../../../lib/emailStorage'
import { EmailMessage, EmailDraft } from '../../../types'

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
    const { email, model, replyType = 'reply', stream = true, context } = body as {
      email: EmailMessage
      model: string
      replyType?: EmailDraft['replyType']
      stream?: boolean
      context?: string
    }

    if (!email || !model) {
      return NextResponse.json(
        { error: 'Email and model are required' },
        { status: 400 }
      )
    }

    // Prepare the prompt for draft generation
    const systemPrompt = `You are an AI assistant that helps draft professional email responses. 
Generate appropriate ${replyType} emails based on the original message content.
Consider the tone, context, and formality level of the original email.
Keep responses concise and professional.`

    let userPrompt = `Please draft a ${replyType} to this email:\n\n`
    userPrompt += `From: ${email.from.emailAddress.name || email.from.emailAddress.address}\n`
    userPrompt += `To: ${email.toRecipients.map(r => r.emailAddress.name || r.emailAddress.address).join(', ')}\n`
    userPrompt += `Subject: ${email.subject}\n`
    userPrompt += `Date: ${new Date(email.receivedDateTime).toLocaleString()}\n\n`
    userPrompt += `Body:\n${email.body?.content || email.bodyPreview}\n\n`
    
    if (context) {
      userPrompt += `Additional context for the response:\n${context}\n\n`
    }

    userPrompt += `Generate only the email body text for the ${replyType}. Do not include subject line or email headers.`

    // Prepare the request to LLM proxy
    const llmRequest = {
      model,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userPrompt }
      ],
      stream,
      temperature: 0.7
    }

    // Add API key if configured for Ollama models
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    
    if (process.env.POLYLLAMA_API_KEY && model.startsWith('ollama/')) {
      headers['Authorization'] = `Bearer ${process.env.POLYLLAMA_API_KEY}`
    }

    // Proxy to LLM proxy service
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

    // Generate appropriate subject based on reply type
    let draftSubject = email.subject
    if (replyType === 'reply' || replyType === 'replyAll') {
      if (!draftSubject.toLowerCase().startsWith('re:')) {
        draftSubject = `Re: ${draftSubject}`
      }
    } else if (replyType === 'forward') {
      if (!draftSubject.toLowerCase().startsWith('fwd:')) {
        draftSubject = `Fwd: ${draftSubject}`
      }
    }

    // Handle streaming response
    // Note: We use a TransformStream here to accumulate the full response for saving
    // This differs from the chat route which simply passes through the stream
    if (stream && response.body) {
      let fullContent = ''
      let savedDraftId: string | null = null
      const encoder = new TextEncoder()
      const decoder = new TextDecoder()

      // Create a TransformStream to handle the streaming
      let buffer = ''
      const stream = new TransformStream({
        async transform(chunk, controller) {
          // Decode the chunk and add to buffer
          buffer += decoder.decode(chunk, { stream: true })
          
          // Process complete lines
          const lines = buffer.split('\n')
          // Keep the last line in buffer if it's incomplete
          buffer = lines.pop() || ''
          
          for (const line of lines) {
            if (line.trim() === '') continue // Skip empty lines
            
            if (line.startsWith('data: ')) {
              const jsonStr = line.slice(6).trim()
              if (jsonStr === '[DONE]') {
                // Save the complete draft at the end
                if (!savedDraftId && fullContent) {
                  const draft = await saveEmailDraft(
                    email.id,
                    replyType,
                    draftSubject,
                    fullContent.trim(),
                    model
                  )
                  savedDraftId = draft.id
                  
                  // Send the draft ID before [DONE]
                  const draftIdChunk = {
                    choices: [{
                      delta: {},
                      finish_reason: null
                    }],
                    draft_id: savedDraftId
                  }
                  controller.enqueue(encoder.encode(`data: ${JSON.stringify(draftIdChunk)}\n\n`))
                }
                controller.enqueue(encoder.encode('data: [DONE]\n\n'))
                return
              }
              
              try {
                const data = JSON.parse(jsonStr)
                if (data.choices?.[0]?.delta?.content) {
                  fullContent += data.choices[0].delta.content
                }
                // Forward the complete line with newline
                controller.enqueue(encoder.encode(line + '\n'))
              } catch (e) {
                // Forward non-JSON lines as-is
                controller.enqueue(encoder.encode(line + '\n'))
              }
            } else {
              // Forward non-data lines as-is
              controller.enqueue(encoder.encode(line + '\n'))
            }
          }
        },
        flush(controller) {
          // Handle any remaining data in buffer
          if (buffer.trim()) {
            controller.enqueue(encoder.encode(buffer))
          }
        }
      })

      const transformedStream = response.body.pipeThrough(stream)

      return new NextResponse(transformedStream, {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      })
    } else {
      // Handle non-streaming response
      const data = await response.json()
      const content = data.choices?.[0]?.message?.content
      
      if (content) {
        const draft = await saveEmailDraft(
          email.id,
          replyType,
          draftSubject,
          content.trim(),
          model
        )
        
        return NextResponse.json({ draft, success: true })
      } else {
        return NextResponse.json(
          { error: 'No content in response' },
          { status: 500 }
        )
      }
    }
  } catch (error) {
    console.error('Error in email draft:', error)
    return NextResponse.json(
      { error: 'Failed to generate draft' },
      { status: 500 }
    )
  }
}