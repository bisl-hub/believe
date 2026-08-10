import { useState, useEffect } from 'react'
import { Mail, Lock, CheckCircle, AlertCircle, Eye, EyeOff, ArrowLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import api from '../lib/axios'

interface UserInfo {
  id: number
  email: string
  is_active: boolean
}

type Status = { type: 'success' | 'error'; message: string } | null

function StatusBanner({ status }: { status: Status }) {
  if (!status) return null
  return (
    <div className={`flex items-center gap-2 px-4 py-3 rounded-lg text-sm ${
      status.type === 'success'
        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
        : 'bg-red-50 text-red-700 border border-red-200'
    }`}>
      {status.type === 'success'
        ? <CheckCircle size={16} className="shrink-0" />
        : <AlertCircle size={16} className="shrink-0" />}
      {status.message}
    </div>
  )
}

export default function UserSettings() {
  const navigate = useNavigate()
  const [user, setUser] = useState<UserInfo | null>(null)

  const [newEmail, setNewEmail] = useState('')
  const [emailPassword, setEmailPassword] = useState('')
  const [emailStatus, setEmailStatus] = useState<Status>(null)
  const [emailLoading, setEmailLoading] = useState(false)

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPasswords, setShowPasswords] = useState(false)
  const [passwordStatus, setPasswordStatus] = useState<Status>(null)
  const [passwordLoading, setPasswordLoading] = useState(false)

  useEffect(() => {
    api.get('/users/me').then(res => {
      setUser(res.data)
      setNewEmail(res.data.email)
    })
  }, [])

  const handleEmailUpdate = async (e: React.FormEvent) => {
    e.preventDefault()
    setEmailStatus(null)
    setEmailLoading(true)
    try {
      await api.put('/users/me/email', { email: newEmail, current_password: emailPassword })
      setEmailStatus({ type: 'success', message: 'Email updated. Please log in again with your new email.' })
      setEmailPassword('')
      setTimeout(() => {
        localStorage.removeItem('token')
        window.location.href = '/login'
      }, 2000)
    } catch (err: any) {
      setEmailStatus({ type: 'error', message: err.response?.data?.detail ?? 'Failed to update email.' })
    } finally {
      setEmailLoading(false)
    }
  }

  const handlePasswordUpdate = async (e: React.FormEvent) => {
    e.preventDefault()
    setPasswordStatus(null)
    if (newPassword !== confirmPassword) {
      setPasswordStatus({ type: 'error', message: 'New passwords do not match.' })
      return
    }
    setPasswordLoading(true)
    try {
      await api.put('/users/me/password', { current_password: currentPassword, new_password: newPassword })
      setPasswordStatus({ type: 'success', message: 'Password changed successfully.' })
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err: any) {
      setPasswordStatus({ type: 'error', message: err.response?.data?.detail ?? 'Failed to change password.' })
    } finally {
      setPasswordLoading(false)
    }
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
      </div>
    )
  }

  const initials = user.email.slice(0, 2).toUpperCase()

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-white border-b border-slate-200 px-6 py-4 flex items-center gap-3">
        <button
          onClick={() => navigate(-1)}
          className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
        >
          <ArrowLeft size={18} />
        </button>
        <h1 className="text-lg font-bold text-slate-900">Account Settings</h1>
      </div>
    <div className="max-w-xl mx-auto px-6 py-8 space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Account Settings</h1>
        <p className="text-sm text-slate-500 mt-1">Manage your email and password.</p>
      </div>

      <p className="text-sm text-slate-500 -mt-4">Manage your email and password.</p>

      {/* Profile summary */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 flex items-center gap-4">
        <div className="w-14 h-14 rounded-full bg-gradient-to-br from-blue-400 to-teal-400 flex items-center justify-center text-white font-bold text-lg shrink-0">
          {initials}
        </div>
        <div>
          <p className="font-semibold text-slate-900">{user.email}</p>
          <p className="text-xs text-slate-400 mt-0.5">User ID #{user.id}</p>
        </div>
        <span className={`ml-auto text-xs font-medium px-2.5 py-1 rounded-full border ${
          user.is_active
            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
            : 'bg-slate-100 text-slate-500 border-slate-200'
        }`}>
          {user.is_active ? 'Active' : 'Inactive'}
        </span>
      </div>

      {/* Change email */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
        <div className="flex items-center gap-2 text-slate-800 font-semibold">
          <Mail size={18} className="text-blue-500" />
          Change Email
        </div>
        <form onSubmit={handleEmailUpdate} className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">New Email</label>
            <input
              type="email"
              required
              value={newEmail}
              onChange={e => setNewEmail(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Current Password</label>
            <input
              type="password"
              required
              value={emailPassword}
              onChange={e => setEmailPassword(e.target.value)}
              placeholder="Confirm your password"
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <StatusBanner status={emailStatus} />
          <button
            type="submit"
            disabled={emailLoading || newEmail === user.email}
            className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white rounded-lg transition-colors font-medium"
          >
            {emailLoading ? 'Updating…' : 'Update Email'}
          </button>
        </form>
      </div>

      {/* Change password */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-slate-800 font-semibold">
            <Lock size={18} className="text-blue-500" />
            Change Password
          </div>
          <button
            type="button"
            onClick={() => setShowPasswords(v => !v)}
            className="text-slate-400 hover:text-slate-600 transition-colors"
          >
            {showPasswords ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>
        <form onSubmit={handlePasswordUpdate} className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Current Password</label>
            <input
              type={showPasswords ? 'text' : 'password'}
              required
              value={currentPassword}
              onChange={e => setCurrentPassword(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">New Password</label>
            <input
              type={showPasswords ? 'text' : 'password'}
              required
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              placeholder="At least 8 characters"
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Confirm New Password</label>
            <input
              type={showPasswords ? 'text' : 'password'}
              required
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              className={`w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                confirmPassword && confirmPassword !== newPassword
                  ? 'border-red-300'
                  : 'border-slate-300'
              }`}
            />
          </div>
          <StatusBanner status={passwordStatus} />
          <button
            type="submit"
            disabled={passwordLoading}
            className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white rounded-lg transition-colors font-medium"
          >
            {passwordLoading ? 'Updating…' : 'Change Password'}
          </button>
        </form>
      </div>
    </div>
    </div>
  )
}
