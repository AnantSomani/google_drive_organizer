'use client'

import { Folder, File, X, Check, AlertTriangle } from 'lucide-react'

interface AIProposalViewProps {
  proposal: any
  onApply: () => void
  onCancel: () => void
  loading?: boolean
}

export default function AIProposalView({ proposal, onApply, onCancel, loading }: AIProposalViewProps) {
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
          
          {/* Proposed Folders */}
          <div className="mb-6">
            <h3 className="text-lg font-medium text-gray-900 mb-3">New Folder Structure</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {proposal.proposed_folders.map((folder: any, index: number) => (
                <div key={index} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                  <Folder className="w-5 h-5 text-blue-500" />
                  <div>
                    <div className="font-medium text-gray-900">{folder.name}</div>
                    <div className="text-sm text-gray-600">{folder.description}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          
          {/* File Moves Preview */}
          <div className="mb-6">
            <h3 className="text-lg font-medium text-gray-900 mb-3">
              File Moves ({proposal.file_moves.length} files)
            </h3>
            <div className="max-h-60 overflow-y-auto border rounded-lg">
              {proposal.file_moves.slice(0, 50).map((move: any, index: number) => (
                <div key={index} className="flex items-center gap-3 p-2 border-b last:border-b-0 hover:bg-gray-50">
                  <File className="w-4 h-4 text-gray-500" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-900 truncate">
                      {move.file_name}
                    </div>
                    <div className="text-xs text-gray-500">
                      → {move.proposed_folder}
                    </div>
                  </div>
                </div>
              ))}
              {proposal.file_moves.length > 50 && (
                <div className="p-2 text-sm text-gray-500 text-center">
                  ... and {proposal.file_moves.length - 50} more files
                </div>
              )}
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