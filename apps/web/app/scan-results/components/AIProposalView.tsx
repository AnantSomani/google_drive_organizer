'use client'

import { Folder, File, X, Check, AlertTriangle, Search } from 'lucide-react'
import { useMemo, useState } from 'react'

interface AIProposalViewProps {
  proposal: any
  onApply: () => void
  onCancel: () => void
  loading?: boolean
  folderIdToName?: Record<string, string>
}

export default function AIProposalView({ proposal, onApply, onCancel, loading, folderIdToName = {} }: AIProposalViewProps) {
  const movesByFolder = useMemo(() => {
    const grouped: Record<string, any[]> = {}
    if (!proposal?.file_moves) return grouped
    for (const move of proposal.file_moves) {
      const key = move.proposed_folder || 'Uncategorized'
      if (!grouped[key]) grouped[key] = []
      grouped[key].push(move)
    }
    return grouped
  }, [proposal])

  const [selectedFolderName, setSelectedFolderName] = useState<string>(
    proposal?.proposed_folders?.[0]?.name || ''
  )
  const [searchQuery, setSearchQuery] = useState('')

  const selectedMoves = useMemo(() => {
    const list = selectedFolderName ? (movesByFolder[selectedFolderName] || []) : []
    if (!searchQuery) return list
    const q = searchQuery.toLowerCase()
    return list.filter((m) => String(m.file_name || '').toLowerCase().includes(q))
  }, [movesByFolder, selectedFolderName, searchQuery])

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-xl font-semibold text-gray-900">AI Organization Proposal</h2>
          <button
            onClick={onCancel}
            className="text-gray-400 hover:text-gray-600"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-140px)]">
          {/* Summary */}
          <div className="mb-6 p-4 bg-blue-50 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <Check className="w-5 h-5 text-blue-600" />
              <span className="font-medium text-blue-900">AI Analysis Complete</span>
            </div>
            <p className="text-blue-700 text-sm">
              Analyzed {proposal.total_items} items and proposed {proposal.proposed_folders.length} new folders
            </p>
          </div>
          
          {/* Proposed Folders + Details (side-by-side) */}
          <div className="mb-6">
            <h3 className="text-lg font-medium text-gray-900 mb-3">New Folder Structure</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Left: Proposed folders */}
              <div className="space-y-2">
                {proposal.proposed_folders.map((folder: any, index: number) => {
                  const count = (movesByFolder[folder.name] || []).length
                  const selected = folder.name === selectedFolderName
                  return (
                    <button
                      key={index}
                      onClick={() => setSelectedFolderName(folder.name)}
                      className={`w-full text-left p-3 rounded-lg border transition-colors ${selected ? 'bg-blue-50 border-blue-200' : 'bg-gray-50 border-gray-200 hover:bg-gray-100'}`}
                    >
                      <div className="flex items-start gap-3">
                        <Folder className="w-5 h-5 text-blue-500 mt-0.5" />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-2">
                            <div className="font-medium text-gray-900 truncate">{folder.name}</div>
                            <span className="shrink-0 text-xs px-2 py-0.5 rounded-full bg-white border border-gray-200 text-gray-600">{count}</span>
                          </div>
                          <div className="text-sm text-gray-600">{folder.description}</div>
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>

              {/* Right: Details for selected folder */}
              <div className="border rounded-lg">
                <div className="p-3 border-b flex items-center gap-2">
                  <Search className="w-4 h-4 text-gray-400" />
                  <input
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder={`Search files in "${selectedFolderName || 'Select a folder'}"`}
                    className="w-full outline-none text-sm"
                  />
                </div>
                <div className="max-h-64 overflow-y-auto">
                  {!selectedFolderName && (
                    <div className="p-4 text-sm text-gray-500">Select a proposed folder to see its file moves.</div>
                  )}
                  {selectedFolderName && selectedMoves.length === 0 && (
                    <div className="p-4 text-sm text-gray-500">No files proposed for this folder.</div>
                  )}
                  {selectedFolderName && selectedMoves.map((move: any, idx: number) => {
                    const fromName = folderIdToName[move.current_parent] || 'My Drive'
                    return (
                      <div key={idx} className="flex items-center gap-3 p-2 border-b last:border-b-0 hover:bg-gray-50">
                        <File className="w-4 h-4 text-gray-500" />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-900 truncate">{move.file_name}</div>
                          <div className="text-xs text-gray-500 truncate">From: {fromName}</div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          </div>
          
          {/* Warning */}
          <div className="mb-6 p-4 bg-yellow-50 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="w-5 h-5 text-yellow-600" />
              <span className="font-medium text-yellow-900">Important</span>
            </div>
            <p className="text-yellow-700 text-sm">
              This will reorganize your Google Drive files. Make sure you have a backup or are comfortable with these changes.
            </p>
          </div>
        </div>
        
        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t bg-gray-50">
          <button
            onClick={onCancel}
            disabled={loading}
            className="btn btn-secondary disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={onApply}
            disabled={loading}
            className="btn btn-primary flex items-center gap-2 disabled:opacity-50"
          >
            {loading ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Applying...
              </>
            ) : (
              <>
                <Check className="w-4 h-4" />
                Apply Changes
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
} 