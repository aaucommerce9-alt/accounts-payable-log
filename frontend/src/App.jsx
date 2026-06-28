import React, { useState } from 'react'
import AnalysisForm from './components/AnalysisForm'
import ResultCard from './components/ResultCard'

const defaultForm = {
  price: '',
  cost: '',
  category: 'Other',
  weight_lbs: '',
  monthly_units: '',
  review_count: '0',
  review_rating: '4.0',
}

export default function App() {
  const [formData, setFormData] = useState(defaultForm)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(data) {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await fetch('/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          price: parseFloat(data.price),
          cost: parseFloat(data.cost),
          category: data.category,
          weight_lbs: parseFloat(data.weight_lbs),
          monthly_units: parseInt(data.monthly_units, 10),
          review_count: parseInt(data.review_count, 10),
          review_rating: parseFloat(data.review_rating),
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      const json = await res.json()
      setResult(json)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: '2rem', fontFamily: 'sans-serif' }}>
      <h1 style={{ textAlign: 'center', marginBottom: '1.5rem' }}>WAMP Product Analyzer</h1>
      <AnalysisForm formData={formData} setFormData={setFormData} onSubmit={handleSubmit} loading={loading} />
      {error && (
        <div style={{ color: 'red', marginTop: '1rem', padding: '0.75rem', border: '1px solid red', borderRadius: 4 }}>
          Error: {error}
        </div>
      )}
      {result && <ResultCard result={result} />}
    </div>
  )
}
