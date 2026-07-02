"use client";

import { useEffect, useState, Fragment } from 'react';

export default function Capital() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      fetch('/data/stories.json').then(res => res.json()),
      fetch('/data/narratives.json').then(res => res.json())
    ])
      .then(([rawData, narrativesData]) => {
        const capitalData = [];
        const narrativesMap = narrativesData?.narratives || {};
        if (rawData?.containers) {
          for (const [cid, cdata] of Object.entries(rawData.containers)) {
            const stories = cdata?.stories || [];
            let inflow = 0;
            let outflow = 0;
            let totalCap = 0;
            let discCount = 0;
            let sumGap = 0;
            
            stories.forEach(s => {
              if (s) {
                const gap = s.contradiction_gap || 0;
                const vol = s.capital_volume_usd || s.capital_at_stake_usd || 0;
                const dir = s.capital_flow?.direction;
                
                if (dir === 'inflow') inflow += vol;
                if (dir === 'outflow') outflow += vol;
                if (gap >= 40) discCount++;
                sumGap += gap;
                totalCap += vol;
              }
            });
            
            const avgGap = stories.length > 0 ? (sumGap / stories.length) : 0;
            
            // Format numbers to Billions
            const toB = (val) => (val / 1e9).toFixed(1);
            
            const narrMeta = narrativesMap[cid] || {};
            
            capitalData.push({
              id: cid,
              title: narrMeta.display_name || cdata?.title || cid.replace(/_/g, ' ').toUpperCase(),
              tag: narrMeta.tag || '',
              subnarratives: narrMeta.subnarratives || {},
              ticker: stories[0]?.narrative_id || 'MULTI-ASSET', // simplified
              inflow_b: toB(inflow),
              outflow_b: toB(outflow),
              net_b: toB(inflow - outflow),
              total_b: toB(inflow + outflow),
              storiesCount: stories.length,
              discrepancies: discCount,
              gap: avgGap.toFixed(1)
            });
          }
        }
        
        // Sort by Net Capital Flow (absolute magnitude)
        capitalData.sort((a, b) => Math.abs(parseFloat(b.net_b)) - Math.abs(parseFloat(a.net_b)));
        setData(capitalData);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load capital data:", err);
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return (
    <main className="container" style={{paddingTop: '3rem'}}>
      <div style={{marginBottom: '2rem', paddingBottom: '1rem', borderBottom: '2px solid var(--gold)'}}>
        <h2 style={{fontFamily: 'var(--font-serif)', fontSize: '2rem', color: 'var(--text-primary)'}}>Narrative Capitalisation</h2>
        <p style={{fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em'}}>
          Capital Flow Ledger
        </p>
      </div>
      
      {loading ? (
        <div className="empty-state" style={{minHeight: '400px'}}>
          Synchronizing ledger data...
        </div>
      ) : error ? (
        <div className="empty-state" style={{color: 'var(--error)'}}>
          Failed to synchronize ledger: {error}
        </div>
      ) : (
        <div style={{overflowX: 'auto', background: 'var(--bg-secondary)', border: '1px solid var(--glass-border)', borderRadius: '8px', padding: '1rem'}}>
          <table style={{width: '100%', textAlign: 'left', borderCollapse: 'collapse', fontFamily: 'var(--font-mono)', fontSize: '0.9rem'}}>
            <thead>
              <tr style={{borderBottom: '1px solid var(--glass-border)', color: 'var(--text-muted)'}}>
                <th style={{padding: '1rem', textTransform: 'uppercase'}}>Narrative</th>
                <th style={{padding: '1rem', textTransform: 'uppercase'}}>Inflow</th>
                <th style={{padding: '1rem', textTransform: 'uppercase'}}>Outflow</th>
                <th style={{padding: '1rem', textTransform: 'uppercase'}}>Net Flow</th>
                <th style={{padding: '1rem', textTransform: 'uppercase'}}>Gross Vol</th>
                <th style={{padding: '1rem', textTransform: 'uppercase'}}>Stories</th>
                <th style={{padding: '1rem', textTransform: 'uppercase'}}>Discrepancies</th>
                <th style={{padding: '1rem', textTransform: 'uppercase'}}>Δ Edge</th>
              </tr>
            </thead>
            <tbody>
              {data.map(row => (
                <Fragment key={row.id}>
                  <tr style={{borderBottom: '1px solid var(--glass-border)'}} className="capital-row">
                    <td style={{padding: '1rem', color: 'var(--gold)', fontWeight: 'bold'}}>
                      {row.title}
                      {row.tag && <div style={{fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 'normal', marginTop: '4px'}}>{row.tag}</div>}
                    </td>
                    <td style={{padding: '1rem', color: 'var(--green)'}}>${row.inflow_b}B</td>
                    <td style={{padding: '1rem', color: 'var(--red)'}}>${row.outflow_b}B</td>
                    <td style={{padding: '1rem', color: parseFloat(row.net_b) >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 'bold'}}>
                      {parseFloat(row.net_b) >= 0 ? '+' : ''}${row.net_b}B
                    </td>
                    <td style={{padding: '1rem', color: 'var(--text-primary)'}}>${row.total_b}B</td>
                    <td style={{padding: '1rem', color: 'var(--text-secondary)'}}>{row.storiesCount}</td>
                    <td style={{padding: '1rem', color: row.discrepancies > 0 ? 'var(--red)' : 'var(--text-secondary)'}}>
                      {row.discrepancies}
                    </td>
                    <td style={{padding: '1rem', color: 'var(--blue)'}}>{row.gap}</td>
                  </tr>
                  {row.subnarratives && Object.keys(row.subnarratives).length > 0 && (
                    <tr style={{borderBottom: '2px solid var(--gold)', background: 'rgba(0,0,0,0.2)'}}>
                      <td colSpan="8" style={{padding: '1rem 1rem 1rem 3rem'}}>
                        <div style={{display: 'flex', gap: '1rem', flexWrap: 'wrap'}}>
                          {Object.values(row.subnarratives).map((sub, i) => (
                            <div key={i} style={{flex: '1 1 200px', minWidth: '200px', borderLeft: '1px solid var(--glass-border)', paddingLeft: '0.5rem'}}>
                              <div style={{color: 'var(--text-primary)', fontSize: '0.8rem', fontWeight: 'bold'}}>{sub?.title}</div>
                              <div style={{color: 'var(--text-muted)', fontSize: '0.75rem'}}>{sub?.description}</div>
                            </div>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
              {data.length === 0 && (
                <tr>
                  <td colSpan="8" style={{padding: '2rem', textAlign: 'center', color: 'var(--text-muted)'}}>
                    No capital flow data available.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
