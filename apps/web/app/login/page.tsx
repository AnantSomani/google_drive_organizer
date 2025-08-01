'use client'

import { useAuth } from '../contexts/auth-context'
import { useState } from 'react'
import { Chrome } from 'lucide-react'

export default function LoginPage() {
  const { signInWithGoogle } = useAuth()
  const [isLoading, setIsLoading] = useState(false)

  const handleGoogleSignIn = async () => {
    try {
      setIsLoading(true)
      await signInWithGoogle()
    } catch (error) {
      console.error('Sign in error:', error)
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-gray-900">Drive Organizer</h1>
          <p className="mt-2 text-gray-600">
            AI-powered Google Drive file organization
          </p>
        </div>

        <div className="card">
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-semibold text-gray-900 text-center">
                Sign in to continue
              </h2>
              <p className="mt-2 text-sm text-gray-600 text-center">
                Connect your Google Drive to get started
              </p>
            </div>

            <button
              onClick={handleGoogleSignIn}
              disabled={isLoading}
              className="w-full btn btn-primary flex items-center justify-center space-x-2"
            >
              {isLoading ? (
                <div className="loading-spinner"></div>
              ) : (
                <Chrome className="h-5 w-5" />
              )}
              <span>
                {isLoading ? 'Signing in...' : 'Sign in with Google'}
              </span>
            </button>

            <div className="text-xs text-gray-500 text-center">
              By signing in, you agree to our terms of service and privacy policy
            </div>
          </div>
        </div>
      </div>
    </div>
  )
} 