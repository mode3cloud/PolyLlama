// Configuration - will be dynamically populated
let OLLAMA_INSTANCES = [
    { name: 'polyllama1' }
];

// Elements
const refreshBtn = document.getElementById('refresh-btn');
const instanceGrid = document.getElementById('instance-grid');
const modelTableBody = document.getElementById('model-table-body');
const searchInput = document.getElementById('search-input');

// System overview elements
const totalInstancesEl = document.getElementById('total-instances');
const instanceDetailsEl = document.getElementById('instance-details');
const gpuCountEl = document.getElementById('gpu-count');
const gpuDetailsEl = document.getElementById('gpu-details');
const activeModelsEl = document.getElementById('active-models');
const modelDetailsEl = document.getElementById('model-details');
const systemStatusEl = document.getElementById('system-status');
const statusDetailsEl = document.getElementById('status-details');

// Modal elements
const loadModal = document.getElementById('load-modal');
const loadModelNameInput = document.getElementById('load-model-name');
const loadInstanceSelect = document.getElementById('load-instance');
const loadContextInput = document.getElementById('load-context');

// State
let instanceStatuses = {};
let availableModels = [];
let runningModels = {};
let modelMappings = {};
let modelContexts = {};
let currentFilter = 'all';
let searchQuery = '';
let isLoadingModel = false;
let expandedModels = new Set(); // Track which models are expanded

// Initialize the application
async function initializeApp() {
    try {
        await initializeInstances();
        await refreshData();
        setupEventListeners();

        // Auto-refresh every 5 seconds
        setInterval(refreshData, 5000);
    } catch (error) {
        console.error('Failed to initialize app:', error);
    }
}

// Fetch instance count and initialize instances array
async function initializeInstances() {
    try {
        const response = await fetch('/api/ui/instance-count');
        if (response.ok) {
            const data = await response.json();
            const instanceCount = data.instance_count || 2;

            // Update OLLAMA_INSTANCES array based on actual count
            OLLAMA_INSTANCES = [];
            for (let i = 1; i <= instanceCount; i++) {
                OLLAMA_INSTANCES.push({ name: `polyllama${i}` });
            }

            console.log(`Initialized with ${instanceCount} instances:`, OLLAMA_INSTANCES);
        } else {
            console.warn('Failed to fetch instance count, using default');
        }
    } catch (error) {
        console.error('Error initializing instances:', error);
    }
}

// Setup event listeners
function setupEventListeners() {
    refreshBtn.addEventListener('click', refreshData);

    // Search functionality
    searchInput.addEventListener('input', (e) => {
        searchQuery = e.target.value.toLowerCase();
        filterAndDisplayModels();
    });

    // Filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentFilter = this.dataset.filter;
            filterAndDisplayModels();
        });
    });

    // Modal close functionality
    document.querySelector('.close').addEventListener('click', () => {
        if (!isLoadingModel) {
            closeLoadModal();
        }
    });
    window.addEventListener('click', (e) => {
        if (e.target === loadModal && !isLoadingModel) {
            closeLoadModal();
        }
    });

    // Refresh button animation
    refreshBtn.addEventListener('click', function () {
        const icon = this.querySelector('span:first-child');
        icon.style.animation = 'spin 1s linear';
        setTimeout(() => {
            icon.style.animation = '';
        }, 1000);
    });
}

// Refresh all data
async function refreshData() {
    try {
        console.log('Refreshing data...');

        // Fetch all data in parallel
        const [instanceStatusResult, modelsResult, runningModelsResult, mappingsResult, contextsResult] = await Promise.all([
            fetchInstanceStatuses(),
            fetchAvailableModels(),
            fetchRunningModels(),
            fetchModelMappings(),
            fetchModelContexts()
        ]);
        
        // Sync contexts from running models if we have running models but missing contexts
        const runningModelNames = Object.keys(runningModelsResult || {});
        const hasRunningModels = runningModelNames.length > 0;
        const hasMissingContexts = runningModelNames.some(model => !modelContexts[model]);
        
        if (hasRunningModels && hasMissingContexts) {
            try {
                const syncResponse = await fetch('/api/ui/sync-contexts');
                if (syncResponse.ok) {
                    const syncData = await syncResponse.json();
                    console.log(`Synced context sizes for ${syncData.synced_count} models`);
                    // Re-fetch contexts after sync
                    await fetchModelContexts();
                }
            } catch (error) {
                console.error('Error syncing contexts:', error);
            }
        }

        // Update system overview
        updateSystemOverview();

        // Update displays
        displayInstances();
        filterAndDisplayModels();

        console.log('Data refresh completed');
    } catch (error) {
        console.error('Error refreshing data:', error);
        showError('Failed to refresh data');
    }
}

