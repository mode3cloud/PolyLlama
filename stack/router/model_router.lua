local _M = {}
local cjson = require "cjson"





-- Documentation for shared memory usage:
-- model_mappings: Stores model to instance mappings and loading locks
--   Format for mappings: Base64-encoded JSON with structure {instance = "ollama1", running = true/nil}
--   Format for locks: "loading:modelname" = "instance"
--   Format: "client_id:model_name" = "instance"

-- Function to log request context (num_ctx) for all requests
function _M.log_request_context()
    local request_uri = ngx.var.request_uri
    local request_method = ngx.req.get_method()
    local num_ctx = nil
    
    -- Try to get num_ctx from request body for POST/PUT requests
    if request_method == "POST" or request_method == "PUT" then
        ngx.req.read_body()
        local body_data = ngx.req.get_body_data()
        
        if not body_data then
            local body_file = ngx.req.get_body_file()
            if body_file then
                local file, err = io.open(body_file, "rb")
                if file then
                    body_data = file:read("*all")
                    file:close()
                end
            end
        end
        
        if body_data then
            local success, body = pcall(cjson.decode, body_data)
            if success and body then
                if body.options and body.options.num_ctx then
                    num_ctx = body.options.num_ctx
                elseif body.num_ctx then
                    num_ctx = body.num_ctx
                elseif body.parameters and body.parameters.num_ctx then
                    num_ctx = body.parameters.num_ctx
                end
            end
        end
    end
    
    -- Check query parameters
    local args = ngx.req.get_uri_args()
    if args and args.num_ctx and not num_ctx then
        num_ctx = args.num_ctx
    end
    
    -- Log the context information
    if num_ctx then
        ngx.log(ngx.INFO, "REQUEST CONTEXT: num_ctx=" .. tostring(num_ctx) .. " for " .. request_method .. " " .. request_uri)
    else
        ngx.log(ngx.INFO, "REQUEST CONTEXT: num_ctx=default (not specified) for " .. request_method .. " " .. request_uri)
    end
end

