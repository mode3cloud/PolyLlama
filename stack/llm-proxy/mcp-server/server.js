import express from 'express';
import cors from 'cors';
import { v4 as uuidv4 } from 'uuid';

const app = express();
app.use(cors());
app.use(express.json());

// Configuration
const PORT = process.env.MCP_SERVER_PORT || 3001;
const OLLAMA_BASE_URL = process.env.OLLAMA_BASE_URL || 'http://polyllama:11434';
const MCP_BRIDGE_URL = process.env.MCP_BRIDGE_URL || 'http://mcp-bridge:3000';
const API_KEY = process.env.POLYLLAMA_API_KEY;

// Store active SSE connections and pending messages
const activeConnections = new Map();
const pendingMessages = new Map();

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
      
      // Pass through tools directly from MCP bridge (preserve complete schemas)
      cachedTools = tools;
      
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
    if (cachedTools.length > 0) {
      console.log(`Returning ${cachedTools.length} cached tools due to fetch error`);
      return cachedTools;
    }
    return [];
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
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
    
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
      const content = result.result;
      
      if (Array.isArray(content)) {
        console.log(`Tool ${toolName} returning array content with ${content.length} items`);
        return content;
      } else if (typeof content === 'string') {
        console.log(`Tool ${toolName} returning string content (${content.length} chars)`);
        return [{
          type: 'text',
          text: content
        }];
      } else if (content && typeof content === 'object') {
        const stringified = safeStringify(content);
        console.log(`Tool ${toolName} returning object content (${stringified.length} chars)`);
        return [{
          type: 'text', 
          text: stringified
        }];
      } else {
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
    throw new Error(`Tool execution failed: ${error.message}`);
  }
}

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'polyllama-mcp-server-async' });
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
      name: 'PolyLlama MCP Server (Async)',
      version: '1.0.0',
      description: 'Async MCP Server that exposes all PolyLlama MCP tools for external consumption',
      protocol: 'asynchronous-sse',
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
      authenticationRequired: false, // Auth handled by nginx
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
      message: error.message
    };
    res.status(500).json(errorResponse);
  }
});

// SSE endpoint - establishes connection and provides session_id
app.get('/sse', async (req, res) => {
  const userAgent = req.headers['user-agent'] || 'unknown';
  console.log(`SSE connection from: ${userAgent}`);
  
  // Set SSE headers
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, api-key, x-api-key'
  });

  // Generate session ID
  const sessionId = uuidv4().replace(/-/g, '');
  
  // Store connection
  activeConnections.set(sessionId, {
    response: res,
    sessionId,
    userAgent
  });

  // Send endpoint event with session_id (like working server)
  const endpointUrl = `/messages/?session_id=${sessionId}`;
  res.write(`event: endpoint\n`);
  res.write(`data: ${endpointUrl}\n\n`);
  console.log(`SSE: Sent endpoint event: ${endpointUrl}`);

  // Handle disconnect
  req.on('close', () => {
    console.log(`SSE client disconnected (session: ${sessionId})`);
    activeConnections.delete(sessionId);
    pendingMessages.delete(sessionId);
  });

  req.on('error', (error) => {
    console.error(`SSE error (session: ${sessionId}):`, error);
    activeConnections.delete(sessionId);
    pendingMessages.delete(sessionId);
  });

  console.log(`SSE connection established (session: ${sessionId})`);
});

// Messages endpoint - handles JSON-RPC requests asynchronously
app.post('/messages/', express.json(), async (req, res) => {
  const sessionId = req.query.session_id;
  
  if (!sessionId) {
    return res.status(400).send('session_id is required');
  }

  const connection = activeConnections.get(sessionId);
  if (!connection) {
    return res.status(404).send('Session not found');
  }

  console.log(`JSON-RPC request for session ${sessionId}:`, req.body);
  
  // Immediately return "Accepted" (like working server)
  res.send('Accepted');
  
  // Process request asynchronously and send response via SSE
  setTimeout(async () => {
    try {
      const { method, params, id, jsonrpc } = req.body;
      let response;

      if (method === 'initialize') {
        // Use the same protocol version that the client requested
        const clientProtocolVersion = params?.protocolVersion || '2025-06-18';
        response = {
          jsonrpc: '2.0',
          id,
          result: {
            protocolVersion: clientProtocolVersion,
            capabilities: { tools: {} },
            serverInfo: {
              name: 'polyllama-async-mcp-server',
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
      } else if (method === 'resources/list') {
        response = {
          jsonrpc: '2.0',
          id,
          result: { resources: [] }
        };
      } else if (method === 'prompts/list') {
        response = {
          jsonrpc: '2.0',
          id,
          result: { prompts: [] }
        };
      } else if (method === 'tools/call') {
        const { name, arguments: args } = params;
        try {
          const content = await executeToolViaBridge(name, args || {});
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

      // Send response via SSE
      if (connection.response && !connection.response.destroyed) {
        const responseData = JSON.stringify(response);
        connection.response.write(`data: ${responseData}\n\n`);
        console.log(`Sent JSON-RPC response via SSE for ${method} (session: ${sessionId})`);
      }
      
    } catch (error) {
      console.error(`Error processing request for session ${sessionId}:`, error);
      
      if (connection.response && !connection.response.destroyed) {
        const errorResponse = {
          jsonrpc: '2.0',
          id: req.body?.id || null,
          error: {
            code: -32603,
            message: error.message
          }
        };
        connection.response.write(`data: ${JSON.stringify(errorResponse)}\n\n`);
      }
    }
  }, 100); // Small delay to simulate async processing
});

// Start server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 PolyLlama MCP Server (Async) running on port ${PORT}`);
  console.log(`📡 SSE endpoint: http://localhost:${PORT}/sse`);
  console.log(`📤 Messages endpoint: http://localhost:${PORT}/messages/`);
  console.log(`🔍 Health check: http://localhost:${PORT}/health`);
  console.log(`ℹ️  Server info: http://localhost:${PORT}/info`);
  console.log(`🎯 Target PolyLlama: ${OLLAMA_BASE_URL}`);
  console.log(`🔐 API Key protection: Handled by nginx router`);
  console.log(`🌉 MCP Bridge: ${MCP_BRIDGE_URL}`);
  
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
    console.log('\n✨ PolyLlama Async MCP Server ready for connections!');
  }).catch(error => {
    console.log('\n🛠️  Available Tools: Error fetching tools from MCP Bridge');
    console.log(`   Error: ${error.message}`);
    console.log('\n✨ PolyLlama Async MCP Server ready for connections!');
  });
});