import { serverFetch } from '@/app/lib/serverFetch';
import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    // Call the Ollama API directly to get only Ollama models
    const response = await serverFetch('http://router:11434/api/tags', {
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Models request failed: ${response.statusText}`);
    }

    const data = await response.json();
    
    // Return the models as-is from Ollama (without provider prefix)
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching Ollama models:', error);
    return NextResponse.json(
      { error: 'Failed to fetch Ollama models' },
      { status: 500 }
    );
  }
}