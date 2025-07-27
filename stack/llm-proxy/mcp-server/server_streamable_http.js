import express from 'express';
import cors from 'cors';
import { spawn } from 'child_process';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { readFile } from 'fs/promises';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { v4 as uuidv4 } from 'uuid';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app = express();
app.use(cors());
app.use(express.json());

// Configuration
const PORT = process.env.MCP_SERVER_PORT || 3001;
const OLLAMA_BASE_URL = process.env.OLLAMA_BASE_URL || 'http://polyllama:11434';
const API_KEY = process.env.POLYLLAMA_API_KEY;

// Store active MCP connections
const mcpConnections = new Map();

// Store initialization state and tool counts per server
const serverState = new Map();

// Cache for MCP tools fetched from the bridge
let cachedTools = [];
let lastToolsFetch = 0;
const TOOLS_CACHE_DURATION = 60000; // 1 minute cache

// Configuration constants
const INIT_RETRY_DELAY = 2000; // 2 seconds
const INIT_MAX_RETRIES = 3;
const HEALTH_CHECK_INTERVAL = 30000; // 30 seconds

// Beautiful console formatter for initialization results
function displayInitializationResults(results) {
  console.log('\n' + '═'.repeat(60));
  console.log('🚀 MCP SERVERS INITIALIZATION RESULTS');
  console.log('═'.repeat(60) + '\n');
  
  const servers = Object.entries(results);
  const totalServers = servers.length;
  const successfulServers = servers.filter(([_, success]) => success).length;
  const failedServers = totalServers - successfulServers;
  
  // Create a formatted table
  console.log('┌─────────────────────────┬──────────┬────────────────────┐');
  console.log('│ Server Name             │ Status   │ Tools              │');
  console.log('├─────────────────────────┼──────────┼────────────────────┤');
  
  for (const [name, success] of servers) {
    const state = serverState.get(name);
    const toolCount = state?.toolCount || 0;
    const statusEmoji = success ? '✅' : '❌';
    const statusText = success ? 'Online' : 'Failed';
    const toolsText = success ? `${toolCount} tools` : state?.lastError || 'Error';
    
    // Pad strings for alignment
    const paddedName = name.padEnd(23);
    const paddedStatus = `${statusEmoji} ${statusText}`.padEnd(8);
    const paddedTools = toolsText.padEnd(18);
    
    console.log(`│ ${paddedName} │ ${paddedStatus} │ ${paddedTools} │`);
  }
  
  console.log('└─────────────────────────┴──────────┴────────────────────┘');
  
  // Summary statistics
  console.log('\n📊 SUMMARY:');
  console.log('─'.repeat(40));
  console.log(`  Total Servers:      ${totalServers}`);
  console.log(`  ✅ Successful:      ${successfulServers}`);
  console.log(`  ❌ Failed:          ${failedServers}`);
  console.log(`  Success Rate:       ${((successfulServers/totalServers) * 100).toFixed(1)}%`);
  
  // Show failed server details if any
  if (failedServers > 0) {
    console.log('\n⚠️  FAILED SERVERS:');
    console.log('─'.repeat(40));
    for (const [name, success] of servers) {
      if (!success) {
        const state = serverState.get(name);
        console.log(`  • ${name}: ${state?.lastError || 'Unknown error'}`);
      }
    }
  }
  
  // Show successful servers with tool details
  if (successfulServers > 0) {
    console.log('\n✨ READY SERVERS:');
    console.log('─'.repeat(40));
    for (const [name, success] of servers) {
      if (success) {
        const state = serverState.get(name);
        const toolCount = state?.toolCount || 0;
        const emoji = getServerEmoji(name);
        console.log(`  ${emoji} ${name}: ${toolCount} tool${toolCount !== 1 ? 's' : ''} available`);
      }
    }
  }
  
  console.log('\n' + '═'.repeat(60) + '\n');
}

// Get emoji for server based on name
function getServerEmoji(serverName) {
  const emojiMap = {
    'github': '🐙',
    'gitlab': '🦊',
    'docker': '🐳',
    'kubernetes': '☸️',
    'aws': '☁️',
    'azure': '☁️',
    'google': '🔍',
    'database': '🗄️',
    'api': '🔌',
    'web': '🌐',
    'file': '📁',
    'system': '⚙️',
    'default': '🔧'
  };
  
  const lowerName = serverName.toLowerCase();
  for (const [key, emoji] of Object.entries(emojiMap)) {
    if (lowerName.includes(key)) {
      return emoji;
    }
  }
  return emojiMap.default;
}

