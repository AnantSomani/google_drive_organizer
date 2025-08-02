'use client'

import { useEffect, useRef, useState } from 'react'
import Tree from 'react-d3-tree'
import { 
  Folder, 
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

interface TreeDiagramProps {
  data: TreeNode
  searchQuery: string
  onFileSelect: (file: TreeNode) => void
}

const getFileIcon = (mimeType?: string) => {
  if (!mimeType) return '📄'
  
  if (mimeType.includes('image/')) return '🖼️'
  if (mimeType.includes('video/')) return '🎥'
  if (mimeType.includes('audio/')) return '🎵'
  if (mimeType.includes('application/zip') || mimeType.includes('application/x-rar')) return '📦'
  if (mimeType.includes('application/pdf')) return '📄'
  if (mimeType.includes('application/vnd.openxmlformats-officedocument')) return '📝'
  
  return '📄'
}

const formatFileSize = (bytes?: number) => {
  if (!bytes) return ''
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// Transform our data structure to D3 tree format
const transformToD3Tree = (node: TreeNode): any => {
  return {
    name: node.name,
    attributes: {
      id: node.id,
      type: node.type,
      mime_type: node.mime_type,
      size: node.size,
      level: node.level
    },
    children: node.children ? node.children.map(transformToD3Tree) : []
  }
}

const CustomNode = ({ nodeDatum, toggleNode, foreignObjectProps }: any) => {
  const isFolder = nodeDatum.attributes?.type === 'folder'
  const isFile = nodeDatum.attributes?.type === 'file'
  const mimeType = nodeDatum.attributes?.mime_type
  const size = nodeDatum.attributes?.size
  
  return (
    <g>
      <circle r={15} fill={isFolder ? '#3b82f6' : '#6b7280'} />
      <foreignObject {...foreignObjectProps}>
        <div className="flex items-center justify-center w-full h-full">
          <span className="text-white text-xs font-bold">
            {isFolder ? '📁' : getFileIcon(mimeType)}
          </span>
        </div>
      </foreignObject>
      {isFolder && nodeDatum.children && (
        <circle
          r={8}
          fill="white"
          stroke="#3b82f6"
          strokeWidth="2"
          onClick={toggleNode}
          style={{ cursor: 'pointer' }}
        />
      )}
    </g>
  )
}

export default function TreeDiagram({ data, searchQuery, onFileSelect }: TreeDiagramProps) {
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 })
  const containerRef = useRef<HTMLDivElement>(null)
  
  useEffect(() => {
    if (containerRef.current) {
      setDimensions({
        width: containerRef.current.offsetWidth,
        height: Math.max(600, window.innerHeight - 400)
      })
    }
  }, [])

  const d3TreeData = transformToD3Tree(data)

  return (
    <div className="p-4">
      <div className="text-sm text-gray-500 mb-4 pb-2 border-b">
        Interactive tree diagram view
        {searchQuery && ` - Filtered by "${searchQuery}"`}
      </div>
      
      <div 
        ref={containerRef}
        className="border border-gray-200 rounded-lg overflow-hidden"
        style={{ height: `${dimensions.height}px` }}
      >
        {dimensions.width > 0 && (
          <Tree
            data={d3TreeData}
            nodeSize={{ x: 200, y: 100 }}
            separation={{ siblings: 1.5, nonSiblings: 2 }}
            translate={{ x: dimensions.width / 2, y: 50 }}
            renderCustomNodeElement={(rd3tProps) => (
              <CustomNode {...rd3tProps} />
            )}
            pathClassFunc={() => 'stroke-gray-300 stroke-2'}
            zoom={0.8}
            scaleExtent={{ min: 0.1, max: 2 }}
            onNodeClick={(nodeDatum: any) => {
              if (nodeDatum.attributes?.type === 'file') {
                onFileSelect({
                  id: nodeDatum.attributes.id,
                  name: nodeDatum.name,
                  type: nodeDatum.attributes.type,
                  mime_type: nodeDatum.attributes.mime_type,
                  size: nodeDatum.attributes.size,
                  created_time: '',
                  modified_time: '',
                  parents: [],
                  web_view_link: '',
                  children: [],
                  level: nodeDatum.attributes.level
                })
              }
            }}
          />
        )}
      </div>
      
      {/* Legend */}
      <div className="mt-4 p-3 bg-gray-50 rounded-lg">
        <div className="text-sm font-medium text-gray-700 mb-2">Legend</div>
        <div className="flex flex-wrap gap-4 text-xs text-gray-600">
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
            <span>Folders</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-gray-500 rounded-full"></div>
            <span>Files</span>
          </div>
          <div className="flex items-center gap-1">
            <span>🖼️</span>
            <span>Images</span>
          </div>
          <div className="flex items-center gap-1">
            <span>📝</span>
            <span>Documents</span>
          </div>
          <div className="flex items-center gap-1">
            <span>🎥</span>
            <span>Videos</span>
          </div>
        </div>
      </div>
    </div>
  )
} 