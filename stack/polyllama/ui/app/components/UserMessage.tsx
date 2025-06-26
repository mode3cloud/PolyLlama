'use client'

import { useState } from 'react'
import { ChatMessage, ChatImage } from '../types'
import ImagePreview from './ImagePreview'

interface UserMessageProps {
  message: ChatMessage
}

export default function UserMessage({ message }: UserMessageProps) {
  const [previewImage, setPreviewImage] = useState<{ url: string; name?: string } | null>(null)

  return (
    <>
      <div>
        <div className="whitespace-pre-wrap">{String(message.content || '')}</div>
        {message.images && message.images.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {message.images.map((image, imgIndex) => {
              // Ensure image has valid structure
              if (!image || typeof image !== 'object' || !image.url) {
                return null
              }
              return (
                <div key={imgIndex} className="relative">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={image.url}
                    alt={image.name || `Image ${imgIndex + 1}`}
                    className="max-h-64 max-w-full rounded border border-white/20 cursor-pointer hover:opacity-90 transition-opacity"
                    onClick={() => setPreviewImage({ url: image.url, name: image.name })}
                  />
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Image Preview Modal */}
      <ImagePreview
        imageUrl={previewImage?.url || ''}
        imageName={previewImage?.name}
        isOpen={!!previewImage}
        onClose={() => setPreviewImage(null)}
      />
    </>
  )
}