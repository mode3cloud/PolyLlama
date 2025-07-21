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
      console.log(`Using cached tools (${cachedTools.length} tools)`);
      return cachedTools;
    }

    console.log(`Fetching tools from MCP bridge at ${MCP_BRIDGE_URL}/tools`);
    
    // Add timeout to prevent hanging
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
    
    try {
      const response = await fetch(`${MCP_BRIDGE_URL}/tools`, {
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        throw new Error(`MCP Bridge returned ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      const tools = data.tools || [];
      
      console.log(`Successfully fetched ${tools.length} tools from MCP bridge`);
      
      // Convert MCP bridge tool format to MCP protocol format
      cachedTools = tools.map(tool => ({
        name: tool.name,
        description: tool.description || 'No description available',
        inputSchema: tool.inputSchema || {
          type: 'object',
          properties: {},
          additionalProperties: true
        }
      }));
      
      lastToolsFetch = now;
      return cachedTools;
      
    } catch (fetchError) {
      clearTimeout(timeoutId);
      if (fetchError.name === 'AbortError') {
        throw new Error('Request to MCP bridge timed out after 10 seconds');
      }
      throw fetchError;
    }
    
  } catch (error) {
    console.error('Failed to fetch tools from MCP bridge:', error);
    console.error('Error details:', {
      message: error.message,
      stack: error.stack,
      mcpBridgeUrl: MCP_BRIDGE_URL
    });
    // Return cached tools if available, otherwise empty array
    if (cachedTools.length > 0) {
      console.log(`Returning ${cachedTools.length} cached tools due to fetch error`);
      return cachedTools;
    }
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

// Safe JSON stringify that handles circular references
function safeStringify(obj, indent = 2) {
  const seen = new WeakSet();
  return JSON.stringify(obj, (key, val) => {
    if (val != null && typeof val === "object") {
      if (seen.has(val)) {
        return "[Circular]";
      }
      seen.add(val);
    }
    return val;
  }, indent);
}

// Execute a tool via the MCP bridge
async function executeToolViaBridge(toolName, args) {
  try {
    console.log(`Executing tool ${toolName} via MCP bridge with args:`, safeStringify(args));
    
    // Add timeout to prevent hanging
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout for tool execution
    
    try {
      const response = await fetch(`${MCP_BRIDGE_URL}/execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          toolName,
          arguments: args
        }),
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      console.log(`Tool ${toolName} execution response status: ${response.status}`);

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`Tool ${toolName} execution failed with status ${response.status}:`, errorText);
        throw new Error(`MCP Bridge returned ${response.status}: ${response.statusText} - ${errorText}`);
      }

      const result = await response.json();
      console.log(`Tool ${toolName} execution result:`, safeStringify(result));
      
      if (!result.success) {
        throw new Error(result.error || 'Tool execution failed');
      }

      // Format the result for MCP protocol
      // The MCP bridge returns results in different formats, normalize them
      const content = result.result;
      
      if (Array.isArray(content)) {
        // If it's already an array of content items
        console.log(`Tool ${toolName} returning array content with ${content.length} items`);
        return content;
      } else if (typeof content === 'string') {
        // If it's a plain string
        console.log(`Tool ${toolName} returning string content (${content.length} chars)`);
        return [{
          type: 'text',
          text: content
        }];
      } else if (content && typeof content === 'object') {
        // If it's an object, stringify it safely
        const stringified = safeStringify(content);
        console.log(`Tool ${toolName} returning object content (${stringified.length} chars)`);
        return [{
          type: 'text', 
          text: stringified
        }];
      } else {
        // Fallback
        console.log(`Tool ${toolName} returning fallback content`);
        return [{
          type: 'text',
          text: String(content || 'No result')
        }];
      }
      
    } catch (fetchError) {
      clearTimeout(timeoutId);
      if (fetchError.name === 'AbortError') {
        throw new Error(`Tool ${toolName} execution timed out after 30 seconds`);
      }
      throw fetchError;
    }
    
  } catch (error) {
    console.error(`Failed to execute tool ${toolName}:`, error);
    console.error('Tool execution error details:', {
      toolName,
      args,
      message: error.message,
      stack: error.stack,
      mcpBridgeUrl: MCP_BRIDGE_URL
    });
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
  console.log('Info endpoint requested');
  
  try {
    const startTime = Date.now();
    const tools = await fetchMCPTools();
    const fetchTime = Date.now() - startTime;
    
    console.log(`Info endpoint: fetched ${tools.length} tools in ${fetchTime}ms`);
    
    const response = {
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
      toolCount: tools.length,
      performance: {
        toolFetchTime: `${fetchTime}ms`
      }
    };
    
    res.json(response);
    console.log('Info endpoint: response sent successfully');
    
  } catch (error) {
    console.error('Error getting tools for info endpoint:', error);
    const errorResponse = {
      error: 'Failed to get tool information',
      message: error.message,
      stack: error.stack
    };
    res.status(500).json(errorResponse);
  }
});

