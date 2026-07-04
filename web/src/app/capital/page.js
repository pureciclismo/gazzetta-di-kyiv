"use client";

import { useEffect, useState, Fragment } from 'react';

// Map narrative_cap.json short keys → full narrative IDs used in stories.json containers
const CAP_TO_NARRATIVE = {
  "ai_chips": "ai_compute_semiconductor_hegemony",
  "dollar_decline": "usd_debasement_reserve_diversification",
  "critical_resource_control": "critical_resource_control_infrastructure",
  "commodity_supercycle": "commodity_supercycle_supply_rebalancing",
  "deglobalization": "supply_chain_resilience_reshoring_defense",
  "crypto_reserve": "digital_assets_reserves_onchain_finance",
  "rate_cycle": "monetary_policy_regime_shift_rate_cycle",
  "gene_editing": "gene_editing_biotech_longevity",
  "china_ascent": "china_geoeconomic_expansion",
  "space_economy": "space_economy_commercialization",
  "tech_convergence": "tech_convergence_platforms_ai_autonomy",
  "wealthy_sports": "prestige_asset_acquisition_strategic_investment",
};

const formatB = (val) => {
  if (!val || val === 0) return '—';
  if (val >= 1e12) return `$${(val / 1e12).toFixed(2)}T`;
  if (val >= 1e9) return `$${(val / 1e9).toFixed(1)}B`;
  if (val >= 1e6) return `$${(val / 1e6).toFixed(0)}M`;
  return `$${val.toLocaleString()}`;
};

export default function Capital() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      fetch('/data/stories.json?v=' + Date.now()).then(res => res.json()),
      fetch('/data/narratives.json?v=' + Date.now()).then(res => res.json()),
      fetch('/data/narrative_cap.json?v=' + Date.now()).then(res => res.json()).catch(() => ({})),
    ])
      .then(([rawData, narrativesData, capData]) => {
        const capitalData = [];
        const narrativesMap = narrativesData?.narratives || {};

        // Build reverse map: full narrative ID → cap data
        const capByNarrative = {};
        for (const [shortKey, fullId] of Object.entries(CAP_TO_NARRATIVE)) {
          if (capData[shortKey]) {
            capByNarrative[fullId] = capData[shortKey];
          } else if (capData[fullId]) {
            capByNarrative[fullId] = capData[fullId];
          }
        }
        
        if (rawData?.containers) {
          for (const [cid, cdata] of Object.entries(rawData.containers)) {
            if (!capByNarrative[cid] && capData[cid]) {
              capByNarrative[cid] = capData[cid];
            }
            
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
            
            const narrMeta = narrativesMap[cid] || {};
            const cap = capByNarrative[cid] || {};
            
            capitalData.push({
              id: cid,
              title: narrMeta.display_name || cdata?.title || cid.replace(/_/g, ' ').toUpperCase(),
              tag: narrMeta.tag || '',
              subnarratives: narrMeta.subnarratives || {},
              narrativeCap: cap.narrative_cap_usd || 0,
              narrativeLiquidity: cap.narrative_liquidity_usd || 0,
              capDisplayName: cap.display_name || '',
              inflow,
              outflow,
              netFlow: inflow - outflow,
              totalCap,
              storiesCount: stories.length,
              discrepancies: discCount,
              gap: avgGap.toFixed(1)
            });
          }
        }
        
        // Sort by Narrative Market Cap (descending)
        capitalData.sort((a, b) => b.narrativeCap - a.narrativeCap);
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
          Capital tracked via High-Beta Proxy Assets
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
                <th style={{padding: '1rem', textTransform: 'uppercase'}}>Proxy Market Cap</th>
                <th style={{padding: '1rem', textTransform: 'uppercase'}}>Daily Liquidity</th>
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
                      {row.capDisplayName && <div style={{fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 'normal', marginTop: '4px', fontStyle: 'italic'}}>{row.capDisplayName}</div>}
                    </td>
                    <td style={{padding: '1rem', color: 'var(--text-primary)', fontWeight: 'bold', fontSize: '1rem'}}>
                      {formatB(row.narrativeCap)}
                    </td>
                    <td style={{padding: '1rem', color: 'var(--blue)'}}>
                      {formatB(row.narrativeLiquidity)}
                    </td>
                    <td style={{padding: '1rem', color: 'var(--text-secondary)'}}>{row.storiesCount}</td>
                    <td style={{padding: '1rem', color: row.discrepancies > 0 ? 'var(--red)' : 'var(--text-secondary)'}}>
                      {row.discrepancies}
                    </td>
                    <td style={{padding: '1rem', color: 'var(--blue)'}}>{row.gap}</td>
                  </tr>
                  {row.subnarratives && Object.keys(row.subnarratives).length > 0 && (
                    <tr style={{borderBottom: '2px solid var(--gold)', background: 'rgba(0,0,0,0.2)'}}>
                      <td colSpan="6" style={{padding: '1rem 1rem 1rem 3rem'}}>
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
                  <td colSpan="6" style={{padding: '2rem', textAlign: 'center', color: 'var(--text-muted)'}}>
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
