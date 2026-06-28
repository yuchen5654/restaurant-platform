import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'

export function Login() {
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)
  const navigate = useNavigate()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const body = new URLSearchParams({ username: email, password })
      const res  = await api.post('/auth/token', body, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      localStorage.setItem('access_token', res.data.access_token)
      navigate('/dashboard')
    } catch {
      setError('Invalid email or password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className='min-h-screen bg-slate-50 flex items-center justify-center'>
      <div className='bg-white rounded-2xl shadow-sm border border-slate-200 p-8 w-full max-w-sm'>
        <h1 className='text-2xl font-bold text-slate-800 mb-1'>Restaurant Platform</h1>
        <p className='text-sm text-slate-500 mb-6'>Sign in to your account</p>
        <form onSubmit={handleSubmit} className='space-y-4'>
          <div>
            <label className='block text-xs font-semibold text-slate-600 mb-1'>Email</label>
            <input type='email' value={email} onChange={e => setEmail(e.target.value)} required
              className='w-full border border-slate-300 rounded-lg px-3 py-2 text-sm
                         focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-200' />
          </div>
          <div>
            <label className='block text-xs font-semibold text-slate-600 mb-1'>Password</label>
            <input type='password' value={password} onChange={e => setPassword(e.target.value)} required
              className='w-full border border-slate-300 rounded-lg px-3 py-2 text-sm
                         focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-200' />
          </div>
          {error && <p className='text-sm text-red-500'>{error}</p>}
          <button type='submit' disabled={loading}
            className='w-full bg-blue-600 text-white py-2.5 rounded-lg font-semibold text-sm
                       hover:bg-blue-700 disabled:opacity-50'>
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
