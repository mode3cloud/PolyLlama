import json
import aiohttp
from typing import AsyncGenerator, Optional
from config import settings

class LLMProxyClient:
    """Client for LLM proxy (litellm) that supports multiple providers"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.llm_proxy_url
    
    async def stream(self, prompt: str, model: str = None) -> AsyncGenerator[str, None]:
        """Stream response from LLM"""
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": model or "ollama/llama3.1:latest",
                "messages": [{"role": "user", "content": prompt}],
                "stream": True
            }
            
            async with session.post(
                f"{self.base_url}/api/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"LLM proxy error: {response.status} - {text}")
                    
                async for line in response.content:
                    if line:
                        line_text = line.decode('utf-8').strip()
                        if line_text.startswith('data: '):
                            line_text = line_text[6:]
                        if line_text == '[DONE]':
                            break
                        try:
                            chunk = json.loads(line_text)
                            if content := chunk.get('choices', [{}])[0].get('delta', {}).get('content'):
                                yield content
                        except (json.JSONDecodeError, KeyError) as e:
                            continue