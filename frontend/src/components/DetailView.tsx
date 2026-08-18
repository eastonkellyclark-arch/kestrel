import type { ListingDetail } from '../types';

interface Props {
  detail: ListingDetail | null;
  loading: boolean;
  activeProfile?: string;
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

function ScoreBar({ label, score }: { label: string; score: number }) {
  const pct = Math.min(100, score);
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

function daysAgoText(days: number | null | undefined): string {
  if (days === null || days === undefined) return 'unknown age';
  if (days <= 0) return 'posted today';
  if (days === 1) return 'posted yesterday';
  if (days < 7) return `posted ${days} days ago`;
  if (days < 30) return `posted ${Math.floor(days / 7)} weeks ago`;
  return `posted ${Math.floor(days / 30)} months ago`;
}

function buildWhyText(detail: ListingDetail): string[] {
  const bd = detail.breakdown;
  const d = bd.detail ?? {};
  const dims = bd.dimensions;
  const lines: string[] = [];

  // Skill match — the main story
  const sm = d.skill_match;
  const allHits = [
    ...(sm?.primary_hits ?? []),
    ...(sm?.secondary_hits ?? []),
    ...(sm?.bonus_hits ?? []),
  ];
  const titleHits = sm?.title_hits ?? [];
  const skillScore = dims.skill_match?.score ?? 0;
  const factorPct = Math.round((bd.skill_factor ?? 0) * 100);

  if (allHits.length === 0) {
    lines.push(`None of your profiled skills appear in this listing. The overall score was scaled to ${factorPct}%.`);
  } else {
    const titleNote = titleHits.length > 0
      ? ` (${titleHits.join(', ')} appear${titleHits.length === 1 ? 's' : ''} in the title, weighted 2\u00d7)`
      : '';
    lines.push(
      `Matched ${allHits.length} skill${allHits.length > 1 ? 's' : ''}: ${allHits.join(', ')}${titleNote}. ` +
      `Skill match score: ${skillScore.toFixed(0)}/100, scaling the overall result to ${factorPct}%.`
    );
  }

  // Degree posture
  const dp = d.degree_posture;
  if (dp?.posture === 'no_degree') {
    lines.push('Explicitly states no degree is required.');
  } else if (dp?.posture === 'not_mentioned') {
    lines.push('No degree requirement mentioned.');
  } else if (dp?.posture === 'equivalent_ok') {
    lines.push('Degree preferred but equivalent experience accepted.');
  } else if (dp?.posture === 'hard_requirement') {
    lines.push('Requires a specific degree \u2014 scored lower on degree posture.');
  } else if (dp?.posture === 'mentioned_unclear') {
    lines.push('Degree mentioned but requirement is unclear.');
  }

  // Location
  const lf = d.location_fit;
  if (lf?.fit === 'metro') {
    lines.push('Located in the Twin Cities metro \u2014 strong location fit.');
  } else if (lf?.fit === 'state') {
    lines.push('Located in Minnesota.');
  } else if (lf?.fit === 'us_remote' || lf?.fit === 'us_remote_inferred') {
    lines.push('US Remote \u2014 strong location fit.');
  } else if (lf?.fit === 'non_us_remote') {
    lines.push('Remote but outside the US \u2014 likely not eligible.');
  } else if (lf?.fit === 'non_us_onsite') {
    lines.push('Outside the US and not remote \u2014 not a viable location.');
  } else if (lf?.fit === 'us_not_metro') {
    lines.push('US-based but outside the Twin Cities \u2014 would require relocation.');
  } else if (lf?.fit === 'remote_ambiguous') {
    lines.push('Listed as remote but country is unclear.');
  }

  // Freshness
  const fr = d.freshness;
  if (fr?.days_old !== null && fr?.days_old !== undefined) {
    lines.push(`${daysAgoText(fr.days_old).charAt(0).toUpperCase() + daysAgoText(fr.days_old).slice(1)}.`);
  }

  // Experience
  const ef = (d as Record<string, any>).experience_fit;
  if (ef?.experience === 'none_required') {
    lines.push('No experience required \u2014 best fit for your level.');
  } else if (ef?.experience === 'at_or_below') {
    lines.push(`Requires ${ef.required} year${ef.required !== 1 ? 's' : ''} \u2014 at or below your experience.`);
  } else if (ef?.experience === 'mild_stretch') {
    lines.push(`Requires ${ef.required} years (you have ${ef.required - ef.gap}) \u2014 a stretch but doable.`);
  } else if (ef?.experience === 'significant_gap') {
    lines.push(`Requires ${ef.required} years (you have ${ef.required - ef.gap}) \u2014 significant experience gap.`);
  } else if (ef?.experience === 'heavy_gap') {
    lines.push(`Requires ${ef.required} years (you have ${ef.required - ef.gap}) \u2014 well above your experience level.`);
  } else if (ef?.experience === 'not_mentioned') {
    lines.push('Experience requirement not stated \u2014 scored neutral.');
  }

  // Seniority
  const sf = d.seniority_fit;
  if (sf?.level === 'too_senior') {
    lines.push(`Title suggests a very senior role ("${sf.matched}") \u2014 may be above target range.`);
  } else if (sf?.level === 'too_junior') {
    lines.push(`Title suggests a junior role ("${sf.matched}") \u2014 below target range.`);
  }

  return lines;
}

export function DetailView({ detail, loading, activeProfile, onBack }: Props) {
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

  // Use the selected profile's breakdown if available
  const bd = (activeProfile && detail.profile_breakdowns?.[activeProfile])
    ? detail.profile_breakdowns[activeProfile]
    : detail.breakdown;
  const dims = bd?.dimensions ?? {};
  // Build "Why" text from the profile-specific breakdown
  const whyDetail = { ...detail, breakdown: bd } as ListingDetail;
  const whyLines = bd ? buildWhyText(whyDetail) : [];

  return (
    <div className="detail-page">
      <button type="button" className="back-btn" onClick={onBack}>&larr; Back to listings</button>

      <div className="detail-header">
        <div className={`score-badge large ${(bd?.composite ?? 0) >= 50 ? 'high' : (bd?.composite ?? 0) >= 30 ? 'mid' : 'low'}`}>
          {bd?.composite?.toFixed(0) ?? '--'}
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

      {whyLines.length > 0 && (
        <div className="why-panel">
          <h2>Why this score?</h2>
          <ul className="why-list">
            {whyLines.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </div>
      )}

      {bd && (
        <div className="breakdown-panel">
          <h2>Score Breakdown</h2>
          <div className="breakdown-summary">
            Hygiene: {bd.hygiene_score?.toFixed(0)} &times;{' '}
            {((bd.skill_factor ?? 0) * 100).toFixed(0)}% skill factor ={' '}
            <strong>{bd.composite?.toFixed(1)}</strong>
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
          <div
            className="description-html"
            dangerouslySetInnerHTML={{ __html: detail.description }}
          />
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
