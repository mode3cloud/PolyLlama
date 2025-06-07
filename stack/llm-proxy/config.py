"""
Configuration for LLM Proxy Service

Environment-based configuration for LLM providers, database connections, and service URLs.
"""

import os
from typing import Optional


class LLMProxyConfig:
    """Configuration for LLM Proxy Service."""
    
    # Service Configuration
    HOST: str = os.getenv("LLM_PROXY_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("LLM_PROXY_PORT", "8085"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # MCP Service Configuration
    MCP_SERVICE_URL: str = os.getenv("MCP_SERVICE_URL", "http://localhost:8084")
    
    # Neo4j Configuration (for message persistence)
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USERNAME: str = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "neo4jpwd")
    
    # LLM Provider API Keys
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_API_BASE: Optional[str] = os.getenv("OPENAI_API_BASE")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
    
    # Ollama Configuration
    OLLAMA_API_BASE: str = os.getenv("OLLAMA_API_BASE", "http://router:11434")
    
    # LM Studio Configuration
    LM_STUDIO_API_BASE: str = os.getenv("LM_STUDIO_API_BASE", "http://localhost:1234")
    
    # OpenRouter Configuration
    OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_API_BASE: str = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
    
    # File Upload Configuration
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "100")) * 1024 * 1024  # 100MB default
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "/tmp/llm-proxy-uploads")
    
    # Multi-LLM Service Configuration
    MULTI_LLM_JSON_PARSE_RETRIES: int = int(os.getenv("MULTI_LLM_JSON_PARSE_RETRIES", "3"))
    MULTI_LLM_CACHE_SIZE: int = int(os.getenv("MULTI_LLM_CACHE_SIZE", "1000"))
    
    @classmethod
    def get_neo4j_config(cls) -> dict:
        """Get Neo4j connection configuration."""
        return {
            "uri": cls.NEO4J_URI,
            "username": cls.NEO4J_USERNAME,
            "password": cls.NEO4J_PASSWORD
        }
    
    @classmethod
    def get_llm_provider_configs(cls) -> dict:
        """Get all LLM provider configurations."""
        return {
            "openai": {
                "api_key": cls.OPENAI_API_KEY,
                "api_base": cls.OPENAI_API_BASE
            },
            "anthropic": {
                "api_key": cls.ANTHROPIC_API_KEY
            },
            "google": {
                "api_key": cls.GOOGLE_API_KEY
            },
            "groq": {
                "api_key": cls.GROQ_API_KEY
            },
            "ollama": {
                "api_base": cls.OLLAMA_API_BASE
            },
            "lm_studio": {
                "api_base": cls.LM_STUDIO_API_BASE
            },
            "openrouter": {
                "api_key": cls.OPENROUTER_API_KEY,
                "api_base": cls.OPENROUTER_API_BASE
            }
        }