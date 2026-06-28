import React from 'react'

const CATEGORIES = [
  'Electronics',
  'Clothing',
  'Home & Kitchen',
  'Toys',
  'Books',
  'Health',
  'Sports',
  'Automotive',
  'Other',
]

const inputStyle = {
  display: 'block',
  width: '100%',
  padding: '0.5rem',
  marginTop: '0.25rem',
  marginBottom: '1rem',
  border: '1px solid #ccc',
  borderRadius: 4,
  fontSize: '1rem',
  boxSizing: 'border-box',
}

const labelStyle = {
  fontWeight: 600,
  display: 'block',
}

export default function AnalysisForm({ formData, setFormData, onSubmit, loading }) {
  function handleChange(e) {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }))
  }

  function handleSubmit(e) {
    e.preventDefault()
    onSubmit(formData)
  }

  return (
    <form onSubmit={handleSubmit} style={{ background: '#f9f9f9', padding: '1.5rem', borderRadius: 8, border: '1px solid #ddd' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 1.5rem' }}>
        <div>
          <label style={labelStyle}>Sale Price (USD)</label>
          <input
            style={inputStyle}
            type="number"
            name="price"
            min="0.01"
            step="0.01"
            required
            value={formData.price}
            onChange={handleChange}
            placeholder="e.g. 29.99"
          />
        </div>
        <div>
          <label style={labelStyle}>Cost of Goods (USD)</label>
          <input
            style={inputStyle}
            type="number"
            name="cost"
            min="0"
            step="0.01"
            required
            value={formData.cost}
            onChange={handleChange}
            placeholder="e.g. 10.00"
          />
        </div>
        <div>
          <label style={labelStyle}>Category</label>
          <select style={inputStyle} name="category" value={formData.category} onChange={handleChange}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
        <div>
          <label style={labelStyle}>Weight (lbs)</label>
          <input
            style={inputStyle}
            type="number"
            name="weight_lbs"
            min="0.01"
            step="0.01"
            required
            value={formData.weight_lbs}
            onChange={handleChange}
            placeholder="e.g. 1.5"
          />
        </div>
        <div>
          <label style={labelStyle}>Monthly Units Sold</label>
          <input
            style={inputStyle}
            type="number"
            name="monthly_units"
            min="1"
            step="1"
            required
            value={formData.monthly_units}
            onChange={handleChange}
            placeholder="e.g. 50"
          />
        </div>
        <div>
          <label style={labelStyle}>Review Count</label>
          <input
            style={inputStyle}
            type="number"
            name="review_count"
            min="0"
            step="1"
            value={formData.review_count}
            onChange={handleChange}
            placeholder="e.g. 100"
          />
        </div>
        <div>
          <label style={labelStyle}>Review Rating (0–5)</label>
          <input
            style={inputStyle}
            type="number"
            name="review_rating"
            min="0"
            max="5"
            step="0.1"
            value={formData.review_rating}
            onChange={handleChange}
            placeholder="e.g. 4.2"
          />
        </div>
      </div>
      <button
        type="submit"
        disabled={loading}
        style={{
          width: '100%',
          padding: '0.75rem',
          background: loading ? '#999' : '#2563eb',
          color: '#fff',
          border: 'none',
          borderRadius: 4,
          fontSize: '1rem',
          fontWeight: 700,
          cursor: loading ? 'not-allowed' : 'pointer',
        }}
      >
        {loading ? 'Analyzing...' : 'Analyze Product'}
      </button>
    </form>
  )
}
