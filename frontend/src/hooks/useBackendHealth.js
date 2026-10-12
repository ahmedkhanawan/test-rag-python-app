import { useEffect, useState } from 'react'
import { getHealth } from '../services/health.js'

/** Returns "checking" | "online" | "offline". */
export default function useBackendHealth() {
  const [status, setStatus] = useState('checking')

  useEffect(() => {
    let cancelled = false
    getHealth()
      .then((data) => !cancelled && setStatus(data?.status === 'ok' ? 'online' : 'offline'))
      .catch(() => !cancelled && setStatus('offline'))
    return () => {
      cancelled = true
    }
  }, [])

  return status
}
