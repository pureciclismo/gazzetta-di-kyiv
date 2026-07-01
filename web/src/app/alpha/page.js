export default function Alpha() {
  return (
    <main className="container" style={{paddingTop: '3rem'}}>
      <div style={{marginBottom: '2rem', paddingBottom: '1rem', borderBottom: '2px solid var(--gold)'}}>
        <h2 style={{fontFamily: 'var(--font-serif)', fontSize: '2rem', color: 'var(--text-primary)'}}>Situation Room</h2>
        <p style={{fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em'}}>
          Tactical Bets • Multi-Vector Intelligence
        </p>
      </div>
      <div className="empty-state" style={{minHeight: '400px'}}>
        Establishing secure connection to the Situation Room...
      </div>
    </main>
  );
}
