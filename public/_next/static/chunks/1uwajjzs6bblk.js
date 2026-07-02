(globalThis.TURBOPACK||(globalThis.TURBOPACK=[])).push(["object"==typeof document?document.currentScript:void 0,94135,e=>{"use strict";var r=e.i(43476),t=e.i(71645);let a={vix:{name:"VIX",desc:"Volatility Index",prefix:"",suffix:""},dxy:{name:"DXY",desc:"US Dollar Index",prefix:"",suffix:""},eurusd:{name:"EURUSD",desc:"Euro / US Dollar",prefix:"$",suffix:""},brent:{name:"Brent",desc:"Brent Crude Oil",prefix:"$",suffix:"/bbl"},gold:{name:"Gold",desc:"Spot Gold",prefix:"$",suffix:"/oz"},btc:{name:"BTC",desc:"Bitcoin",prefix:"$",suffix:""},spx:{name:"SPX",desc:"S&P 500 Index",prefix:"",suffix:""},nq:{name:"NQ",desc:"Nasdaq 100 Index",prefix:"",suffix:""}};e.s(["default",0,function(){let[e,i]=(0,t.useState)(null),[s,o]=(0,t.useState)(!0),[n,l]=(0,t.useState)(null);return(0,t.useEffect)(()=>{fetch("/data/flows.json").then(e=>{if(!e.ok)throw Error(`Failed to fetch flows data (HTTP ${e.status})`);return e.json()}).then(e=>{i(e),o(!1)}).catch(e=>{console.error("Error fetching flows.json:",e),l(e.message),o(!1)})},[]),(0,r.jsxs)("main",{className:"container",style:{paddingTop:"3rem",paddingBottom:"5rem"},children:[(0,r.jsx)("style",{dangerouslySetInnerHTML:{__html:`
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
      `}}),(0,r.jsxs)("div",{style:{marginBottom:"2rem",paddingBottom:"1rem",borderBottom:"2px solid var(--gold)"},children:[(0,r.jsx)("h2",{style:{fontFamily:"var(--font-serif)",fontSize:"2rem",color:"var(--text-primary)"},children:"Situation Room"}),(0,r.jsx)("p",{style:{fontFamily:"var(--font-mono)",fontSize:"0.8rem",color:"var(--text-secondary)",textTransform:"uppercase",letterSpacing:"0.05em"},children:"Live Macro Regime & Cross-Asset Snapshot"})]}),s?(0,r.jsxs)("div",{className:"empty-state",style:{minHeight:"400px"},children:[(0,r.jsx)("span",{className:"live-indicator",style:{marginBottom:"1rem"}}),"Authenticating secure clearance..."]}):n?(0,r.jsxs)("div",{className:"empty-state",style:{color:"var(--crimson)",border:"1px solid var(--crimson)",background:"rgba(217, 56, 58, 0.05)",padding:"2rem",borderRadius:"12px"},children:[(0,r.jsx)("span",{className:"material-symbols-outlined",style:{fontSize:"3rem",marginBottom:"1rem",display:"block"},children:"warning"}),(0,r.jsx)("h3",{style:{marginBottom:"1rem"},children:"SECURE LINK FAILED"}),(0,r.jsxs)("p",{children:["Failed to establish contact with the data gateway: ",n]})]}):(0,r.jsxs)("div",{className:"alpha-grid",children:[(0,r.jsxs)("div",{children:[(0,r.jsxs)("div",{className:"glass-panel",style:{padding:"1.5rem",marginBottom:"2rem",borderTop:"3px solid var(--gold)"},children:[(0,r.jsxs)("div",{style:{display:"flex",alignItems:"center",gap:"0.5rem",marginBottom:"0.75rem"},children:[(0,r.jsx)("span",{className:"live-indicator"}),(0,r.jsx)("span",{style:{fontFamily:"var(--font-mono)",fontSize:"0.7rem",color:"var(--text-muted)",textTransform:"uppercase",letterSpacing:"0.05em"},children:"Live Macro Regime"})]}),(0,r.jsx)("h3",{style:{fontFamily:"var(--font-serif)",fontSize:"1.6rem",color:"var(--roman-purple)",textTransform:"capitalize",lineHeight:"1.3",marginBottom:"0.5rem"},children:e.regime||"Risk-Neutral Regime"}),(0,r.jsxs)("p",{style:{fontSize:"0.8rem",color:"var(--text-muted)",fontFamily:"var(--font-mono)"},children:["Updated: ",e.generated_at?new Date(e.generated_at).toLocaleString():"Recent"]})]}),(0,r.jsxs)("div",{className:"glass-panel",style:{padding:"1.5rem"},children:[(0,r.jsx)("h4",{style:{fontFamily:"var(--font-serif)",fontSize:"1.2rem",color:"var(--text-primary)",marginBottom:"1rem"},children:"Regime Drivers"}),(0,r.jsx)("div",{style:{display:"flex",flexDirection:"column"},children:e.regime_drivers&&e.regime_drivers.length>0?e.regime_drivers.map((e,t)=>(0,r.jsxs)("div",{className:"driver-item",children:[(0,r.jsx)("span",{style:{color:"var(--gold)",marginRight:"0.5rem",fontFamily:"var(--font-mono)"},children:"⚜"}),e]},t)):(0,r.jsx)("p",{style:{fontStyle:"italic",fontSize:"0.85rem",color:"var(--text-muted)"},children:"No active drivers monitored."})})]})]}),(0,r.jsxs)("div",{children:[(0,r.jsx)("div",{style:{marginBottom:"1rem"},children:(0,r.jsx)("h4",{style:{fontFamily:"var(--font-serif)",fontSize:"1.2rem",color:"var(--text-primary)"},children:"Cross-Asset Metrics"})}),(0,r.jsx)("div",{className:"dashboard-grid",children:Object.entries(a).map(([t,i])=>{let s=e.cross_asset?.[t];return(0,r.jsxs)("div",{className:"asset-card",children:[(0,r.jsxs)("div",{children:[(0,r.jsxs)("div",{style:{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:"0.25rem"},children:[(0,r.jsx)("span",{style:{fontFamily:"var(--font-mono)",fontSize:"1.25rem",fontWeight:"bold",color:"var(--roman-purple)"},children:i.name}),(0,r.jsx)("span",{style:{fontFamily:"var(--font-mono)",fontSize:"0.65rem",color:"var(--text-muted)",background:"var(--bg-tertiary)",padding:"2px 6px",borderRadius:"4px",textTransform:"uppercase"},children:t})]}),(0,r.jsx)("span",{style:{fontSize:"0.75rem",color:"var(--text-muted)",display:"block",marginBottom:"1rem"},children:i.desc})]}),(0,r.jsx)("div",{children:(0,r.jsx)("span",{style:{fontFamily:"var(--font-mono)",fontSize:"1.6rem",fontWeight:"bold",color:"var(--text-primary)",letterSpacing:"-0.02em"},children:((e,r)=>{if(null==r)return"N/A";let t=parseFloat(r);if(isNaN(t))return r;let i=a[e],s=i?.prefix||"",o=i?.suffix||"";return"eurusd"===e?`${s}${t.toFixed(4)}${o}`:"btc"===e||"gold"===e||"spx"===e||"nq"===e?`${s}${t.toLocaleString(void 0,{minimumFractionDigits:2,maximumFractionDigits:2})}${o}`:`${s}${t.toFixed(2)}${o}`})(t,s)})})]},t)})})]})]})]})}])}]);