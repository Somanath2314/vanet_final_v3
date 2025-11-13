import React, { useEffect, useState, useRef } from 'react'

// Simple Sparkline-like SVG chart component
function Sparkline({ data, color = '#3b82f6', height = 80, width = 280, showLabels = true }) {
  if (!data || data.length < 2) return <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b', fontSize: 13 }}>No data</div>
  
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  
  const points = data.map((val, i) => ({
    x: (i / (data.length - 1)) * width,
    y: height - ((val - min) / range) * height
  }))
  
  const pathData = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')
  const areaData = `${pathData} L ${width} ${height} L 0 ${height} Z`
  
  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <defs>
        <linearGradient id={`grad-${color}`} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" style={{ stopColor: color, stopOpacity: 0.3 }} />
          <stop offset="100%" style={{ stopColor: color, stopOpacity: 0.05 }} />
        </linearGradient>
      </defs>
      <path d={areaData} fill={`url(#grad-${color})`} />
      <path d={pathData} fill="none" stroke={color} strokeWidth="2" />
      {showLabels && (
        <>
          <text x={width - 5} y={15} textAnchor="end" fill={color} fontSize="12" opacity="0.7" fontWeight="500">Max: {max.toFixed(1)}</text>
          <text x={width - 5} y={height - 5} textAnchor="end" fill={color} fontSize="12" opacity="0.7" fontWeight="500">Min: {min.toFixed(1)}</text>
        </>
      )}
    </svg>
  )
}

