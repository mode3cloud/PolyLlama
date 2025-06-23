'use client'

interface ChatInputProps {
  input: string
  isLoading: boolean
  selectedModel: string
  onInputChange: (value: string) => void
  onSendMessage: () => void
  onStopGeneration: () => void
}

export default function ChatInput({
  input,
  isLoading,
  selectedModel,
  onInputChange,
  onSendMessage,
  onStopGeneration
}: ChatInputProps) {
  return (
    <div className="bg-white border-t border-gray-200 p-4 flex-shrink-0">
      <div className="max-w-4xl mx-auto">
        <div className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && onSendMessage()}
            placeholder={selectedModel ? "Type your message..." : "Select a model to start chatting"}
            className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={isLoading || !selectedModel}
          />
          {isLoading ? (
            <button
              onClick={onStopGeneration}
              className="px-6 py-3 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
            >
              Stop
            </button>
          ) : (
            <button
              onClick={onSendMessage}
              disabled={!input.trim() || !selectedModel}
              className="px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              Send
            </button>
          )}
        </div>
      </div>
    </div>
  )
}