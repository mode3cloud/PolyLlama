-- MCP Manager Module for Unified LLM Gateway
-- Proxies requests to the MCP Bridge service

local cjson = require "cjson"
local http = require "resty.http"

local _M = {}

-- MCP Bridge configuration
local MCP_BRIDGE_URL = "http://mcp-bridge:3001"
local TIMEOUT_MS = 10000  -- 10 seconds

-- Helper function for HTTP requests
local function make_request(path, method, body)
    local httpc = http.new()
    httpc:set_timeout(TIMEOUT_MS)

    local headers = {
        ["Content-Type"] = "application/json",
        ["Accept"] = "application/json"
    }

    local options = {
        method = method or "GET",
        headers = headers
    }

    if body then
        options.body = cjson.encode(body)
    end

    local res, err = httpc:request_uri(MCP_BRIDGE_URL .. path, options)

    if not res then
        ngx.log(ngx.ERR, "Failed to connect to MCP Bridge: ", err)
        return nil, err
    end

    if res.status ~= 200 then
        ngx.log(ngx.ERR, "MCP Bridge returned status ", res.status, ": ", res.body)
        return nil, "HTTP " .. res.status
    end

    local success, data = pcall(cjson.decode, res.body)
    if not success then
        ngx.log(ngx.ERR, "Failed to decode MCP Bridge response: ", data)
        return nil, "Invalid JSON response"
    end

    return data
end

-- Get MCP status
function _M.get_status()
    local data, err = make_request("/api/mcp/status")

    if not data then
        return {
            initialized = false,
            available = false,
            error = "MCP Bridge unavailable: " .. (err or "unknown error"),
            message = "Unable to connect to MCP Bridge service"
        }
    end

    return data
end

-- Get available tools
function _M.get_tools()
    local data, err = make_request("/api/mcp/tools")

    if not data then
        return {
            tools = {},
            error = "Failed to fetch tools: " .. (err or "unknown error")
        }
    end

    return data
end

-- Get formatted tools (OpenAI-compatible format)
function _M.get_formatted_tools()
    local data, err = make_request("/api/mcp/tools/formatted")

    if not data then
        return {
            tools = {},
            error = "Failed to fetch formatted tools: " .. (err or "unknown error")
        }
    end

    return data
end

-- Execute a tool with SSE streaming support
function _M.execute_tool(tool_name, arguments)
    -- For SSE streaming, we need to use a different approach
    local httpc = http.new()
    httpc:set_timeout(30000)  -- 30 seconds for tool execution

    local headers = {
        ["Content-Type"] = "application/json",
        ["Accept"] = "text/event-stream"
    }

    local body = cjson.encode({
        tool_name = tool_name,
        arguments = arguments or {}
    })

    -- Use the streaming endpoint
    local res, err = httpc:request_uri(MCP_BRIDGE_URL .. "/api/mcp/execute/stream", {
        method = "POST",
        headers = headers,
        body = body
    })

    if not res then
        ngx.log(ngx.ERR, "Failed to execute tool: ", err)
        return {
            tool_name = tool_name,
            result = nil,
            success = false,
            error = "Failed to execute tool: " .. (err or "unknown error")
        }
    end

    -- Parse SSE stream
    local result = nil
    local success = false
    local error_msg = nil

    -- Process SSE events
    for line in res.body:gmatch("[^\r\n]+") do
        if line:match("^data:") then
            local json_str = line:sub(6)  -- Remove "data: " prefix
            local ok, event = pcall(cjson.decode, json_str)

            if ok and event then
                if event.event == "result" and event.success then
                    result = event.result
                    success = true
                elseif event.event == "error" then
                    error_msg = event.error
                    success = false
                end
            end
        end
    end

    return {
        tool_name = tool_name,
        result = result,
        success = success,
        error = error_msg
    }
end

-- Execute tool without streaming (simpler, non-SSE version)
function _M.execute_tool_simple(tool_name, arguments)
    local data, err = make_request("/api/mcp/execute", "POST", {
        tool_name = tool_name,
        arguments = arguments or {}
    })

    if not data then
        return {
            tool_name = tool_name,
            result = nil,
            success = false,
            error = "Failed to execute tool: " .. (err or "unknown error")
        }
    end

    return data
end

-- Health check for MCP Bridge
function _M.health_check()
    local httpc = http.new()
    httpc:set_timeout(2000)  -- 2 second timeout for health check

    local res, err = httpc:request_uri(MCP_BRIDGE_URL .. "/health", {
        method = "GET"
    })

    if not res then
        return false, err
    end

    return res.status == 200, res.body
end

return _M