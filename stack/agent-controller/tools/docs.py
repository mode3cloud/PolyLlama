"""
Tool documentation generator.

This module provides utilities for automatically generating documentation
for tools, including schemas, usage examples, and API references.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import markdown

from .base import Tool, ToolParameter
from .registry import ToolRegistry


class DocumentationGenerator:
    """Generates documentation for tools and tool registry."""
    
    def __init__(self, registry: ToolRegistry):
        """
        Initialize documentation generator.
        
        Args:
            registry: Tool registry to generate docs for
        """
        self.registry = registry
    
    def generate_tool_docs(self, tool_name: str, format: str = "markdown") -> str:
        """
        Generate documentation for a specific tool.
        
        Args:
            tool_name: Name of the tool
            format: Output format ('markdown', 'html', 'json')
            
        Returns:
            Generated documentation string
        """
        tool = self.registry.get_tool(tool_name)
        if not tool:
            return f"Tool '{tool_name}' not found"
        
        if format == "markdown":
            return self._generate_markdown_docs(tool)
        elif format == "html":
            return self._generate_html_docs(tool)
        elif format == "json":
            return self._generate_json_docs(tool)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def generate_registry_docs(self, format: str = "markdown") -> str:
        """
        Generate documentation for the entire tool registry.
        
        Args:
            format: Output format ('markdown', 'html', 'json')
            
        Returns:
            Generated documentation string
        """
        if format == "markdown":
            return self._generate_registry_markdown()
        elif format == "html":
            return self._generate_registry_html()
        elif format == "json":
            return self._generate_registry_json()
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _generate_markdown_docs(self, tool: Tool) -> str:
        """Generate Markdown documentation for a tool."""
        docs = []
        
        # Header
        docs.append(f"# {tool.name}")
        docs.append("")
        docs.append(tool.description)
        docs.append("")
        
        # Metadata
        docs.append("## Tool Information")
        docs.append("")
        docs.append(f"- **Version**: {tool.version}")
        docs.append(f"- **Timeout**: {tool.timeout}s")
        docs.append(f"- **Cacheable**: {'Yes' if tool.cacheable else 'No'}")
        docs.append(f"- **Requires Auth**: {'Yes' if tool.requires_auth else 'No'}")
        docs.append("")
        
        # Parameters
        docs.append("## Parameters")
        docs.append("")
        
        if tool.parameters:
            docs.append("| Name | Type | Required | Description | Default | Constraints |")
            docs.append("|------|------|----------|-------------|---------|-------------|")
            
            for param in tool.parameters:
                required = "✅" if param.required else "❌"
                default = str(param.default) if param.default is not None else "-"
                
                constraints = []
                if param.enum:
                    constraints.append(f"enum: {param.enum}")
                if param.min_value is not None:
                    constraints.append(f"min: {param.min_value}")
                if param.max_value is not None:
                    constraints.append(f"max: {param.max_value}")
                constraints_str = ", ".join(constraints) if constraints else "-"
                
                docs.append(f"| {param.name} | {param.type} | {required} | {param.description} | {default} | {constraints_str} |")
        else:
            docs.append("No parameters required.")
        
        docs.append("")
        
        # Usage Examples
        docs.append("## Usage Examples")
        docs.append("")
        docs.append("### Basic Usage")
        docs.append("")
        docs.append("```python")
        docs.append(f"result = await tool_registry.execute_tool('{tool.name}', {{")
        
        # Generate example args
        example_args = self._generate_example_args(tool.parameters)
        for key, value in example_args.items():
            docs.append(f"    '{key}': {repr(value)},")
        
        docs.append("})")
        docs.append("```")
        docs.append("")
        
        # Response Format
        docs.append("## Response Format")
        docs.append("")
        docs.append("The tool returns a `ToolResult` object with the following structure:")
        docs.append("")
        docs.append("```json")
        docs.append("{")
        docs.append('  "status": "success" | "failure" | "timeout" | "cancelled",')
        docs.append('  "data": { ... },')
        docs.append('  "error": "error message" | null,')
        docs.append('  "execution_time": 1.23,')
        docs.append('  "metadata": { ... }')
        docs.append("}")
        docs.append("```")
        docs.append("")
        
        return "\n".join(docs)
    
    def _generate_html_docs(self, tool: Tool) -> str:
        """Generate HTML documentation for a tool."""
        markdown_docs = self._generate_markdown_docs(tool)
        return markdown.markdown(markdown_docs, extensions=['tables'])
    
    def _generate_json_docs(self, tool: Tool) -> str:
        """Generate JSON documentation for a tool."""
        docs = {
            "name": tool.name,
            "description": tool.description,
            "version": tool.version,
            "timeout": tool.timeout,
            "cacheable": tool.cacheable,
            "requires_auth": tool.requires_auth,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                    "enum": p.enum,
                    "min_value": p.min_value,
                    "max_value": p.max_value
                }
                for p in tool.parameters
            ],
            "example_usage": self._generate_example_args(tool.parameters),
            "generated_at": datetime.now().isoformat()
        }
        return json.dumps(docs, indent=2)
    
    def _generate_registry_markdown(self) -> str:
        """Generate Markdown documentation for the registry."""
        docs = []
        
        # Header
        docs.append("# Tool Registry Documentation")
        docs.append("")
        docs.append("This document provides comprehensive documentation for all available tools in the system.")
        docs.append("")
        docs.append(f"**Generated on**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        docs.append("")
        
        # Table of Contents
        tools = self.registry.list_tools()
        categories = self.registry.get_categories()
        
        docs.append("## Table of Contents")
        docs.append("")
        
        if categories:
            for category in sorted(categories):
                docs.append(f"- [{category.title()}](#{category.lower().replace(' ', '-')})")
                category_tools = self.registry.get_tools_by_category(category)
                for tool_name in sorted(category_tools):
                    docs.append(f"  - [{tool_name}](#{tool_name.replace('_', '-')})")
        else:
            for tool in sorted(tools, key=lambda t: t["name"]):
                docs.append(f"- [{tool['name']}](#{tool['name'].replace('_', '-')})")
        
        docs.append("")
        
        # Overview
        docs.append("## Overview")
        docs.append("")
        docs.append(f"The registry contains **{len(tools)}** tools across **{len(categories)}** categories.")
        docs.append("")
        
        if categories:
            docs.append("### Tools by Category")
            docs.append("")
            for category in sorted(categories):
                category_tools = self.registry.get_tools_by_category(category)
                docs.append(f"- **{category.title()}**: {len(category_tools)} tools")
            docs.append("")
        
        # Generate docs for each category/tool
        if categories:
            for category in sorted(categories):
                docs.append(f"## {category.title()}")
                docs.append("")
                
                category_tools = self.registry.get_tools_by_category(category)
                for tool_name in sorted(category_tools):
                    tool = self.registry.get_tool(tool_name)
                    if tool:
                        docs.append(self._generate_tool_summary(tool))
                        docs.append("")
        else:
            docs.append("## Tools")
            docs.append("")
            for tool in sorted(tools, key=lambda t: t["name"]):
                tool_obj = self.registry.get_tool(tool["name"])
                if tool_obj:
                    docs.append(self._generate_tool_summary(tool_obj))
                    docs.append("")
        
        return "\n".join(docs)
    
    def _generate_registry_html(self) -> str:
        """Generate HTML documentation for the registry."""
        markdown_docs = self._generate_registry_markdown()
        return markdown.markdown(markdown_docs, extensions=['tables', 'toc'])
    
    def _generate_registry_json(self) -> str:
        """Generate JSON documentation for the registry."""
        tools = self.registry.list_tools()
        categories = self.registry.get_categories()
        
        docs = {
            "registry_info": {
                "total_tools": len(tools),
                "categories": categories,
                "generated_at": datetime.now().isoformat()
            },
            "tools": {
                tool["name"]: self.registry.get_tool_schema(tool["name"])
                for tool in tools
            },
            "categories": {
                category: self.registry.get_tools_by_category(category)
                for category in categories
            }
        }
        return json.dumps(docs, indent=2)
    
    def _generate_tool_summary(self, tool: Tool) -> str:
        """Generate a summary section for a tool."""
        lines = []
        
        lines.append(f"### {tool.name}")
        lines.append("")
        lines.append(tool.description)
        lines.append("")
        
        # Quick info
        lines.append("**Quick Info:**")
        lines.append(f"- Version: {tool.version}")
        lines.append(f"- Timeout: {tool.timeout}s")
        if tool.requires_auth:
            lines.append("- ⚠️ Requires authentication")
        if tool.cacheable:
            lines.append("- 💾 Results are cacheable")
        lines.append("")
        
        # Parameters summary
        if tool.parameters:
            required_params = [p for p in tool.parameters if p.required]
            optional_params = [p for p in tool.parameters if not p.required]
            
            lines.append("**Parameters:**")
            if required_params:
                lines.append(f"- Required: {', '.join(f'`{p.name}`' for p in required_params)}")
            if optional_params:
                lines.append(f"- Optional: {', '.join(f'`{p.name}`' for p in optional_params)}")
        else:
            lines.append("**Parameters:** None")
        
        lines.append("")
        lines.append(f"[📖 Full Documentation](#{tool.name.replace('_', '-')}-full)")
        
        return "\n".join(lines)
    
    def _generate_example_args(self, parameters: List[ToolParameter]) -> Dict[str, Any]:
        """Generate example arguments for tool parameters."""
        examples = {}
        
        for param in parameters:
            if param.required or param.default is not None:
                if param.enum:
                    examples[param.name] = param.enum[0]
                elif param.type == "string":
                    examples[param.name] = f"example_{param.name}"
                elif param.type == "number":
                    if param.min_value is not None:
                        examples[param.name] = param.min_value
                    else:
                        examples[param.name] = 10
                elif param.type == "boolean":
                    examples[param.name] = True
                elif param.type == "array":
                    examples[param.name] = ["item1", "item2"]
                elif param.type == "object":
                    examples[param.name] = {"key": "value"}
                else:
                    examples[param.name] = f"example_{param.name}"
        
        return examples
    
    def generate_openapi_spec(self, base_url: str = "http://localhost:11436") -> Dict[str, Any]:
        """
        Generate OpenAPI specification for the tool API.
        
        Args:
            base_url: Base URL for the API
            
        Returns:
            OpenAPI specification dictionary
        """
        tools = self.registry.list_tools()
        
        openapi_spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "PolyLlama Agent Tools API",
                "description": "API for executing agent tools",
                "version": "1.0.0"
            },
            "servers": [
                {"url": base_url, "description": "Agent Controller"}
            ],
            "paths": {
                "/tools": {
                    "get": {
                        "summary": "List all available tools",
                        "parameters": [
                            {
                                "name": "category",
                                "in": "query",
                                "description": "Filter by tool category",
                                "required": False,
                                "schema": {"type": "string"}
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "List of tools",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "total": {"type": "integer"},
                                                "tools": {
                                                    "type": "array",
                                                    "items": {"$ref": "#/components/schemas/ToolInfo"}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "components": {
                "schemas": {
                    "ToolInfo": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "version": {"type": "string"},
                            "parameters": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/ToolParameter"}
                            }
                        }
                    },
                    "ToolParameter": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string"},
                            "description": {"type": "string"},
                            "required": {"type": "boolean"}
                        }
                    },
                    "ToolResult": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "enum": ["success", "failure", "timeout", "cancelled"]},
                            "data": {"type": "object"},
                            "error": {"type": "string"},
                            "execution_time": {"type": "number"}
                        }
                    }
                }
            }
        }
        
        # Add individual tool execution endpoints
        for tool in tools:
            tool_obj = self.registry.get_tool(tool["name"])
            if tool_obj:
                openapi_spec["paths"][f"/tools/{tool['name']}/execute"] = {
                    "post": {
                        "summary": f"Execute {tool['name']} tool",
                        "description": tool["description"],
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": self._parameter_schema_to_openapi(tool_obj.parameters)
                                }
                            }
                        },
                        "responses": {
                            "200": {
                                "description": "Tool execution result",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/ToolResult"}
                                    }
                                }
                            }
                        }
                    }
                }
        
        return openapi_spec
    
    def _parameter_schema_to_openapi(self, parameters: List[ToolParameter]) -> Dict[str, Any]:
        """Convert tool parameters to OpenAPI schema."""
        properties = {}
        required = []
        
        for param in parameters:
            param_schema = {
                "type": param.type,
                "description": param.description
            }
            
            if param.enum:
                param_schema["enum"] = param.enum
            if param.min_value is not None:
                param_schema["minimum"] = param.min_value
            if param.max_value is not None:
                param_schema["maximum"] = param.max_value
            if param.default is not None:
                param_schema["default"] = param.default
            
            properties[param.name] = param_schema
            
            if param.required:
                required.append(param.name)
        
        schema = {
            "type": "object",
            "properties": properties
        }
        
        if required:
            schema["required"] = required
        
        return schema