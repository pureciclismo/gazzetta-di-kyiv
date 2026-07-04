"use client";

import { useEffect, useState } from 'react';

export default function About() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      fetch('/data/stories.json?v=' + Date.now()).then(res => res.json()),
      fetch('/data/narratives.json?v=' + Date.now()).then(res => res.json())
    ])
      .then(([rawData, narrativesData]) => {
        const narratives = [];
        const narrativesMap = narrativesData?.narratives || {};
        if (rawData?.containers) {
          for (const [cid, cdata] of Object.entries(rawData.containers)) {
            const stories = cdata?.stories || [];
            if (stories.length > 0) {
              const narrMeta = narrativesMap[cid] || {};
              narratives.push({
                id: cid,
                title: narrMeta.display_name || cdata?.title || cid.replace(/_/g, ' ').toUpperCase(),
                subtitle: narrMeta.description || cdata?.subtitle || '',
                tag: narrMeta.tag || '',
                tickers: narrMeta.tickers || [],
                invalidation_threshold: narrMeta.invalidation_threshold || '',
                subnarratives: narrMeta.subnarratives || {},
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
              <div style={{color: 'var(--gold)', fontFamily: 'var(--font-mono)', fontSize: '0.8rem', marginBottom: '1rem', textTransform: 'uppercase', display: 'flex', justifyContent: 'space-between'}}>
                <span>{narrative.tag || 'Strategic Objective'}</span>
                <span>[{narrative.count} SIGNALS]</span>
              </div>
              <h3 style={{fontSize: '1.2rem', marginBottom: '0.5rem'}}>{narrative.title}</h3>
              <p style={{color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1.5rem'}}>{narrative.subtitle}</p>
              
              <div style={{borderTop: '1px solid var(--glass-border)', paddingTop: '1rem', marginTop: '1rem'}}>
                <div style={{fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem', fontFamily: 'var(--font-mono)'}}>SUBNARRATIVES</div>
                <ul style={{listStyle: 'none', padding: 0, margin: 0}}>
                  {Object.values(narrative.subnarratives || {}).map((sub, i) => (
                    <li key={i} style={{marginBottom: '0.5rem', borderLeft: '2px solid var(--gold)', paddingLeft: '0.5rem'}}>
                      <strong style={{fontSize: '0.85rem', color: 'var(--text-primary)', display: 'block'}}>{sub?.title}</strong>
                      <span style={{fontSize: '0.8rem', color: 'var(--text-secondary)'}}>{sub?.description}</span>
                    </li>
                  ))}
                </ul>
              </div>
              
              <div style={{background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '4px', marginTop: '1.5rem', fontFamily: 'var(--font-mono)', fontSize: '0.8rem'}}>
                <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem'}}>
                  <span style={{color: 'var(--text-muted)'}}>INVALIDATION THRESHOLD</span>
                  <span style={{color: 'var(--red)'}}>{narrative.invalidation_threshold}</span>
                </div>
                <div style={{display: 'flex', justifyContent: 'space-between'}}>
                  <span style={{color: 'var(--text-muted)'}}>TARGET TICKERS</span>
                  <span style={{color: 'var(--blue)'}}>{Array.isArray(narrative.tickers) ? narrative.tickers.join(', ') : ''}</span>
                </div>
              </div>
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