// Load MCP configuration
async function loadConfig() {
  try {
    const configPath = process.env.MCP_CONFIG_PATH || join(__dirname, 'mcp-config.json');
    const configData = await readFile(configPath, 'utf-8');
    return JSON.parse(configData);
  } catch (error) {
    console.error('Failed to load MCP config:', error);
    return { mcpServers: {} };
  }
}

// Initialize MCP server connection with retries
async function initializeMcpServer(name, config, retryCount = 0) {
  console.log(`Initializing MCP server: ${name} (attempt ${retryCount + 1})`);
  console.log(`Server config:`, JSON.stringify(config, null, 2));
  
  try {
    // Create transport with proper process management
    const transport = new StdioClientTransport({
      command: config.command,
      args: config.args,
      env: { ...process.env, ...config.env }
    });

    // Add error handling for transport
    transport.onError = (error) => {
      console.error(`Transport error for ${name}:`, error);
      // Mark server as disconnected but don't crash main process
      serverState.set(name, {
        connected: false,
        toolCount: 0,
        lastError: error.message,
        initTime: Date.now()
      });
    };

    transport.onClose = () => {
      console.log(`Transport closed for ${name}`);
      // Mark server as disconnected
      serverState.set(name, {
        connected: false,
        toolCount: 0,
        lastError: 'Transport closed',
        initTime: Date.now()
      });
    };

    // Create client
    const client = new Client({
      name: `mcp-server-${name}`,
      version: '1.0.0'
    }, {
      capabilities: {}
    });

    // Connect client to transport
    await client.connect(transport);

    // Fetch initial tools to verify connection
    const tools = await client.listTools();
    const toolCount = tools.tools?.length || 0;

    // Store connection
    mcpConnections.set(name, {
      client,
      transport,
      config,
      lastHealthCheck: Date.now()
    });

    // Store server state
    serverState.set(name, {
      connected: true,
      toolCount,
      lastError: null,
      initTime: Date.now()
    });

    console.log(`Successfully connected to MCP server: ${name} with ${toolCount} tools`);
    return true;
  } catch (error) {
    console.error(`Failed to initialize MCP server ${name}:`, error);
    
    // Store failed state
    serverState.set(name, {
      connected: false,
      toolCount: 0,
      lastError: error.message,
      initTime: Date.now()
    });

    // Retry logic
    if (retryCount < INIT_MAX_RETRIES) {
      console.log(`Retrying ${name} in ${INIT_RETRY_DELAY}ms...`);
      await new Promise(resolve => setTimeout(resolve, INIT_RETRY_DELAY));
      return await initializeMcpServer(name, config, retryCount + 1);
    }

    return false;
  }
}

// Initialize all MCP servers
async function initializeAllServers() {
  const config = await loadConfig();
  const results = {};

  // Initialize servers in parallel with staggered start
  const initPromises = Object.entries(config.mcpServers).map(async ([name, serverConfig], index) => {
    // Stagger initialization to avoid overwhelming the system
    await new Promise(resolve => setTimeout(resolve, index * 500));
    results[name] = await initializeMcpServer(name, serverConfig);
  });

  await Promise.all(initPromises);
  return results;
}

// Health check for a single server
async function checkServerHealth(name) {
  const connection = mcpConnections.get(name);
  const state = serverState.get(name) || { connected: false, toolCount: 0 };

  if (!connection) {
    serverState.set(name, { ...state, connected: false, lastError: 'No connection' });
    return false;
  }

  try {
    // Try to list tools as a health check
    const tools = await connection.client.listTools();
    const toolCount = tools.tools?.length || 0;
    
    serverState.set(name, {
      connected: true,
      toolCount,
      lastError: null,
      lastHealthCheck: Date.now()
    });
    
    connection.lastHealthCheck = Date.now();
    return true;
  } catch (error) {
    console.error(`Health check failed for ${name}:`, error.message);
    serverState.set(name, {
      ...state,
      connected: false,
      lastError: error.message,
      lastHealthCheck: Date.now()
    });
    return false;
  }
}

// Periodic health check for all servers
async function runHealthChecks() {
  for (const [name] of mcpConnections) {
    await checkServerHealth(name);
  }
}

