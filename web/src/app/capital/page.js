export default function Capital() {
  return (
    <main className="container" style={{paddingTop: '3rem'}}>
      <div style={{marginBottom: '2rem', paddingBottom: '1rem', borderBottom: '2px solid var(--gold)'}}>
        <h2 style={{fontFamily: 'var(--font-serif)', fontSize: '2rem', color: 'var(--text-primary)'}}>Narrative Capitalisation</h2>
        <p style={{fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em'}}>
          Capital Flow Ledger
        </p>
      </div>
      <div className="empty-state" style={{minHeight: '400px'}}>
        Synchronizing ledger data...
      </div>
    </main>
  );
}
