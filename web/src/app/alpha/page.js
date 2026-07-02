"use client";

import { useEffect, useState } from 'react';

const METRIC_LABELS = {
  vix: { name: "VIX", desc: "Volatility Index", prefix: "", suffix: "" },
  dxy: { name: "DXY", desc: "US Dollar Index", prefix: "", suffix: "" },
  eurusd: { name: "EURUSD", desc: "Euro / US Dollar", prefix: "$", suffix: "" },
  brent: { name: "Brent", desc: "Brent Crude Oil", prefix: "$", suffix: "/bbl" },
  gold: { name: "Gold", desc: "Spot Gold", prefix: "$", suffix: "/oz" },
  btc: { name: "BTC", desc: "Bitcoin", prefix: "$", suffix: "" },
  spx: { name: "SPX", desc: "S&P 500 Index", prefix: "", suffix: "" },
  nq: { name: "NQ", desc: "Nasdaq 100 Index", prefix: "", suffix: "" }
};

export default function Alpha() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('/data/flows.json')
      .then(res => {
        if (!res.ok) {
          throw new Error(`Failed to fetch flows data (HTTP ${res.status})`);
        }
        return res.json();
      })
      .then(json => {
        setData(json);
        setLoading(false);
      })
      .catch(err => {
        console.error('Error fetching flows.json:', err);
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const formatValue = (key, val) => {
    if (val === undefined || val === null) return "N/A";
    const num = parseFloat(val);
    if (isNaN(num)) return val;
    
    const meta = METRIC_LABELS[key];
    const prefix = meta?.prefix || "";
    const suffix = meta?.suffix || "";

    if (key === 'eurusd') return `${prefix}${num.toFixed(4)}${suffix}`;
    if (key === 'btc' || key === 'gold' || key === 'spx' || key === 'nq') {
      return `${prefix}${num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}${suffix}`;
    }
    return `${prefix}${num.toFixed(2)}${suffix}`;
  };

  return (
    <main className="container" style={{paddingTop: '3rem', paddingBottom: '5rem'}}>
      <style dangerouslySetInnerHTML={{__html: `
        .alpha-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 2rem;
          margin-top: 2rem;
        }
        @media(min-width: 1024px) {
          .alpha-grid {
            grid-template-columns: 350px 1fr;
          }
        }
        .dashboard-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          gap: 1.5rem;
        }
        .asset-card {
          background: var(--bg-secondary);
          border: 1px solid var(--glass-border);
          border-radius: 12px;
          padding: 1.5rem;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
          position: relative;
          overflow: hidden;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          min-height: 140px;
        }
        .asset-card:hover {
          transform: translateY(-4px);
          border-color: var(--gold);
          box-shadow: 0 10px 15px -3px rgba(212, 175, 55, 0.1), 0 4px 6px -2px rgba(212, 175, 55, 0.05);
        }
        .asset-card::before {
          content: '';
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 3px;
          background: linear-gradient(90deg, transparent, var(--gold), transparent);
          transform: translateX(-100%);
          transition: transform 0.5s ease;
        }
        .asset-card:hover::before {
          transform: translateX(100%);
        }
        .driver-item {
          padding: 0.75rem 1rem;
          background: rgba(212, 175, 55, 0.02);
          border-left: 2px solid var(--gold);
          margin-bottom: 0.75rem;
          border-radius: 0 8px 8px 0;
          font-size: 0.85rem;
          line-height: 1.4;
          color: var(--text-secondary);
          transition: all 0.2s ease;
        }
        .driver-item:hover {
          background: var(--gold-glow);
          color: var(--text-primary);
          transform: translateX(4px);
        }
      `}} />

      <div style={{marginBottom: '2rem', paddingBottom: '1rem', borderBottom: '2px solid var(--gold)'}}>
        <h2 style={{fontFamily: 'var(--font-serif)', fontSize: '2rem', color: 'var(--text-primary)'}}>Situation Room</h2>
        <p style={{fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em'}}>
          Live Macro Regime & Cross-Asset Snapshot
        </p>
      </div>
      
      {loading ? (
        <div className="empty-state" style={{minHeight: '400px'}}>
          <span className="live-indicator" style={{marginBottom: '1rem'}}></span>
          Authenticating secure clearance...
        </div>
      ) : error ? (
        <div className="empty-state" style={{color: 'var(--crimson)', border: '1px solid var(--crimson)', background: 'rgba(217, 56, 58, 0.05)', padding: '2rem', borderRadius: '12px'}}>
          <span className="material-symbols-outlined" style={{fontSize: '3rem', marginBottom: '1rem', display: 'block'}}>warning</span>
          <h3 style={{marginBottom: '1rem'}}>SECURE LINK FAILED</h3>
          <p>Failed to establish contact with the data gateway: {error}</p>
        </div>
      ) : (
        <div className="alpha-grid">
          {/* Regime and Drivers Panel */}
          <div>
            <div className="glass-panel" style={{padding: '1.5rem', marginBottom: '2rem', borderTop: '3px solid var(--gold)'}}>
              <div style={{display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem'}}>
                <span className="live-indicator"></span>
                <span style={{fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em'}}>
                  Live Macro Regime
                </span>
              </div>
              <h3 style={{
                fontFamily: 'var(--font-serif)', 
                fontSize: '1.6rem', 
                color: 'var(--roman-purple)', 
                textTransform: 'capitalize',
                lineHeight: '1.3',
                marginBottom: '0.5rem'
              }}>
                {data.regime || "Risk-Neutral Regime"}
              </h3>
              <p style={{fontSize: '0.8rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)'}}>
                Updated: {data.generated_at ? new Date(data.generated_at).toLocaleString() : 'Recent'}
              </p>
            </div>

            <div className="glass-panel" style={{padding: '1.5rem'}}>
              <h4 style={{fontFamily: 'var(--font-serif)', fontSize: '1.2rem', color: 'var(--text-primary)', marginBottom: '1rem'}}>
                Regime Drivers
              </h4>
              <div style={{display: 'flex', flexDirection: 'column'}}>
                {data.regime_drivers && data.regime_drivers.length > 0 ? (
                  data.regime_drivers.map((driver, idx) => (
                    <div key={idx} className="driver-item">
                      <span style={{color: 'var(--gold)', marginRight: '0.5rem', fontFamily: 'var(--font-mono)'}}>⚜</span>
                      {driver}
                    </div>
                  ))
                ) : (
                  <p style={{fontStyle: 'italic', fontSize: '0.85rem', color: 'var(--text-muted)'}}>No active drivers monitored.</p>
                )}
              </div>
            </div>
          </div>

          {/* Cross Asset Grid */}
          <div>
            <div style={{marginBottom: '1rem'}}>
              <h4 style={{fontFamily: 'var(--font-serif)', fontSize: '1.2rem', color: 'var(--text-primary)'}}>
                Cross-Asset Metrics
              </h4>
            </div>
            <div className="dashboard-grid">
              {Object.entries(METRIC_LABELS).map(([key, label]) => {
                const val = data.cross_asset?.[key];
                return (
                  <div key={key} className="asset-card">
                    <div>
                      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.25rem'}}>
                        <span style={{fontFamily: 'var(--font-mono)', fontSize: '1.25rem', fontWeight: 'bold', color: 'var(--roman-purple)'}}>
                          {label.name}
                        </span>
                        <span style={{
                          fontFamily: 'var(--font-mono)', 
                          fontSize: '0.65rem', 
                          color: 'var(--text-muted)', 
                          background: 'var(--bg-tertiary)',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          textTransform: 'uppercase'
                        }}>
                          {key}
                        </span>
                      </div>
                      <span style={{fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '1rem'}}>
                        {label.desc}
                      </span>
                    </div>
                    <div>
                      <span style={{
                        fontFamily: 'var(--font-mono)', 
                        fontSize: '1.6rem', 
                        fontWeight: 'bold', 
                        color: 'var(--text-primary)',
                        letterSpacing: '-0.02em'
                      }}>
                        {formatValue(key, val)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
