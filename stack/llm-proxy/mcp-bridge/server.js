import express from 'express';
import cors from 'cors';
import { spawn } from 'child_process';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { readFile } from 'fs/promises';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app = express();
app.use(cors());
app.use(express.json());

// Store active MCP connections
const mcpConnections = new Map();

// Store initialization state and tool counts per server
const serverState = new Map();

// Configuration constants
const INIT_RETRY_DELAY = 2000; // 2 seconds
const INIT_MAX_RETRIES = 3;
const HEALTH_CHECK_INTERVAL = 30000; // 30 seconds

// Load MCP configuration
async function loadConfig() {
  try {
    const configPath = process.env.MCP_CONFIG_PATH || '/app/mcp-config.json';
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
  
  try {
    // Create transport
    const transport = new StdioClientTransport({
      command: config.command,
      args: config.args,
      env: { ...process.env, ...config.env }
    });

    // Create client
    const client = new Client({
      name: `mcp-bridge-${name}`,
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

// API Routes

// Get status of all MCP servers
app.get('/status', async (req, res) => {
  const status = {};
  const includeTools = req.query.includeTools === 'true';
  
  // Include both configured servers and their actual state
  const config = await loadConfig();
  const allServerNames = new Set([
    ...Object.keys(config.mcpServers),
    ...mcpConnections.keys()
  ]);

  for (const name of allServerNames) {
    const state = serverState.get(name);
    const connection = mcpConnections.get(name);
    
    const serverStatus = {
      connected: state?.connected || false,
      toolCount: state?.toolCount || 0,
      lastError: state?.lastError || null,
      lastHealthCheck: state?.lastHealthCheck || null,
      configured: config.mcpServers.hasOwnProperty(name),
      capabilities: connection?.client?.getServerCapabilities() || null
    };

    // Include tool details if requested
    if (includeTools && connection && state?.connected) {
      try {
        const tools = await connection.client.listTools();
        // Prefix tool names with server name
        const safeName = name.replace(/-/g, '_');
        serverStatus.tools = (tools.tools || []).map(tool => ({
          ...tool,
          name: `${safeName}__${tool.name}`,
          originalName: tool.name,
          server: name
        }));
      } catch (error) {
        console.error(`Failed to list tools for status from ${name}:`, error);
        serverStatus.tools = [];
      }
    }

    status[name] = serverStatus;
  }

  res.json({
    servers: status,
    total: mcpConnections.size,
    totalConfigured: Object.keys(config.mcpServers).length
  });
});

// List all available tools
app.get('/tools', async (req, res) => {
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

  res.json({ 
    tools: allTools, 
    errors: Object.keys(errors).length > 0 ? errors : undefined,
    totalTools: allTools.length
  });
});

// Execute a tool
app.post('/execute', async (req, res) => {
  const { toolName, arguments: args, server } = req.body;

  // Handle prefixed tool names (server__toolName)
  let actualToolName = toolName;
  let targetServer = server;
  
  if (toolName.includes('__')) {
    const [prefix, ...nameParts] = toolName.split('__');
    // Try to find the actual server name (with hyphens) from the safe name (with underscores)
    for (const [serverName] of mcpConnections.entries()) {
      if (serverName.replace(/-/g, '_') === prefix) {
        targetServer = serverName;
        break;
      }
    }
    // If not found, use the prefix as-is (might be a server without hyphens)
    if (targetServer === server) {
      targetServer = prefix;
    }
    actualToolName = nameParts.join('__'); // Handle tool names that might contain __
  }

  if (!targetServer || !mcpConnections.has(targetServer)) {
    return res.status(400).json({ error: `Invalid or missing server: ${targetServer}` });
  }

  const connection = mcpConnections.get(targetServer);

  try {
    const result = await connection.client.callTool({
      name: actualToolName,
      arguments: args
    });

    res.json({
      success: true,
      result: result.content
    });
  } catch (error) {
    console.error(`Failed to execute tool ${actualToolName} on ${targetServer}:`, error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

// Reinitialize servers
app.post('/reinitialize', async (req, res) => {
  // Close existing connections
  for (const [name, connection] of mcpConnections.entries()) {
    try {
      await connection.client.close();
      if (connection.process) {
        connection.process.kill();
      }
    } catch (error) {
      console.error(`Error closing connection ${name}:`, error);
    }
  }
  
  mcpConnections.clear();
  
  // Reinitialize
  const results = await initializeAllServers();
  res.json({ results });
});

// Start server
const PORT = process.env.MCP_BRIDGE_PORT || 3000;
let healthCheckInterval;

app.listen(PORT, async () => {
  console.log(`MCP Bridge server running on port ${PORT}`);
  
  // Initialize MCP servers on startup
  const results = await initializeAllServers();
  console.log('MCP servers initialization results:', results);
  
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
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM received, shutting down gracefully');
  
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
});