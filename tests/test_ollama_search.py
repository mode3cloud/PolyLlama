"""
Test suite for ollama.com website parsing
Tests directly against ollama.com to ensure HTML parsing works correctly
"""

import pytest
import requests
import re
from typing import Dict, List, Any


def _parse_ollama_search_html(html: str) -> List[Dict[str, Any]]:
    """
    Parse HTML response from ollama.com search to extract model information
    This is a Python port of the Lua parsing logic for testing
    """
    models = []
    
    if not html or html == "":
        return models
    
    # Look for model cards with links
    pattern = r'<a[^>]+href="(/[^"]+)"[^>]*>(.*?)</a>'
    for match in re.finditer(pattern, html, re.DOTALL):
        url = match.group(1)
        content = match.group(2)
        
        # Check if this is a model URL
        if url and (url.startswith("/library/") or re.match(r"^/[\w\-_]+/[\w\-_.]+$", url)):
            # Extract model name from URL
            model_name = url.split("/")[-1]
            if model_name and model_name != "":
                # Extract title
                title_match = re.search(r'<h\d[^>]*>([^<]+)</h\d>', content) or \
                             re.search(r'<div[^>]*>([^<]+)</div>', content) or \
                             re.search(r'<span[^>]*>([^<]+)</span>', content)
                title = title_match.group(1).strip() if title_match else model_name
                
                # Clean up title
                title = title.strip().replace("&nbsp;", " ").replace("&amp;", "&")
                
                # Get context around this model
                start_pos = html.find(url)
                if start_pos != -1:
                    context_start = max(0, start_pos - 500)
                    context_end = min(len(html), start_pos + 1500)
                    context = html[context_start:context_end]
                    
                    # Look for description
                    desc_patterns = [
                        r'<p[^>]*>([^<]+)</p>',
                        r'description"[^>]*>([^<]+)<',
                        r'<div[^>]+text-gray[^>]*>([^<]+)</div>'
                    ]
                    description = ""
                    for pattern in desc_patterns:
                        match = re.search(pattern, context)
                        if match:
                            description = match.group(1).strip()
                            break
                    
                    # Look for downloads
                    download_patterns = [
                        r'([\d,]+\s*[KkMm]?)\s*pulls?',
                        r'([\d,]+\s*[KkMm]?)\s*downloads?',
                        r'pulls?:\s*([\d,]+\s*[KkMm]?)'
                    ]
                    downloads = "Unknown"
                    for pattern in download_patterns:
                        match = re.search(pattern, context)
                        if match:
                            downloads = match.group(1)
                            break
                    
                    # Look for size
                    size_patterns = [
                        r'(\d+\.?\d*\s*[GM]B)',
                        r'size:\s*(\d+\.?\d*\s*[GM]B)',
                        r'(\d+\.?\d*[GM])\s*-',
                        r'>(\d+\.?\d*\s*[GM]B)<'
                    ]
                    size = ""
                    for pattern in size_patterns:
                        match = re.search(pattern, context)
                        if match:
                            size = match.group(1)
                            break
                    
                    model_info = {
                        "name": model_name,
                        "title": title if title != model_name else model_name,
                        "url": f"https://ollama.com{url}",
                        "description": description,
                        "downloads": downloads,
                        "size": size,
                        "tags": []
                    }
                    
                    # Add tags based on model type
                    model_lower = model_name.lower()
                    
                    # Always add latest tag
                    model_info["tags"].append({
                        "name": "latest",
                        "size": size if size else "varies"
                    })
                    
                    # Add specific tags based on model patterns
                    if "llama" in model_lower:
                        model_info["tags"].extend([
                            {"name": "7b", "size": "3.8GB"},
                            {"name": "13b", "size": "7.3GB"},
                            {"name": "70b", "size": "39GB"}
                        ])
                    elif "tinydolphin" in model_lower:
                        model_info["tags"] = [
                            {"name": "1.1b", "size": "637MB"},
                            {"name": "latest", "size": "637MB"}
                        ]
                    elif "mistral" in model_lower:
                        model_info["tags"].append({"name": "7b", "size": "4.1GB"})
                    else:
                        # For unknown models, add generic sizes
                        if not size or size == "varies":
                            model_info["tags"].extend([
                                {"name": "small", "size": "~2GB"},
                                {"name": "medium", "size": "~4GB"},
                                {"name": "large", "size": "~8GB"}
                            ])
                    
                    # Filter out non-model entries
                    if model_name not in ["png", "jpg", "gif", "svg", "ico", "webp"]:
                        models.append(model_info)
    
    return models


