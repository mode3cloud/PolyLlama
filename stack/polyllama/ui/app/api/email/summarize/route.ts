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
    const systemPrompt = `You are an AI assistant that analyzes emails and provides structured summaries. 
Extract key information including:
- A concise summary (2-3 sentences)
- Key topics discussed
- People, organizations, and locations mentioned
- Important facts
- Action items or tasks

Respond in JSON format with the following structure:
{
  "summary": "Brief summary here",
  "keyTopics": ["topic1", "topic2"],
  "entities": {
    "people": ["name1", "name2"],
    "organizations": ["org1", "org2"],
    "locations": ["location1", "location2"]
  },
  "extractedFacts": ["fact1", "fact2"],
  "actionItems": ["action1", "action2"]
}`

    const userPrompt = `Please analyze this email:

From: ${email.from.emailAddress.name || email.from.emailAddress.address}
To: ${email.toRecipients.map(r => r.emailAddress.name || r.emailAddress.address).join(', ')}
Subject: ${email.subject}
Date: ${new Date(email.receivedDateTime).toLocaleString()}

Body:
${email.body?.content || email.bodyPreview}`

    // Prepare the request to LLM proxy
    const llmRequest = {
      model,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userPrompt }
      ],
      stream,
      temperature: 0.3,
      response_format: { type: 'json_object' }
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

    // Handle streaming response
    // Note: We use a TransformStream here to accumulate the full response for saving
    // This differs from the chat route which simply passes through the stream
    if (stream && response.body) {
      let fullContent = ''
      const encoder = new TextEncoder()
      const decoder = new TextDecoder()

      // Create a TransformStream to handle the streaming
      const stream = new TransformStream({
        async transform(chunk, controller) {
          const text = decoder.decode(chunk, { stream: true })
          const lines = text.split('\n')
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const jsonStr = line.slice(6)
              if (jsonStr === '[DONE]') {
                // Parse the complete response and save summary
                try {
                  const summaryData = JSON.parse(fullContent)
                  await saveEmailSummary(
                    email.id,
                    summaryData.summary,
                    summaryData.keyTopics,
                    summaryData.entities,
                    summaryData.extractedFacts,
                    summaryData.actionItems,
                    model
                  )
                } catch (e) {
                  console.error('Error parsing summary:', e)
                }
                controller.enqueue(encoder.encode('data: [DONE]\n\n'))
                return
              }
              
              try {
                const data = JSON.parse(jsonStr)
                if (data.choices?.[0]?.delta?.content) {
                  fullContent += data.choices[0].delta.content
                }
                controller.enqueue(chunk)
              } catch (e) {
                // Pass through non-JSON lines
                controller.enqueue(chunk)
              }
            } else {
              controller.enqueue(chunk)
            }
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
        try {
          const summaryData = JSON.parse(content)
          const summary = await saveEmailSummary(
            email.id,
            summaryData.summary,
            summaryData.keyTopics,
            summaryData.entities,
            summaryData.extractedFacts,
            summaryData.actionItems,
            model
          )
          
          return NextResponse.json({ summary, success: true })
        } catch (e) {
          return NextResponse.json(
            { error: 'Failed to parse summary response' },
            { status: 500 }
          )
        }
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