// Fetch available tools from all managed MCP servers
async function fetchMCPTools() {
  try {
    const now = Date.now();
    if (cachedTools.length > 0 && (now - lastToolsFetch) < TOOLS_CACHE_DURATION) {
      console.log(`Using cached tools (${cachedTools.length} tools)`);
      return cachedTools;
    }

    console.log(`Fetching tools from all managed MCP servers`);
    const allTools = [];
    const errors = {};

    for (const [serverName, connection] of mcpConnections.entries()) {
      const state = serverState.get(serverName);
      
      // Skip if server is known to be disconnected
      if (state && !state.connected) {
        errors[serverName] = state.lastError || 'Server disconnected';
        continue;
      }

      try {
        const tools = await connection.client.listTools();
        const toolCount = tools.tools?.length || 0;
        
        // Update tool count in server state
        if (state) {
          state.toolCount = toolCount;
        }
        
        // Add server name to each tool and prefix tool name
        for (const tool of tools.tools || []) {
          // Replace hyphens in server name with underscores for OpenAI compatibility
          const safeServerName = serverName.replace(/-/g, '_');
          allTools.push({
            ...tool,
            name: `${safeServerName}__${tool.name}`,
            originalName: tool.name,
            server: serverName
          });
        }
      } catch (error) {
        console.error(`Failed to list tools from ${serverName}:`, error);
        errors[serverName] = error.message;
        
        // Update server state to reflect error
        serverState.set(serverName, {
          ...state,
          connected: false,
          lastError: error.message,
          toolCount: 0
        });
      }
    }

    cachedTools = allTools;
    lastToolsFetch = now;
    console.log(`Successfully fetched ${allTools.length} tools from managed servers`);
    return allTools;

  } catch (error) {
    console.error('Failed to fetch tools from managed MCP servers:', error);
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

// Execute a tool on the appropriate managed MCP server
async function executeTool(toolName, args) {
  try {
    console.log(`Executing tool ${toolName} with args:`, safeStringify(args));

    // Handle prefixed tool names (server__toolName)
    let actualToolName = toolName;
    let targetServer = null;
    
    if (toolName.includes('__')) {
      const [prefix, ...nameParts] = toolName.split('__');
      // Try to find the actual server name (with hyphens) from the safe name (with underscores)
      let foundServer = false;
      for (const [serverName] of mcpConnections.entries()) {
        if (serverName.replace(/-/g, '_') === prefix) {
          targetServer = serverName;
          foundServer = true;
          break;
        }
      }
      // If not found by underscore conversion, try the prefix as-is
      if (!foundServer && mcpConnections.has(prefix)) {
        targetServer = prefix;
      }
      actualToolName = nameParts.join('__'); // Handle tool names that might contain __
    }
    
    console.log(`Resolved - actualToolName: ${actualToolName}, targetServer: ${targetServer}`);
    console.log(`Available connections:`, Array.from(mcpConnections.keys()));

    if (!targetServer || !mcpConnections.has(targetServer)) {
      console.error(`Server not found for tool: ${toolName}. Target server: ${targetServer}`);
      throw new Error(`Invalid or missing server for tool: ${toolName}`);
    }

    const connection = mcpConnections.get(targetServer);

    // Add timeout wrapper for tool execution
    const TOOL_TIMEOUT = 30000; // 30 seconds
    const toolPromise = connection.client.callTool({
      name: actualToolName,
      arguments: args
    });
    
    const timeoutPromise = new Promise((_, reject) => {
      setTimeout(() => {
        reject(new Error(`Tool execution timed out after ${TOOL_TIMEOUT/1000} seconds`));
      }, TOOL_TIMEOUT);
    });
    
    console.log(`[${toolName}] Waiting for tool completion...`);
    const result = await Promise.race([toolPromise, timeoutPromise]);
    console.log(`[${toolName}] Tool call returned:`, safeStringify(result));

    // Format the result for MCP protocol
    const content = result.content;

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

  } catch (error) {
    console.error(`Failed to execute tool ${toolName}:`, error);
    throw new Error(`Tool execution failed: ${error.message}`);
  }
}

// Check if client supports streaming (looks for Accept: text/event-stream)
function supportsStreaming(req) {
  const accept = req.headers.accept || '';
  return accept.includes('text/event-stream');
}

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'polyllama-mcp-server-streamable-http' });
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
      name: 'PolyLlama MCP Server (Streamable HTTP)',
      version: '1.0.0',
      description: 'Streamable HTTP MCP Server that exposes all PolyLlama MCP tools for external consumption',
      protocol: 'streamable-http',
      protocolVersion: '2025-03-26',
      tools: tools.map(tool => ({
        name: tool.name,
        description: tool.description
      })),
      endpoints: {
        mcp: '/mcp',
        health: '/health',
        info: '/info'
      },
      authenticationRequired: false, // Auth handled by nginx
      toolCount: tools.length,
      features: {
        streamingSupported: true,
        bidirectionalCommunication: true,
        connectionResumption: false // Future feature
      },
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

