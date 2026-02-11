import { NextRequest, NextResponse } from 'next/server'
import { verifyAuth } from '../../auth-utils'
import { saveEmailSummary } from '../../../lib/emailStorage'
import { EmailMessage } from '../../../types'

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
    const { email, model, stream = true } = body as {
      email: EmailMessage
      model: string
      stream?: boolean
    }

    if (!email || !model) {
      return NextResponse.json(
        { error: 'Email and model are required' },
        { status: 400 }
      )
    }

    // Prepare the prompt for summarization
    const systemPrompt = `You are an AI assistant that analyzes emails and provides clear, concise summaries. 
Extract and present key information in a readable format.`

    const userPrompt = `Please analyze this email and provide a comprehensive summary:

From: ${email.from.emailAddress.name || email.from.emailAddress.address}
To: ${email.toRecipients.map(r => r.emailAddress.name || r.emailAddress.address).join(', ')}
Subject: ${email.subject}
Date: ${new Date(email.receivedDateTime).toLocaleString()}

Body:
${email.body?.content || email.bodyPreview}

Please provide:
1. A brief summary (2-3 sentences)
2. Key topics discussed
3. Any people, organizations, or locations mentioned
4. Important facts or information
5. Any action items or tasks mentioned

Format your response as clear, readable text (not JSON).`

    // Prepare the request to LLM proxy
    const llmRequest = {
      model,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userPrompt }
      ],
      stream,
      temperature: 0.3
    }

    // Add API key if configured for Ollama models
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    
    if (process.env.POLYLLAMA_API_KEY && model.startsWith('ollama/')) {
      headers['api-key'] = process.env.POLYLLAMA_API_KEY
    }

    // Proxy to LLM proxy service
    const response = await fetch('http://router:11434/v1/chat/completions', {
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

    // Handle streaming response
    // Note: We use a TransformStream here to accumulate the full response for saving
    // This differs from the chat route which simply passes through the stream
    if (stream && response.body) {
      let fullContent = ''
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
                // Save the complete text summary
                if (fullContent.trim()) {
                  try {
                    // For now, save the full text as summary
                    // In a real implementation, you might want to parse the text
                    await saveEmailSummary(
                      email.id,
                      fullContent.trim(),
                      [], // keyTopics - would need text parsing
                      { people: [], organizations: [], locations: [] }, // entities
                      [], // extractedFacts
                      [], // actionItems
                      model
                    )
                  } catch (e) {
                    console.error('Error saving summary:', e)
                  }
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
        const summary = await saveEmailSummary(
          email.id,
          content.trim(),
          [], // keyTopics
          { people: [], organizations: [], locations: [] }, // entities
          [], // extractedFacts
          [], // actionItems
          model
        )
        
        return NextResponse.json({ summary, success: true })
      } else {
        return NextResponse.json(
          { error: 'No content in response' },
          { status: 500 }
        )
      }
    }
  } catch (error) {
    console.error('Error in email summarize:', error)
    return NextResponse.json(
      { error: 'Failed to summarize email' },
      { status: 500 }
    )
  }
}