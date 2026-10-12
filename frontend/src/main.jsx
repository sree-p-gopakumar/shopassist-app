import React, { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const scenarios = [
  { label: 'Damaged item', order: 'ORD-12345678', issue: 'damaged item', note: '12 days since delivery · refund path' },
  { label: 'Duplicate charge', order: 'ORD-12345678', issue: 'duplicate charge', note: 'Verified order · refund path' },
  { label: 'Policy exception', order: 'ORD-87654321', issue: 'damaged item', note: '45 days since delivery · specialist path' },
]

function App() {
  const [form, setForm] = React.useState({
    email: 'alex@example.com', order_id: 'ORD-12345678', issue: 'damaged item', context: '',
  })
  const [result, setResult] = React.useState(null)
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState('')

  const useScenario = (scenario) => {
    setForm({ ...form, order_id: scenario.order, issue: scenario.issue })
    setResult(null)
    setError('')
  }

  const submit = async (event) => {
    event.preventDefault()
    setLoading(true); setError(''); setResult(null)
    const message = [
      `My email address is ${form.email}.`,
      `My order number is ${form.order_id}.`,
      `I need help with: ${form.issue}.`,
      form.context.trim(),
    ].filter(Boolean).join(' ')
    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message }),
      })
      if (!response.ok) throw new Error((await response.json()).detail || 'Unable to resolve this case.')
      setResult(await response.json())
    } catch (err) { setError(err.message) } finally { setLoading(false) }
  }

  const change = (field) => (event) => setForm({ ...form, [field]: event.target.value })
  const outcomeTitle = result?.refund ? 'Refund submitted' : result?.escalation ? 'Specialist assigned' : result ? 'ShopAssist reply' : 'Ready when you are'

  return <main>
    <nav><div className="brand"><span className="brand-mark">S</span><span>shop<span>assist</span></span></div><div className="nav-status"><i /> AI workflow <a href="http://localhost:8000/docs" target="_blank">Swagger docs ↗</a></div></nav>
    <section className="hero">
      <div><p className="eyebrow">AI-ASSISTED SUPPORT OPERATIONS</p><h1>Resolve customer cases with <em>confidence.</em></h1><p className="intro">Claude decides what to investigate and explains the outcome. The backend verifies ownership, applies policy, and performs protected actions.</p></div>
      <aside className="policy-card"><span className="shield">✓</span><div><strong>Guardrails built in</strong><p>Verified account required · 30-day policy enforced · audit trail included</p></div></aside>
    </section>
    <section className="workspace">
      <div className="panel case-panel"><div className="panel-heading"><div><p className="eyebrow">AI CASE BRIEF</p><h2>What can we help with?</h2></div><span className="step">Claude + tools</span></div>
        <div className="scenario-row">{scenarios.map(s => <button key={s.label} type="button" className={form.order_id === s.order && form.issue === s.issue ? 'scenario active' : 'scenario'} onClick={() => useScenario(s)}><strong>{s.label}</strong><small>{s.note}</small></button>)}</div>
        <form onSubmit={submit}>
          <label>Email address<input value={form.email} onChange={change('email')} type="email" required /></label>
          <div className="two-col"><label>Order number<input value={form.order_id} onChange={change('order_id')} required /></label><label>Issue<select value={form.issue} onChange={change('issue')}><option>damaged item</option><option>duplicate charge</option><option>missing item</option><option>wrong item</option><option>other</option></select></label></div>
          <label>Additional context <span className="optional">optional</span><textarea value={form.context} onChange={change('context')} placeholder="Tell ShopAssist anything else that matters." rows="3" /></label>
          <button className="primary" disabled={loading}>{loading ? 'ShopAssist is investigating…' : 'Ask ShopAssist  →'}</button>
        </form>
      </div>
      <div className="panel result-panel"><div className="panel-heading"><div><p className="eyebrow">CASE ACTIVITY</p><h2>{outcomeTitle}</h2></div>{result && <span className="pill">AI casework</span>}</div>
        {!result && !error && <div className="empty"><div className="empty-icon">✦</div><p>Describe a case. ShopAssist will call only the support tools needed to verify, assess, and resolve it.</p></div>}
        {error && <div className="error">{error}</div>}
        {result && <><p className="result-message">{result.message}</p>{result.steps.length > 0 && <div className="timeline">{result.steps.map((step, index) => <div className="timeline-step" key={index}><span>{index + 1}</span><div><strong>{step.tool.replaceAll('_', ' ')}</strong><small>{step.detail}</small></div><b>{step.status === 'blocked' ? '!' : '✓'}</b></div>)}</div>}{result.refund && <div className="receipt"><span>Refund amount</span><strong>${result.refund.amount.toFixed(2)} {result.refund.currency}</strong></div>}{result.escalation && <div className="receipt"><span>Support ticket</span><strong>{result.escalation.ticket_id}</strong></div>}</>}
      </div>
    </section>
    <section className="principles"><div><b>01</b><h3>Safe by design</h3><p>Orders stay private until account ownership is confirmed.</p></div><div><b>02</b><h3>Policy-led decisions</h3><p>Refund eligibility is service-enforced, never improvised by an AI response.</p></div><div><b>03</b><h3>Human when it matters</h3><p>Exceptions become concise, ready-to-action specialist tickets.</p></div></section>
  </main>
}

createRoot(document.getElementById('root')).render(<StrictMode><App /></StrictMode>)