// Main MCP endpoint - handles all MCP requests with optional streaming
app.post('/mcp', express.json(), async (req, res) => {
  const userAgent = req.headers['user-agent'] || 'unknown';
  const requestId = uuidv4().replace(/-/g, '').substring(0, 8);

  console.log(`[${requestId}] MCP request from: ${userAgent}`);
  console.log(`[${requestId}] Request body:`, safeStringify(req.body));

  try {
    const { method, params, id, jsonrpc } = req.body;

    // Determine if we should stream the response
    const shouldStream = supportsStreaming(req) && (
      method === 'tools/call' ||
      method === 'initialize' ||
      (params && params.stream === true)
    );

    console.log(`[${requestId}] Method: ${method}, Streaming: ${shouldStream}`);

    let response;

    if (method === 'initialize') {
      // Use the same protocol version that the client requested
      const clientProtocolVersion = params?.protocolVersion || '2025-03-26';
      response = {
        jsonrpc: '2.0',
        id,
        result: {
          protocolVersion: clientProtocolVersion,
          capabilities: {
            tools: {},
            streaming: {
              supported: true,
              protocols: ['sse']
            }
          },
          serverInfo: {
            name: 'polyllama-streamable-http-mcp-server',
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

      if (shouldStream) {
        // Upgrade to SSE streaming for tool execution
        console.log(`[${requestId}] Upgrading to SSE streaming for tool: ${name}`);
        
        // Track this operation
        incrementActiveOperations();

        // Monitor connection events
        req.on('close', () => {
          console.log(`[${requestId}] Client disconnected`);
        });

        req.on('error', (err) => {
          console.log(`[${requestId}] Client connection error:`, err.message);
        });

        res.writeHead(200, {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Headers': 'Content-Type, Authorization, api-key, x-api-key'
        });

        try {
          // Execute tool first
          console.log(`[${requestId}] Starting tool execution: ${name}`);
          const content = await executeTool(name, args || {});
          console.log(`[${requestId}] Tool execution completed: ${name}`);

          // Send only the final result as standard MCP response
          const finalEvent = {
            jsonrpc: '2.0',
            id,
            result: {
              content
            }
          };
          console.log(`[${requestId}] Sending final result for: ${name}`);
          console.log(`[${requestId}] Result content length: ${JSON.stringify(content).length} chars`);
          res.write(`data: ${JSON.stringify(finalEvent)}\n\n`);
          console.log(`[${requestId}] Final event written, connection alive: ${!res.destroyed}`);

          console.log(`[${requestId}] Streaming tool execution completed for: ${name}`);
          res.end();
          
          // Operation completed successfully
          decrementActiveOperations();
          return;

        } catch (error) {
          console.error(`[${requestId}] Tool execution error for ${name}:`, error);
          
          // Send error event
          const errorEvent = {
            jsonrpc: '2.0',
            id,
            error: {
              code: -32603,
              message: error.message,
              type: 'error'
            }
          };
          res.write(`data: ${JSON.stringify(errorEvent)}\n\n`);
          res.end();
          
          // Operation completed with error
          decrementActiveOperations();
          return;
        }
      } else {
        // Standard HTTP response for tool execution
        try {
          const content = await executeTool(name, args || {});
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

    // Send standard HTTP response
    console.log(`[${requestId}] Sending HTTP response for method: ${method}`);
    res.json(response);

  } catch (error) {
    console.error(`[${requestId}] Error processing MCP request:`, error);

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

// Legacy SSE endpoint for backward compatibility
app.get('/sse', async (req, res) => {
  console.log('⚠️  Legacy SSE endpoint accessed - consider upgrading to streamable HTTP /mcp endpoint');

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

  // Send deprecation notice
  res.write(`event: deprecation\n`);
  res.write(`data: {"message": "SSE transport is deprecated. Please upgrade to streamable HTTP at /mcp endpoint.", "sessionId": "${sessionId}"}\n\n`);

  // Send endpoint event for backward compatibility
  const endpointUrl = `/messages/?session_id=${sessionId}`;
  res.write(`event: endpoint\n`);
  res.write(`data: ${endpointUrl}\n\n`);

  console.log(`Legacy SSE: Sent endpoint event: ${endpointUrl}`);

  // Handle disconnect
  req.on('close', () => {
    console.log(`Legacy SSE client disconnected (session: ${sessionId})`);
  });

  req.on('error', (error) => {
    console.error(`Legacy SSE error (session: ${sessionId}):`, error);
  });
});

// Legacy messages endpoint for backward compatibility
app.post('/messages/', express.json(), async (req, res) => {
  console.log('⚠️  Legacy messages endpoint accessed - consider upgrading to streamable HTTP /mcp endpoint');

  const sessionId = req.query.session_id;

  if (!sessionId) {
    return res.status(400).send('session_id is required');
  }

  console.log(`Legacy JSON-RPC request for session ${sessionId}:`, req.body);

  // Redirect to main MCP endpoint
  res.status(302).json({
    message: 'This endpoint is deprecated. Please use POST /mcp for all MCP requests.',
    newEndpoint: '/mcp',
    migration: 'Remove session_id and send requests directly to /mcp with Accept: text/event-stream for streaming'
  });
});

// Start server
let healthCheckInterval;

app.listen(PORT, '0.0.0.0', async () => {
  console.log(`🚀 PolyLlama MCP Server (Streamable HTTP) running on port ${PORT}`);
  console.log(`📡 Main MCP endpoint: http://localhost:${PORT}/mcp`);
  console.log(`🔍 Health check: http://localhost:${PORT}/health`);
  console.log(`ℹ️  Server info: http://localhost:${PORT}/info`);
  console.log(`📜 Legacy SSE endpoint: http://localhost:${PORT}/sse (deprecated)`);
  console.log(`🎯 Target PolyLlama: ${OLLAMA_BASE_URL}`);
  console.log(`🔐 API Key protection: Handled by nginx router`);
  console.log(`📊 Protocol: Streamable HTTP (2025-03-26)`);

  // Initialize MCP servers on startup
  const results = await initializeAllServers();
  displayInitializationResults(results);
  
  // Start periodic health checks
  healthCheckInterval = setInterval(() => {
    runHealthChecks().catch(error => {
      console.error('Error during health checks:', error);
    });
  }, HEALTH_CHECK_INTERVAL);
  
  // Run initial health check after 5 seconds
  setTimeout(() => {
    runHealthChecks().catch(error => {
      console.error('Error during initial health check:', error);
    });
  }, 5000);

  // Fetch and display available tools
  fetchMCPTools().then(tools => {
    console.log('\n🛠️  Available Tools:');
    if (tools.length > 0) {
      tools.forEach(tool => {
        console.log(` ⛏️ ${tool.name}`);
      });
    } else {
      console.log('   No tools available (MCP Bridge may be starting up)');
    }
    console.log('\n✨ PolyLlama Streamable HTTP MCP Server ready for connections!');
    console.log('💡 Key Features:');
    console.log('   • Single endpoint for all MCP operations');
    console.log('   • Dynamic SSE streaming for long-running operations');
    console.log('   • Backward compatibility with legacy SSE transport');
    console.log('   • Better resource efficiency and connection management');
  }).catch(error => {
    console.log('\n🛠️  Available Tools: Error fetching tools from MCP Bridge');
    console.log(`   Error: ${error.message}`);
    console.log('\n✨ PolyLlama Streamable HTTP MCP Server ready for connections!');
  });
});

// Graceful shutdown with active operation tracking
let activeOperations = 0;
let shutdownRequested = false;

function incrementActiveOperations() {
  activeOperations++;
  console.log(`Active operations: ${activeOperations}`);
}

function decrementActiveOperations() {
  activeOperations--;
  console.log(`Active operations: ${activeOperations}`);
  
  // If shutdown was requested and no active operations, proceed with shutdown
  if (shutdownRequested && activeOperations === 0) {
    console.log('All operations completed, proceeding with shutdown');
    performShutdown();
  }
}

function performShutdown() {
  console.log('Performing shutdown...');
  
  // Clear health check interval
  if (healthCheckInterval) {
    clearInterval(healthCheckInterval);
  }
  
  for (const [name, connection] of mcpConnections.entries()) {
    try {
      connection.client.close();
      if (connection.process) {
        connection.process.kill();
      }
    } catch (error) {
      console.error(`Error closing connection ${name}:`, error);
    }
  }
  process.exit(0);
}

process.on('SIGTERM', () => {
  console.log('SIGTERM received');
  
  if (activeOperations > 0) {
    console.log(`Waiting for ${activeOperations} active operations to complete before shutdown...`);
    shutdownRequested = true;
    
    // Force shutdown after 30 seconds
    setTimeout(() => {
      console.log('Force shutdown after timeout');
      performShutdown();
    }, 30000);
  } else {
    console.log('No active operations, shutting down immediately');
    performShutdown();
  }
});

process.on('SIGINT', () => {
  console.log('SIGINT received, shutting down gracefully');
  shutdownRequested = true;
  if (activeOperations === 0) {
    performShutdown();
  }
});