-- Extract model name from various request patterns
function _M.extract_model_name()
    local request_uri = ngx.var.request_uri
    local request_method = ngx.req.get_method()
    local headers = ngx.req.get_headers()
    local model_name = nil
    
    -- Log request basics
    ngx.log(ngx.INFO, string.format("Processing request: Method=%s, URI=%s", request_method, request_uri))
    
    -- Log headers (sanitizing auth tokens)
    local headers_log = {}
    for k, v in pairs(headers) do
        if k:lower() == "authorization" or k:lower() == "api-key" then
            headers_log[k] = "REDACTED"
        else
            headers_log[k] = tostring(v)
        end
    end
    ngx.log(ngx.DEBUG, "Request headers: " .. cjson.encode(headers_log))
    
    -- Try to read request body for POST/PUT requests
    if request_method == "POST" or request_method == "PUT" then
        ngx.req.read_body()
        
        -- Get body data - either in memory or from temp file
        local body_data = ngx.req.get_body_data()
        
        if not body_data then
            -- Body might be in a temp file
            local body_file = ngx.req.get_body_file()
            
            if body_file then
                ngx.log(ngx.DEBUG, "Request body in file: " .. body_file)
                
                -- Read from temp file
                local file, err = io.open(body_file, "rb")
                if file then
                    body_data = file:read("*all")
                    file:close()
                else
                    ngx.log(ngx.ERR, "Failed to read body file: " .. (err or "unknown error"))
                end
            end
        end
        
        if body_data then
            -- Log truncated body (for privacy/size reasons)
            local log_body = body_data
            if #log_body > 1000 then
                log_body = string.sub(log_body, 1, 1000) .. "... [truncated]"
            end
            ngx.log(ngx.DEBUG, "Request body (truncated): " .. log_body)
            
            local success, body = pcall(cjson.decode, body_data)
            if success and body then
                -- Log num_ctx parameter if present
                local num_ctx = nil
                if body.options and body.options.num_ctx then
                    num_ctx = body.options.num_ctx
                elseif body.num_ctx then
                    num_ctx = body.num_ctx
                elseif body.parameters and body.parameters.num_ctx then
                    num_ctx = body.parameters.num_ctx
                end
                
                if num_ctx then
                    ngx.log(ngx.INFO, "REQUEST CONTEXT: num_ctx=" .. tostring(num_ctx) .. " for request to " .. request_uri)
                else
                    ngx.log(ngx.INFO, "REQUEST CONTEXT: num_ctx=default (not specified) for request to " .. request_uri)
                end
                
                -- First check for direct model field
                if body.model then
                    model_name = body.model
                    ngx.log(ngx.INFO, "Extracted model name from request body: " .. model_name)
                    return model_name
                end
                
                -- Check for Ollama specific format
                if body.model == nil and request_uri == "/api/generate" then
                    -- Special case for Ollama API which may use "name" field instead of "model"
                    if body.name then
                        model_name = body.name
                        ngx.log(ngx.INFO, "Extracted model name from Ollama-style 'name' field: " .. model_name)
                        return model_name
                    end
                end
                
                -- Check other common patterns
                if body.messages and body.messages[1] and body.messages[1].model then
                    model_name = body.messages[1].model
                    ngx.log(ngx.INFO, "Extracted model name from messages[1].model: " .. model_name)
                    return model_name
                elseif body.parameters and body.parameters.model then
                    model_name = body.parameters.model
                    ngx.log(ngx.INFO, "Extracted model name from parameters.model: " .. model_name)
                    return model_name
                else
                    -- Log detailed structure for debugging
                    local body_structure = {}
                    for k, v in pairs(body) do
                        if type(v) == "table" then
                            body_structure[k] = "table"
                        else
                            body_structure[k] = tostring(v):sub(1, 100)
                        end
                    end
                    ngx.log(ngx.WARN, "No model found in body. Keys present: " .. cjson.encode(body_structure))
                end
            else
                local err_msg = "Failed to parse request body JSON"
                if not success and body then
                    err_msg = err_msg .. ": " .. body
                end
                ngx.log(ngx.DEBUG, err_msg)
                
                -- Try to see if it's a different format (form data, etc.)
                local args, err = ngx.req.get_post_args()
                if args and not err then
                    if args.model then
                        model_name = args.model
                        ngx.log(ngx.DEBUG, "Extracted model name from form data: " .. model_name)
                        return model_name
                    else
                        ngx.log(ngx.WARN, "No model found in form data: " .. cjson.encode(args))
                    end
                end
            end
        else
            ngx.log(ngx.WARN, "Empty request body for " .. request_method .. " request")
        end
    end
    
    -- Extract from URL patterns if body parsing failed
    local patterns = {
        "/api/generate%?model=([^&]+)",       -- Generate API with query parameter
        "/api/chat/([^/]+)",                  -- Chat API 
        "/api/embeddings/([^/]+)",            -- Embeddings API
        "/v1/models/([^/]+)",                 -- OpenAI compatible endpoint
        "/v1/chat/completions%?model=([^&]+)" -- Alternative OpenAI pattern
    }
    
    for _, pattern in ipairs(patterns) do
        local match = string.match(request_uri, pattern)
        if match then
            model_name = match
            ngx.log(ngx.INFO, "Extracted model name from URL: " .. model_name)
            return model_name
        end
    end
    
    -- Extract from query parameters if present
    local args = ngx.req.get_uri_args()
    if args then
        -- Log num_ctx from query parameters if present
        if args.num_ctx then
            ngx.log(ngx.INFO, "REQUEST CONTEXT: num_ctx=" .. tostring(args.num_ctx) .. " for request to " .. request_uri .. " (from query params)")
        end
        
        if args.model then
            model_name = args.model
            ngx.log(ngx.INFO, "Extracted model name from query parameters: " .. model_name)
            return model_name
        end
    end
    
    -- For Ollama API specific fallbacks
    if request_uri == "/api/generate" then
        -- Check for a default Ollama model
        if headers["ollama-model"] then
            model_name = headers["ollama-model"]
            ngx.log(ngx.INFO, "Extracted model name from Ollama-specific header: " .. model_name)
            return model_name
        end
        
        -- Add any other Ollama-specific extraction logic here
    end
    
    -- Check additional headers that might contain model info
    if headers["x-model"] then
        model_name = headers["x-model"]
        ngx.log(ngx.INFO, "Extracted model name from X-Model header: " .. model_name)
        return model_name
    end
    
    -- Log comprehensive warning if extraction failed
    ngx.log(ngx.ERR, string.format(
        "Could not extract model name. Method: %s, URI: %s, Headers: %s, Body available: %s",
        request_method,
        request_uri,
        cjson.encode(headers_log),
        tostring(body_data ~= nil)
    ))
    
    return nil
