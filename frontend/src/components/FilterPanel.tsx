import type { Filters } from '../types';

interface Props {
  filters: Filters;
  onChange: (f: Filters) => void;
  total: number;
  showing: number;
}

export function FilterPanel({ filters, onChange, total, showing }: Props) {
  return (
    <div className="filter-panel">
      <div className="filter-row">
        <input
          type="text"
          className="search-input"
          placeholder="Search company, title, or location..."
          value={filters.search}
          onChange={e => onChange({ ...filters, search: e.target.value })}
        />
      </div>
      <div className="filter-row">
        <div className="toggle-group">
          {(['all', 'job', 'gig'] as const).map(t => (
            <button
              key={t}
              type="button"
              className={`toggle-btn ${filters.listingType === t ? 'active' : ''}`}
              onClick={() => onChange({ ...filters, listingType: t })}
            >
              {t === 'all' ? 'All' : t === 'job' ? 'Jobs' : 'Gigs'}
            </button>
          ))}
        </div>
        <label className="filter-chip">
          <input
            type="checkbox"
            checked={filters.remote === true}
            onChange={e => onChange({ ...filters, remote: e.target.checked ? true : null })}
          />
          Remote only
        </label>
        <label className="filter-chip">
          <input
            type="checkbox"
            checked={filters.degreeNotRequired}
            onChange={e => onChange({ ...filters, degreeNotRequired: e.target.checked })}
          />
          No degree required
        </label>
        <label className="filter-chip">
          <input
            type="checkbox"
            checked={filters.entryLevel}
            onChange={e => onChange({ ...filters, entryLevel: e.target.checked })}
          />
          Entry level (0-1 yr)
        </label>
        <label className="filter-range">
          Min score: {filters.minScore}
          <input
            type="range"
            min={0}
            max={80}
            step={5}
            value={filters.minScore}
            onChange={e => onChange({ ...filters, minScore: Number(e.target.value) })}
          />
        </label>
      </div>
      <div className="filter-count">
        {showing === total
          ? `${total} listings`
          : `${showing} of ${total} listings`}
      </div>
    </div>
  );
}
