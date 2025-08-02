'use client'

import { useState } from 'react'
import { 
  Folder, 
  FileText, 
  Image, 
  Video, 
  Music, 
  Archive,
  ChevronRight,
  ChevronDown,
  ExternalLink,
  Download,
  Share2
} from 'lucide-react'

interface TreeNode {
  id: string
  name: string
  type: 'file' | 'folder'
  mime_type?: string
  size?: number
  created_time?: string
  modified_time?: string
  parents: string[]
  web_view_link: string
  children: TreeNode[]
  level: number
}

interface TreeListProps {
  data: TreeNode
  searchQuery: string
  onFileSelect: (file: TreeNode) => void
}

const getFileIcon = (mimeType?: string) => {
  if (!mimeType) return <FileText className="w-4 h-4" />
  
  if (mimeType.includes('image/')) return <Image className="w-4 h-4" />
  if (mimeType.includes('video/')) return <Video className="w-4 h-4" />
  if (mimeType.includes('audio/')) return <Music className="w-4 h-4" />
  if (mimeType.includes('application/zip') || mimeType.includes('application/x-rar')) return <Archive className="w-4 h-4" />
  if (mimeType.includes('application/pdf')) return <FileText className="w-4 h-4" />
  if (mimeType.includes('application/vnd.openxmlformats-officedocument')) return <FileText className="w-4 h-4" />
  
  return <FileText className="w-4 h-4" />
}

const formatFileSize = (bytes?: number) => {
  if (!bytes) return ''
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const TreeNode = ({ node, level, searchQuery, onFileSelect }: {
  node: TreeNode
  level: number
  searchQuery: string
  onFileSelect: (file: TreeNode) => void
}) => {
  const [isExpanded, setIsExpanded] = useState(level < 2) // Auto-expand first 2 levels
  const hasChildren = node.children && node.children.length > 0
  const isFolder = node.type === 'folder'
  
  // Highlight search matches
  const highlightSearch = (text: string) => {
    if (!searchQuery) return text
    const regex = new RegExp(`(${searchQuery})`, 'gi')
    const parts = text.split(regex)
    return parts.map((part, index) => 
      regex.test(part) ? (
        <span key={index} className="bg-yellow-200 font-medium">{part}</span>
      ) : part
    )
  }

  return (
    <div>
      <div 
        className={`flex items-center py-2 px-3 hover:bg-gray-50 cursor-pointer group ${
          level > 0 ? 'border-l border-gray-200' : ''
        }`}
        style={{ paddingLeft: `${level * 20 + 12}px` }}
        onClick={() => {
          if (isFolder) {
            setIsExpanded(!isExpanded)
          } else {
            onFileSelect(node)
          }
        }}
      >
        {/* Expand/Collapse Icon */}
        {isFolder && (
          <div className="w-4 h-4 mr-2 flex items-center justify-center">
            {hasChildren ? (
              isExpanded ? (
                <ChevronDown className="w-4 h-4 text-gray-500" />
              ) : (
                <ChevronRight className="w-4 h-4 text-gray-500" />
              )
            ) : (
              <div className="w-4 h-4" />
            )}
          </div>
        )}
        
        {/* File/Folder Icon */}
        <div className="w-4 h-4 mr-3 flex items-center justify-center">
          {isFolder ? (
            <Folder className="w-4 h-4 text-blue-500" />
          ) : (
            getFileIcon(node.mime_type)
          )}
        </div>
        
        {/* Name */}
        <span className="flex-1 text-sm text-gray-900">
          {highlightSearch(node.name)}
        </span>
        
        {/* File Size */}
        {!isFolder && node.size && (
          <span className="text-xs text-gray-500 mr-2">
            {formatFileSize(node.size)}
          </span>
        )}
        
        {/* Actions */}
        <div className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
          {!isFolder && (
            <>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  // Open in Drive
                  if (node.web_view_link) {
                    window.open(node.web_view_link, '_blank')
                  }
                }}
                className="p-1 hover:bg-gray-200 rounded"
                title="Open in Drive"
              >
                <ExternalLink className="w-3 h-3 text-gray-500" />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  // Download
                  if (node.web_view_link) {
                    window.open(node.web_view_link, '_blank')
                  }
                }}
                className="p-1 hover:bg-gray-200 rounded"
                title="Download"
              >
                <Download className="w-3 h-3 text-gray-500" />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  // Share
                  if (node.web_view_link) {
                    window.open(node.web_view_link, '_blank')
                  }
                }}
                className="p-1 hover:bg-gray-200 rounded"
                title="Share"
              >
                <Share2 className="w-3 h-3 text-gray-500" />
              </button>
            </>
          )}
        </div>
      </div>
      
      {/* Children */}
      {isFolder && isExpanded && hasChildren && (
        <div>
          {node.children.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              level={level + 1}
              searchQuery={searchQuery}
              onFileSelect={onFileSelect}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export default function TreeList({ data, searchQuery, onFileSelect }: TreeListProps) {
  return (
    <div className="p-4">
      <div className="text-sm text-gray-500 mb-4 pb-2 border-b">
        Showing {data.children?.length || 0} root items
        {searchQuery && ` matching "${searchQuery}"`}
      </div>
      <TreeNode
        node={data}
        level={0}
        searchQuery={searchQuery}
        onFileSelect={onFileSelect}
      />
    </div>
  )
} 