export default function Live() {
  const [pointsActive, setPointsActive] = useState([])
  const [pointsWait, setPointsWait] = useState([])
  const [pointsPDR, setPointsPDR] = useState([])
  const [pointsQueue, setPointsQueue] = useState([])
  const [pointsThroughput, setPointsThroughput] = useState([])
  const [pointsEmergency, setPointsEmergency] = useState([])
  const [statusMsg, setStatusMsg] = useState('Connecting...')
  const [mode, setMode] = useState('unknown')
  const [paused, setPaused] = useState(false)
  const [modalData, setModalData] = useState(null)

  const maxPoints = 60

  useEffect(() => {
    let mounted = true
    async function poll() {
      try {
        const res = await fetch('http://localhost:5000/api/live')
        if (!res.ok) throw new Error('live fetch failed')
        const j = await res.json()
        if (!mounted) return
        const a = j.activeVehicles ?? 0
        const w = j.avgWait ?? 0
        const p = j.pdr ?? 0
        const q = j.queueLength ?? 0
        const th = j.throughput ?? 0
        const e = j.emergencyCount ?? 0
        setMode(j.mode ?? 'unknown')
        setPointsActive(prev => [...(prev.slice(-maxPoints + 1)), a])
        setPointsWait(prev => [...(prev.slice(-maxPoints + 1)), w])
        setPointsPDR(prev => [...(prev.slice(-maxPoints + 1)), p])
        setPointsQueue(prev => [...(prev.slice(-maxPoints + 1)), q])
        setPointsThroughput(prev => [...(prev.slice(-maxPoints + 1)), th])
        setPointsEmergency(prev => [...(prev.slice(-maxPoints + 1)), e])
        // Update status: show if data is from real simulation or demo
        setStatusMsg(j.isLive ? 'Live 🔴' : 'Demo')
      } catch (err) {
        setStatusMsg('Disconnected')
      }
    }

    // immediate first poll
    poll()
    const id = setInterval(() => { if (!paused) poll() }, 1000)
    return () => { mounted = false; clearInterval(id) }
  }, [paused])

  const cardStyle = {
    background: 'rgba(30, 41, 59, 0.9)',
    backdropFilter: 'blur(10px)',
    borderRadius: 16,
    padding: 20,
    color: '#cbd5e1',
    border: '1px solid rgba(71,85,105,0.5)',
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
    transition: 'transform 0.2s ease, box-shadow 0.2s ease',
    cursor: 'pointer',
  }

  function pctChange(arr) {
    if (!arr || arr.length < 2) return 0
    const a = arr[arr.length - 2]
    const b = arr[arr.length - 1]
    if (a === 0) return 0
    return ((b - a) / Math.abs(a)) * 100
  }

  function formatChange(v) {
    const sign = v > 0 ? '+' : ''
    return `${sign}${v.toFixed(1)}%`
  }

  function openModal(title, dataKey, color, description) {
    setModalData({ title, dataKey, color, description })
  }

  function closeModal() {
    setModalData(null)
  }

  function getDataForKey(key) {
    switch(key) {
      case 'active': return pointsActive
      case 'wait': return pointsWait
      case 'pdr': return pointsPDR
      case 'queue': return pointsQueue
      case 'throughput': return pointsThroughput
      case 'emergency': return pointsEmergency
      default: return []
    }
  }

  // ESC key to close modal
  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape' && modalData) {
        closeModal()
      }
    }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [modalData])

  return (
    <div style={{ minHeight: '100vh', padding: '40px 20px', fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", background: 'linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%)' }}>
      <div style={{ maxWidth: 1300, margin: '0 auto' }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: 48 }}>
          <div style={{ fontSize: 48, fontWeight: 'bold', color: 'white', marginBottom: 12, letterSpacing: '-0.5px' }}>📊 Live Simulation Analytics</div>
          <div style={{ fontSize: 18, color: '#93c5fd' }}>Real-time monitoring of VANET simulation metrics</div>
        </div>

        {/* Status bar */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20, alignItems: 'center', marginBottom: 32 }}>
          <div style={{ ...cardStyle, padding: '16px 24px', cursor: 'default' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ width: 12, height: 12, borderRadius: '50%', background: statusMsg === 'Live' ? '#10b981' : '#f87171' }}></div>
              <div style={{ color: '#93c5fd', fontWeight: 600, fontSize: 15 }}>Status:</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: 'white' }}>{statusMsg}</div>
            </div>
          </div>
          <div style={{ ...cardStyle, padding: '16px 24px', cursor: 'default' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ color: '#93c5fd', fontWeight: 600, fontSize: 15 }}>Window:</div>
              <div style={{ fontSize: 16, fontWeight: 600, color: 'white' }}>Last {pointsActive.length}s</div>
            </div>
          </div>
          <div style={{ ...cardStyle, padding: '16px 24px', cursor: 'default' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ color: '#93c5fd', fontWeight: 600, fontSize: 15 }}>Mode:</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#10b981', textTransform: 'uppercase' }}>{mode}</div>
            </div>
          </div>
        </div>

        {/* Primary metrics row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24, marginBottom: 28 }}>
          <div
            style={cardStyle}
            onClick={() => openModal('Active Vehicles', 'active', '#3b82f6', 'Count of vehicles currently present (includes emergency vehicles)')}
            onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-5px)'; e.currentTarget.style.boxShadow = '0 12px 32px rgba(59, 130, 246, 0.4)' }}
            onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.3)' }}
          >
            <div style={{ color: '#93c5fd', fontWeight: 700, fontSize: 15, marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Active Vehicles</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 16 }}>
              <div style={{ fontSize: 36, color: 'white', fontWeight: 'bold' }}>{pointsActive[pointsActive.length -1] ?? 0}</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: pctChange(pointsActive) >= 0 ? '#10b981' : '#fb7185' }}>{formatChange(pctChange(pointsActive))}</div>
            </div>
            <div style={{ marginBottom: 14 }}><Sparkline data={pointsActive} color="#3b82f6" height={100} width={320} /></div>
            <div style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.5 }}>Count of vehicles currently in network</div>
          </div>

          <div
            style={cardStyle}
            onClick={() => openModal('Average Wait Time (s)', 'wait', '#10b981', 'Average waiting time for vehicles (lower is better)')}
            onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-5px)'; e.currentTarget.style.boxShadow = '0 12px 32px rgba(16, 185, 129, 0.4)' }}
            onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.3)' }}
          >
            <div style={{ color: '#6ee7b7', fontWeight: 700, fontSize: 15, marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Average Wait (s)</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 16 }}>
              <div style={{ fontSize: 36, color: 'white', fontWeight: 'bold' }}>{(pointsWait[pointsWait.length -1] ?? 0).toFixed?.(2) ?? (pointsWait[pointsWait.length -1] ?? 0)}</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: pctChange(pointsWait) >= 0 ? '#fb7185' : '#10b981' }}>{formatChange(pctChange(pointsWait))}</div>
            </div>
            <div style={{ marginBottom: 14 }}><Sparkline data={pointsWait} color="#10b981" height={100} width={320} /></div>
            <div style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.5 }}>Average waiting time for vehicles</div>
          </div>

          <div
            style={cardStyle}
            onClick={() => openModal('Packet Delivery Ratio (%)', 'pdr', '#fb923c', 'Packet Delivery Ratio — network reliability')}
            onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-5px)'; e.currentTarget.style.boxShadow = '0 12px 32px rgba(251, 146, 60, 0.4)' }}
            onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.3)' }}
          >
            <div style={{ color: '#fbbf24', fontWeight: 700, fontSize: 15, marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Packet Delivery Ratio (%)</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 16 }}>
              <div style={{ fontSize: 36, color: 'white', fontWeight: 'bold' }}>{(pointsPDR[pointsPDR.length -1] ?? 0).toFixed?.(2) ?? (pointsPDR[pointsPDR.length -1] ?? 0)}</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: pctChange(pointsPDR) >= 0 ? '#10b981' : '#fb7185' }}>{formatChange(pctChange(pointsPDR))}</div>
            </div>
            <div style={{ marginBottom: 14 }}><Sparkline data={pointsPDR} color="#fb923c" height={100} width={320} /></div>
            <div style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.5 }}>Network reliability metric</div>
          </div>
        </div>

        {/* Additional metrics row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24 }}>
          <div
            style={cardStyle}
            title="Average queue length at junctions"
            onClick={() => openModal('Queue Length', 'queue', '#60a5fa', 'Average queue at junctions')}
            onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-5px)'; e.currentTarget.style.boxShadow = '0 12px 32px rgba(96, 165, 250, 0.4)' }}
            onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.3)' }}
          >
            <div style={{ color: '#93c5fd', fontWeight: 700, fontSize: 15, marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Queue Length</div>
            <div style={{ fontSize: 32, color: 'white', fontWeight: 'bold', marginBottom: 16 }}>{pointsQueue[pointsQueue.length -1] ?? 0}</div>
            <div style={{ marginBottom: 14 }}><Sparkline data={pointsQueue} color="#60a5fa" height={100} width={320} /></div>
            <div style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.5 }}>Average queue at junctions</div>
          </div>

          <div
            style={cardStyle}
            title="Throughput in Mbps"
            onClick={() => openModal('Throughput (Mbps)', 'throughput', '#f59e0b', 'Network throughput')}
            onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-5px)'; e.currentTarget.style.boxShadow = '0 12px 32px rgba(245, 158, 11, 0.4)' }}
            onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.3)' }}
          >
            <div style={{ color: '#fbbf24', fontWeight: 700, fontSize: 15, marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Throughput (Mbps)</div>
            <div style={{ fontSize: 32, color: 'white', fontWeight: 'bold', marginBottom: 16 }}>{(pointsThroughput[pointsThroughput.length -1] ?? 0).toFixed?.(1) ?? 0}</div>
            <div style={{ marginBottom: 14 }}><Sparkline data={pointsThroughput} color="#f59e0b" height={100} width={320} /></div>
            <div style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.5 }}>Network throughput</div>
          </div>

          <div
            style={cardStyle}
            title="Count of emergency vehicles active"
            onClick={() => openModal('Emergency Vehicles', 'emergency', '#ef4444', 'Emergency vehicles currently in network')}
            onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-5px)'; e.currentTarget.style.boxShadow = '0 12px 32px rgba(239, 68, 68, 0.4)' }}
            onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.3)' }}
          >
            <div style={{ color: '#fca5a5', fontWeight: 700, fontSize: 15, marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Emergency Vehicles</div>
            <div style={{ fontSize: 32, color: 'white', fontWeight: 'bold', marginBottom: 16 }}>{pointsEmergency[pointsEmergency.length -1] ?? 0}</div>
            <div style={{ marginBottom: 14 }}><Sparkline data={pointsEmergency} color="#ef4444" height={100} width={320} /></div>
            <div style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.5 }}>Emergency vehicles in network</div>
          </div>
        </div>

        {/* Footer controls */}
        <div style={{ marginTop: 48, display: 'flex', gap: 16, alignItems: 'center' }}>
          <a href="/" style={{ color: '#93c5fd', textDecoration: 'none', fontSize: 16, fontWeight: 600, padding: '12px 24px', borderRadius: 10, border: '1px solid rgba(71,85,105,0.5)', background: 'rgba(30, 41, 59, 0.6)', transition: 'all 0.2s' }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(30, 41, 59, 0.9)'; e.currentTarget.style.borderColor = 'rgba(59, 130, 246, 0.6)' }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(30, 41, 59, 0.6)'; e.currentTarget.style.borderColor = 'rgba(71,85,105,0.5)' }}
          >← Back to Home</a>
          <div style={{ flex: 1 }} />
          <button
            onClick={() => { setPaused(p => !p) }}
            style={{ padding: '12px 24px', borderRadius: 10, border: '1px solid rgba(71,85,105,0.5)', background: paused ? 'rgba(16, 185, 129, 0.25)' : 'rgba(251, 113, 133, 0.25)', color: paused ? '#10b981' : '#fb7185', cursor: 'pointer', fontWeight: 700, fontSize: 15, transition: 'all 0.2s' }}
            onMouseEnter={(e) => { e.currentTarget.style.transform = 'scale(1.05)' }}
            onMouseLeave={(e) => { e.currentTarget.style.transform = 'scale(1)' }}
          >{paused ? '▶ Resume' : '⏸ Pause'}</button>
          <button
            onClick={() => { window.location.reload() }}
            style={{ padding: '12px 24px', borderRadius: 10, border: '1px solid rgba(71,85,105,0.5)', background: 'rgba(59, 130, 246, 0.25)', color: '#93c5fd', cursor: 'pointer', fontWeight: 700, fontSize: 15, transition: 'all 0.2s' }}
            onMouseEnter={(e) => { e.currentTarget.style.transform = 'scale(1.05)' }}
            onMouseLeave={(e) => { e.currentTarget.style.transform = 'scale(1)' }}
          >🔄 Refresh</button>
        </div>
      </div>

      {/* Modal for enlarged graph */}
      {modalData && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.85)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            padding: 20,
          }}
          onClick={closeModal}
        >
          <div
            style={{
              background: 'rgba(30, 41, 59, 0.95)',
              borderRadius: 20,
              padding: 40,
              maxWidth: 900,
              width: '100%',
              border: '1px solid rgba(71, 85, 105, 0.5)',
              boxShadow: '0 20px 60px rgba(0, 0, 0, 0.6)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
              <div>
                <div style={{ fontSize: 28, fontWeight: 'bold', color: 'white', marginBottom: 4 }}>{modalData.title}</div>
                <div style={{ fontSize: 14, color: '#94a3b8' }}>{modalData.description}</div>
              </div>
              <button
                onClick={closeModal}
                style={{
                  background: 'rgba(239, 68, 68, 0.2)',
                  border: '1px solid rgba(239, 68, 68, 0.4)',
                  borderRadius: 8,
                  padding: '8px 16px',
                  color: '#fca5a5',
                  cursor: 'pointer',
                  fontWeight: 600,
                  fontSize: 14,
                  transition: 'all 0.2s',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(239, 68, 68, 0.3)' }}
                onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)' }}
              >✕ Close</button>
            </div>

            <div style={{ background: 'rgba(15, 23, 42, 0.6)', borderRadius: 16, padding: 40, marginBottom: 24 }}>
              <Sparkline data={getDataForKey(modalData.dataKey)} color={modalData.color} height={400} width={820} showLabels={true} />
            </div>

            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', alignItems: 'center' }}>
              <div style={{ color: '#94a3b8', fontSize: 14 }}>Mode: <strong style={{ color: '#10b981' }}>{mode.toUpperCase()}</strong></div>
              <div style={{ color: '#64748b', fontSize: 13, marginRight: 'auto' }}>Press <kbd style={{ padding: '2px 6px', borderRadius: 4, background: 'rgba(71, 85, 105, 0.4)', border: '1px solid rgba(71, 85, 105, 0.6)', fontSize: 12 }}>ESC</kbd> to close</div>
              <button
                onClick={() => { setPaused(p => !p) }}
                style={{
                  padding: '8px 16px',
                  borderRadius: 8,
                  border: '1px solid rgba(71,85,105,0.4)',
                  background: paused ? 'rgba(16, 185, 129, 0.2)' : 'rgba(251, 113, 133, 0.2)',
                  color: paused ? '#10b981' : '#fb7185',
                  cursor: 'pointer',
                  fontWeight: 600,
                  fontSize: 13,
                  transition: 'all 0.2s',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.transform = 'scale(1.05)' }}
                onMouseLeave={(e) => { e.currentTarget.style.transform = 'scale(1)' }}
              >{paused ? '▶ Resume' : '⏸ Pause'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
