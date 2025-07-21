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
const API_KEY = process.env.POLYLLAMA_API_KEY;

// PolyLlama tool definitions - these are the capabilities we expose via MCP
const POLYLLAMA_TOOLS = [
  {
    name: 'polyllama_list_models',
    description: 'List all available models across PolyLlama instances',
    inputSchema: {
      type: 'object',
      properties: {
        show_details: {
          type: 'boolean',
          description: 'Include detailed model information',
          default: false
        }
      }
    }
  },
  {
    name: 'polyllama_load_model',
    description: 'Load a model on the optimal PolyLlama instance',
    inputSchema: {
      type: 'object',
      properties: {
        name: {
          type: 'string',
          description: 'Name of the model to load'
        },
        force_instance: {
          type: 'string',
          description: 'Optional: Force loading on specific instance (polyllama1, polyllama2, etc.)'
        }
      },
      required: ['name']
    }
  },
  {
    name: 'polyllama_get_status',
    description: 'Get PolyLlama system status and health information',
    inputSchema: {
      type: 'object',
      properties: {
        include_metrics: {
          type: 'boolean',
          description: 'Include GPU and performance metrics',
          default: false
        }
      }
    }
  },
  {
    name: 'polyllama_get_running_models',
    description: 'Get currently running models across all instances',
    inputSchema: {
      type: 'object',
      properties: {}
    }
  },
  {
    name: 'polyllama_route_request',
    description: 'Execute a direct Ollama API request with PolyLlama routing',
    inputSchema: {
      type: 'object',
      properties: {
        method: {
          type: 'string',
          enum: ['GET', 'POST', 'DELETE'],
          description: 'HTTP method'
        },
        endpoint: {
          type: 'string',
          description: 'Ollama API endpoint (e.g., /api/generate, /api/chat)'
        },
        payload: {
          type: 'object',
          description: 'Request payload for POST requests'
        }
      },
      required: ['method', 'endpoint']
    }
  },
  {
    name: 'polyllama_get_model_mappings',
    description: 'Get current model-to-instance mappings and routing information',
    inputSchema: {
      type: 'object',
      properties: {}
    }
  }
];

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

// Tool execution implementations
const toolExecutors = {
  async polyllama_list_models(args) {
    const showDetails = args.show_details || false;
    const endpoint = showDetails ? '/api/tags?details=true' : '/api/tags';
    const result = await makePolyllamaRequest(endpoint);
    
    return {
      type: 'text',
      text: `Available models in PolyLlama:\n\n${JSON.stringify(result, null, 2)}`
    };
  },

  async polyllama_load_model(args) {
    const { name, force_instance } = args;
    
    // Use PolyLlama's model loading endpoint
    const payload = {
      name,
      stream: false,
      ...(force_instance && { instance: force_instance })
    };

    const result = await makePolyllamaRequest('/api/pull', {
      method: 'POST',
      body: JSON.stringify(payload)
    });

    return {
      type: 'text',
      text: `Model loading initiated: ${name}\n\nResponse: ${JSON.stringify(result, null, 2)}`
    };
  },

  async polyllama_get_status(args) {
    const includeMetrics = args.include_metrics || false;
    
    // Get basic system status
    let statusInfo = {};
    
    try {
      // Get instance status
      const instanceStatus = await makePolyllamaRequest('/api/polyllama/instance-status');
      statusInfo.instances = instanceStatus;

      // Get model mappings
      const modelMappings = await makePolyllamaRequest('/api/polyllama/model-mappings');
      statusInfo.modelMappings = modelMappings;

      if (includeMetrics) {
        try {
          const metrics = await makePolyllamaRequest('/api/polyllama/gpu-metrics');
          statusInfo.metrics = metrics;
        } catch (error) {
          statusInfo.metricsError = `Failed to get metrics: ${error.message}`;
        }
      }

    } catch (error) {
      statusInfo.error = `Failed to get status: ${error.message}`;
    }

    return {
      type: 'text',
      text: `PolyLlama System Status:\n\n${JSON.stringify(statusInfo, null, 2)}`
    };
  },

  async polyllama_get_running_models(args) {
    const result = await makePolyllamaRequest('/api/polyllama/running-models');
    
    return {
      type: 'text',
      text: `Currently running models:\n\n${JSON.stringify(result, null, 2)}`
    };
  },

  async polyllama_route_request(args) {
    const { method, endpoint, payload } = args;
    
    const options = {
      method: method.toUpperCase()
    };

    if (payload && (method.toLowerCase() === 'post' || method.toLowerCase() === 'put')) {
      options.body = JSON.stringify(payload);
    }

    const result = await makePolyllamaRequest(endpoint, options);
    
    return {
      type: 'text',
      text: `${method} ${endpoint} response:\n\n${JSON.stringify(result, null, 2)}`
    };
  },

  async polyllama_get_model_mappings(args) {
    const result = await makePolyllamaRequest('/api/polyllama/model-mappings');
    
    return {
      type: 'text',
      text: `Current model-to-instance mappings:\n\n${JSON.stringify(result, null, 2)}`
    };
  }
};

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
    return {
      tools: POLYLLAMA_TOOLS
    };
  });

  mcpServer.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    
    const executor = toolExecutors[name];
    if (!executor) {
      throw new Error(`Unknown tool: ${name}`);
    }

    try {
      const result = await executor(args || {});
      return {
        content: [result]
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
app.get('/info', (req, res) => {
  res.json({
    name: 'PolyLlama MCP Server',
    version: '1.0.0',
    description: 'MCP Server that exposes PolyLlama orchestration capabilities as tools',
    tools: POLYLLAMA_TOOLS.map(tool => ({
      name: tool.name,
      description: tool.description
    })),
    endpoints: {
      sse: '/sse',
      health: '/health',
      info: '/info'
    },
    polyllamaBaseUrl: OLLAMA_BASE_URL,
    authenticationRequired: !!API_KEY
  });
});

// Main SSE endpoint for MCP protocol
app.get('/sse', async (req, res) => {
  console.log('New MCP client connection via SSE');
  
  try {
    // Create a new MCP server instance for this connection
    const mcpServer = createMCPServer();
    
    // Create SSE transport - let it handle all header setup
    const transport = new SSEServerTransport('/sse', res);
    
    // Handle client disconnect before connecting
    req.on('close', () => {
      console.log('MCP client disconnected');
      if (transport.close) {
        transport.close();
      }
    });

    req.on('error', (error) => {
      console.error('SSE request error:', error);
      if (transport.close) {
        transport.close();
      }
    });
    
    // Connect server to transport
    await mcpServer.connect(transport);
    console.log('MCP server connected to SSE transport successfully');

  } catch (error) {
    console.error('Failed to initialize MCP connection:', error);
    
    // Only try to send error if we haven't started SSE yet
    if (!res.headersSent) {
      res.status(500).json({
        error: 'Failed to initialize MCP connection',
        message: error.message,
        stack: process.env.NODE_ENV === 'development' ? error.stack : undefined
      });
    } else {
      // If SSE has started, write an error event
      try {
        res.write(`data: ${JSON.stringify({
          error: 'MCP connection failed',
          message: error.message
        })}\n\n`);
        res.end();
      } catch (writeError) {
        console.error('Failed to write error to SSE stream:', writeError);
      }
    }
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
  
  console.log('\n🛠️  Available Tools:');
  POLYLLAMA_TOOLS.forEach(tool => {
    console.log(`   • ${tool.name}: ${tool.description}`);
  });
  
  console.log('\n✨ PolyLlama MCP Server ready for connections!');
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