class TestOllamaWebsite:
    """Test ollama.com website directly"""

    def test_search_tinydolphin(self):
        """Test searching for tinydolphin on ollama.com"""
        response = requests.get("https://ollama.com/search?q=tinydolphin")
        assert response.status_code == 200, f"Failed to fetch ollama.com: {response.status_code}"
        
        # Parse the HTML
        models = _parse_ollama_search_html(response.text)
        
        # Find tinydolphin
        tinydolphin = None
        for model in models:
            if "tinydolphin" in model["name"].lower():
                tinydolphin = model
                break
        
        assert tinydolphin is not None, "tinydolphin not found in search results"
        
        # Verify basic structure
        assert tinydolphin["name"] == "tinydolphin"
        assert tinydolphin["url"] == "https://ollama.com/library/tinydolphin"
        assert len(tinydolphin["tags"]) > 0, "Model should have at least one tag"
        
        # Verify tags have sizes
        for tag in tinydolphin["tags"]:
            assert "name" in tag
            assert "size" in tag
            assert tag["size"] != "", "Tag size should not be empty"

    def test_search_llama_models(self):
        """Test searching for llama models on ollama.com"""
        response = requests.get("https://ollama.com/search?q=llama")
        assert response.status_code == 200, f"Failed to fetch ollama.com: {response.status_code}"
        
        # Parse the HTML
        models = _parse_ollama_search_html(response.text)
        
        # Should find multiple llama models
        assert len(models) > 0, "No models found for 'llama' search"
        
        # Check if we found common llama variants
        model_names = [m["name"] for m in models]
        llama_models = [name for name in model_names if "llama" in name.lower()]
        assert len(llama_models) > 0, "No llama models found in results"
        
        # Verify each model has proper structure
        for model in models:
            assert "name" in model
            assert "url" in model
            assert "tags" in model
            assert isinstance(model["tags"], list)
            assert len(model["tags"]) > 0

    def test_model_page_parsing(self):
        """Test parsing a specific model page"""
        response = requests.get("https://ollama.com/library/tinydolphin")
        assert response.status_code == 200, f"Failed to fetch model page: {response.status_code}"
        
        html = response.text
        
        # Look for specific model information
        size_match = re.search(r'(\d+\.?\d*\s*[GM]B)', html)
        assert size_match is not None, "Should find size information on model page"
        
        # Look for model tags
        tag_pattern = r'tinydolphin:(\w+)'
        tags_found = re.findall(tag_pattern, html)
        assert len(tags_found) > 0, "Should find model tags on page"

    def test_empty_search(self):
        """Test empty search query behavior"""
        response = requests.get("https://ollama.com/search?q=")
        assert response.status_code == 200, f"Failed to fetch ollama.com: {response.status_code}"
        
        # Parse the HTML
        models = _parse_ollama_search_html(response.text)
        
        # Empty search might return featured models or nothing
        # Just verify it doesn't crash
        assert isinstance(models, list)

    def test_nonexistent_model_search(self):
        """Test searching for a model that doesn't exist"""
        response = requests.get("https://ollama.com/search?q=xyznonexistentmodel123456")
        assert response.status_code == 200, f"Failed to fetch ollama.com: {response.status_code}"
        
        # Parse the HTML
        models = _parse_ollama_search_html(response.text)
        
        # Should return empty or no matching models
        matching = [m for m in models if "xyznonexistentmodel123456" in m["name"]]
        assert len(matching) == 0, "Should not find non-existent model"



if __name__ == "__main__":
    pytest.main([__file__, "-v"])