// Fetch instance statuses
async function fetchInstanceStatuses() {
    try {
        const response = await fetch('/api/ui/instance-status');
        if (response.ok) {
            const data = await response.json();
            instanceStatuses = {};
            data.instances.forEach(instance => {
                instanceStatuses[instance.name] = instance;
            });
            return instanceStatuses;
        }
    } catch (error) {
        console.error('Error fetching instance statuses:', error);
    }
    return {};
}

// Fetch available models
async function fetchAvailableModels() {
    try {
        const response = await fetch('/api/tags');
        if (response.ok) {
            const data = await response.json();
            availableModels = data.models || [];
            // Ensure consistent alphabetical sorting
            availableModels.sort((a, b) => a.name.localeCompare(b.name));
            return availableModels;
        }
    } catch (error) {
        console.error('Error fetching available models:', error);
    }
    return [];
}

// Fetch running models
async function fetchRunningModels() {
    try {
        const response = await fetch('/api/ui/running-models');
        if (response.ok) {
            const data = await response.json();
            runningModels = data.running_models || {};
            return runningModels;
        }
    } catch (error) {
        console.error('Error fetching running models:', error);
    }
    return {};
}

// Fetch model mappings
async function fetchModelMappings() {
    try {
        const response = await fetch('/api/ui/model-mappings');
        if (response.ok) {
            const data = await response.json();
            modelMappings = data.mappings || {};
            return data;
        }
    } catch (error) {
        console.error('Error fetching model mappings:', error);
    }
    return {};
}

// Fetch model contexts
async function fetchModelContexts() {
    try {
        const response = await fetch('/api/ui/get-contexts');
        if (response.ok) {
            const data = await response.json();
            modelContexts = data.contexts || {};
            return modelContexts;
        }
    } catch (error) {
        console.error('Error fetching model contexts:', error);
    }
    return {};
}

// Update system overview cards
function updateSystemOverview() {
    // Total instances
    totalInstancesEl.textContent = OLLAMA_INSTANCES.length;
    const onlineInstances = Object.values(instanceStatuses).filter(i => i.status === 'online').length;
    instanceDetailsEl.textContent = `${onlineInstances} Online • ${OLLAMA_INSTANCES.length - onlineInstances} Offline`;

    // GPU resources (dynamic based on instance count)
    const gpuInstances = Object.values(instanceStatuses).filter(i => i.status === 'online');
    const totalGpuCount = gpuInstances.length;
    gpuCountEl.textContent = totalGpuCount > 0 ? totalGpuCount : '0';
    gpuDetailsEl.textContent = totalGpuCount > 0 ? `${totalGpuCount} GPU Groups Active` : 'No GPUs available';

    // Active models
    const activeModelCount = Object.keys(runningModels).length;
    activeModelsEl.textContent = activeModelCount;
    const modelNames = Object.keys(runningModels).slice(0, 3).join(' • ');
    modelDetailsEl.textContent = modelNames || 'No active models';

    // System status
    systemStatusEl.textContent = onlineInstances > 0 ? 'Online' : 'Offline';
    statusDetailsEl.textContent = `${onlineInstances}/${OLLAMA_INSTANCES.length} instances healthy`;
}

// Display instances
function displayInstances() {
    instanceGrid.innerHTML = '';

    OLLAMA_INSTANCES.forEach(instance => {
        const status = instanceStatuses[instance.name] || { status: 'offline', name: instance.name };
        const instanceModels = Object.keys(runningModels).filter(model =>
            runningModels[model].includes(instance.name)
        );

        const instanceCard = createInstanceCard(instance.name, status, instanceModels);
        instanceGrid.appendChild(instanceCard);
    });
}

// Create instance card element
function createInstanceCard(instanceName, status, models) {
    const card = document.createElement('div');
    card.className = 'instance-card';

    const isOnline = status.status === 'online';
    const gpuInfo = getGPUInfo(instanceName);

    card.innerHTML = `
        <div class="instance-header">
            <div class="instance-name">
                <span class="status-indicator ${!isOnline ? 'offline' : ''}"></span>
                <span>${instanceName}</span>
            </div>
            <span class="instance-type">${gpuInfo.type}</span>
        </div>
        <div class="instance-body">
            <div class="hardware-info">
                <div class="gpu-badge">${gpuInfo.description}</div>
            </div>
            <div class="instance-stats">
                <div class="stat-item">
                    <div class="stat-label">Status</div>
                    <div class="stat-value">${isOnline ? 'Online' : 'Offline'}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Models</div>
                    <div class="stat-value">${models.length}</div>
                </div>
            </div>
            <div class="loaded-models">
                <div class="loaded-models-header">Loaded Models</div>
                ${models.length > 0 ?
            models.map(model => {
                const contextInfo = modelContexts[model] ? ` <small style="color: #666;">(ctx: ${modelContexts[model]})</small>` : '';
                return `
                <div class="model-item">
                    <span class="model-tag loaded">${model}${contextInfo}</span>
                    <button class="unload-btn" onclick="unloadModelFromInstance('${model}', '${instanceName}')" title="Unload ${model} from ${instanceName}">×</button>
                </div>
            `}).join('') :
            '<span class="model-tag">No models loaded</span>'
        }
            </div>
        </div>
    `;

    return card;
}

