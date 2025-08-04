'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '../contexts/auth-context'
import { useRouter } from 'next/navigation'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { 
  Folder, 
  File, 
  Calendar, 
  HardDrive, 
  RefreshCw, 
  Brain, 
  Search,
  Eye,
  EyeOff
} from 'lucide-react'
import TreeList from './components/TreeList'
import TreeDiagram from './components/TreeDiagram'
import FileDetailsPanel from './components/FileDetailsPanel'
import AIProposalView from './components/AIProposalView'

// Types for the scan results
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

interface ScanResults {
  scan_id: string
  status: string
  file_count: number
  folder_count: number
  scan_timestamp: string
  tree_data: TreeNode
  files: any[]
  folders: any[]
}

export default function ScanResultsPage() {
  const { user, loading } = useAuth()
  const router = useRouter()
  const supabase = createClientComponentClient()
  const [activeView, setActiveView] = useState<'list' | 'diagram'>('list')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedFile, setSelectedFile] = useState<TreeNode | null>(null)
  const [showDetailsPanel, setShowDetailsPanel] = useState(false)
  const [scanData, setScanData] = useState<ScanResults | null>(null)
  const [loadingData, setLoadingData] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // AI state variables
  const [aiAnalysisId, setAiAnalysisId] = useState<string | null>(null)
  const [aiAnalysisStatus, setAiAnalysisStatus] = useState<string | null>(null)
  const [aiProposal, setAiProposal] = useState<any>(null)
  const [showAIProposal, setShowAIProposal] = useState(false)
  const [loadingAI, setLoadingAI] = useState(false)

  useEffect(() => {
    if (!loading && !user) {
      router.push('/login')
    }
  }, [user, loading, router])

  useEffect(() => {
    if (user) {
      fetchLatestScanResults()
    }
  }, [user])

  const fetchLatestScanResults = async () => {
    try {
      setLoadingData(true)
      setError(null)
      
      // Get the Supabase session token for authentication
      const { data: { session } } = await supabase.auth.getSession()
      const sessionToken = session?.access_token
      
      if (!sessionToken) {
        throw new Error('No session token available')
      }
      
      const response = await fetch('/api/drive/scan-results/latest', {
        headers: {
          'Authorization': `Bearer ${sessionToken}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.status === 404) {
        // No completed scans found - this is expected for new users
        setScanData(null)
        return
      }
      
      if (!response.ok) {
        throw new Error(`Failed to fetch scan results: ${response.statusText}`)
      }

      const data = await response.json()
      setScanData(data)
    } catch (err) {
      console.error('Error fetching scan results:', err)
      setError(err instanceof Error ? err.message : 'Failed to fetch scan results')
    } finally {
      setLoadingData(false)
    }
  }

  const handleRescan = async () => {
    try {
      setLoadingData(true)
      setError(null)
      
      // Get the Supabase session token for authentication
      const { data: { session } } = await supabase.auth.getSession()
      const sessionToken = session?.access_token
      
      if (!sessionToken) {
        throw new Error('No session token available')
      }
      
      const response = await fetch('/api/drive/scan', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${sessionToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          include_folders: true,
          include_files: true,
          max_results: 1000
        })
      })

      if (!response.ok) {
        throw new Error(`Failed to start scan: ${response.statusText}`)
      }

      const data = await response.json()
      
      // Poll for scan completion
      await pollScanStatus(data.scan_id)
    } catch (err) {
      console.error('Error starting scan:', err)
      setError(err instanceof Error ? err.message : 'Failed to start scan')
      setLoadingData(false)
    }
  }

  const pollScanStatus = async (scanId: string) => {
    const maxAttempts = 60 // 5 minutes with 5-second intervals
    let attempts = 0

    const poll = async () => {
      try {
        // Get the Supabase session token for authentication
        const { data: { session } } = await supabase.auth.getSession()
        const sessionToken = session?.access_token
        
        if (!sessionToken) {
          throw new Error('No session token available')
        }
        
        const response = await fetch(`/api/drive/scan/status/${scanId}`, {
          headers: {
            'Authorization': `Bearer ${sessionToken}`,
            'Content-Type': 'application/json'
          }
        })

        if (!response.ok) {
          throw new Error(`Failed to check scan status: ${response.statusText}`)
        }

        const data = await response.json()
        
        if (data.status === 'completed') {
          await fetchLatestScanResults()
          return
        } else if (data.status === 'error') {
          throw new Error(data.error_message || 'Scan failed')
        }

        attempts++
        if (attempts < maxAttempts) {
          setTimeout(poll, 5000) // Poll every 5 seconds
        } else {
          throw new Error('Scan timed out')
        }
      } catch (err) {
        console.error('Error polling scan status:', err)
        setError(err instanceof Error ? err.message : 'Failed to check scan status')
        setLoadingData(false)
      }
    }

    poll()
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  // AI Organization Functions
  const handleAIOrganization = async () => {
    if (!scanData) return
    
    try {
      setLoadingAI(true)
      setError(null)
      
      // Get session token
      const { data: { session } } = await supabase.auth.getSession()
      const sessionToken = session?.access_token
      
      if (!sessionToken) {
        throw new Error('No session token available')
      }
      
      // Start AI analysis
      const response = await fetch(`/api/ai/analyze/${scanData.scan_id}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${sessionToken}`,
          'Content-Type': 'application/json'
        }
      })
      
      if (!response.ok) {
        throw new Error('Failed to start AI analysis')
      }
      
      const result = await response.json()
      setAiAnalysisId(result.analysis_id)
      setAiAnalysisStatus('processing')
      
      // Poll for results
      await pollAIResults(result.analysis_id, sessionToken)
      
    } catch (error: any) {
      setError('AI analysis failed: ' + error.message)
    } finally {
      setLoadingAI(false)
    }
  }

  const pollAIResults = async (analysisId: string, sessionToken: string) => {
    const poll = async () => {
      try {
        const response = await fetch(`/api/ai/analysis/${analysisId}`, {
          headers: {
            'Authorization': `Bearer ${sessionToken}`,
            'Content-Type': 'application/json'
          }
        })
        
        if (!response.ok) {
          throw new Error('Failed to check AI analysis status')
        }
        
        const status = await response.json()
        setAiAnalysisStatus(status.status)
        
        if (status.status === 'completed') {
          // Get proposal
          const proposalResponse = await fetch(`/api/ai/proposal/${analysisId}`, {
            headers: {
              'Authorization': `Bearer ${sessionToken}`,
              'Content-Type': 'application/json'
            }
          })
          
          if (proposalResponse.ok) {
            const proposal = await proposalResponse.json()
            setAiProposal(proposal)
            setShowAIProposal(true)
          }
          return
        } else if (status.status === 'error') {
          setError('AI analysis failed: ' + (status.error_message || 'Unknown error'))
          return
        }
        
        // Continue polling
        setTimeout(poll, 2000)
        
      } catch (error: any) {
        setError('Failed to check AI analysis status: ' + error.message)
      }
    }
    
    poll()
  }

  const handleApplyAIProposal = async () => {
    if (!aiAnalysisId || !aiProposal) return
    
    try {
      setLoadingAI(true)
      
      const { data: { session } } = await supabase.auth.getSession()
      const sessionToken = session?.access_token
      
      if (!sessionToken) {
        throw new Error('No session token available')
      }
      
      const response = await fetch(`/api/ai/apply/${aiAnalysisId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${sessionToken}`,
          'Content-Type': 'application/json'
        }
      })
      
      if (!response.ok) {
        throw new Error('Failed to apply AI proposal')
      }
      
      const result = await response.json()
      
      // Show success message
      alert(`Successfully applied ${result.results.successful_moves.length} file moves!`)
      
      // Refresh scan data
      await fetchLatestScanResults()
      
      // Reset AI state
      setShowAIProposal(false)
      setAiProposal(null)
      setAiAnalysisId(null)
      setAiAnalysisStatus(null)
      
    } catch (error: any) {
      setError('Failed to apply AI proposal: ' + error.message)
    } finally {
      setLoadingAI(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="loading-spinner"></div>
      </div>
    )
  }

  if (!user) {
    return null // Will redirect to login
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation Header */}
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <h1 className="text-xl font-semibold text-gray-900">
                Drive Organizer
              </h1>
            </div>
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                {user.user_metadata?.avatar_url && (
                  <img
                    src={user.user_metadata.avatar_url}
                    alt="Profile"
                    className="w-8 h-8 rounded-full"
                  />
                )}
                <span className="text-sm text-gray-700">
                  {user.user_metadata?.full_name || user.email}
                </span>
              </div>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        {/* Page Header */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between">
            <div className="flex-1">
              <h2 className="text-2xl font-bold text-gray-900 mb-2">
                Drive Structure
              </h2>
              {scanData ? (
                <div className="flex flex-wrap items-center gap-4 text-sm text-gray-600">
                  <span className="flex items-center gap-1">
                    <Calendar className="w-4 h-4" />
                    Last scanned: {formatDate(scanData.scan_timestamp)}
                  </span>
                  <span className="flex items-center gap-1">
                    <Folder className="w-4 h-4" />
                    {scanData.folder_count} folders
                  </span>
                  <span className="flex items-center gap-1">
                    <File className="w-4 h-4" />
                    {scanData.file_count} files
                  </span>
                  <span className="flex items-center gap-1">
                    <HardDrive className="w-4 h-4" />
                    {scanData.folder_count + scanData.file_count} total items
                  </span>
                </div>
              ) : (
                <p className="text-gray-600">No scan data available</p>
              )}
            </div>
            <div className="flex flex-col sm:flex-row gap-3 mt-4 lg:mt-0">
              <button 
                onClick={handleRescan}
                disabled={loadingData}
                className="btn btn-secondary flex items-center gap-2 disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${loadingData ? 'animate-spin' : ''}`} />
                {loadingData ? 'Scanning...' : 'Rescan Drive'}
              </button>
              <button 
                onClick={handleAIOrganization}
                disabled={loadingAI || !scanData}
                className="btn btn-primary flex items-center gap-2 disabled:opacity-50"
              >
                <Brain className={`w-4 h-4 ${loadingAI ? 'animate-spin' : ''}`} />
                {loadingAI ? 'Analyzing...' : 'Organize with AI'}
              </button>
            </div>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <h3 className="text-sm font-medium text-red-800">Error</h3>
                <div className="mt-2 text-sm text-red-700">
                  <p>{error}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Search Bar */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              placeholder="Search files and folders..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* View Toggle */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-1 mb-6">
          <div className="flex">
            <button
              onClick={() => setActiveView('list')}
              className={`flex-1 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                activeView === 'list'
                  ? 'bg-primary-600 text-white'
                  : 'text-gray-700 hover:text-gray-900 hover:bg-gray-100'
              }`}
            >
              Tree List
            </button>
            <button
              onClick={() => setActiveView('diagram')}
              className={`flex-1 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                activeView === 'diagram'
                  ? 'bg-primary-600 text-white'
                  : 'text-gray-700 hover:text-gray-900 hover:bg-gray-100'
              }`}
            >
              Tree Diagram
            </button>
          </div>
        </div>

        {/* Loading State */}
        {loadingData && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12">
            <div className="flex flex-col items-center justify-center">
              <div className="loading-spinner mb-4"></div>
              <p className="text-gray-600">Loading scan results...</p>
            </div>
          </div>
        )}

        {/* Main Content Area */}
        {!loadingData && scanData && (
          <div className="flex gap-6">
            {/* Tree View */}
            <div className={`flex-1 bg-white rounded-lg shadow-sm border border-gray-200 ${
              showDetailsPanel ? 'lg:w-2/3' : 'w-full'
            }`}>
              {activeView === 'list' ? (
                <TreeList
                  data={scanData.tree_data}
                  searchQuery={searchQuery}
                  onFileSelect={(file: TreeNode) => {
                    setSelectedFile(file)
                    setShowDetailsPanel(true)
                  }}
                />
              ) : (
                <TreeDiagram
                  data={scanData.tree_data}
                  searchQuery={searchQuery}
                  onFileSelect={(file: TreeNode) => {
                    setSelectedFile(file)
                    setShowDetailsPanel(true)
                  }}
                />
              )}
            </div>

            {/* File Details Panel */}
            {showDetailsPanel && selectedFile && (
              <div className="w-full lg:w-1/3">
                <FileDetailsPanel
                  file={selectedFile}
                  onClose={() => {
                    setShowDetailsPanel(false)
                    setSelectedFile(null)
                  }}
                />
              </div>
            )}
          </div>
        )}

        {/* No Data State */}
        {!loadingData && !scanData && !error && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12">
            <div className="flex flex-col items-center justify-center text-center">
              <Folder className="w-16 h-16 text-gray-400 mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No Scan Data Available</h3>
              <p className="text-gray-600 mb-6">
                Run your first scan to see your Google Drive structure.
              </p>
              <button 
                onClick={handleRescan}
                className="btn btn-primary flex items-center gap-2"
              >
                <RefreshCw className="w-4 h-4" />
                Start First Scan
              </button>
            </div>
          </div>
        )}

        {/* AI Proposal Modal */}
        {showAIProposal && aiProposal && (
          <AIProposalView
            proposal={aiProposal}
            onApply={handleApplyAIProposal}
            onCancel={() => {
              setShowAIProposal(false)
              setAiProposal(null)
              setAiAnalysisId(null)
              setAiAnalysisStatus(null)
            }}
            loading={loadingAI}
          />
        )}

        {/* AI Analysis Progress Indicator */}
        {aiAnalysisStatus === 'processing' && (
          <div className="fixed bottom-4 right-4 bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              <span>AI Analysis in Progress...</span>
            </div>
          </div>
        )}
      </main>
    </div>
  )
} 