// Store active connections for the SSE transport
const activeConnections = new Map();

// Handle the different client types (n8n vs Claude Desktop/mcp-remote)
function detectClientType(userAgent, headers) {
  if (userAgent && userAgent.includes('node')) {
    return 'n8n';
  } else if (headers['user-agent'] && headers['user-agent'].includes('mcp-remote')) {
    return 'mcp-remote';
  } else {
    return 'unknown';
  }
}

// MCP over SSE - GET endpoint for establishing SSE connection
app.get('/sse', async (req, res) => {
  const userAgent = req.headers['user-agent'] || 'unknown';
  const clientType = detectClientType(userAgent, req.headers);
  
  console.log(`SSE connection established from: ${userAgent} (detected: ${clientType})`);
  
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
    connectionId,
    clientType
  });
  
  if (clientType === 'n8n') {
    console.log('SSE: Configuring for n8n client');
    
    // For n8n, send a complete MCP server info in a format it expects
    res.write(`data: ${safeStringify({
      jsonrpc: '2.0',
      method: 'notifications/initialized',
      params: {
        protocolVersion: '2025-06-18',
        capabilities: { 
          tools: {},
          resources: { subscribe: false, listChanged: false },
          prompts: { listChanged: false }
        },
        serverInfo: {
          name: 'polyllama-mcp-server',
          version: '1.0.0'
        }
      }
    }, 0)}\n\n`);

    // Send tools immediately in MCP JSON-RPC format
    try {
      console.log('SSE: Fetching and sending tools for n8n');
      const tools = await fetchMCPTools();
      console.log(`SSE: Sending ${tools.length} tools to n8n`);
      
      res.write(`data: ${safeStringify({
        jsonrpc: '2.0',
        method: 'notifications/tools/list_changed',
        params: { tools }
      }, 0)}\n\n`);
      
    } catch (error) {
      console.error('SSE: Error fetching tools for n8n:', error);
      res.write(`data: ${safeStringify({
        jsonrpc: '2.0',
        method: 'notifications/error',
        params: { error: error.message }
      }, 0)}\n\n`);
    }
    
  } else {
    console.log('SSE: Configuring for standard MCP client');
    
    // For other clients (like mcp-remote), use event-based format
    res.write('event: server-ready\n');
    res.write(`data: ${safeStringify({
      name: 'polyllama-mcp-server',
      version: '1.0.0',
      protocolVersion: '2025-06-18',
      capabilities: { tools: {} }
    }, 0)}\n\n`);

    // Send tools list
    try {
      const tools = await fetchMCPTools();
      res.write('event: tools\n');
      res.write(`data: ${safeStringify({ tools }, 0)}\n\n`);
    } catch (error) {
      res.write('event: error\n');
      res.write(`data: ${safeStringify({ error: error.message }, 0)}\n\n`);
    }
  }

  // Keep connection alive
  const heartbeat = setInterval(() => {
    if (res.writableEnded) {
      clearInterval(heartbeat);
      return;
    }
    
    if (clientType === 'n8n') {
      res.write(`data: ${safeStringify({
        jsonrpc: '2.0',
        method: 'notifications/ping',
        params: { timestamp: Date.now() }
      }, 0)}\n\n`);
    } else {
      res.write('event: ping\n');
      res.write(`data: ${Date.now()}\n\n`);
    }
  }, 30000);

  // Handle client disconnect
  req.on('close', () => {
    console.log(`SSE client disconnected (${clientType})`);
    clearInterval(heartbeat);
    activeConnections.delete(connectionId);
  });

  req.on('error', (error) => {
    console.error(`SSE error (${clientType}):`, error);
    clearInterval(heartbeat);
    activeConnections.delete(connectionId);
  });
  
  console.log(`SSE connection fully initialized for ${clientType}`);
});

