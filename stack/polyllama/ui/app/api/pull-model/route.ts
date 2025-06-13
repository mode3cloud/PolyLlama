import { serverFetch } from '@/app/lib/serverFetch';
import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    console.log('Pull model request body:', JSON.stringify(body));

    const response = await serverFetch('http://router:11434/api/polyllama/pull-model', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      // Try to get error details from response
      let errorMessage = `Pull model request failed: ${response.statusText}`;
      try {
        const errorData = await response.json();
        if (errorData.error) {
          errorMessage = errorData.error;
        }
      } catch (e) {
        // If we can't parse the error response, use the default message
      }
      throw new Error(errorMessage);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error pulling model:', error);
    const errorMessage = error instanceof Error ? error.message : 'Failed to pull model';
    return NextResponse.json(
      { success: false, error: errorMessage },
      { status: 500 }
    );
  }
}