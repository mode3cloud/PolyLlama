import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    const response = await fetch('http://localhost:11434/api/polyllama/instance-count', {
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Instance count request failed: ${response.statusText}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching instance count:', error);
    return NextResponse.json(
      { error: 'Failed to fetch instance count' },
      { status: 500 }
    );
  }
}