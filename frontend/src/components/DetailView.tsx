import type { ListingDetail } from '../types';

interface Props {
  detail: ListingDetail | null;
  loading: boolean;
  onBack: () => void;
}

const DIM_LABELS: Record<string, string> = {
  skill_match: 'Skill Match',
  degree_posture: 'Degree Posture',
  freshness: 'Freshness',
  location_fit: 'Location Fit',
  seniority_fit: 'Seniority Fit',
  source_quality: 'Source Quality',
};

function ScoreBar({ label, score, maxScore = 100 }: { label: string; score: number; maxScore?: number }) {
  const pct = Math.min(100, (score / maxScore) * 100);
  const color = pct >= 70 ? 'var(--green)' : pct >= 40 ? 'var(--amber)' : 'var(--red)';
  return (
    <div className="score-bar-row">
      <span className="score-bar-label">{label}</span>
      <div className="score-bar-track">
        <div className="score-bar-fill" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="score-bar-value">{score.toFixed(0)}</span>
    </div>
  );
}

export function DetailView({ detail, loading, onBack }: Props) {
  if (loading) {
    return (
      <div className="detail-page">
        <button type="button" className="back-btn" onClick={onBack}>&larr; Back</button>
        <div className="state-screen"><div className="spinner" /><p>Loading detail...</p></div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="detail-page">
        <button type="button" className="back-btn" onClick={onBack}>&larr; Back</button>
        <div className="state-screen error"><h2>Detail not available</h2></div>
      </div>
    );
  }

  const bd = detail.breakdown;
  const dims = bd?.dimensions ?? {};

  return (
    <div className="detail-page">
      <button type="button" className="back-btn" onClick={onBack}>&larr; Back to listings</button>

      <div className="detail-header">
        <div className={`score-badge large ${(detail.score ?? 0) >= 50 ? 'high' : (detail.score ?? 0) >= 30 ? 'mid' : 'low'}`}>
          {detail.score?.toFixed(0) ?? '--'}
        </div>
        <div>
          <h1 className="detail-title">{detail.title}</h1>
          <div className="detail-company">{detail.company}</div>
          <div className="detail-meta">
            <span>{detail.location || 'Location not specified'}</span>
            {detail.is_remote && <span className="tag remote">Remote</span>}
            {!detail.degree_hard_required && <span className="tag degree">No degree req.</span>}
            {detail.department && <span className="tag dept">{detail.department}</span>}
          </div>
        </div>
      </div>

      {bd && (
        <div className="breakdown-panel">
          <h2>Score Breakdown</h2>
          <div className="breakdown-summary">
            Hygiene: {bd.hygiene_score?.toFixed(0)} &times;{' '}
            {((bd.skill_factor ?? 0) * 100).toFixed(0)}% skill factor ={' '}
            <strong>{bd.composite?.toFixed(1)}</strong>
            <span className="scale-label">{bd.scale_label}</span>
          </div>
          <div className="score-bars">
            {Object.entries(dims).map(([key, val]) => (
              <ScoreBar key={key} label={DIM_LABELS[key] ?? key} score={val.score} />
            ))}
          </div>
        </div>
      )}

      {detail.url && (
        <a href={detail.url} target="_blank" rel="noopener noreferrer" className="apply-link">
          View original posting &rarr;
        </a>
      )}

      {detail.description && detail.description_quality === 'good' && (
        <div className="description-panel">
          <h2>Description</h2>
          <div className="description-text">{detail.description}</div>
        </div>
      )}

      {detail.description_quality !== 'good' && (
        <div className="description-panel">
          <h2>Description</h2>
          <p className="hint">
            {detail.description_quality === 'non_english'
              ? 'Description is not in English.'
              : 'No description available.'}
          </p>
        </div>
      )}
    </div>
  );
}
