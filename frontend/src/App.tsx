import { useState, useEffect, useMemo, useCallback } from 'react';
import type { IndexData, ListingDetail, Filters } from './types';
import { FilterPanel } from './components/FilterPanel';
import { ListingCard } from './components/ListingCard';
import { DetailView } from './components/DetailView';
import './styles.css';

const DATA_BASE = import.meta.env.BASE_URL + 'data';

type AppState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'loaded'; data: IndexData };

function App() {
  const [state, setState] = useState<AppState>({ kind: 'loading' });
  const [filters, setFilters] = useState<Filters>({
    remote: null,
    minScore: 0,
    degreeNotRequired: false,
    search: '',
  });
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ListingDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    fetch(`${DATA_BASE}/index.json`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: IndexData) => setState({ kind: 'loaded', data }))
      .catch(err => setState({ kind: 'error', message: err.message }));
  }, []);

  const loadDetail = useCallback((id: number) => {
    setSelectedId(id);
    setDetail(null);
    setDetailLoading(true);
    fetch(`${DATA_BASE}/listings/${id}.json`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d: ListingDetail) => setDetail(d))
      .catch(() => setDetail(null))
      .finally(() => setDetailLoading(false));
  }, []);

  const filtered = useMemo(() => {
    if (state.kind !== 'loaded') return [];
    let items = state.data.listings;
    const { remote, minScore, degreeNotRequired, search } = filters;

    if (remote === true) items = items.filter(l => l.is_remote);
    else if (remote === false) items = items.filter(l => !l.is_remote);
    if (minScore > 0) items = items.filter(l => (l.score ?? 0) >= minScore);
    if (degreeNotRequired) items = items.filter(l => !l.degree_hard_required);
    if (search) {
      const q = search.toLowerCase();
      items = items.filter(l =>
        l.title.toLowerCase().includes(q) ||
        l.company.toLowerCase().includes(q) ||
        (l.location ?? '').toLowerCase().includes(q)
      );
    }
    return items;
  }, [state, filters]);

  if (state.kind === 'loading') {
    return (
      <div className="state-screen">
        <div className="spinner" />
        <p>Loading listings...</p>
      </div>
    );
  }

  if (state.kind === 'error') {
    return (
      <div className="state-screen error">
        <h2>Something went wrong</h2>
        <p>{state.message}</p>
        <p className="hint">The data export may not be available yet.</p>
      </div>
    );
  }

  if (selectedId !== null) {
    return (
      <DetailView
        detail={detail}
        loading={detailLoading}
        onBack={() => { setSelectedId(null); setDetail(null); }}
      />
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1><span className="brand">Kestrel</span></h1>
        <p className="tagline">Jobs and gigs, ranked and reasoned</p>
      </header>

      <FilterPanel
        filters={filters}
        onChange={setFilters}
        total={state.data.count}
        showing={filtered.length}
      />

      <main className="listing-list">
        {filtered.length === 0 ? (
          <div className="state-screen empty">
            <h2>No listings match</h2>
            <p>Try adjusting your filters.</p>
          </div>
        ) : (
          filtered.map(listing => (
            <ListingCard
              key={listing.id}
              listing={listing}
              onClick={() => loadDetail(listing.id)}
            />
          ))
        )}
      </main>

      <footer className="app-footer">
        <p>
          {state.data.count} listings &middot; Updated{' '}
          {new Date(state.data.exported_at).toLocaleDateString()}
        </p>
        <p className="attribution">
          Remote listings powered by{' '}
          <a href="https://weworkremotely.com" target="_blank" rel="noopener noreferrer">We Work Remotely</a>
        </p>
      </footer>
    </div>
  );
}

export default App;