end

-- Cache for running models to reduce lookups
local running_models_cache = {
    data = {},
    timestamp = 0,
    ttl = 30  -- Cache TTL in seconds (increased from 5 to 30)
}

-- Function to invalidate the running models cache
function _M.invalidate_running_models_cache()
    ngx.log(ngx.INFO, "Invalidating running models cache")
    running_models_cache.timestamp = 0
end

-- Force refresh the running models cache
function _M.force_refresh_running_models_cache()
    ngx.log(ngx.INFO, "Force refreshing running models cache")
    local running_models = _M.get_running_models()
    running_models_cache.data = running_models
    running_models_cache.timestamp = ngx.time()
    return running_models
end

-- Check if a model is running on any instance and return the instance name
function _M.is_model_running_on_any_instance(model_name, force_refresh)
    if not model_name then
        return nil
    end
    
    -- Check if we need to force refresh or if cache is expired
    local current_time = ngx.time()
    if force_refresh or current_time - running_models_cache.timestamp > running_models_cache.ttl then
        -- Cache expired or force refresh requested, refresh it
        _M.force_refresh_running_models_cache()
    end
    
    -- Check if model is running on any instance
    if running_models_cache.data[model_name] then
        local instances = running_models_cache.data[model_name]
        if #instances > 0 then
            ngx.log(ngx.DEBUG, "Found running model " .. model_name .. " on " .. instances[1])
            return instances[1]
        end
    end
    
    -- If not found and force_refresh wasn't already true, try one more time with a force refresh
    if not force_refresh then
        ngx.log(ngx.INFO, "Model " .. model_name .. " not found in cache, forcing refresh and checking again")
        _M.force_refresh_running_models_cache()
        
        -- Check again after force refresh
        if running_models_cache.data[model_name] then
            local instances = running_models_cache.data[model_name]
            if #instances > 0 then
                ngx.log(ngx.DEBUG, "Found running model " .. model_name .. " on " .. instances[1] .. " after force refresh")
                return instances[1]
            end
        end
    end
    
    return nil
end

-- Get instance for a given model from shared dict
function _M.get_instance_for_model(model_name)
    if not model_name then
        return nil
    end
    
    -- Standard model routing approach
    -- Check global model mappings using safe helper
    local instance = _M.get_safe_instance_mapping(model_name)
    if instance then
        -- Verify if the model is actually running on this instance
        local running_models = running_models_cache.data
        if running_models and running_models[model_name] then
            for _, running_instance in ipairs(running_models[model_name]) do
                if running_instance == instance then
                    ngx.log(ngx.INFO, "Found global mapping for " .. model_name .. " on " .. instance .. " and verified it's running")
                    return instance
                end
            end
        end
        
        ngx.log(ngx.DEBUG, "Found global mapping for " .. model_name .. ": " .. instance)
        return instance
    end
    
    -- Check if model is running on any instance (with force refresh)
    local running_instance = _M.is_model_running_on_any_instance(model_name, true)
    if running_instance then
        ngx.log(ngx.INFO, "Model " .. model_name .. " is already running on " .. running_instance .. ", using that instance")
        -- Create a mapping for this model to the instance where it's running
        _M.set_model_mapping(model_name, running_instance, true)
        return running_instance
    end
    
    -- Return nil instead of auto-assigning to least loaded instance
    ngx.log(ngx.INFO, "No existing mapping found for model: " .. model_name)
    return nil
end

-- Get the number of instances from shared memory
local function get_instance_count()
    local env_vars = ngx.shared.env_vars
    return tonumber(env_vars:get("OLLAMA_INSTANCE_COUNT") or "2")
end

