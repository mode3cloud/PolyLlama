-- Session Manager Module for Unified LLM Gateway
-- Handles session storage and retrieval using Redis

local cjson = require "cjson"
local redis = require "resty.redis"

local _M = {}

-- Initialize Redis connection
local function get_redis_connection()
    local red = redis:new()
    red:set_timeout(1000)  -- 1 second timeout

    -- Connect to Redis (using Docker service name)
    local ok, err = red:connect("redis", 6379)
    if not ok then
        ngx.log(ngx.ERR, "Failed to connect to Redis: ", err)
        return nil, err
    end

    return red
end

-- Close Redis connection (return to pool)
local function close_redis_connection(red)
    local ok, err = red:set_keepalive(10000, 100)
    if not ok then
        ngx.log(ngx.ERR, "Failed to set Redis keepalive: ", err)
    end
end

-- Get all sessions
function _M.get_all_sessions()
    local red, err = get_redis_connection()
    if not red then
        return nil, err
    end

    -- Get the sessions list from the polyllama:sessions key
    local sessions_data, err = red:get("polyllama:sessions")
    if not sessions_data or sessions_data == ngx.null then
        close_redis_connection(red)
        return {sessions = {}}
    end

    local sessions = cjson.decode(sessions_data)

    close_redis_connection(red)
    return {sessions = sessions}
end

-- Get specific session
function _M.get_session(session_id)
    local red, err = get_redis_connection()
    if not red then
        return nil, err
    end

    -- Get session data from polyllama:session:id key
    local session_key = "polyllama:session:" .. session_id
    local session_data, err = red:get(session_key)
    if not session_data or session_data == ngx.null then
        close_redis_connection(red)
        return nil, "Session not found"
    end

    local session = cjson.decode(session_data)

    close_redis_connection(red)
    return session
end

-- Create or update session
function _M.update_session(session_id, data)
    local red, err = get_redis_connection()
    if not red then
        return nil, err
    end

    local session_key = "polyllama:session:" .. session_id

    -- Get existing session or create new
    local existing, err = red:get(session_key)
    local session_data = {}
    if existing and existing ~= ngx.null then
        session_data = cjson.decode(existing)
    else
        session_data = {
            id = session_id,
            created_at = os.date("!%Y-%m-%dT%H:%M:%S"),
            message_count = 0,
            messages = {}
        }
    end

    -- Update fields if provided
    if data.model then
        session_data.model = data.model
    end
    if data.title then
        session_data.title = data.title
    end
    if data.messages then
        session_data.messages = data.messages
    end
    if data.message_count then
        session_data.message_count = data.message_count
    end

    -- Save session
    local ok, err = red:set(session_key, cjson.encode(session_data))
    if not ok then
        close_redis_connection(red)
        return nil, err
    end

    -- Update sessions list
    local sessions_data, err = red:get("polyllama:sessions")
    local sessions = {sessions = {}}
    if sessions_data and sessions_data ~= ngx.null then
        sessions = cjson.decode(sessions_data)
    end

    -- Check if session already exists in list
    local found = false
    for _, s in ipairs(sessions.sessions or {}) do
        if s.id == session_id then
            found = true
            s.message_count = session_data.message_count
            break
        end
    end

    -- Add if new
    if not found then
        table.insert(sessions.sessions, {
            id = session_id,
            created_at = session_data.created_at,
            message_count = session_data.message_count or 0
        })
    end

    red:set("polyllama:sessions", cjson.encode(sessions))

    -- Set expiration (7 days)
    red:expire(session_key, 604800)

    close_redis_connection(red)
    return session_data
end

-- Delete session
function _M.delete_session(session_id)
    local red, err = get_redis_connection()
    if not red then
        return nil, err
    end

    -- Delete session key
    local session_key = "polyllama:session:" .. session_id
    red:del(session_key)

    -- Remove from sessions list
    local sessions_data, err = red:get("polyllama:sessions")
    if sessions_data and sessions_data ~= ngx.null then
        local sessions = cjson.decode(sessions_data)
        local new_sessions = {sessions = {}}

        for _, s in ipairs(sessions.sessions or {}) do
            if s.id ~= session_id then
                table.insert(new_sessions.sessions, s)
            end
        end

        red:set("polyllama:sessions", cjson.encode(new_sessions))
    end

    close_redis_connection(red)
    return true
end

-- Get tool selection for session
function _M.get_tool_selection(session_id)
    local red, err = get_redis_connection()
    if not red then
        return nil, err
    end

    local tools_key = "session:" .. session_id .. ":selected_tools"
    local selected_tools, err = red:smembers(tools_key)

    if not selected_tools or selected_tools == ngx.null then
        selected_tools = {}
    end

    close_redis_connection(red)
    return {
        session_id = session_id,
        selected_tools = selected_tools
    }
end

-- Update tool selection for session
function _M.update_tool_selection(session_id, selected_tools)
    local red, err = get_redis_connection()
    if not red then
        return nil, err
    end

    local tools_key = "session:" .. session_id .. ":selected_tools"

    -- Clear existing selection
    red:del(tools_key)

    -- Add new selection
    if selected_tools and #selected_tools > 0 then
        for _, tool in ipairs(selected_tools) do
            red:sadd(tools_key, tool)
        end
    end

    -- Set expiration (7 days)
    red:expire(tools_key, 604800)

    close_redis_connection(red)
    return {
        session_id = session_id,
        selected_tools = selected_tools
    }
end

return _M