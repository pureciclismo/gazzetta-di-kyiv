"use client";

import { useEffect, useState } from 'react';

export default function About() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('/data/stories.json')
      .then(res => res.json())
      .then(rawData => {
        const narratives = [];
        if (rawData.containers) {
          for (const [cid, cdata] of Object.entries(rawData.containers)) {
            const stories = cdata.stories || [];
            if (stories.length > 0) {
              narratives.push({
                id: cid,
                title: cdata.title || cid.replace('_', ' ').toUpperCase(),
                subtitle: cdata.subtitle || '',
                count: stories.length
              });
            }
          }
        }
        
        setData(narratives);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load narratives:", err);
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return (
    <main className="container" style={{paddingTop: '3rem'}}>
      <div style={{marginBottom: '2rem', paddingBottom: '1rem', borderBottom: '2px solid var(--gold)'}}>
        <h2 style={{fontFamily: 'var(--font-serif)', fontSize: '2rem', color: 'var(--text-primary)'}}>Investment Horizon</h2>
        <p style={{fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em'}}>
          Strategic Overviews & Tracked Narratives
        </p>
      </div>
      
      {loading ? (
        <div className="empty-state" style={{minHeight: '400px'}}>
          Generating strategic thesis...
        </div>
      ) : error ? (
        <div className="empty-state" style={{color: 'var(--error)'}}>
          Failed to load overviews: {error}
        </div>
      ) : (
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1.5rem'}}>
          {data.map(narrative => (
            <div key={narrative.id} style={{
              background: 'var(--bg-secondary)', 
              border: '1px solid var(--glass-border)',
              borderRadius: '8px', 
              padding: '1.5rem'
            }}>
              <div style={{color: 'var(--gold)', fontFamily: 'var(--font-mono)', fontSize: '0.8rem', marginBottom: '1rem', textTransform: 'uppercase'}}>
                Tracking {narrative.count} Signals
              </div>
              <h3 style={{fontSize: '1.2rem', marginBottom: '0.5rem'}}>{narrative.title}</h3>
              <p style={{color: 'var(--text-secondary)', fontSize: '0.9rem'}}>{narrative.subtitle}</p>
            </div>
          ))}
          {data.length === 0 && (
            <div className="empty-state" style={{gridColumn: '1 / -1'}}>
              No active narratives being tracked.
            </div>
          )}
        </div>
      )}
    </main>
  );
}
