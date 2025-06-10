import { serverFetch } from '@/app/lib/serverFetch';
import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const targetInstance = request.headers.get('X-Target-Instance');

    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };

    if (targetInstance) {
      headers['X-Target-Instance'] = targetInstance;
    }

    const response = await serverFetch('http://router:11434/api/generate', {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      throw new Error(`Generate request failed: ${response.statusText}`);
    }

    // For streaming responses
    if (body.stream) {
      const stream = response.body;
      if (!stream) {
        throw new Error('No response stream available');
      }

      return new NextResponse(stream, {
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      });
    }

    // For non-streaming responses
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error in generate API:', error);
    return NextResponse.json(
      { error: 'Failed to generate', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}