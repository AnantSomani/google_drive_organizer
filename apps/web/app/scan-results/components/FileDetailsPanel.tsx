'use client'

import { 
  X, 
  ExternalLink, 
  Download, 
  Share2, 
  Calendar, 
  User, 
  HardDrive,
  FileText,
  Image,
  Video,
  Music,
  Archive
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

interface FileDetailsPanelProps {
  file: TreeNode
  onClose: () => void
}

const getFileIcon = (mimeType?: string) => {
  if (!mimeType) return <FileText className="w-6 h-6" />
  
  if (mimeType.includes('image/')) return <Image className="w-6 h-6" />
  if (mimeType.includes('video/')) return <Video className="w-6 h-6" />
  if (mimeType.includes('audio/')) return <Music className="w-6 h-6" />
  if (mimeType.includes('application/zip') || mimeType.includes('application/x-rar')) return <Archive className="w-6 h-6" />
  if (mimeType.includes('application/pdf')) return <FileText className="w-6 h-6" />
  if (mimeType.includes('application/vnd.openxmlformats-officedocument')) return <FileText className="w-6 h-6" />
  
  return <FileText className="w-6 h-6" />
}

const formatFileSize = (bytes?: number) => {
  if (!bytes) return 'Unknown size'
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const formatDate = (dateString: string) => {
  if (!dateString) return 'Unknown date'
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

export default function FileDetailsPanel({ file, onClose }: FileDetailsPanelProps) {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-gray-900">File Details</h3>
        <button
          onClick={onClose}
          className="p-1 hover:bg-gray-100 rounded-full"
        >
          <X className="w-5 h-5 text-gray-500" />
        </button>
      </div>

      {/* File Info */}
      <div className="space-y-6">
        {/* File Icon and Name */}
        <div className="flex items-center gap-3">
          <div className="p-3 bg-gray-100 rounded-lg">
            {getFileIcon(file.mime_type)}
          </div>
          <div className="flex-1">
            <h4 className="font-medium text-gray-900">{file.name}</h4>
            <p className="text-sm text-gray-500">
              {file.type === 'folder' ? 'Folder' : 'File'}
            </p>
          </div>
        </div>

        {/* Quick Actions */}
        {file.type === 'file' && (
          <div className="flex gap-2">
            <button 
              onClick={() => {
                if (file.web_view_link) {
                  window.open(file.web_view_link, '_blank')
                }
              }}
              className="flex-1 btn btn-primary flex items-center justify-center gap-2"
            >
              <ExternalLink className="w-4 h-4" />
              Open in Drive
            </button>
            <button 
              onClick={() => {
                if (file.web_view_link) {
                  window.open(file.web_view_link, '_blank')
                }
              }}
              className="flex-1 btn btn-secondary flex items-center justify-center gap-2"
            >
              <Download className="w-4 h-4" />
              Download
            </button>
            <button 
              onClick={() => {
                if (file.web_view_link) {
                  window.open(file.web_view_link, '_blank')
                }
              }}
              className="flex-1 btn btn-secondary flex items-center justify-center gap-2"
            >
              <Share2 className="w-4 h-4" />
              Share
            </button>
          </div>
        )}

        {/* Metadata */}
        <div className="space-y-4">
          <h5 className="font-medium text-gray-900">File Information</h5>
          
          <div className="space-y-3">
            {file.size && (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <HardDrive className="w-4 h-4" />
                  <span>Size</span>
                </div>
                <span className="text-sm font-medium text-gray-900">
                  {formatFileSize(file.size)}
                </span>
              </div>
            )}

            {file.created_time && (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <Calendar className="w-4 h-4" />
                  <span>Created</span>
                </div>
                <span className="text-sm font-medium text-gray-900">
                  {formatDate(file.created_time)}
                </span>
              </div>
            )}

            {file.modified_time && (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <Calendar className="w-4 h-4" />
                  <span>Modified</span>
                </div>
                <span className="text-sm font-medium text-gray-900">
                  {formatDate(file.modified_time)}
                </span>
              </div>
            )}

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <User className="w-4 h-4" />
                <span>Owner</span>
              </div>
              <span className="text-sm font-medium text-gray-900">
                You
              </span>
            </div>

            {file.mime_type && (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <FileText className="w-4 h-4" />
                  <span>Type</span>
                </div>
                <span className="text-sm font-medium text-gray-900">
                  {file.mime_type}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* File Path */}
        <div className="space-y-2">
          <h5 className="font-medium text-gray-900">Location</h5>
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-600 font-mono">
              /My Drive/{file.name}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
} 