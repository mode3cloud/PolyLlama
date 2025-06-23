'use client'

import { useState, useRef } from 'react'
import { ChatImage } from '../types'

interface ChatInputProps {
  input: string
  isLoading: boolean
  selectedModel: string
  supportsVision: boolean
  onInputChange: (value: string) => void
  onSendMessage: (images?: ChatImage[]) => void
  onStopGeneration: () => void
}

export default function ChatInput({
  input,
  isLoading,
  selectedModel,
  supportsVision,
  onInputChange,
  onSendMessage,
  onStopGeneration
}: ChatInputProps) {
  const [attachedImages, setAttachedImages] = useState<ChatImage[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handlePaste = async (e: React.ClipboardEvent) => {
    const items = Array.from(e.clipboardData.items)
    const imageItems = items.filter(item => item.type.startsWith('image/'))
    
    if (imageItems.length > 0) {
      if (!supportsVision) {
        e.preventDefault()
        alert('This model does not support image inputs. Please select a vision-enabled model to use images.')
        return
      }
      
      e.preventDefault()
      
      for (const item of imageItems) {
        const file = item.getAsFile()
        if (file) {
          const reader = new FileReader()
          reader.onload = (event) => {
            const dataUrl = event.target?.result as string
            setAttachedImages(prev => [...prev, {
              url: dataUrl,
              name: file.name || 'pasted-image',
              type: file.type
            }])
          }
          reader.readAsDataURL(file)
        }
      }
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    
    if (!supportsVision && files.some(f => f.type.startsWith('image/'))) {
      alert('This model does not support image inputs. Please select a vision-enabled model to use images.')
      // Clear the input
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
      return
    }
    
    for (const file of files) {
      if (file.type.startsWith('image/')) {
        const reader = new FileReader()
        reader.onload = (event) => {
          const dataUrl = event.target?.result as string
          setAttachedImages(prev => [...prev, {
            url: dataUrl,
            name: file.name,
            type: file.type
          }])
        }
        reader.readAsDataURL(file)
      }
    }
  }

  const removeImage = (index: number) => {
    setAttachedImages(prev => prev.filter((_, i) => i !== index))
  }

  const handleSend = () => {
    onSendMessage(attachedImages.length > 0 ? attachedImages : undefined)
    setAttachedImages([])
  }
  return (
    <div className="bg-white border-t border-gray-200 p-4 flex-shrink-0">
      <div className="max-w-4xl mx-auto">
        {/* Image preview area */}
        {attachedImages.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {attachedImages.map((image, index) => (
              <div key={index} className="relative group">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={image.url}
                  alt={image.name}
                  className="h-20 w-20 object-cover rounded border border-gray-300"
                />
                <button
                  onClick={() => removeImage(index)}
                  className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs hover:bg-red-600 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
        
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <input
              type="text"
              value={input}
              onChange={(e) => onInputChange(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
              onPaste={handlePaste}
              placeholder={selectedModel ? (supportsVision ? "Type your message or paste an image..." : "Type your message...") : "Select a model to start chatting"}
              className="w-full px-4 py-3 pr-12 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={isLoading || !selectedModel}
            />
            {/* Image upload button */}
            <button
              onClick={() => fileInputRef.current?.click()}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-gray-500 hover:text-gray-700 disabled:text-gray-300"
              disabled={isLoading || !selectedModel || !supportsVision}
              title={!supportsVision ? "This model doesn't support images" : "Attach image"}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </button>
          </div>
          
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            onChange={handleFileSelect}
            className="hidden"
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
              onClick={handleSend}
              disabled={(!input.trim() && attachedImages.length === 0) || !selectedModel}
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