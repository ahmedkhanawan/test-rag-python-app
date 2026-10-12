import useBackendHealth from '../hooks/useBackendHealth.js'

const BADGES = {
  checking: { className: 'text-bg-secondary', label: 'Checking backend…' },
  online: { className: 'text-bg-success', label: 'Backend online' },
  offline: { className: 'text-bg-danger', label: 'Backend offline' },
}

export default function BackendStatus() {
  const status = useBackendHealth()
  const { className, label } = BADGES[status]
  return (
    <span className={`badge ${className}`} role="status">
      <i className="bi bi-circle-fill me-1" />
      {label}
    </span>
  )
}
