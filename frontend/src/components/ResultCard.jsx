import React from 'react'

const GRADE_COLORS = {
  A: '#16a34a',
  B: '#2563eb',
  C: '#d97706',
  D: '#dc2626',
  F: '#7f1d1d',
}

const RISK_COLORS = {
  high: { background: '#fee2e2', border: '#dc2626', text: '#7f1d1d', badge: '#dc2626' },
  medium: { background: '#fef9c3', border: '#ca8a04', text: '#78350f', badge: '#d97706' },
  low: { background: '#dcfce7', border: '#16a34a', text: '#14532d', badge: '#16a34a' },
}

function fmt(n) {
  return typeof n === 'number' ? n.toFixed(2) : n
}

export default function ResultCard({ result }) {
  const { fees, grade, risks, recommendation } = result
  const gradeColor = GRADE_COLORS[grade.grade] || '#374151'

  return (
    <div style={{ marginTop: '2rem' }}>
      {/* Grade */}
      <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 90,
          height: 90,
          borderRadius: '50%',
          background: gradeColor,
          color: '#fff',
          fontSize: '2.5rem',
          fontWeight: 900,
          marginBottom: '0.5rem',
        }}>
          {grade.grade}
        </div>
        <div style={{ color: '#374151', fontSize: '1rem' }}>Score: {grade.score} / 100</div>
        {grade.reasons.length > 0 && (
          <ul style={{ textAlign: 'left', display: 'inline-block', marginTop: '0.5rem', color: '#6b7280', fontSize: '0.875rem' }}>
            {grade.reasons.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        )}
      </div>

      {/* Recommendation */}
      <div style={{
        background: '#f0fdf4',
        border: '1px solid #86efac',
        borderRadius: 6,
        padding: '0.75rem 1rem',
        marginBottom: '1.5rem',
        fontWeight: 600,
        color: '#15803d',
        fontSize: '1rem',
      }}>
        {recommendation}
      </div>

      {/* Fee Breakdown */}
      <h3 style={{ marginBottom: '0.5rem' }}>Fee Breakdown</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '1.5rem', fontSize: '0.95rem' }}>
        <tbody>
          {[
            ['Referral Fee', `$${fmt(fees.referral_fee)}`],
            ['Fulfillment Fee', `$${fmt(fees.fulfillment_fee)}`],
            ['Storage Fee', `$${fmt(fees.storage_fee)}`],
            ['Total Fees', `$${fmt(fees.total_fees)}`],
            ['Net Revenue', `$${fmt(fees.net_revenue)}`],
            ['Margin %', `${fmt(fees.margin_pct)}%`],
          ].map(([label, value]) => (
            <tr key={label} style={{ borderBottom: '1px solid #e5e7eb' }}>
              <td style={{ padding: '0.5rem 0.75rem', color: '#374151' }}>{label}</td>
              <td style={{
                padding: '0.5rem 0.75rem',
                fontWeight: 700,
                color: label === 'Net Revenue' || label === 'Margin %'
                  ? (parseFloat(value) >= 0 ? '#16a34a' : '#dc2626')
                  : '#111827',
                textAlign: 'right',
              }}>
                {value}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Risk Flags */}
      {risks.length > 0 && (
        <>
          <h3 style={{ marginBottom: '0.75rem' }}>Risk Flags</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {risks.map((risk, i) => {
              const colors = RISK_COLORS[risk.level] || RISK_COLORS.low
              return (
                <div key={i} style={{
                  background: colors.background,
                  border: `1px solid ${colors.border}`,
                  borderRadius: 6,
                  padding: '0.6rem 0.9rem',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '0.75rem',
                }}>
                  <span style={{
                    background: colors.badge,
                    color: '#fff',
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    padding: '0.15rem 0.4rem',
                    borderRadius: 4,
                    textTransform: 'uppercase',
                    whiteSpace: 'nowrap',
                    marginTop: 2,
                  }}>
                    {risk.level}
                  </span>
                  <div>
                    <div style={{ fontWeight: 700, color: colors.text, fontSize: '0.875rem' }}>{risk.label}</div>
                    <div style={{ color: colors.text, fontSize: '0.8rem', marginTop: 2 }}>{risk.detail}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </>
      )}
      {risks.length === 0 && (
        <div style={{ color: '#16a34a', fontWeight: 600 }}>No risk flags — clean product profile.</div>
      )}
    </div>
  )
}
