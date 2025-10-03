-- Provider Router Module for Unified LLM Gateway
-- Handles routing to multiple LLM providers (Ollama, OpenAI, Anthropic, LM Studio, etc.)

local cjson = require "cjson"
local model_router = require "model_router"

local _M = {}

-- Extract provider and model name from the full model identifier
function _M.extract_provider_from_model(model)
    if not model then
        return nil, nil
    end

    -- Check if model has provider prefix (provider/model)
    local provider, model_name = model:match("^([^/]+)/(.+)$")

    if not provider then
        -- No provider prefix, check defaults
        local env_vars = ngx.shared.env_vars

        -- If LM Studio is configured and no prefix, default to lmstudio
        local lmstudio_base = env_vars:get("LMSTUDIO_API_BASE") or os.getenv("LMSTUDIO_API_BASE")
        if lmstudio_base and lmstudio_base ~= "" then
            return "lmstudio", model
        end

        -- Default to ollama
        return "ollama", model
    end

    return provider, model_name
end

-- Route request to appropriate Ollama instance
function _M.route_to_ollama(model_name, request_body)
    ngx.log(ngx.INFO, "Routing to Ollama for model: " .. model_name)

    -- Check if model is running on any instance
    local running_instance = model_router.is_model_running_on_any_instance(model_name)

    if running_instance then
        ngx.log(ngx.INFO, "Model " .. model_name .. " is running on " .. running_instance)
        ngx.var.target_instance = running_instance
        ngx.var.provider = "ollama"
        ngx.var.model_name = model_name
        return running_instance
    end

    -- Model not running, assign to least loaded instance
    local instance = model_router.get_instance_for_model(model_name)
    if not instance then
        instance = model_router.assign_model_to_least_loaded_instance(model_name)
    end

    if instance then
        ngx.var.target_instance = instance
        ngx.var.provider = "ollama"
        ngx.var.model_name = model_name
        ngx.log(ngx.INFO, "Assigned model " .. model_name .. " to instance " .. instance)
        return instance
    end

    ngx.log(ngx.ERR, "Failed to assign Ollama instance for model: " .. model_name)
    return nil
end

-- Route request to external provider
function _M.route_to_external_provider(provider, model_name, request_body)
    ngx.log(ngx.INFO, "Routing to external provider: " .. provider .. " for model: " .. model_name)

    local env_vars = ngx.shared.env_vars
    local api_base = nil
    local api_key = nil
    local extra_headers = {}

    if provider == "openai" then
        api_base = "https://api.openai.com/v1"
        api_key = env_vars:get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")

    elseif provider == "anthropic" then
        api_base = "https://api.anthropic.com/v1"
        api_key = env_vars:get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        extra_headers["anthropic-version"] = "2023-06-01"
        extra_headers["Content-Type"] = "application/json"

    elseif provider == "lmstudio" then
        local lmstudio_base = env_vars:get("LMSTUDIO_API_BASE") or os.getenv("LMSTUDIO_API_BASE")
        if lmstudio_base then
            -- Ensure proper URL format
            if not lmstudio_base:match("^http") then
                lmstudio_base = "http://" .. lmstudio_base
            end
            api_base = lmstudio_base .. "/v1"
        else
            api_base = "http://host.docker.internal:9090/v1"
        end
        api_key = env_vars:get("LMSTUDIO_API_KEY") or os.getenv("LMSTUDIO_API_KEY")

    elseif provider == "google" then
        -- Google/Vertex AI configuration
        api_base = "https://generativelanguage.googleapis.com/v1beta"
        api_key = env_vars:get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")

    elseif provider == "groq" then
        api_base = "https://api.groq.com/openai/v1"
        api_key = env_vars:get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")

    else
        ngx.log(ngx.ERR, "Unknown provider: " .. provider)
        return nil
    end

    -- Check if API key is available for providers that require it
    if provider ~= "lmstudio" and not api_key then
        ngx.log(ngx.ERR, "No API key configured for provider: " .. provider)
        ngx.status = 401
        ngx.say(cjson.encode({
            error = "No API key configured for provider: " .. provider
        }))
        return ngx.exit(401)
    end

    -- Set nginx variables for proxy pass
    ngx.var.provider = provider
    ngx.var.api_base = api_base
    ngx.var.api_key = api_key or ""
    ngx.var.model_name = model_name

    -- Store extra headers if needed
    if next(extra_headers) then
        ngx.ctx.extra_headers = extra_headers
    end

    return true
end

