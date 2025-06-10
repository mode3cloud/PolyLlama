import { serverFetch } from '@/app/lib/serverFetch';
import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    const response = await serverFetch('http://router:11434/api/polyllama/store-context', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      throw new Error(`Store context request failed: ${response.statusText}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error storing context:', error);
    return NextResponse.json(
      { error: 'Failed to store context', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}