-- Find least loaded instance and assign model to it
function _M.assign_model_to_least_loaded_instance(model_name)
    if not model_name then
        return nil
    end
    
    -- Get current model counts per instance
    local instance_count = get_instance_count()
    local instance_counts = {}
    for i=1,instance_count do
        instance_counts[i] = {instance = "ollama" .. i, count = 0}
    end
    
    -- Count models on each instance
    local keys = ngx.shared.model_mappings:get_keys() or {}
    for _, key in ipairs(keys) do
        -- Skip lock keys
        if not string.match(key, "^loading:") then
            local instance = _M.get_safe_instance_mapping(key)
            if instance then
                local instance_num = tonumber(string.match(instance, "ollama(%d+)"))
                if instance_num and instance_counts[instance_num] then
                    instance_counts[instance_num].count = instance_counts[instance_num].count + 1
                end
            end
        end
    end
    
    -- Find instance with least models
    table.sort(instance_counts, function(a, b) return a.count < b.count end)
    local least_loaded = instance_counts[1].instance
    
    -- Store the new mapping
    _M.set_model_mapping(model_name, least_loaded, false)
    ngx.log(ngx.INFO, "Assigned model " .. model_name .. " to " .. least_loaded .. " (has " .. instance_counts[1].count .. " models)")
  
    return least_loaded
end

-- Helper function to get table length
local function table_length(t)
    local count = 0
    for _ in pairs(t) do count = count + 1 end
    return count
end

-- Update model mappings from all instances
function _M.update_model_mappings()
    local success = true
    local start_time = ngx.now()
    local http = require "resty.http"
    
    -- Debug: Get detailed PS data from each instance directly
    ngx.log(ngx.DEBUG, "DEBUG: Getting detailed running model data from each instance:")
    local instance_ps_data = {}
    
    local instance_count = get_instance_count()
    for i=1,instance_count do
        local instance = "ollama" .. i
        local httpc = http.new()
        httpc:set_timeout(5000)
        
        local res, err = httpc:request_uri("http://" .. instance .. ":11434/api/ps", {
            method = "GET"
        })
        
        if res and res.status == 200 then
            local ps_success, ps = pcall(cjson.decode, res.body)
            if ps_success and ps then
                instance_ps_data[instance] = ps
                
                -- Log raw data for verification
                ngx.log(ngx.DEBUG, "DEBUG: " .. instance .. " reported raw PS data: " .. res.body)
                
                -- Log each model reported as running
                if ps.models and #ps.models > 0 then
                    local model_names = {}
                    for _, model in ipairs(ps.models) do
                        table.insert(model_names, model.name or "unknown")
                    end
                    ngx.log(ngx.DEBUG, "DEBUG: " .. instance .. " reports running models: " .. table.concat(model_names, ", "))
                else
                    ngx.log(ngx.DEBUG, "DEBUG: " .. instance .. " reports NO running models")
                end
            else
                ngx.log(ngx.ERR, "DEBUG: Failed to parse PS data from " .. instance)
                instance_ps_data[instance] = nil
            end
        else
            ngx.log(ngx.ERR, "DEBUG: Failed to get PS data from " .. instance .. ": " .. (err or "unknown error"))
            instance_ps_data[instance] = nil
        end
    end
    
    -- Get currently running models through the standard function
    local running_models = _M.get_running_models()
    ngx.log(ngx.DEBUG, "Found " .. table_length(running_models) .. " running models according to get_running_models()")
    
    -- DEBUG: Compare raw PS data with aggregated running_models data
    ngx.log(ngx.DEBUG, "DEBUG: Comparing raw PS data with aggregated running_models data:")
    for model_name, instances in pairs(running_models) do
        local reported_instances = {}
        for _, instance in ipairs(instances) do
            table.insert(reported_instances, instance)
        end
        ngx.log(ngx.DEBUG, "DEBUG: Aggregated data shows model " .. model_name .. " running on: " .. table.concat(reported_instances, ", "))
    end
    
    -- Process each running model
    for model_name, running_instances in pairs(running_models) do
        if #running_instances > 0 then
            -- Standard model processing approach
            -- Get current mapping
            local current_instance = _M.get_safe_instance_mapping(model_name)
            ngx.log(ngx.DEBUG, "DEBUG: Current mapping for " .. model_name .. ": " .. (current_instance or "none"))
            
            -- Check if current mapping is valid (model is running on that instance)
            local current_mapping_valid = false
            if current_instance then
                for _, instance in ipairs(running_instances) do
                    if instance == current_instance then
                        current_mapping_valid = true
                        break
                    end
                end
            end
            
            -- DEBUG: Log validity of current mapping
            ngx.log(ngx.DEBUG, "DEBUG: Current mapping valid? " .. (current_mapping_valid and "yes" or "no"))
            
            -- Only update mapping if necessary
            if not current_instance or not current_mapping_valid then
                -- Use stable instance selection - prefer lower-numbered instances
                -- Copy the array to avoid modifying the original
                local instances_copy = {}
                for _, instance in ipairs(running_instances) do
                    table.insert(instances_copy, instance)
                end
                
                table.sort(instances_copy)
                local target_instance = instances_copy[1]
                
                ngx.log(ngx.DEBUG, "DEBUG: Selected target_instance: " .. target_instance)
                
                -- Only set mapping if it's changing
                if current_instance ~= target_instance then
                    _M.set_model_mapping(model_name, target_instance, true)
                    ngx.log(ngx.DEBUG, "Updated mapping for model " .. model_name .. ": " .. 
                            (current_instance or "none") .. " -> " .. target_instance)
                else
                    ngx.log(ngx.DEBUG, "DEBUG: Mapping unchanged for " .. model_name)
                end
            else
                ngx.log(ngx.DEBUG, "DEBUG: Keeping existing mapping for " .. model_name .. " to " .. current_instance)
            end
        else
            ngx.log(ngx.DEBUG, "Running model " .. model_name .. " has no instances")
        end
    end
    
    -- Calculate elapsed time
    local elapsed = ngx.now() - start_time
    ngx.log(ngx.DEBUG, "Model mapping updated in " .. string.format("%.2f", elapsed) .. "s")
    
    return success
