import { serverFetch } from '@/app/lib/serverFetch';
import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const query = searchParams.get('q');

    if (!query) {
      return NextResponse.json(
        { success: false, error: 'Query parameter is required' },
        { status: 400 }
      );
    }

    const response = await serverFetch(`http://router:11434/api/polyllama/search-models?q=${encodeURIComponent(query)}`, {
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Search models request failed: ${response.statusText}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error searching models:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to search models' },
      { status: 500 }
    );
  }
}