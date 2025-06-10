import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    const response = await fetch('http://localhost:11434/api/polyllama/model-mappings', {
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Model mappings request failed: ${response.statusText}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching model mappings:', error);
    return NextResponse.json(
      { error: 'Failed to fetch model mappings' },
      { status: 500 }
    );
  }
}