end



-- Helper functions for shared memory access
-- These functions centralize all interactions with shared memory to ensure consistency

-- Get full mapping information for a model (returns the complete decoded object)
function _M.get_model_mapping_info(model_name)
    if not model_name then
        return nil
    end
    
    local mapping = ngx.shared.model_mappings:get(model_name)
    if not mapping then
        return nil
    end
    
    local success, decoded = pcall(function()
        local decoded_base64 = ngx.decode_base64(mapping)
        if not decoded_base64 then
            return nil
        end
        return cjson.decode(decoded_base64)
    end)
    
    if success and decoded then
        return decoded
    end
    
    return nil
end

-- Helper function to safely fetch instance mapping (returns just the instance name)
function _M.get_safe_instance_mapping(model_name)
    local mapping_info = _M.get_model_mapping_info(model_name)
    if mapping_info and mapping_info.instance then
        return mapping_info.instance
    end
    return nil
end

-- Helper function to check if a model is marked as running in its mapping
function _M.is_model_running_from_mapping(model_name)
    local mapping_info = _M.get_model_mapping_info(model_name)
    return mapping_info and mapping_info.running == true
end

-- Helper function to set a model mapping with standardized format
function _M.set_model_mapping(model_name, instance, is_running)
    if not model_name or not instance then
        return false
    end
    
    -- Proceed with normal mapping
    -- Get the current mapping to check if it's changing
    local current_mapping = _M.get_safe_instance_mapping(model_name)
    local current_running = _M.is_model_running_from_mapping(model_name)
    
    -- Only proceed if the mapping is actually changing
    if current_mapping ~= instance or current_running ~= is_running then
        local mapping_data = {
            instance = instance
        }
        
        if is_running then
            mapping_data.running = true
        else
            mapping_data.running = false
        end
        
        local mapping_json = ngx.encode_base64(cjson.encode(mapping_data))
        ngx.shared.model_mappings:set(model_name, mapping_json)
        ngx.log(ngx.INFO, "Set mapping for model " .. model_name .. " to " .. instance .. 
                (is_running and " (running)" or ""))
        
        -- Invalidate the running models cache when a mapping changes
        _M.invalidate_running_models_cache()
    else
        ngx.log(ngx.DEBUG, "Mapping for model " .. model_name .. " already set to " .. instance .. 
                (is_running and " (running)" or "") .. ", skipping update")
    end
    
    return true
end

-- Function to clean up all mappings for models that aren't running
function _M.clean_non_running_mappings()
    local running_models = _M.get_running_models()
    local keys = ngx.shared.model_mappings:get_keys() or {}
    local removed_count = 0
    
    for _, key in ipairs(keys) do
        -- Skip lock keys
        if not string.match(key, "^loading:") then
            if not running_models[key] then
                ngx.log(ngx.INFO, "Removing mapping for non-running model: " .. key)
                ngx.shared.model_mappings:delete(key)
                removed_count = removed_count + 1
            end
        end
    end
    
    return removed_count
end


