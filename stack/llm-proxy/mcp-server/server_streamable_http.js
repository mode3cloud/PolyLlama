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
const TOOLS_CACHE_DURATION = 30000; // 1 minute cache

// Store tool output schemas for validation and logging
const toolOutputSchemas = new Map();

// Configuration constants
const INIT_RETRY_DELAY = 2000; // 2 seconds
const INIT_MAX_RETRIES = 3;
const HEALTH_CHECK_INTERVAL = 30000; // 30 seconds
const RECONNECT_BASE_DELAY = 5000; // 5 seconds base delay for reconnection
const RECONNECT_MAX_DELAY = 300000; // 5 minutes max delay
const RECONNECT_MAX_ATTEMPTS = 10; // Maximum reconnection attempts before giving up

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
  console.log('┌─────────────────────────┬──────────┬────────────────────┬─────────────────────┐');
  console.log('│ Server Name             │ Status   │ Tools              │ Reconnect Attempts  │');
  console.log('├─────────────────────────┼──────────┼────────────────────┼─────────────────────┤');

  for (const [name, success] of servers) {
    const state = serverState.get(name);
    const toolCount = state?.toolCount || 0;
    const statusEmoji = success ? '✅' : '❌';
    const statusText = success ? 'Online' : 'Failed';
    const toolsText = success ? `${toolCount} tools` : state?.lastError || 'Error';
    const reconnectText = state?.reconnectAttempts ?
      `${state.reconnectAttempts}/${RECONNECT_MAX_ATTEMPTS}` :
      success ? 'N/A' : '0/10';

    // Pad strings for alignment
    const paddedName = name.padEnd(23);
    const paddedStatus = `${statusEmoji} ${statusText}`.padEnd(8);
    const paddedTools = toolsText.padEnd(18);
    const paddedReconnect = reconnectText.padEnd(19);

    console.log(`│ ${paddedName} │ ${paddedStatus} │ ${paddedTools} │ ${paddedReconnect} │`);
  }

  console.log('└─────────────────────────┴──────────┴────────────────────┴─────────────────────┘');

  // Summary statistics
  console.log('\n📊 SUMMARY:');
  console.log('─'.repeat(40));
  console.log(`  Total Servers:      ${totalServers}`);
  console.log(`  ✅ Successful:      ${successfulServers}`);
  console.log(`  ❌ Failed:          ${failedServers}`);
  console.log(`  Success Rate:       ${((successfulServers / totalServers) * 100).toFixed(1)}%`);

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
      console.error(`❌ Transport error for ${name}:`, error);

      // Check if this is a session error
      const isSessionError = error.message && (
        error.message.includes('No valid session ID provided') ||
        error.message.includes('session') ||
        error.message.includes('Session')
      );

      if (isSessionError) {
        console.log(`📌 Session error detected for ${name}, will attempt reconnection`);
      }

      // Mark server as disconnected and remove connection
      const currentState = serverState.get(name) || {};
      serverState.set(name, {
        ...currentState,
        connected: false,
        toolCount: 0,
        lastError: error.message,
        initTime: Date.now()
      });
      mcpConnections.delete(name);

      // Trigger reconnection attempt after a short delay
      setTimeout(() => {
        reconnectMcpServer(name).catch(err => {
          console.error(`Failed to trigger reconnection for ${name}:`, err);
        });
      }, 1000);
    };

    transport.onClose = () => {
      console.log(`🔌 Transport closed for ${name}`);
      // Mark server as disconnected and remove connection
      const currentState = serverState.get(name) || {};
      serverState.set(name, {
        ...currentState,
        connected: false,
        toolCount: 0,
        lastError: 'Transport closed',
        initTime: Date.now()
      });
      mcpConnections.delete(name);

      // Trigger reconnection attempt after a short delay
      setTimeout(() => {
        reconnectMcpServer(name).catch(err => {
          console.error(`Failed to trigger reconnection for ${name}:`, err);
        });
      }, 1000);
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
      initTime: Date.now(),
      reconnectAttempts: 0,
      lastReconnectAttempt: null,
      nextReconnectDelay: RECONNECT_BASE_DELAY
    });

    console.log(`Successfully connected to MCP server: ${name} with ${toolCount} tools`);
    return true;
  } catch (error) {
    console.error(`Failed to initialize MCP server ${name}:`, error);

    // Store failed state
    const currentState = serverState.get(name) || {};
    serverState.set(name, {
      connected: false,
      toolCount: 0,
      lastError: error.message,
      initTime: Date.now(),
      reconnectAttempts: currentState.reconnectAttempts || 0,
      lastReconnectAttempt: currentState.lastReconnectAttempt || null,
      nextReconnectDelay: currentState.nextReconnectDelay || RECONNECT_BASE_DELAY
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

// Reconnect to a failed MCP server with exponential backoff
async function reconnectMcpServer(name) {
  const state = serverState.get(name);
  if (!state || state.connected) {
    return true; // Already connected
  }

  // Check if we should attempt reconnection
  const now = Date.now();
  if (state.lastReconnectAttempt && (now - state.lastReconnectAttempt) < state.nextReconnectDelay) {
    return false; // Too soon to retry
  }

  if (state.reconnectAttempts >= RECONNECT_MAX_ATTEMPTS) {
    console.log(`⚠️  Server ${name} has exceeded maximum reconnection attempts (${RECONNECT_MAX_ATTEMPTS}), giving up`);
    return false; // Exceeded max attempts
  }

  // Check if this is a session-related reconnection
  const isSessionError = state.lastError && (
    state.lastError.includes('No valid session ID provided') ||
    state.lastError.includes('session') ||
    state.lastError.includes('Session')
  );

  if (isSessionError) {
    console.log(`🔑 Reconnecting ${name} due to session error: ${state.lastError}`);
  }

  console.log(`🔄 Attempting to reconnect to MCP server: ${name} (attempt ${state.reconnectAttempts + 1}/${RECONNECT_MAX_ATTEMPTS})`);

  // Clean up existing connection if any
  const existingConnection = mcpConnections.get(name);
  if (existingConnection) {
    try {
      existingConnection.client.close();
      if (existingConnection.transport) {
        existingConnection.transport.close();
      }
    } catch (error) {
      console.log(`Warning: Error cleaning up existing connection for ${name}:`, error.message);
    }
    mcpConnections.delete(name);
  }

  // Update reconnection state
  const nextDelay = Math.min(
    state.nextReconnectDelay * 2, // Exponential backoff
    RECONNECT_MAX_DELAY
  );

  serverState.set(name, {
    ...state,
    reconnectAttempts: state.reconnectAttempts + 1,
    lastReconnectAttempt: now,
    nextReconnectDelay: nextDelay
  });

  // Load config and attempt reconnection
  try {
    const config = await loadConfig();
    const serverConfig = config.mcpServers[name];

    if (!serverConfig) {
      console.error(`⚠️  No configuration found for server: ${name}`);
      return false;
    }

    // Use the existing initialization function but without internal retries
    const success = await initializeMcpServer(name, serverConfig, 0);

    if (success) {
      console.log(`✅ Successfully reconnected to MCP server: ${name}`);
      // Reset reconnection state on successful connection
      const currentState = serverState.get(name);
      serverState.set(name, {
        ...currentState,
        reconnectAttempts: 0,
        lastReconnectAttempt: null,
        nextReconnectDelay: RECONNECT_BASE_DELAY
      });

      // Invalidate tools cache to refetch from reconnected server
      cachedTools = [];
      lastToolsFetch = 0;

      return true;
    }

    return false;
  } catch (error) {
    console.error(`❌ Failed to reconnect to MCP server ${name}:`, error.message);
    return false;
  }
}

// Health check for a single server
async function checkServerHealth(name) {
  const connection = mcpConnections.get(name);
  const state = serverState.get(name) || {
    connected: false,
    toolCount: 0,
    reconnectAttempts: 0,
    lastReconnectAttempt: null,
    nextReconnectDelay: RECONNECT_BASE_DELAY
  };

  if (!connection) {
    serverState.set(name, { ...state, connected: false, lastError: 'No connection' });
    // Attempt reconnection for servers without connections
    await reconnectMcpServer(name);
    return serverState.get(name)?.connected || false;
  }

  try {
    // Try to list tools as a health check
    const tools = await connection.client.listTools();
    const toolCount = tools.tools?.length || 0;

    serverState.set(name, {
      ...state,
      connected: true,
      toolCount,
      lastError: null,
      lastHealthCheck: Date.now(),
      reconnectAttempts: 0, // Reset on successful health check
      lastReconnectAttempt: null,
      nextReconnectDelay: RECONNECT_BASE_DELAY
    });

    connection.lastHealthCheck = Date.now();
    return true;
  } catch (error) {
    console.error(`❌ Health check failed for ${name}:`, error.message);

    // Check if this is a session error
    const isSessionError = error.message && (
      error.message.includes('No valid session ID provided') ||
      error.message.includes('session') ||
      error.message.includes('Session')
    );

    if (isSessionError) {
      console.log(`📌 Session error detected during health check for ${name}`);
    }

    serverState.set(name, {
      ...state,
      connected: false,
      lastError: error.message,
      lastHealthCheck: Date.now()
    });

    // Remove failed connection
    mcpConnections.delete(name);

    // Attempt reconnection
    await reconnectMcpServer(name);
    return serverState.get(name)?.connected || false;
  }
}

// Periodic health check for all servers
async function runHealthChecks() {
  // Check all configured servers, not just connected ones
  const config = await loadConfig();
  const configuredServers = Object.keys(config.mcpServers);

  for (const name of configuredServers) {
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
          const prefixedName = `${safeServerName}__${tool.name}`;
          
          // Store output schema if present
          if (tool.outputSchema) {
            toolOutputSchemas.set(prefixedName, tool.outputSchema);
          }
          
          allTools.push({
            ...tool,
            name: prefixedName,
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
        reject(new Error(`Tool execution timed out after ${TOOL_TIMEOUT / 1000} seconds`));
      }, TOOL_TIMEOUT);
    });

    console.log(`[${toolName}] Waiting for tool completion...`);
    const result = await Promise.race([toolPromise, timeoutPromise]);
    console.log(`[${toolName}] Tool call returned:`, safeStringify(result));
    console.log(`[${toolName}] Result type:`, typeof result, 'isArray:', Array.isArray(result), 'has content:', !!result?.content, 'has structuredContent:', !!result?.structuredContent);

    // Check if this tool has an output schema
    const hasOutputSchema = toolOutputSchemas.has(toolName);
    console.log(`[${toolName}] Has output schema:`, hasOutputSchema, 'Total schemas stored:', toolOutputSchemas.size);
    
    // Log MCP spec violations
    if (hasOutputSchema) {
      if (result && result.structuredContent) {
        console.log(`✅ [${toolName}] Tool with outputSchema correctly returned structuredContent`);
      } else if (result && Array.isArray(result.content)) {
        console.warn(`⚠️  MCP SPEC VIOLATION: Tool '${toolName}' has an outputSchema but returned content array instead of structuredContent`);
        console.warn(`   This violates the MCP specification. Tools with outputSchema should return structuredContent.`);
        console.warn(`   The tool's outputSchema:`, safeStringify(toolOutputSchemas.get(toolName)));
      }
    } else {
      console.log(`[${toolName}] No output schema defined for this tool`);
    }

    // The MCP SDK callTool response should already be in the correct format
    // with a 'content' array. We just need to extract and validate it.

    // If result already has the proper MCP format with content array
    if (result && Array.isArray(result.content)) {
      console.log(`Tool ${toolName} returning properly formatted content with ${result.content.length} items`);
      return result.content;
    }

    // Fallback handling for legacy or non-standard responses
    // This ensures backward compatibility while encouraging proper format
    const content = result.content || result;

    if (Array.isArray(content) && content.length > 0 && content[0].type) {
      // Already in correct format [{type: 'text', text: '...'}]
      console.log(`Tool ${toolName} returning array content with ${content.length} items`);
      return content;
    } else if (typeof content === 'string') {
      console.log(`Tool ${toolName} returning string content (${content.length} chars) - converting to MCP format`);
      return [{
        type: 'text',
        text: content
      }];
    } else if (content && typeof content === 'object') {
      const stringified = safeStringify(content);
      console.log(`Tool ${toolName} returning object content (${stringified.length} chars) - converting to MCP format`);
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

    // Check for session-related errors and trigger reconnection
    if (error.message && (
      error.message.includes('No valid session ID provided') ||
      error.message.includes('session') ||
      error.message.includes('Session')
    )) {
      console.log(`Session error detected for ${targetServer}, triggering reconnection...`);

      // Mark server as disconnected
      const state = serverState.get(targetServer);
      if (state) {
        serverState.set(targetServer, {
          ...state,
          connected: false,
          lastError: error.message
        });
      }

      // Remove the failed connection
      mcpConnections.delete(targetServer);

      // Trigger reconnection
      const reconnected = await reconnectMcpServer(targetServer);

      if (reconnected) {
        console.log(`Reconnection successful for ${targetServer}, retrying tool execution...`);
        // Retry the tool execution after successful reconnection
        return executeTool(toolName, args);
      } else {
        throw new Error(`Tool execution failed after reconnection attempt: ${error.message}`);
      }
    }

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

// Server status endpoint with reconnection information
app.get('/status', async (req, res) => {
  try {
    const config = await loadConfig();
    const configuredServers = Object.keys(config.mcpServers);
    const status = {};

    for (const name of configuredServers) {
      const state = serverState.get(name);
      const connection = mcpConnections.get(name);

      status[name] = {
        connected: state?.connected || false,
        toolCount: state?.toolCount || 0,
        lastError: state?.lastError || null,
        lastHealthCheck: state?.lastHealthCheck || null,
        reconnectAttempts: state?.reconnectAttempts || 0,
        maxReconnectAttempts: RECONNECT_MAX_ATTEMPTS,
        lastReconnectAttempt: state?.lastReconnectAttempt || null,
        nextReconnectDelay: state?.nextReconnectDelay || RECONNECT_BASE_DELAY,
        hasConnection: !!connection,
        initTime: state?.initTime || null
      };
    }

    res.json({
      service: 'polyllama-mcp-server-streamable-http',
      timestamp: new Date().toISOString(),
      servers: status,
      config: {
        healthCheckInterval: HEALTH_CHECK_INTERVAL,
        reconnectBaseDelay: RECONNECT_BASE_DELAY,
        reconnectMaxDelay: RECONNECT_MAX_DELAY,
        maxReconnectAttempts: RECONNECT_MAX_ATTEMPTS
      }
    });
  } catch (error) {
    res.status(500).json({
      error: 'Failed to get server status',
      message: error.message
    });
  }
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
          console.log(`[${requestId}] Result content length: ${JSON.stringify(finalEvent).length} chars`);
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

// SSE endpoint that wraps MCP streamable HTTP functionality
app.get('/sse', async (req, res) => {
  const userAgent = req.headers['user-agent'] || 'unknown';
  const sessionId = uuidv4().replace(/-/g, '').substring(0, 8);

  console.log(`[${sessionId}] SSE connection from: ${userAgent}`);

  // Set SSE headers
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, api-key, x-api-key'
  });

  // Send initial connection event
  res.write(`event: connected\n`);
  res.write(`data: {"sessionId": "${sessionId}", "message": "SSE connection established"}\n\n`);

  // Send endpoint event for clients expecting it
  const endpointUrl = `/messages/?session_id=${sessionId}`;
  res.write(`event: endpoint\n`);
  res.write(`data: ${endpointUrl}\n\n`);

  console.log(`[${sessionId}] SSE connection established, endpoint: ${endpointUrl}`);

  // Handle connection events
  req.on('close', () => {
    console.log(`[${sessionId}] SSE client disconnected`);
  });

  req.on('error', (error) => {
    console.error(`[${sessionId}] SSE connection error:`, error.message);
  });

  // Keep connection alive with periodic ping
  const pingInterval = setInterval(() => {
    if (!res.destroyed) {
      res.write(`event: ping\n`);
      res.write(`data: {"timestamp": "${new Date().toISOString()}"}\n\n`);
    } else {
      clearInterval(pingInterval);
    }
  }, 30000); // Ping every 30 seconds

  // Clean up on disconnect
  req.on('close', () => {
    clearInterval(pingInterval);
  });
});

// Messages endpoint that wraps MCP functionality for SSE clients
app.post('/messages/', express.json(), async (req, res) => {
  const sessionId = req.query.session_id;
  const requestId = uuidv4().replace(/-/g, '').substring(0, 8);

  if (!sessionId) {
    return res.status(400).json({
      error: 'session_id is required',
      code: 400
    });
  }

  console.log(`[${sessionId}:${requestId}] Messages endpoint request:`, req.body);

  try {
    const { method, params, id, jsonrpc } = req.body;

    // Create a mock request object with SSE accept header
    const mockReq = {
      headers: {
        'accept': 'text/event-stream',
        'user-agent': req.headers['user-agent'] || 'sse-wrapper'
      },
      body: req.body,
      on: () => { } // Mock event handlers
    };

    let response;

    if (method === 'initialize') {
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

      try {
        console.log(`[${sessionId}:${requestId}] Executing tool: ${name}`);
        const content = await executeTool(name, args || {});
        response = {
          jsonrpc: '2.0',
          id,
          result: { content }
        };
        console.log(`[${sessionId}:${requestId}] Tool execution completed: ${name}`);
      } catch (error) {
        console.error(`[${sessionId}:${requestId}] Tool execution error:`, error);
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

    console.log(`[${sessionId}:${requestId}] Sending response for method: ${method}`);
    res.json(response);

  } catch (error) {
    console.error(`[${sessionId}:${requestId}] Error processing messages request:`, error);

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
let healthCheckInterval;

app.listen(PORT, '0.0.0.0', async () => {
  console.log(`🚀 PolyLlama MCP Server (Streamable HTTP) running on port ${PORT}`);
  console.log(`📡 Main MCP endpoint: http://localhost:${PORT}/mcp`);
  console.log(`🔍 Health check: http://localhost:${PORT}/health`);
  console.log(`📊 Server status: http://localhost:${PORT}/status`);
  console.log(`ℹ️  Server info: http://localhost:${PORT}/info`);
  console.log(`📡 SSE endpoint: http://localhost:${PORT}/sse`);
  console.log(`💬 Messages endpoint: http://localhost:${PORT}/messages/`);
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
    console.log('   • Automatic reconnection with exponential backoff');
    console.log('   • Health monitoring and status reporting');
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