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

// Initialize MCP server connection
async function initializeMcpServer(name, config) {
  console.log(`Initializing MCP server: ${name}`);
  
  try {
    // Spawn the MCP server process
    const serverProcess = spawn(config.command, config.args, {
      env: { ...process.env, ...config.env },
      stdio: ['pipe', 'pipe', 'pipe']
    });

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

    // Store connection
    mcpConnections.set(name, {
      client,
      transport,
      process: serverProcess,
      config
    });

    console.log(`Successfully connected to MCP server: ${name}`);
    return true;
  } catch (error) {
    console.error(`Failed to initialize MCP server ${name}:`, error);
    return false;
  }
}

// Initialize all MCP servers
async function initializeAllServers() {
  const config = await loadConfig();
  const results = {};

  for (const [name, serverConfig] of Object.entries(config.mcpServers)) {
    results[name] = await initializeMcpServer(name, serverConfig);
  }

  return results;
}

// API Routes

// Get status of all MCP servers
app.get('/status', async (req, res) => {
  const status = {};
  
  for (const [name, connection] of mcpConnections.entries()) {
    status[name] = {
      connected: connection.client.getServerCapabilities() !== null,
      capabilities: connection.client.getServerCapabilities()
    };
  }

  res.json({
    servers: status,
    total: mcpConnections.size
  });
});

// List all available tools
app.get('/tools', async (req, res) => {
  const allTools = [];

  for (const [serverName, connection] of mcpConnections.entries()) {
    try {
      const tools = await connection.client.listTools();
      
      // Add server name to each tool
      for (const tool of tools.tools || []) {
        allTools.push({
          ...tool,
          server: serverName
        });
      }
    } catch (error) {
      console.error(`Failed to list tools from ${serverName}:`, error);
    }
  }

  res.json({ tools: allTools });
});

// Execute a tool
app.post('/execute', async (req, res) => {
  const { toolName, arguments: args, server } = req.body;

  if (!server || !mcpConnections.has(server)) {
    return res.status(400).json({ error: 'Invalid or missing server' });
  }

  const connection = mcpConnections.get(server);

  try {
    const result = await connection.client.callTool({
      name: toolName,
      arguments: args
    });

    res.json({
      success: true,
      result: result.content
    });
  } catch (error) {
    console.error(`Failed to execute tool ${toolName}:`, error);
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

app.listen(PORT, async () => {
  console.log(`MCP Bridge server running on port ${PORT}`);
  
  // Initialize MCP servers on startup
  const results = await initializeAllServers();
  console.log('MCP servers initialization results:', results);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM received, shutting down gracefully');
  
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