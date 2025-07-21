/**
 * Utility functions for determining model capabilities based on model names and patterns
 * This mirrors the capability detection logic from the LLM proxy service
 */

/**
 * Patterns that indicate vision support in model names
 */
const VISION_PATTERNS = [
  'vision',
  'llava',
  'bakllava', 
  'vl',
  'minicpm-v',
  'llama3.2-vision',
  'llama3.2:11b-vision',
  'llama3.2:90b-vision',
  'pixtral'
]

/**
 * Patterns that indicate tool/function calling support in model names
 */
const TOOL_PATTERNS = [
  'devstral',
  'mistral-nemo', 
  'llama3.1',
  'llama3.3',
  'firefunction',
  'tools',
  'function',
  'functionary',
  'hermes',
  'nous-hermes'
]

/**
 * Check if a model supports vision capabilities based on its name
 */
export function supportsVision(modelName: string): boolean {
  const name = modelName.toLowerCase()
  return VISION_PATTERNS.some(pattern => name.includes(pattern))
}

/**
 * Check if a model supports tool/function calling based on its name
 */
export function supportsTools(modelName: string): boolean {
  const name = modelName.toLowerCase()
  return TOOL_PATTERNS.some(pattern => name.includes(pattern))
}

/**
 * Get both capabilities for a model
 */
export function getModelCapabilities(modelName: string): {
  supports_vision: boolean
  supports_tools: boolean
} {
  return {
    supports_vision: supportsVision(modelName),
    supports_tools: supportsTools(modelName)
  }
}