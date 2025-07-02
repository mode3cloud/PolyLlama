'use client'

import { useState } from 'react'
import { ChevronRightIcon, ChevronDownIcon, FolderIcon, FolderOpenIcon, InboxIcon, PaperAirplaneIcon, DocumentIcon, TrashIcon, ArchiveBoxIcon } from '@heroicons/react/24/outline'

interface MailFolder {
  id: string
  displayName: string
  parentFolderId?: string
  childFolderCount: number
  unreadItemCount: number
  totalItemCount: number
  childFolders?: MailFolder[]
}

interface FolderTreeProps {
  folders: MailFolder[]
  selectedFolderId: string | null
  onFolderSelect: (folderId: string | null) => void
  isLoading?: boolean
}

const SPECIAL_FOLDER_ICONS: Record<string, any> = {
  'inbox': InboxIcon,
  'sentitems': PaperAirplaneIcon,
  'sent': PaperAirplaneIcon,
  'drafts': DocumentIcon,
  'deleteditems': TrashIcon,
  'deleted': TrashIcon,
  'trash': TrashIcon,
  'archive': ArchiveBoxIcon,
  'junk': TrashIcon,
  'spam': TrashIcon,
}

function FolderItem({ 
  folder, 
  level = 0, 
  selectedFolderId, 
  onFolderSelect 
}: { 
  folder: MailFolder
  level?: number
  selectedFolderId: string | null
  onFolderSelect: (folderId: string | null) => void
}) {
  const [isExpanded, setIsExpanded] = useState(true)
  const hasChildren = folder.childFolders && folder.childFolders.length > 0
  
  // Get icon for special folders
  const folderNameLower = folder.displayName.toLowerCase().replace(/\s+/g, '')
  const IconComponent = SPECIAL_FOLDER_ICONS[folderNameLower] || (isExpanded ? FolderOpenIcon : FolderIcon)
  
  const isSelected = selectedFolderId === folder.id

  return (
    <div>
      <div
        className={`flex items-center px-2 py-1 cursor-pointer hover:bg-gray-100 rounded ${
          isSelected ? 'bg-blue-50 text-blue-600' : ''
        }`}
        style={{ paddingLeft: `${level * 12 + 8}px` }}
        onClick={() => onFolderSelect(folder.id)}
      >
        {hasChildren && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              setIsExpanded(!isExpanded)
            }}
            className="p-0.5 hover:bg-gray-200 rounded"
          >
            {isExpanded ? (
              <ChevronDownIcon className="h-3 w-3" />
            ) : (
              <ChevronRightIcon className="h-3 w-3" />
            )}
          </button>
        )}
        {!hasChildren && <div className="w-4" />}
        
        <IconComponent className="h-4 w-4 mx-1 flex-shrink-0" />
        
        <span className="text-sm flex-grow truncate">{folder.displayName}</span>
        
        {folder.unreadItemCount > 0 && (
          <span className="text-xs bg-gray-200 text-gray-700 px-1.5 py-0.5 rounded-full ml-1">
            {folder.unreadItemCount}
          </span>
        )}
      </div>
      
      {isExpanded && hasChildren && (
        <div>
          {folder.childFolders!.map((childFolder) => (
            <FolderItem
              key={childFolder.id}
              folder={childFolder}
              level={level + 1}
              selectedFolderId={selectedFolderId}
              onFolderSelect={onFolderSelect}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export default function FolderTree({ folders, selectedFolderId, onFolderSelect, isLoading }: FolderTreeProps) {
  if (isLoading) {
    return (
      <div className="p-4">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2 mb-2 ml-4"></div>
          <div className="h-4 bg-gray-200 rounded w-2/3 mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2 mb-2"></div>
        </div>
      </div>
    )
  }

  // Sort folders to put special folders first
  const sortedFolders = [...folders].sort((a, b) => {
    const aIsSpecial = SPECIAL_FOLDER_ICONS[a.displayName.toLowerCase().replace(/\s+/g, '')]
    const bIsSpecial = SPECIAL_FOLDER_ICONS[b.displayName.toLowerCase().replace(/\s+/g, '')]
    
    if (aIsSpecial && !bIsSpecial) return -1
    if (!aIsSpecial && bIsSpecial) return 1
    
    // Sort special folders in a specific order
    const specialOrder = ['inbox', 'sentitems', 'sent', 'drafts', 'deleteditems', 'deleted', 'trash', 'junk', 'spam', 'archive']
    const aIndex = specialOrder.indexOf(a.displayName.toLowerCase().replace(/\s+/g, ''))
    const bIndex = specialOrder.indexOf(b.displayName.toLowerCase().replace(/\s+/g, ''))
    
    if (aIndex !== -1 && bIndex !== -1) {
      return aIndex - bIndex
    }
    
    return a.displayName.localeCompare(b.displayName)
  })

  return (
    <div className="py-2">
      <div className="px-4 pb-2">
        <button
          onClick={() => onFolderSelect(null)}
          className={`text-sm font-medium ${
            selectedFolderId === null ? 'text-blue-600' : 'text-gray-700 hover:text-gray-900'
          }`}
        >
          All Mail
        </button>
      </div>
      
      <div className="border-t pt-2">
        {sortedFolders.map((folder) => (
          <FolderItem
            key={folder.id}
            folder={folder}
            selectedFolderId={selectedFolderId}
            onFolderSelect={onFolderSelect}
          />
        ))}
      </div>
    </div>
  )
}