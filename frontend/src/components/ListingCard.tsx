import type { ListingSummary } from '../types';

interface Props {
  listing: ListingSummary;
  onClick: () => void;
}

function daysAgo(dateStr: string | null): string {
  if (!dateStr) return '';
  const d = Math.floor((Date.now() - new Date(dateStr).getTime()) / 86400000);
  if (d <= 0) return 'today';
  if (d === 1) return '1d ago';
  if (d < 30) return `${d}d ago`;
  if (d < 365) return `${Math.floor(d / 30)}mo ago`;
  return `${Math.floor(d / 365)}y ago`;
}

function scoreTier(score: number | null): string {
  if (score === null) return 'none';
  if (score >= 50) return 'high';
  if (score >= 30) return 'mid';
  return 'low';
}

export function ListingCard({ listing, onClick }: Props) {
  const score = listing.score ?? 0;
  const tier = scoreTier(listing.score);

  return (
    <button type="button" className="listing-card" onClick={onClick}>
      <div className={`score-badge ${tier}`}>
        {score > 0 ? score.toFixed(0) : '--'}
      </div>
      <div className="card-body">
        <div className="card-title">{listing.title}</div>
        <div className="card-company">{listing.company}</div>
        <div className="card-meta">
          <span className="card-location">{listing.location || 'Location not specified'}</span>
          {listing.is_remote && <span className="tag remote">Remote</span>}
          {!listing.degree_hard_required && <span className="tag degree">No degree req.</span>}
          {listing.posted_at && (
            <span className="card-date">{daysAgo(listing.posted_at)}</span>
          )}
        </div>
        {listing.scale_label && (
          <div className="card-scale">{listing.scale_label}</div>
        )}
      </div>
    </button>
  );
}