// MCP over SSE - POST endpoint for receiving JSON-RPC messages
app.post('/sse', express.json(), async (req, res) => {
  const startTime = Date.now();
  console.log(`MCP POST request received: ${req.body?.method || 'unknown'} (id: ${req.body?.id})`);
  console.log('Full POST body:', safeStringify(req.body));
  
  try {
    const { method, params, id, jsonrpc } = req.body;
    let response;

    if (method === 'initialize') {
      console.log('Processing initialize request');
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
      console.log('Processing tools/list request');
      const toolsFetchStart = Date.now();
      const tools = await fetchMCPTools();
      const toolsFetchTime = Date.now() - toolsFetchStart;
      console.log(`tools/list: fetched ${tools.length} tools in ${toolsFetchTime}ms`);
      
      response = {
        jsonrpc: '2.0',
        id,
        result: { tools }
      };
    } else if (method === 'tools/call') {
      console.log(`Processing tools/call request for tool: ${params?.name}`);
      const toolExecStart = Date.now();
      
      try {
        const content = await executeToolViaBridge(params.name, params.arguments || {});
        const toolExecTime = Date.now() - toolExecStart;
        console.log(`tools/call: executed ${params.name} in ${toolExecTime}ms`);
        
        response = {
          jsonrpc: '2.0',
          id,
          result: { content }
        };
      } catch (error) {
        const toolExecTime = Date.now() - toolExecStart;
        console.error(`tools/call: failed ${params.name} after ${toolExecTime}ms:`, error.message);
        
        response = {
          jsonrpc: '2.0',
          id,
          error: {
            code: -32603,
            message: error.message
          }
        };
      }
    } else if (method === 'notifications/initialized') {
      console.log('Processing notifications/initialized (acknowledging client initialization)');
      // This is a notification, no response needed but return success
      response = {
        jsonrpc: '2.0',
        id,
        result: {}
      };
    } else if (method === 'resources/list') {
      console.log('Processing resources/list request');
      // We don't have resources, return empty list
      response = {
        jsonrpc: '2.0',
        id,
        result: { resources: [] }
      };
    } else if (method === 'prompts/list') {
      console.log('Processing prompts/list request');
      // We don't have prompts, return empty list
      response = {
        jsonrpc: '2.0',
        id,
        result: { prompts: [] }
      };
    } else {
      console.log(`Unknown method requested: ${method}`);
      response = {
        jsonrpc: '2.0',
        id,
        error: {
          code: -32601,
          message: `Method not found: ${method}`
        }
      };
    }

    // Send response back via HTTP
    const totalTime = Date.now() - startTime;
    console.log(`MCP POST response sent for ${method} (id: ${id}) in ${totalTime}ms`);
    res.json(response);
    
  } catch (error) {
    const totalTime = Date.now() - startTime;
    console.error(`Error handling MCP POST after ${totalTime}ms:`, error);
    console.error('POST error details:', {
      message: error.message,
      stack: error.stack,
      body: req.body
    });
    
    const errorResponse = {
      jsonrpc: '2.0',
      id: req.body?.id || null,
      error: {
        code: -32603,
        message: error.message
      }
    };
    
    res.status(500).json(errorResponse);
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