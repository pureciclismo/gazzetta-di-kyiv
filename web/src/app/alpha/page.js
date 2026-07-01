"use client";

import { useEffect, useState } from 'react';

export default function Alpha() {
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Simulate loading secure clearance
    const timer = setTimeout(() => {
      setLoading(false);
    }, 1500);
    return () => clearTimeout(timer);
  }, []);

  return (
    <main className="container" style={{paddingTop: '3rem'}}>
      <div style={{marginBottom: '2rem', paddingBottom: '1rem', borderBottom: '2px solid var(--gold)'}}>
        <h2 style={{fontFamily: 'var(--font-serif)', fontSize: '2rem', color: 'var(--text-primary)'}}>Situation Room</h2>
        <p style={{fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em'}}>
          Live Macro Regime & Cross-Asset Snapshot
        </p>
      </div>
      
      {loading ? (
        <div className="empty-state" style={{minHeight: '400px'}}>
          Authenticating secure clearance...
        </div>
      ) : (
        <div className="empty-state" style={{color: 'var(--gold)', border: '1px solid var(--gold)', background: 'rgba(212, 175, 55, 0.05)'}}>
          <span className="material-symbols-outlined" style={{fontSize: '3rem', marginBottom: '1rem', display: 'block'}}>lock</span>
          <h3 style={{marginBottom: '1rem'}}>RESTRICTED INTELLIGENCE</h3>
          <p>Access to live macro regimes and institutional cross-asset correlations requires Tier 1 clearance.</p>
        </div>
      )}
    </main>
  );
}
