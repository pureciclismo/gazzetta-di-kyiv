"use client";

import { useEffect, useState } from 'react';

export default function Contradictions() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [narratives, setNarratives] = useState({});

  useEffect(() => {
    Promise.all([
      fetch('/data/stories.json').then(res => res.json()),
      fetch('/data/narratives.json').then(res => res.json())
    ])
      .then(([rawData, narrativesData]) => {
        if (narrativesData && narrativesData.narratives) {
          setNarratives(narrativesData.narratives);
        }
        let allStories = [];
        if (rawData.containers) {
          for (const cdata of Object.values(rawData.containers)) {
            if (cdata.stories) {
              allStories = allStories.concat(cdata.stories);
            }
          }
        } else if (Array.isArray(rawData)) {
          allStories = rawData;
        }
        
        // Filter only those with high contradictions
        const contradictions = allStories.filter(s => (s.contradiction_gap || 0) >= 30);
        
        // Sort by highest gap first
        contradictions.sort((a, b) => (b.contradiction_gap || 0) - (a.contradiction_gap || 0));
        
        setData(contradictions);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load contradictions:", err);
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return (
    <main className="container" style={{paddingTop: '3rem'}}>
      <div style={{marginBottom: '2rem', paddingBottom: '1rem', borderBottom: '2px solid var(--gold)'}}>
        <h2 style={{fontFamily: 'var(--font-serif)', fontSize: '2rem', color: 'var(--text-primary)'}}>Contradiction Matrix</h2>
        <p style={{fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em'}}>
          Media Consensus vs Market Reality
        </p>
      </div>
      
      {loading ? (
        <div className="empty-state" style={{minHeight: '400px'}}>
          Synchronizing anomaly data...
        </div>
      ) : error ? (
        <div className="empty-state" style={{color: 'var(--error)'}}>
          Failed to load anomalies: {error}
        </div>
      ) : (
        <div style={{display: 'flex', flexDirection: 'column', gap: '1rem'}}>
          {data.map(story => (
            <div key={story.story_id || story.id} style={{
              background: 'var(--bg-secondary)', 
              border: '1px solid var(--glass-border)',
              borderLeft: '4px solid var(--blue)',
              borderRadius: '8px', 
              padding: '1.5rem'
            }}>
              <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: '1rem', fontFamily: 'var(--font-mono)', fontSize: '0.8rem'}}>
                <span style={{color: 'var(--gold)', textTransform: 'uppercase'}}>{narratives[story.narrative_id]?.display_name || story.narrative_id?.replace('_', ' ')}</span>
                <span style={{color: 'var(--blue)'}}>Δ EDGE: {story.contradiction_gap || 0}</span>
              </div>
              <h3 style={{fontSize: '1.2rem', marginBottom: '1rem'}}>{story.title || story.headline}</h3>
              <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem'}}>
                <div>
                  <h4 style={{fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem', textTransform: 'uppercase'}}>Consensus (They Say)</h4>
                  <p style={{color: 'var(--text-secondary)', fontSize: '0.95rem'}}>{story.they_say}</p>
                </div>
                <div>
                  <h4 style={{fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem', textTransform: 'uppercase'}}>Reality (Market Action)</h4>
                  <p style={{color: 'var(--text-primary)', fontSize: '0.95rem'}}>{story.reality}</p>
                </div>
              </div>
            </div>
          ))}
          {data.length === 0 && (
            <div className="empty-state">
              No significant anomalies detected in current feed.
            </div>
          )}
        </div>
      )}
    </main>
  );
}