-- Main routing function
function _M.route_request()
    ngx.req.read_body()
    local body_data = ngx.req.get_body_data()

    if not body_data then
        ngx.log(ngx.ERR, "No request body")
        ngx.status = 400
        ngx.say(cjson.encode({error = "No request body"}))
        return ngx.exit(400)
    end

    local ok, request_body = pcall(cjson.decode, body_data)
    if not ok then
        ngx.log(ngx.ERR, "Failed to parse request body: " .. tostring(request_body))
        ngx.status = 400
        ngx.say(cjson.encode({error = "Invalid JSON in request body"}))
        return ngx.exit(400)
    end

    -- Extract model from request
    local model = request_body.model
    if not model then
        ngx.log(ngx.ERR, "No model specified in request")
        ngx.status = 400
        ngx.say(cjson.encode({error = "No model specified"}))
        return ngx.exit(400)
    end

    -- Extract provider and model name
    local provider, model_name = _M.extract_provider_from_model(model)

    ngx.log(ngx.INFO, "Request for provider: " .. (provider or "nil") .. ", model: " .. (model_name or "nil"))

    -- Update request body with just the model name (without provider prefix)
    request_body.model = model_name
    ngx.req.set_body_data(cjson.encode(request_body))

    -- Route based on provider
    if provider == "ollama" then
        local instance = _M.route_to_ollama(model_name, request_body)
        if not instance then
            ngx.status = 503
            ngx.say(cjson.encode({error = "No Ollama instance available for model"}))
            return ngx.exit(503)
        end
    else
        local success = _M.route_to_external_provider(provider, model_name, request_body)
        if not success then
            return ngx.exit(503)
        end
    end
end

-- Get available models from all providers
function _M.get_all_models()
    local models = {}
    local env_vars = ngx.shared.env_vars

    -- Get Ollama models
    local ollama_models = model_router.get_all_models()
    if ollama_models and ollama_models.models then
        for _, model in ipairs(ollama_models.models) do
            -- Prefix with ollama/ for consistency
            model.id = "ollama/" .. (model.name or model.id)
            model.provider = "ollama"

            -- Add capabilities based on model name
            model.capabilities = {
                chat = true,
                completion = true,
                embedding = model.name:match("embed") ~= nil,
                vision = model.name:match("vision") ~= nil or model.name:match("llava") ~= nil,
                function_calling = model.name:match("mistral") ~= nil or model.name:match("llama") ~= nil,
                streaming = true
            }

            table.insert(models, model)
        end
    end

    -- Check for LM Studio
    local lmstudio_base = env_vars:get("LMSTUDIO_API_BASE") or os.getenv("LMSTUDIO_API_BASE")
    if lmstudio_base then
        -- In production, would make HTTP call to LM Studio /v1/models endpoint
        -- For now, return placeholder
        table.insert(models, {
            id = "lmstudio/available-models",
            name = "LM Studio Models",
            provider = "lmstudio",
            note = "Connect to LM Studio to see available models"
        })
    end

    -- Check for other providers with specific models
    local provider_models = {
        openai = {
            {id = "gpt-4-turbo", name = "GPT-4 Turbo", vision = true, function_calling = true},
            {id = "gpt-4", name = "GPT-4", vision = false, function_calling = true},
            {id = "gpt-3.5-turbo", name = "GPT-3.5 Turbo", vision = false, function_calling = true}
        },
        anthropic = {
            {id = "claude-3-opus-20240229", name = "Claude 3 Opus", vision = true, function_calling = true},
            {id = "claude-3-sonnet-20240229", name = "Claude 3 Sonnet", vision = true, function_calling = true},
            {id = "claude-3-haiku-20240307", name = "Claude 3 Haiku", vision = true, function_calling = true}
        },
        google = {
            {id = "gemini-pro", name = "Gemini Pro", vision = false, function_calling = true},
            {id = "gemini-pro-vision", name = "Gemini Pro Vision", vision = true, function_calling = true}
        },
        groq = {
            {id = "llama2-70b-4096", name = "Llama 2 70B", vision = false, function_calling = false},
            {id = "mixtral-8x7b-32768", name = "Mixtral 8x7B", vision = false, function_calling = true}
        }
    }

    local providers = {
        {key = "OPENAI_API_KEY", provider = "openai"},
        {key = "ANTHROPIC_API_KEY", provider = "anthropic"},
        {key = "GOOGLE_API_KEY", provider = "google"},
        {key = "GROQ_API_KEY", provider = "groq"}
    }

    for _, prov in ipairs(providers) do
        local api_key = env_vars:get(prov.key) or os.getenv(prov.key)
        if api_key and api_key ~= "" then
            -- Add specific models for this provider
            local models_for_provider = provider_models[prov.provider] or {}
            for _, model_info in ipairs(models_for_provider) do
                table.insert(models, {
                    id = prov.provider .. "/" .. model_info.id,
                    name = model_info.name,
                    provider = prov.provider,
                    capabilities = {
                        chat = true,
                        completion = true,
                        embedding = false,
                        vision = model_info.vision,
                        function_calling = model_info.function_calling,
                        streaming = true
                    }
                })
            end
        end
    end

    return {models = models}
end

return _M