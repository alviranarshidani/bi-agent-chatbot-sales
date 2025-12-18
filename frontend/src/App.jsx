import React, { useState } from 'react'
import { Chart, LineController, LineElement, PointElement, CategoryScale, LinearScale, BarController, BarElement, Tooltip, Legend } from 'chart.js'

Chart.register(LineController, LineElement, PointElement, CategoryScale, LinearScale, BarController, BarElement, Tooltip, Legend)

function ChartView({ title, labels, datasets }) {
  const canvasRef = React.useRef(null)

  React.useEffect(() => {
    if (!canvasRef.current) return
    const ctx = canvasRef.current.getContext('2d')
    const chart = new Chart(ctx, {
      type: 'bar',
      data: { labels, datasets: datasets.map(d => ({ ...d })) },
      options: {
        responsive: true,
        plugins: { legend: { display: true }, title: { display: !!title, text: title } }
      }
    })
    return () => chart.destroy()
  }, [labels, datasets, title])

  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 16, marginTop: 12 }}>
      <canvas ref={canvasRef} height="140"></canvas>
    </div>
  )
}

export default function App() {
  const [messages, setMessages] = useState([
    { role: 'system', text: 'Ask me about purchases, redemptions, assets. Try: "Show redemptions by fund type last quarter".' }
  ])
  const [input, setInput] = useState('Show redemptions by fund type last quarter')
  const [loading, setLoading] = useState(false)
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

  async function send() {
    if (!input.trim()) return
    const userMsg = { role: 'user', text: input }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: userMsg.text })
      })
      const data = await res.json()
      if (data.type === 'chart') {
        setMessages(prev => [...prev, { role: 'assistant', chart: data, text: data.title }])
      } else if (data.type === 'text') {
        setMessages(prev => [...prev, { role: 'assistant', text: `${data.title}: ${data.text}` }])
      } else if (data.type === 'table') {
        setMessages(prev => [...prev, { role: 'assistant', text: JSON.stringify(data.table, null, 2) }])
      } else {
        setMessages(prev => [...prev, { role: 'assistant', text: 'I did not understand the response.' }])
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', text: `Error: ${e}` }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ fontFamily: 'Inter, system-ui, Arial', margin: '0 auto', maxWidth: 880, padding: 24 }}>
      <h1>BI Agent Chatbot (Sales)</h1>
      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask a question..."
          style={{ flex: 1, padding: 12, borderRadius: 12, border: '1px solid #e5e7eb' }}
        />
        <button onClick={send} disabled={loading} style={{ padding: '12px 16px', borderRadius: 12, border: '1px solid #e5e7eb', background: '#111827', color: 'white' }}>
          {loading ? 'Thinking...' : 'Ask'}
        </button>
      </div>

      <div style={{ marginTop: 16 }}>
        {messages.slice(1).map((m, i) => (
          <div key={i} style={{ marginBottom: 12, padding: 12, background: m.role === 'user' ? '#f9fafb' : '#fff', borderRadius: 12, border: '1px solid #e5e7eb' }}>
            <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>{m.role.toUpperCase()}</div>
            {m.chart ? <ChartView title={m.chart.title} labels={m.chart.labels} datasets={m.chart.datasets} /> : <div>{m.text}</div>}
          </div>
        ))}
      </div>

      <p style={{ marginTop: 24, color: '#6b7280' }}>
        Tip: Try "Purchases by wholesaler last quarter", "Assets by advisor", or "RVP Alice purchases last quarter".
      </p>
    </div>
  )
}