// Get GPU info for instance (dynamic based on detected hardware)
function getGPUInfo(instanceName) {
    // Default fallback for instances
    const instanceNumber = instanceName.replace('polyllama', '');

    // TODO: Could be enhanced to fetch actual GPU configuration from API
    // For now, provide generic descriptions
    return {
        type: 'GPU Group',
        description: `GPU Group ${instanceNumber}`
    };
}

// Filter and display models
function filterAndDisplayModels() {
    const filteredModels = availableModels.filter(model => {
        const matchesSearch = model.name.toLowerCase().includes(searchQuery);
        const isLoaded = runningModels.hasOwnProperty(model.name);

        switch (currentFilter) {
            case 'loaded':
                return matchesSearch && isLoaded;
            case 'available':
                return matchesSearch && !isLoaded;
            default:
                return matchesSearch;
        }
    });

    // Ensure filtered models maintain alphabetical order
    filteredModels.sort((a, b) => a.name.localeCompare(b.name));
    
    displayModels(filteredModels);
}

// Display models in table
function displayModels(models) {
    if (models.length === 0) {
        modelTableBody.innerHTML = '<tr><td class="loading">No models found</td></tr>';
        return;
    }

    modelTableBody.innerHTML = models.map((model, index) => {
        const isLoaded = runningModels.hasOwnProperty(model.name);
        const loadedOn = isLoaded ? runningModels[model.name] : [];
        const modelId = `model-${index}`;
        const isExpanded = expandedModels.has(model.name);

        // Create status and action content
        let statusContent = '';
        let actionContent = '';

        if (isLoaded) {
            // Show which instance(s) the model is loaded on in the status
            const instanceList = loadedOn.join(', ');
            let contextInfo = '';

            // Show context size if available
            if (modelContexts[model.name]) {
                contextInfo = ` <small style="color: #666;">(ctx: ${modelContexts[model.name]})</small>`;
            }

            statusContent = `<span class="model-tag loaded">Loaded on ${instanceList}${contextInfo}</span>`;
            actionContent = `<button class="action-btn danger" onclick="unloadModel('${model.name}')">Unload</button>`;
        } else {
            statusContent = '<span class="model-tag">Available</span>';
            actionContent = `<button class="action-btn primary" onclick="openLoadModal('${model.name}')">Load</button>`;
        }

        return `
            <tr>
                <td colspan="3">
                    <div class="model-row-content">
                        <div class="model-main-info">
                            <div class="model-header">
                                <button class="model-expand-btn" onclick="toggleModelDetails('${modelId}', '${model.name}')" title="Show model details">
                                    <span id="${modelId}-arrow">${isExpanded ? '▼' : '▶'}</span>
                                </button>
                                <div>
                                    <div class="model-name">${model.name}</div>
                                    <div class="model-size">${formatSize(model.size)}</div>
                                </div>
                            </div>
                            <div class="model-status">${statusContent}</div>
                            <div class="model-action">${actionContent}</div>
                        </div>
                        <div id="${modelId}-details" class="model-details" style="display: ${isExpanded ? 'block' : 'none'};">
                            <div class="loading">Loading model details...</div>
                        </div>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
    
    // After rendering, re-fetch details for expanded models
    models.forEach((model, index) => {
        if (expandedModels.has(model.name)) {
            const modelId = `model-${index}`;
            fetchAndDisplayModelDetails(modelId, model.name);
        }
    });
}

// Fetch and display model details without toggling
async function fetchAndDisplayModelDetails(modelId, modelName) {
    const detailsDiv = document.getElementById(`${modelId}-details`);
    if (!detailsDiv) return;
    
    try {
        const response = await fetch('/api/ui/model-details', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: modelName })
        });
        
        if (response.ok) {
            const data = await response.json();
            detailsDiv.innerHTML = formatModelDetails(data);
        } else {
            detailsDiv.innerHTML = '<div class="error">Failed to load model details</div>';
        }
    } catch (error) {
        console.error('Error fetching model details:', error);
        detailsDiv.innerHTML = '<div class="error">Error loading model details</div>';
    }
}

// Toggle model details expansion
async function toggleModelDetails(modelId, modelName) {
    const detailsDiv = document.getElementById(`${modelId}-details`);
    const arrow = document.getElementById(`${modelId}-arrow`);
    
    if (detailsDiv.style.display === 'none') {
        // Expand
        detailsDiv.style.display = 'block';
        arrow.textContent = '▼';
        expandedModels.add(modelName); // Track that this model is expanded
        
        // Fetch and display model details
        fetchAndDisplayModelDetails(modelId, modelName);
    } else {
        // Collapse
        detailsDiv.style.display = 'none';
        arrow.textContent = '▶';
        expandedModels.delete(modelName); // Remove from expanded set
    }
}

// Format model details for display
function formatModelDetails(data) {
    let html = '<div class="model-details-content">';
    
    // Model info section
    if (data.model_info) {
        html += '<div class="detail-section"><h4>Model Information</h4><div class="detail-grid">';
        
        // Extract key information
        const info = data.model_info;
        const details = data.details || {};
        
        // Basic info
        if (details.format) html += `<div class="detail-item"><span class="detail-label">Format:</span> ${details.format}</div>`;
        if (details.family) html += `<div class="detail-item"><span class="detail-label">Family:</span> ${details.family}</div>`;
        if (details.parameter_size) html += `<div class="detail-item"><span class="detail-label">Parameters:</span> ${details.parameter_size}</div>`;
        if (details.quantization_level) html += `<div class="detail-item"><span class="detail-label">Quantization:</span> ${details.quantization_level}</div>`;
        
        // Context info
        const contextKey = details.family ? `${details.family}.context_length` : null;
        if (contextKey && info[contextKey]) {
            html += `<div class="detail-item"><span class="detail-label">Default Context:</span> ${info[contextKey]}</div>`;
        }
        
        html += '</div></div>';
    }
    
    // Template section
    if (data.template) {
        html += '<div class="detail-section"><h4>Template</h4>';
        html += `<pre class="template-preview">${escapeHtml(data.template)}</pre>`;
        html += '</div>';
    }
    
    // Parameters section
    if (data.parameters) {
        html += '<div class="detail-section"><h4>Parameters</h4>';
        html += `<pre class="parameters-preview">${escapeHtml(data.parameters)}</pre>`;
        html += '</div>';
    }
    
    // Modelfile section (if available)
    if (data.modelfile) {
        html += '<div class="detail-section"><h4>Modelfile</h4>';
        html += `<pre class="modelfile-preview">${escapeHtml(data.modelfile)}</pre>`;
        html += '</div>';
    }
    
    html += '</div>';
    return html;
}

// Escape HTML for safe display
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Format file size
function formatSize(bytes) {
    if (!bytes) return '0 B';
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
}

// Modal functions
async function openLoadModal(modelName) {
    loadModelNameInput.value = modelName;

    // Populate instance dropdown
    loadInstanceSelect.innerHTML = '<option value="">Select instance...</option>';
    OLLAMA_INSTANCES.forEach(instance => {
        const option = document.createElement('option');
        option.value = instance.name;
        option.textContent = instance.name;
        loadInstanceSelect.appendChild(option);
    });

    // Try to fetch model details to get default context size
    try {
        const response = await fetch('/api/ui/model-details', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: modelName })
        });

        if (response.ok) {
            const data = await response.json();

            // Extract default context size from model info
            let defaultContext = null;
            if (data.model_info && data.details && data.details.family) {
                const contextKey = data.details.family + '.context_length';
                defaultContext = data.model_info[contextKey];
            }

            // Update the context input placeholder with model default
            if (defaultContext) {
                loadContextInput.placeholder = `Default: ${defaultContext}`;

                // Add a hint about the default context
                const existingHint = document.getElementById('context-hint');
                if (existingHint) {
                    existingHint.textContent = `Model default context: ${defaultContext}`;
                } else {
                    const hint = document.createElement('small');
                    hint.id = 'context-hint';
                    hint.style.color = '#666';
                    hint.textContent = `Model default context: ${defaultContext}`;
                    loadContextInput.parentNode.appendChild(hint);
                }
            }
        }
    } catch (error) {
        console.error('Error fetching model details:', error);
        // Continue without model details
    }

    loadModal.style.display = 'block';
}

function closeLoadModal() {
    if (isLoadingModel) {
        return; // Prevent closing while loading
    }
    loadModal.style.display = 'none';
    loadContextInput.value = '';
    loadContextInput.placeholder = '';

    // Remove context hint
    const contextHint = document.getElementById('context-hint');
    if (contextHint) {
        contextHint.remove();
    }
}

// Load model
async function confirmLoadModel() {
    const modelName = loadModelNameInput.value;
    const instanceName = loadInstanceSelect.value;
    const contextLength = loadContextInput.value;

    if (!instanceName) {
        alert('Please select an instance');
        return;
    }

    // Set loading state and disable form controls
    isLoadingModel = true;
    const loadButton = document.querySelector('.btn-primary');
    const cancelButton = document.querySelector('.btn-secondary');
    const closeButton = document.querySelector('.close');
    const originalLoadText = loadButton.textContent;

    loadModelNameInput.disabled = true;
    loadInstanceSelect.disabled = true;
    loadContextInput.disabled = true;
    loadButton.disabled = true;
    cancelButton.disabled = true;
    closeButton.style.opacity = '0.3';
    closeButton.style.cursor = 'not-allowed';
    loadButton.textContent = 'Loading...';
    loadButton.style.opacity = '0.7';

    try {
        const payload = {
            model: modelName
        };

        if (contextLength) {
            payload.options = { num_ctx: parseInt(contextLength) };
        }

        const headers = {
            'Content-Type': 'application/json',
            'X-Target-Instance': instanceName
        };

        // Use /api/generate with empty prompt to load the model
        const loadPayload = {
            ...payload,
            prompt: "",
            stream: false
        };
        
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(loadPayload)
        });

        if (response.ok) {
            // Store the context length if specified
            if (contextLength) {
                try {
                    await fetch('/api/ui/store-context', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            model: modelName,
                            num_ctx: parseInt(contextLength)
                        })
                    });
                } catch (error) {
                    console.error('Failed to store context length:', error);
                }
            }
            
            closeLoadModal();
            setTimeout(refreshData, 2000); // Refresh after 2 seconds
            const contextMsg = contextLength ? ` with context ${contextLength}` : '';
            showSuccess(`Loading ${modelName} on ${instanceName}${contextMsg}...`);
        } else {
            throw new Error(`Failed to load model: ${response.statusText}`);
        }
    } catch (error) {
        console.error('Error loading model:', error);
        showError(`Failed to load model: ${error.message}`);
    } finally {
        // Reset loading state and re-enable form controls
        isLoadingModel = false;
        loadModelNameInput.disabled = false;
        loadInstanceSelect.disabled = false;
        loadContextInput.disabled = false;
        loadButton.disabled = false;
        cancelButton.disabled = false;
        closeButton.style.opacity = '1';
        closeButton.style.cursor = 'pointer';
        loadButton.textContent = originalLoadText;
        loadButton.style.opacity = '1';
    }
}

// Unload model
async function unloadModel(modelName) {
    if (!confirm(`Are you sure you want to unload ${modelName}?`)) {
        return;
    }

    try {
        const instances = runningModels[modelName] || [];

        for (const instanceName of instances) {
            const response = await fetch('/api/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Target-Instance': instanceName
                },
                body: JSON.stringify({
                    model: modelName,
                    keep_alive: 0
                })
            });

            if (!response.ok) {
                throw new Error(`Failed to unload from ${instanceName}`);
            }
        }

        setTimeout(refreshData, 2000); // Refresh after 2 seconds
        showSuccess(`Unloading ${modelName}...`);
    } catch (error) {
        console.error('Error unloading model:', error);
        showError(`Failed to unload model: ${error.message}`);
    }
}

// Unload model from specific instance (used by instance cards)
async function unloadModelFromInstance(modelName, instanceName) {
    if (!confirm(`Are you sure you want to unload ${modelName} from ${instanceName}?`)) {
        return;
    }

    try {
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Target-Instance': instanceName
            },
            body: JSON.stringify({
                model: modelName,
                keep_alive: 0
            })
        });

        if (!response.ok) {
            throw new Error(`Failed to unload from ${instanceName}: ${response.statusText}`);
        }

        setTimeout(refreshData, 2000); // Refresh after 2 seconds
        showSuccess(`Unloading ${modelName} from ${instanceName}...`);
    } catch (error) {
        console.error('Error unloading model:', error);
        showError(`Failed to unload model: ${error.message}`);
    }
}

// Utility functions
function showSuccess(message) {
    console.log('Success:', message);
    // TODO: Implement toast notifications
}

function showError(message) {
    console.error('Error:', message);
    // TODO: Implement toast notifications
}

// Add spin animation for refresh button
const style = document.createElement('style');
style.textContent = `
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initializeApp);