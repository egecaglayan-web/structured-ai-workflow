import React, { useEffect, useRef, useState } from 'react';

const PROVIDER_LABELS = { openai: 'OpenAI', anthropic: 'Anthropic', demo: 'Demo' };

const EXAMPLES = [
  ['Account access', 'My password reset link is broken. How can I login?'],
  ['Refund request', 'I would like to request a refund. What should I do next?'],
  ['Product feedback', 'I have feedback: please improve the search workflow for the product team.'],
];

export default function App() {
  const [text, setText] = useState('');
  const [useReferences, setUseReferences] = useState(true);
  const [accessCode, setAccessCode] = useState('');
  const [website, setWebsite] = useState('');
  const [health, setHealth] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState('brief');
  const pending = useRef(null);
  const resultHeading = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch('/health', { signal: controller.signal })
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(setHealth)
      .catch(e => { if (e.name !== 'AbortError') setError('Cannot reach the service. Check the server and reload.'); });
    return () => controller.abort();
  }, []);

  function changeInput(value) {
    setText(value);
    setResult(null);
    setError('');
  }

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    const fingerprint = JSON.stringify([text.trim(), useReferences]);
    if (!pending.current || pending.current.fingerprint !== fingerprint) {
      pending.current = { fingerprint, id: crypto.randomUUID() };
    }
    setBusy(true);
    setError('');
    setResult(null);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 210000);
    try {
      const response = await fetch('/api/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(accessCode ? { Authorization: `Bearer ${accessCode}` } : {}) },
        body: JSON.stringify({ request_id: pending.current.id, text: text.trim(), use_references: useReferences, website }),
        signal: controller.signal,
      });
      let data;
      try {
        data = await response.json();
      } catch {
        if (controller.signal.aborted) throw new DOMException('Aborted', 'AbortError');
        throw new Error('The service returned an unreadable response. It may be temporarily unavailable. Please retry shortly.');
      }
      if (!data || typeof data !== 'object') throw new Error('The service returned an unexpected result. Please retry shortly.');
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'The request could not be processed.');
      if (!data.brief || !Array.isArray(data.citations)) throw new Error('The service returned an unexpected result.');
      setResult(data);
      setTab('brief');
      requestAnimationFrame(() => resultHeading.current?.focus());
    } catch (e) {
      setError(e.name === 'AbortError' ? 'The request timed out. Retry to recover the same request safely.' : e.message || 'Connection failed. Retry with the same input.');
    } finally {
      clearTimeout(timeout);
      setBusy(false);
    }
  }

  function newRun() {
    pending.current = null;
    setResult(null);
    setError('');
  }

  return <div className="shell">
    <header className="topbar">
      <a className="brand" href="/" aria-label="Brief Studio home"><span className="brand-mark">b.</span> Brief Studio</a>
      <span className={`status ${health ? '' : 'pending'}`}><span className="status-dot" />{health ? (health.demo_mode ? 'Offline demo' : 'Live workspace') : 'Connecting…'}</span>
    </header>
    <main>
      <div className="intro"><p className="eyebrow">ONE INPUT. A CLEARER NEXT STEP.</p><h1>From a request<br />to a useful brief.</h1><p>Summarize, categorize, and find the next steps.<br className="desktop-break" /> Keep reference evidence close and a person in the loop.</p></div>
      {health?.demo_mode && <div className="demo-banner"><span className="tiny-icon">↳</span><p><strong>You’re in demo mode.</strong> Try a sample to explore the workflow. Results use a template; no external API is called.</p></div>}
      <div className="workspace">
        <section className="panel input-panel" aria-labelledby="input-title">
          <div className="panel-heading"><span className="step">01</span><h2 id="input-title">Your input</h2><span className="panel-meta">Text → structure</span></div>
          <form onSubmit={submit}>
            <label htmlFor="request-text">What would you like to process?</label>
            <textarea id="request-text" value={text} onChange={e => changeInput(e.target.value)} minLength={3} maxLength={8000} required disabled={busy} placeholder="Paste a request, question, or piece of feedback…" />
            <div className="field-footer"><span>Use fictional data when trying the demo.</span><span>{text.length.toLocaleString()} / 8,000</span></div>
            <div className="samples"><span>TRY A SAMPLE</span><div>{EXAMPLES.map(([name, value]) => <button key={name} type="button" className="sample" disabled={busy} onClick={() => changeInput(value)}>{name} <span aria-hidden="true">↗</span></button>)}</div></div>
            <label className="reference-option"><input type="checkbox" checked={useReferences} disabled={busy} onChange={e => { setUseReferences(e.target.checked); setResult(null); }} /><span><strong>Use reference documents</strong><small>Look for supporting excerpts in the local collection.</small></span><span className="document-icon" aria-hidden="true">▤</span></label>
            {health?.access_code_required && <div className="access-field"><label htmlFor="access-code">Workspace access code</label><input id="access-code" type="password" autoComplete="off" value={accessCode} onChange={e => setAccessCode(e.target.value)} disabled={busy} required /><small>Provided by your workspace owner. Kept only in this page’s memory.</small></div>}
            <div className="honeypot" aria-hidden="true"><label htmlFor="website">Website</label><input id="website" value={website} onChange={e => setWebsite(e.target.value)} tabIndex={-1} autoComplete="off" /></div>
            {error && <p className="error" role="alert">{error}</p>}
            <button className="primary" disabled={busy || text.trim().length < 3 || !health}>{busy ? 'Preparing your brief…' : 'Generate brief'} <span aria-hidden="true">→</span></button>
            <p className="privacy-note">Review every result before acting on it.</p>
          </form>
        </section>
        <section className="panel output-panel" aria-labelledby="result-title" aria-busy={busy}>
          <div className="panel-heading"><span className="step">02</span><h2 id="result-title" ref={resultHeading} tabIndex={-1}>Structured result</h2>{result && <span className="result-badges"><span className="result-provider" aria-label={`AI provider: ${PROVIDER_LABELS[result.provider] || 'Unknown'}`}>{PROVIDER_LABELS[result.provider] || 'Unknown'}</span><span className={`result-mode ${result.mode}`}>{result.mode}</span></span>}</div>
          {!result ? <div className="empty" role="status"><div className={`empty-art ${busy ? 'working' : ''}`} aria-hidden="true"><span>≡</span><i>✓</i></div><h3>{busy ? 'Finding the useful parts…' : 'A little structure goes a long way.'}</h3><p>{busy ? 'Your request is being processed. Keep this page open.' : 'Add your input and generate a brief. Your summary, next steps, and reference evidence will appear here.'}</p><div className="output-tags"><span>Summary</span><span>Next steps</span><span>Sources</span></div></div> : <div className="result-content">
            <div className="tabs" role="group" aria-label="Result view"><button type="button" aria-pressed={tab === 'brief'} onClick={() => setTab('brief')}>Brief</button><button type="button" aria-pressed={tab === 'json'} onClick={() => setTab('json')}>JSON</button></div>
            {result.warning && <p className="warning" role="status">{result.warning}</p>}
            {tab === 'json' ? <pre className="json-output">{JSON.stringify(result, null, 2)}</pre> : <>
              <div className="result-labels"><span className="category">{result.brief.category}</span><span>Human review required</span></div>
              <h3>Summary</h3><p className="summary">{result.brief.summary}</p>
              <h3>Suggested next steps</h3><ol className="next-steps">{result.brief.next_steps.map((step, index) => <li key={index}>{step}</li>)}</ol>
              <div className="evidence"><h3>{result.mode === 'demo' ? 'Retrieved demo excerpts' : 'Reference evidence'} <span>{result.citations.length}</span></h3>{result.citations.length ? result.citations.map(source => <details key={source.source_id}><summary>{source.document}</summary><blockquote>{source.excerpt}</blockquote><small>{source.source_id}</small></details>) : <p>No reference was cited. Verify any policy details manually.</p>}</div>
            </>}
            <button type="button" className="text-button" onClick={newRun}>Start a new run <span aria-hidden="true">↗</span></button>
          </div>}
        </section>
      </div>
      <footer><span>Small workflow. Clear outputs.</span><span>Input → optional references → structured brief</span></footer>
    </main>
  </div>;
}
