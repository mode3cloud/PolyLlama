import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    const response = await fetch('http://localhost:11434/api/polyllama/sync-contexts', {
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Sync contexts request failed: ${response.statusText}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error syncing contexts:', error);
    return NextResponse.json(
      { error: 'Failed to sync contexts' },
      { status: 500 }
    );
  }
}