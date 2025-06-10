import { serverFetch } from '@/app/lib/serverFetch';
import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    const response = await serverFetch('http://router:11434/api/polyllama/gpu-metrics', {
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`GPU metrics request failed: ${response.statusText}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching GPU metrics:', error);
    return NextResponse.json(
      { error: 'Failed to fetch GPU metrics' },
      { status: 500 }
    );
  }
}