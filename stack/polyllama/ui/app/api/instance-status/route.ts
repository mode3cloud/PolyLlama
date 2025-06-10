import { serverFetch } from '@/app/lib/serverFetch';
import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    const response = await serverFetch('http://router:11434/api/polyllama/instance-status', {
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Instance status request failed: ${response.statusText}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching instance status:', error);
    return NextResponse.json(
      { error: 'Failed to fetch instance status' },
      { status: 500 }
    );
  }
}