-- Function to check for and fix inconsistent mappings
-- This ensures that if a model is running on multiple instances, we only have one mapping for it
function _M.check_and_fix_inconsistent_mappings()
    local running_models = _M.get_running_models()
    local fixed_count = 0
    
    -- Check each running model
    for model_name, instances in pairs(running_models) do
        if #instances > 0 then
            -- Get the current mapping for this model
            local current_instance = _M.get_safe_instance_mapping(model_name)
            
            -- If the model is mapped to an instance where it's not running, or not mapped at all
            if not current_instance or not _M.table_contains(instances, current_instance) then
                -- Map it to the first instance where it's running
                local preferred_instance = instances[1]
                _M.set_model_mapping(model_name, preferred_instance, true)
                ngx.log(ngx.INFO, "Fixed inconsistent mapping for model " .. model_name .. ": now mapped to " .. preferred_instance)
                fixed_count = fixed_count + 1
            end
        end
    end
    
    -- Also check for duplicate model instances and log them
    _M.detect_duplicate_model_instances(running_models)
    
    return fixed_count
end

-- Function to detect and log duplicate model instances
-- This helps identify when a model is running on multiple instances
function _M.detect_duplicate_model_instances(running_models)
    if not running_models then
        running_models = _M.get_running_models()
    end
    
    local duplicates = {}
    
    -- Check each running model
    for model_name, instances in pairs(running_models) do
        if #instances > 1 then
            -- This model is running on multiple instances
            table.insert(duplicates, {
                model = model_name,
                instances = instances
            })
            
            ngx.log(ngx.WARN, "Model " .. model_name .. " is running on multiple instances: " .. table.concat(instances, ", "))
        end
    end
    
    return duplicates
end

-- Helper function to check if a table contains a value
function _M.table_contains(table, value)
    for _, v in ipairs(table) do
        if v == value then
            return true
        end
    end
    return false
end


-- Get running models from all instances
-- Returns a table where keys are model names and values are arrays of instances where the model is running
function _M.get_running_models()
    local http = require "resty.http"
    local running_models = {}
    local model_details = {}  -- Store additional details for each model
    
    -- Create HTTP client
    local httpc = http.new()
    httpc:set_timeout(5000)  -- 5 second timeout
    
    -- Check each Ollama instance
    local instance_count = get_instance_count()
    for i=1,instance_count do
        local instance = "ollama" .. i
        local running_models_list = {}
       
        local ok, res = pcall(function()
            local res, err = httpc:request_uri("http://" .. instance .. ":11434/api/ps", {
                method = "GET"
            })
            return res, err
        end)
    
        if ok and res and res.status == 200 then
            ngx.log(ngx.DEBUG, "PS response from " .. instance .. ": " .. res.body)
            local ps_success, ps = pcall(cjson.decode, res.body)
            
            -- The /api/ps endpoint returns a "models" array, not "running"
            if ps_success and ps and ps.models then
                running_models_list = ps.models
            end
        end
        
        -- Process running models
        for _, running in ipairs(running_models_list) do
            if running.name then
                local model_name = running.name
                -- Initialize or update the list of instances for this model
                if not running_models[model_name] then
                    running_models[model_name] = {}
                    -- Store model details for the first instance we find it on
                    model_details[model_name] = running
                    
                    -- REMOVED: Don't automatically create mappings when discovering models
                    -- This should be a separate operation or done only when explicitly requested
                    -- _M.set_model_mapping(model_name, instance, true)
                    -- ngx.log(ngx.INFO, "Created mapping for running model " .. model_name .. " to " .. instance)
                end
                
                -- Add this instance to the list of instances where the model is running
                table.insert(running_models[model_name], instance)
                
                ngx.log(ngx.DEBUG, "Found running model " .. model_name .. " on " .. instance)
            end
        end
    end
    
    -- Add model_details to the return value
    return running_models, model_details
end

-- Get detailed running models information for the merged /api/ps response
-- Returns a table in the format expected by the Ollama API
function _M.get_merged_ps_response()
    local running_models, model_details = _M.get_running_models()
    local merged_models = {}
    
    for model_name, instances in pairs(running_models) do
        -- Get the model details if available
        local details = model_details[model_name] or {}
        
        -- Create a merged model entry
        local model_entry = {
            name = model_name,
            model = model_name,
            instances = instances  -- Add instances information for transparency
        }
        
        -- Copy any additional fields from the original model details
        for k, v in pairs(details) do
            if k ~= "name" and k ~= "model" and k ~= "instances" then
                model_entry[k] = v
            end
        end
        
        table.insert(merged_models, model_entry)
    end
    
    return {
        models = merged_models
    }
