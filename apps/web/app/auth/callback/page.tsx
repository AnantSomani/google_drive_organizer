'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'

export default function AuthCallbackPage() {
  const router = useRouter()
  const supabase = createClientComponentClient()

  useEffect(() => {
    const handleAuthCallback = async () => {
      try {
        const { data, error } = await supabase.auth.getSession()
        
        if (error) {
          console.error('Auth callback error:', error)
          router.push('/login?error=auth_failed')
          return
        }

        if (data.session) {
          // Debug: Log session data
          console.log('Session data:', {
            hasProviderToken: !!data.session.provider_token,
            hasProviderRefreshToken: !!data.session.provider_refresh_token,
            provider: data.session.user?.app_metadata?.provider,
            expiresIn: data.session.expires_in
          })
          
          // Store Google OAuth tokens if available
          if (data.session.provider_token && data.session.provider_refresh_token) {
            console.log('Attempting to store Google tokens...')
            try {
              const response = await fetch('/api/google/store-token', {
                method: 'POST',
                headers: { 
                  'Content-Type': 'application/json',
                  'Authorization': `Bearer ${data.session.access_token}`
                },
                body: JSON.stringify({
                  access_token: data.session.provider_token,
                  refresh_token: data.session.provider_refresh_token,
                  expires_at: Date.now() + (data.session.expires_in || 3600) * 1000,
                  scope: 'drive'
                })
              })
              
              if (response.ok) {
                console.log('Google tokens stored successfully')
              } else {
                const errorData = await response.json()
                console.error('Failed to store Google tokens:', errorData)
              }
            } catch (tokenError) {
              console.error('Error storing Google tokens:', tokenError)
            }
          } else {
            console.log('No provider tokens available in session')
          }
          
          // Successfully authenticated, redirect to dashboard
          router.push('/dashboard')
        } else {
          // No session found, redirect to login
          router.push('/login')
        }
      } catch (error) {
        console.error('Unexpected error during auth callback:', error)
        router.push('/login?error=unexpected')
      }
    }

    handleAuthCallback()
  }, [router, supabase.auth])

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="loading-spinner mb-4"></div>
        <p className="text-gray-600">Completing authentication...</p>
      </div>
    </div>
  )
} 