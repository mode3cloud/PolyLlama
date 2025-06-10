import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    // Call LiteLLM to get all available models (Ollama + external providers)
    const response = await fetch('http://llm-proxy:11435/api/models', {
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Models request failed: ${response.statusText}`);
    }

    const data = await response.json();
    
    // Transform LiteLLM response to match Ollama's tags format
    // LiteLLM returns models with structure: { models: [ { id: "provider/model", name: "model", provider: "provider" } ] }
    const models = data.models || [];
    
    return NextResponse.json({
      models: models.map((model: any) => ({
        name: model.id,  // Use the full id (e.g., "ollama/gemma3", "openai/gpt-4")
        model: model.id,
        modified_at: new Date().toISOString(),
        size: 0,
        digest: "",
        details: {
          format: model.provider === 'ollama' ? "gguf" : "api",
          family: model.provider,
          families: null,
          parameter_size: "",
          quantization_level: ""
        }
      }))
    });
  } catch (error) {
    console.error('Error fetching models:', error);
    return NextResponse.json(
      { error: 'Failed to fetch models' },
      { status: 500 }
    );
  }
}