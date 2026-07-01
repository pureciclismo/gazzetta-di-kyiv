import Link from 'next/link';
import './globals.css';

export const metadata = {
  title: 'La Gazzetta di Kyiv — Geopolitical Intelligence',
  description: 'Institutional-grade narrative intelligence. Tracking the Contrarian Edge between media consensus and capital flows.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='12' fill='%230a0a0a'/><text x='50' y='65' text-anchor='middle' font-family='Georgia,serif' font-size='52' font-weight='bold' fill='%23D4AF37'>G</text></svg>"/>
      </head>
      <body>
        <header className="masthead">
          <div className="brand">
            <svg width="48" height="48" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="Crossed Bulavas">
              <defs>
                <g id="bulava">
                  {/* Handle Base / Pommel */}
                  <path d="M18.5 35 Q20 37.5 21.5 35 L21 33 L19 33 Z" fill="#D4AF37" />
                  
                  {/* Shaft / Grip */}
                  <rect x="19" y="16" width="2" height="17" fill="#C5A880" />
                  {/* Grip Wrapping / Details */}
                  <path d="M18.5 28 L21.5 28 M18.5 24 L21.5 24 M18.5 20 L21.5 20" stroke="#4A0E4E" strokeWidth="0.8" />
                  
                  {/* Handguard / Collar */}
                  <rect x="18" y="14" width="4" height="2" rx="1" fill="#D4AF37" />
                  <rect x="18.5" y="12.5" width="3" height="1.5" fill="#C5A880" />
                  
                  {/* Head Base (Mace head) */}
                  <circle cx="20" cy="8" r="5" fill="#4A0E4E" stroke="#D4AF37" strokeWidth="1.5" />
                  
                  {/* Spikes / Studs on the head */}
                  {/* Top spike */}
                  <path d="M19 3 L20 0 L21 3 Z" fill="#D4AF37" />
                  {/* Side spikes */}
                  <path d="M14 7 L11 8 L14 9 Z" fill="#D4AF37" />
                  <path d="M26 7 L29 8 L26 9 Z" fill="#D4AF37" />
                  {/* Diagonal spikes */}
                  <path d="M16 4.5 L14 2 L15 5.5 Z" fill="#D4AF37" />
                  <path d="M24 4.5 L26 2 L25 5.5 Z" fill="#D4AF37" />
                  
                  {/* Inner details / Jewels on the head */}
                  <circle cx="20" cy="8" r="1.2" fill="#D4AF37" />
                  <circle cx="17.5" cy="6.5" r="0.8" fill="#D4AF37" />
                  <circle cx="22.5" cy="6.5" r="0.8" fill="#D4AF37" />
                  <circle cx="17.5" cy="9.5" r="0.8" fill="#D4AF37" />
                  <circle cx="22.5" cy="9.5" r="0.8" fill="#D4AF37" />
                </g>
              </defs>
              
              {/* Left Bulava: rotated left */}
              <use href="#bulava" transform="rotate(-55 20 25)" />
              {/* Right Bulava: rotated right */}
              <use href="#bulava" transform="rotate(55 20 25)" />
            </svg>
            <div style={{display: 'flex', flexDirection: 'column'}}>
              <h1 className="brand-title">La Gazzetta di Kyiv</h1>
              <span style={{fontSize: '1.3rem', color: 'var(--text-secondary)', fontStyle: 'normal', fontFamily: 'var(--font-serif)', letterSpacing: '0.05em', marginTop: '2px'}}>The stories that move markets</span>
            </div>
          </div>
          
          <nav className="nav-tabs">
            <Link href="/" className="nav-item">Events Horizon</Link>
            <Link href="/alpha" className="nav-item">Situation Room</Link>
            <Link href="/capital" className="nav-item">Narrative Capitalisation</Link>
            <Link href="/contradictions" className="nav-item">Markets Room</Link>
            <Link href="/about" className="nav-item">Investment Horizon</Link>
          </nav>

          <div style={{display: 'flex', alignItems: 'center', gap: '0.5rem', fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-secondary)'}}>
            <span className="live-indicator"></span>
            <span>LIVE INTELLIGENCE</span>
            <span style={{fontSize: '1.2rem', color: 'var(--gold)', marginLeft: '0.5rem'}}>⚜</span>
          </div>
        </header>

        {children}
      </body>
    </html>
  );
}
