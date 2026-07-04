'use client';

import { useState, useEffect } from 'react';

export default function Home() {
  const [stories, setStories] = useState([]);
  const [narratives, setNarratives] = useState({});
  const [selectedStory, setSelectedStory] = useState(null);
  const [loading, setLoading] = useState(true);

  const getRepricingClaim = (story) => {
    if (!story) return 'Neutral Flow ⇢';
    const gap = story.contradiction_gap || 0;
    
    // Find direction from various possible fields
    let direction = 'neutral';
    if (story.trade_thesis?.direction) {
      direction = String(story.trade_thesis.direction).toLowerCase();
    } else if (story.capital_flow?.direction) {
      direction = String(story.capital_flow.direction).toLowerCase();
    }
  
    // Determine arrow
    let arrow = '⇢';
    if (direction === 'long' || direction === 'inflow') arrow = '⇡';
    if (direction === 'short' || direction === 'outflow') arrow = '⇣';
    
    // Determine textual claim based on gap
    let text = 'Neutral Flow';
    if (gap >= 76) text = 'Systemic Repricing';
    else if (gap >= 51) text = 'Capital Diversion';
    else if (gap >= 31) text = 'Consensus Drift';
    else if (gap >= 16) text = 'Minor Tension';
    
    return `${text} ${arrow}`;
  };

  useEffect(() => {
    Promise.all([
      fetch('/data/stories.json?v=' + Date.now()).then(res => res.json()),
      fetch('/data/narratives.json?v=' + Date.now()).then(res => res.json())
    ])
      .then(([rawData, narrativesData]) => {
        if (narrativesData && narrativesData.narratives) {
          setNarratives(narrativesData.narratives);
        }
        let allStories = rawData?.all_stories || [];
        
        // Flatten legacy containers if necessary
        if (allStories.length === 0 && rawData?.containers) {
          for (const [cid, cdata] of Object.entries(rawData.containers)) {
            const storiesList = cdata?.stories || [];
            for (const s of storiesList) {
              if (s) {
                s._container_id = cid;
                allStories.push(s);
              }
            }
          }
        }
        
        // Sort by generated_at
        allStories.sort((a, b) => {
          const dA = new Date(a?.generated_at || a?.timestamp || 0).getTime();
          const dB = new Date(b?.generated_at || b?.timestamp || 0).getTime();
          return dB - dA;
        });

        if (allStories && allStories.length > 0) {
          setStories(allStories);
          setSelectedStory(allStories[0]);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error('Error fetching stories:', err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="empty-state">
        <span className="live-indicator" style={{marginBottom: '1rem'}}></span>
        Decrypting Intelligence...
      </div>
    );
  }

  return (
    <main className="stream-layout">
      {/* Left List Column */}
      <div className="story-list hide-scrollbar">
        {stories.map((story, index) => (
          <button 
            key={story?.id || story?.story_id || index} 
            className={`story-item ${(selectedStory?.id || selectedStory?.story_id) === (story?.id || story?.story_id) ? 'active' : ''}`}
            onClick={() => setSelectedStory(story)}
          >
            <div className={`story-tier ${story?.tier_level || 'ACTIVE'}`}></div>
            <h3 className="story-title">{story?.title || story?.headline || 'Untitled Dispatch'}</h3>
            <div className="story-meta">
              <span className={`edge-badge ${(story?.contradiction_gap || 0) >= 60 ? 'high' : 'med'}`}>
                {getRepricingClaim(story)}
              </span>
              <span>{story?.source || 'Intel'}</span>
              <span>{story?.generated_at ? new Date(story.generated_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : ''}</span>
            </div>
          </button>
        ))}
      </div>

      {/* Right Detail Panel */}
      {selectedStory ? (
        <div className="story-detail hide-scrollbar">
          <div className="detail-content">
            <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem'}}>
              <span className="section-label">Intercepted Dispatch • {selectedStory.tier_level || 'ACTIVE'}</span>
              <span style={{fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', fontSize: '0.8rem'}}>
                ID: {typeof selectedStory.id === 'string' ? selectedStory.id.split('-')[0].toUpperCase() : (selectedStory.story_id || 'UNKNOWN')}
              </span>
            </div>
            
            <h1>{selectedStory.title || selectedStory.headline || 'Untitled Dispatch'}</h1>
            
            <p style={{fontSize: '1.1rem', color: 'var(--text-secondary)', marginBottom: '2rem'}}>
              {selectedStory.summary || selectedStory.projected || selectedStory.capital_flow?.projected || ""}
            </p>

            <div className="synthesis-grid">
              <div className="synthesis-card capital-says">
                <span className="section-label">Media Consensus</span>
                <p style={{fontSize: '0.9rem', color: 'var(--text-secondary)'}}>
                  {selectedStory.claim_analysis?.media_consensus || selectedStory.synthesis || selectedStory.they_say || "—"}
                </p>
              </div>
              <div className="synthesis-card capital-goes">
                <span className="section-label">Market Reality</span>
                <p style={{fontSize: '0.9rem', color: 'var(--text-secondary)'}}>
                  {selectedStory.claim_analysis?.market_reality || selectedStory.synthesis_details || selectedStory.reality || "—"}
                </p>
              </div>
            </div>

            <div className="trade-thesis">
              <span className="section-label">Tactical Implication</span>
              <p style={{fontSize: '1.05rem', color: 'var(--text-primary)', fontStyle: 'italic'}}>
                {selectedStory.claim_analysis?.trade_implication || selectedStory.conclusion || selectedStory.implication_note || selectedStory.trade_thesis?.alpha_trigger || "—"}
              </p>
              
              <div className="trade-stats">
                <div className="stat-box">
                  <span>Asset Repricing</span>
                  <strong style={{color: (selectedStory.contradiction_gap || 0) >= 60 ? 'var(--crimson)' : 'var(--gold)'}}>
                    {getRepricingClaim(selectedStory)}
                  </strong>
                </div>
                <div className="stat-box">
                  <span>Asset Flow</span>
                  <strong style={{color: 'var(--green)'}}>
                    {selectedStory.capital_flow?.direction === 'inflow' ? '+' : selectedStory.capital_flow?.direction === 'outflow' ? '-' : ''}
                    ${((selectedStory.capital_volume_usd || selectedStory.capital_at_stake_usd || 0) / 1e9).toFixed(1)}B
                  </strong>
                </div>
                <div className="stat-box">
                  <span>Target Ticker</span>
                  <strong>{narratives[selectedStory.narrative_id]?.display_name || selectedStory.narrative_id?.replace(/_/g, ' ').toUpperCase() || 'MULTI-ASSET'}</strong>
                </div>
              </div>
            </div>

            {/* Sovereign Auditor's Review */}
            {(selectedStory.brief_review || selectedStory.contradiction_note || selectedStory.implication_note) && (
              <div className="editorial-review-box" style={{
                marginTop: '2rem',
                padding: '1.5rem',
                background: 'rgba(212, 175, 55, 0.03)',
                border: '1px solid var(--gold)',
                borderRadius: '8px',
                borderLeft: '4px solid var(--gold)'
              }}>
                <span className="section-label" style={{color: 'var(--gold)', marginBottom: '0.5rem', display: 'block'}}>Sovereign Auditor's Commentary</span>
                {selectedStory.brief_review && (
                  <p style={{fontSize: '1rem', color: 'var(--text-primary)', marginBottom: '0.5rem', fontWeight: '500', lineHeight: '1.4'}}>
                    {selectedStory.brief_review}
                  </p>
                )}
                {selectedStory.contradiction_note && (
                  <p style={{fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.4', fontStyle: 'italic'}}>
                    <strong>Contradiction Gap:</strong> {selectedStory.contradiction_note}
                  </p>
                )}
              </div>
            )}
            
            {/* Displaying original content if available */}
            {typeof selectedStory.content === 'string' && selectedStory.content.length > 0 && (
              <div style={{marginTop: '3rem'}}>
                <span className="section-label">Raw Transcript / Signal</span>
                <div style={{
                  padding: '1.5rem', 
                  background: 'var(--bg-secondary)', 
                  border: '1px solid var(--glass-border)',
                  borderRadius: '8px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.85rem',
                  color: 'var(--text-muted)',
                  whiteSpace: 'pre-wrap'
                }}>
                  {selectedStory.content.substring(0, 800)}...
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="empty-state">
          No dispatches intercepted today.
        </div>
      )}
    </main>
  );
}