end

function _M.lock_model_loading(model_name, instance)
    local lock_key = "loading:" .. model_name
    
    -- Check if model is already running on any instance (with force refresh)
    local running_instance = _M.is_model_running_on_any_instance(model_name, true)
    if running_instance then
        ngx.log(ngx.INFO, "Model " .. model_name .. " is already running on " .. running_instance .. ", no need to load it again")
        
        -- Create a mapping for the running model
        _M.set_model_mapping(model_name, running_instance, true)
        
        return false, running_instance
    end
    
    -- Try to acquire lock with extended duration (1 hour)
    local success, err = ngx.shared.model_mappings:add(lock_key, instance, 3600)  -- 1-hour lock
    
    if not success then
        local current_loader = ngx.shared.model_mappings:get(lock_key)
        if current_loader then
            ngx.log(ngx.INFO, "Model " .. model_name .. " is already being loaded by " .. current_loader)
            -- Return the instance that's already loading the model
            return false, current_loader
        else
            -- Lock exists but no instance information, something went wrong
            ngx.log(ngx.WARN, "Lock exists for model " .. model_name .. " but no instance information")
            -- Try to delete the lock and acquire it again
            ngx.shared.model_mappings:delete(lock_key)
            success, err = ngx.shared.model_mappings:add(lock_key, instance, 3600)
            if not success then
                ngx.log(ngx.ERR, "Failed to acquire lock for model " .. model_name .. " after cleanup: " .. (err or "unknown error"))
                return false
            end
        end
    end
    
    ngx.log(ngx.INFO, "Acquired loading lock for model " .. model_name .. " on " .. instance)
    return true
end

function _M.unlock_model_loading(model_name)
    local lock_key = "loading:" .. model_name
    ngx.shared.model_mappings:delete(lock_key)
    ngx.log(ngx.INFO, "Released loading lock for model " .. model_name)
    
    -- Invalidate the running models cache to ensure fresh data
    _M.invalidate_running_models_cache()
end

-- Refresh a model loading lock to prevent expiration during long loads
function _M.refresh_model_loading_lock(model_name, instance)
    local lock_key = "loading:" .. model_name
    local current_instance = ngx.shared.model_mappings:get(lock_key)
    
    -- Only refresh if the lock exists and is owned by the same instance
    if current_instance and current_instance == instance then
        ngx.shared.model_mappings:set(lock_key, instance, 3600)  -- Reset to 1-hour
        ngx.log(ngx.DEBUG, "Refreshed loading lock for model " .. model_name .. " on " .. instance)
        return true
    end
    
    return false
end

-- Get all available models from all instances
-- Returns a table with model information and instance availability
function _M.get_all_models()
    local http = require "resty.http"
    local all_models = {}
    local model_instances = {}
    local success = true
    
    -- Create HTTP client
    local httpc = http.new()
    httpc:set_timeout(5000)  -- 5 second timeout
    
    -- Check each Ollama instance
    local instance_count = get_instance_count()
    for i=1,instance_count do
        local instance = "ollama" .. i
        
        local instance_data
        
        -- Fetch fresh data
        local res, err = httpc:request_uri("http://" .. instance .. ":11434/api/tags", {
            method = "GET"
        })
        
        if res and res.status == 200 then
            local tags_success, tags = pcall(cjson.decode, res.body)
            if tags_success and tags then
                instance_data = tags
            else
                success = false
            end
        else
            success = false
        end
        
        -- Process models from this instance
        if instance_data and instance_data.models then
            for _, model in ipairs(instance_data.models) do
                if not all_models[model.name] then
                    all_models[model.name] = model
                end
                
                if not model_instances[model.name] then
                    model_instances[model.name] = {}
                end
                table.insert(model_instances[model.name], instance)
            end
        end
    end
    
    -- Add instance information to each model
    for name, model in pairs(all_models) do
        model.instances = model_instances[name]
    end
    
    -- Convert all_models map to array and sort alphabetically
    local models_array = {}
    for _, model in pairs(all_models) do
        table.insert(models_array, model)
    end
    table.sort(models_array, function(a, b) return a.name < b.name end)
    
    return {
        models = models_array,
        success = success,
        timestamp = ngx.time()
    }
end

return _M
