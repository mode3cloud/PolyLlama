import express from 'express';
import cors from 'cors';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { SSEServerTransport } from '@modelcontextprotocol/sdk/server/sse.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { readFile } from 'fs/promises';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app = express();
app.use(cors());
app.use(express.json());

// Configuration
const PORT = process.env.MCP_SERVER_PORT || 3001;
const OLLAMA_BASE_URL = process.env.OLLAMA_BASE_URL || 'http://polyllama:11434';
const MCP_BRIDGE_URL = process.env.MCP_BRIDGE_URL || 'http://mcp-bridge:3000';
const API_KEY = process.env.POLYLLAMA_API_KEY;

// Cache for MCP tools fetched from the bridge
let cachedTools = [];
let lastToolsFetch = 0;
const TOOLS_CACHE_DURATION = 60000; // 1 minute cache

// Fetch available tools from the MCP bridge
async function fetchMCPTools() {
  try {
    const now = Date.now();
    if (cachedTools.length > 0 && (now - lastToolsFetch) < TOOLS_CACHE_DURATION) {
      return cachedTools;
    }

    console.log('Fetching tools from MCP bridge...');
    const response = await fetch(`${MCP_BRIDGE_URL}/tools`);
    
    if (!response.ok) {
      throw new Error(`MCP Bridge returned ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    const tools = data.tools || [];
    
    console.log(`Fetched ${tools.length} tools from MCP bridge`);
    
    // Convert MCP bridge tool format to MCP protocol format
    cachedTools = tools.map(tool => ({
      name: tool.name,
      description: tool.description,
      inputSchema: tool.inputSchema || {
        type: 'object',
        properties: {},
        additionalProperties: true
      }
    }));
    
    lastToolsFetch = now;
    return cachedTools;
    
  } catch (error) {
    console.error('Failed to fetch tools from MCP bridge:', error);
    // Return empty array if bridge is unavailable
    return [];
  }
}

// Utility function to make requests to PolyLlama with proper authentication
async function makePolyllamaRequest(endpoint, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(API_KEY && { 'api-key': API_KEY }),
    ...options.headers
  };

  const url = `${OLLAMA_BASE_URL}${endpoint}`;
  
  try {
    const response = await fetch(url, {
      ...options,
      headers
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      return await response.json();
    } else {
      return await response.text();
    }
  } catch (error) {
    throw new Error(`Failed to connect to PolyLlama: ${error.message}`);
  }
}

// Execute a tool via the MCP bridge
async function executeToolViaBridge(toolName, args) {
  try {
    console.log(`Executing tool ${toolName} via MCP bridge`);
    
    const response = await fetch(`${MCP_BRIDGE_URL}/execute`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        toolName,
        arguments: args
      })
    });

    if (!response.ok) {
      throw new Error(`MCP Bridge returned ${response.status}: ${response.statusText}`);
    }

    const result = await response.json();
    
    if (!result.success) {
      throw new Error(result.error || 'Tool execution failed');
    }

    // Format the result for MCP protocol
    // The MCP bridge returns results in different formats, normalize them
    const content = result.result;
    
    if (Array.isArray(content)) {
      // If it's already an array of content items
      return content;
    } else if (typeof content === 'string') {
      // If it's a plain string
      return [{
        type: 'text',
        text: content
      }];
    } else if (content && typeof content === 'object') {
      // If it's an object, stringify it
      return [{
        type: 'text', 
        text: JSON.stringify(content, null, 2)
      }];
    } else {
      // Fallback
      return [{
        type: 'text',
        text: String(content || 'No result')
      }];
    }
    
  } catch (error) {
    console.error(`Failed to execute tool ${toolName}:`, error);
    throw new Error(`Tool execution failed: ${error.message}`);
  }
}

// Create MCP server instance - will be created per connection to avoid state issues
function createMCPServer() {
  const mcpServer = new Server(
    {
      name: 'polyllama-mcp-server',
      version: '1.0.0'
    },
    {
      capabilities: {
        tools: {}
      }
    }
  );

  // Register tool handlers
  mcpServer.setRequestHandler(ListToolsRequestSchema, async () => {
    const tools = await fetchMCPTools();
    return {
      tools: tools
    };
  });

  mcpServer.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    
    try {
      const content = await executeToolViaBridge(name, args || {});
      return {
        content: content
      };
    } catch (error) {
      throw new Error(`Tool execution failed: ${error.message}`);
    }
  });

  return mcpServer;
}

// Express routes

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    service: 'polyllama-mcp-server',
    version: '1.0.0',
    timestamp: new Date().toISOString()
  });
});

// MCP server info endpoint
app.get('/info', async (req, res) => {
  try {
    const tools = await fetchMCPTools();
    
    res.json({
      name: 'PolyLlama MCP Server',
      version: '1.0.0',
      description: 'MCP Server that exposes all PolyLlama MCP tools for external consumption',
      tools: tools.map(tool => ({
        name: tool.name,
        description: tool.description
      })),
      endpoints: {
        sse: '/sse',
        health: '/health',
        info: '/info'
      },
      mcpBridgeUrl: MCP_BRIDGE_URL,
      authenticationRequired: !!API_KEY,
      toolCount: tools.length
    });
  } catch (error) {
    console.error('Error getting tools for info endpoint:', error);
    res.status(500).json({
      error: 'Failed to get tool information',
      message: error.message
    });
  }
});

// Store active connections for the SSE transport
const activeConnections = new Map();

// MCP over SSE - GET endpoint for establishing SSE connection
app.get('/sse', (req, res) => {
  console.log('SSE connection established');
  
  // Set SSE headers
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, api-key, x-api-key'
  });

  // Generate connection ID
  const connectionId = Date.now().toString();
  
  // Create MCP server for this connection
  const mcpServer = createMCPServer();
  
  // Store connection state
  activeConnections.set(connectionId, {
    response: res,
    server: mcpServer,
    connectionId
  });
  
  // Send connection established event
  res.write(`data: ${JSON.stringify({
    jsonrpc: '2.0',
    method: 'notifications/initialized',
    params: {
      protocolVersion: '2025-06-18',
      capabilities: { tools: {} },
      serverInfo: {
        name: 'polyllama-mcp-server',
        version: '1.0.0'
      },
      connectionId
    }
  })}\n\n`);

  // Keep connection alive
  const heartbeat = setInterval(() => {
    if (res.writableEnded) {
      clearInterval(heartbeat);
      return;
    }
    res.write(`data: ${JSON.stringify({
      jsonrpc: '2.0',
      method: 'notifications/ping',
      params: { timestamp: Date.now() }
    })}\n\n`);
  }, 30000);

  // Handle client disconnect
  req.on('close', () => {
    console.log('SSE client disconnected');
    clearInterval(heartbeat);
    activeConnections.delete(connectionId);
  });

  req.on('error', (error) => {
    console.error('SSE error:', error);
    clearInterval(heartbeat);
    activeConnections.delete(connectionId);
  });
});

// MCP over SSE - POST endpoint for receiving JSON-RPC messages
app.post('/sse', express.json(), async (req, res) => {
  console.log('MCP POST request:', req.body);
  
  try {
    const { method, params, id, jsonrpc } = req.body;
    let response;

    if (method === 'initialize') {
      response = {
        jsonrpc: '2.0',
        id,
        result: {
          protocolVersion: '2025-06-18',
          capabilities: { tools: {} },
          serverInfo: {
            name: 'polyllama-mcp-server',
            version: '1.0.0'
          }
        }
      };
    } else if (method === 'tools/list') {
      const tools = await fetchMCPTools();
      response = {
        jsonrpc: '2.0',
        id,
        result: { tools }
      };
    } else if (method === 'tools/call') {
      try {
        const content = await executeToolViaBridge(params.name, params.arguments || {});
        response = {
          jsonrpc: '2.0',
          id,
          result: { content }
        };
      } catch (error) {
        response = {
          jsonrpc: '2.0',
          id,
          error: {
            code: -32603,
            message: error.message
          }
        };
      }
    } else {
      response = {
        jsonrpc: '2.0',
        id,
        error: {
          code: -32601,
          message: `Method not found: ${method}`
        }
      };
    }

    // Send response back via the appropriate SSE connection if available
    // For now, we'll send the response directly via HTTP
    res.json(response);
    
  } catch (error) {
    console.error('Error handling MCP POST:', error);
    res.status(500).json({
      jsonrpc: '2.0',
      id: req.body.id || null,
      error: {
        code: -32603,
        message: error.message
      }
    });
  }
});

// Start server
app.listen(PORT, () => {
  console.log(`🚀 PolyLlama MCP Server running on port ${PORT}`);
  console.log(`📡 SSE endpoint: http://localhost:${PORT}/sse`);
  console.log(`🔍 Health check: http://localhost:${PORT}/health`);
  console.log(`ℹ️  Server info: http://localhost:${PORT}/info`);
  console.log(`🎯 Target PolyLlama: ${OLLAMA_BASE_URL}`);
  console.log(`🔐 API Key protection: ${API_KEY ? 'Enabled' : 'Disabled'}`);
  
  // Fetch and display available tools
  fetchMCPTools().then(tools => {
    console.log('\n🛠️  Available Tools:');
    if (tools.length > 0) {
      tools.forEach(tool => {
        console.log(`   • ${tool.name}: ${tool.description}`);
      });
    } else {
      console.log('   No tools available (MCP Bridge may be starting up)');
    }
    console.log('\n✨ PolyLlama MCP Server ready for connections!');
  }).catch(error => {
    console.log('\n🛠️  Available Tools: Error fetching tools from MCP Bridge');
    console.log(`   Error: ${error.message}`);
    console.log('\n✨ PolyLlama MCP Server ready for connections!');
  });
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM received, shutting down gracefully');
  process.exit(0);
});

process.on('SIGINT', () => {
  console.log('SIGINT received, shutting down gracefully');
  process.exit(0);
});