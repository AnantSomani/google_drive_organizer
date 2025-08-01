'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '../contexts/auth-context'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'

export default function TestApiPage() {
  const { user } = useAuth()
  const [files, setFiles] = useState<any[]>([])
  const [folders, setFolders] = useState<any[]>([])
  const [scanStatus, setScanStatus] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>('')
  const [accessToken, setAccessToken] = useState<string>('')
  const supabase = createClientComponentClient()

  useEffect(() => {
    const getAccessToken = async () => {
      const { data: { session } } = await supabase.auth.getSession()
      if (session?.access_token) {
        setAccessToken(session.access_token)
      }
    }
    getAccessToken()
  }, [supabase.auth])

  const testGetFiles = async () => {
    if (!accessToken) {
      setError('No access token available')
      return
    }
    
    setLoading(true)
    setError('')
    try {
      const response = await fetch('http://localhost:3030/api/drive/files', {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        }
      })
      
      if (response.ok) {
        const data = await response.json()
        setFiles(data.files || [])
        console.log('Files response:', data)
      } else {
        const errorData = await response.json()
        setError(`Error: ${errorData.detail}`)
      }
    } catch (err) {
      setError(`Network error: ${err}`)
    } finally {
      setLoading(false)
    }
  }

  const testGetFolders = async () => {
    if (!accessToken) {
      setError('No access token available')
      return
    }
    
    setLoading(true)
    setError('')
    try {
      const response = await fetch('http://localhost:3030/api/drive/folders', {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        }
      })
      
      if (response.ok) {
        const data = await response.json()
        setFolders(data.folders || [])
        console.log('Folders response:', data)
      } else {
        const errorData = await response.json()
        setError(`Error: ${errorData.detail}`)
      }
    } catch (err) {
      setError(`Network error: ${err}`)
    } finally {
      setLoading(false)
    }
  }

  const testScanDrive = async () => {
    if (!accessToken) {
      setError('No access token available')
      return
    }
    
    setLoading(true)
    setError('')
    try {
      const response = await fetch('http://localhost:3030/api/drive/scan', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          include_folders: true,
          include_files: true,
          max_results: 100
        })
      })
      
      if (response.ok) {
        const data = await response.json()
        setScanStatus(data)
        console.log('Scan response:', data)
      } else {
        const errorData = await response.json()
        setError(`Error: ${errorData.detail}`)
      }
    } catch (err) {
      setError(`Network error: ${err}`)
    } finally {
      setLoading(false)
    }
  }

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">Please Sign In</h1>
          <p>You need to be authenticated to test the API endpoints.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-8">API Testing Page</h1>
        
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Google Drive API Tests</h2>
          
          <div className="space-y-4">
            <div>
              <button
                onClick={testGetFiles}
                disabled={loading}
                className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
              >
                {loading ? 'Loading...' : 'Test Get Files'}
              </button>
              {files.length > 0 && (
                <div className="mt-2">
                  <h3 className="font-semibold">Files ({files.length}):</h3>
                  <ul className="text-sm">
                    {files.slice(0, 5).map((file, index) => (
                      <li key={index} className="py-1">
                        {file.name} ({file.mime_type})
                      </li>
                    ))}
                    {files.length > 5 && <li>... and {files.length - 5} more</li>}
                  </ul>
                </div>
              )}
            </div>

            <div>
              <button
                onClick={testGetFolders}
                disabled={loading}
                className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 disabled:opacity-50"
              >
                {loading ? 'Loading...' : 'Test Get Folders'}
              </button>
              {folders.length > 0 && (
                <div className="mt-2">
                  <h3 className="font-semibold">Folders ({folders.length}):</h3>
                  <ul className="text-sm">
                    {folders.slice(0, 5).map((folder, index) => (
                      <li key={index} className="py-1">
                        {folder.name}
                      </li>
                    ))}
                    {folders.length > 5 && <li>... and {folders.length - 5} more</li>}
                  </ul>
                </div>
              )}
            </div>

            <div>
              <button
                onClick={testScanDrive}
                disabled={loading}
                className="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700 disabled:opacity-50"
              >
                {loading ? 'Loading...' : 'Test Scan Drive'}
              </button>
              {scanStatus && (
                <div className="mt-2">
                  <h3 className="font-semibold">Scan Status:</h3>
                  <pre className="text-sm bg-gray-100 p-2 rounded">
                    {JSON.stringify(scanStatus, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </div>

          {error && (
            <div className="mt-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
              <strong>Error:</strong> {error}
            </div>
          )}
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">User Info</h2>
          <div className="text-sm">
            <p><strong>Email:</strong> {user.email}</p>
            <p><strong>User ID:</strong> {user.id}</p>
            <p><strong>Access Token:</strong> {accessToken ? 'Present' : 'Missing'}</p>
          </div>
        </div>
      </div>
    </div>
  )
} 