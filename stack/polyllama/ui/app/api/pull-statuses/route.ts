import { serverFetch } from '@/app/lib/serverFetch';
import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    const response = await serverFetch('http://router:11434/api/polyllama/pull-statuses', {
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Pull statuses request failed: ${response.statusText}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching pull statuses:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to fetch pull statuses', pull_statuses: [] },
      { status: 500 }
    );
  }
}