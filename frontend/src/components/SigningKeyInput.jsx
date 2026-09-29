import React, { useState } from 'react';
import { session } from '../lib/app';

// Lets the recipient load THEIR ML-DSA-65 signing private key (the *.sig.private file from
// their offline USB) for this session. The server never stores it; we keep it in memory only.
export function SigningKeyInput({ onChange }) {
  const [loaded, setLoaded] = useState(!!session.signingKey);
  const [paste, setPaste] = useState('');

  const set = (text) => {
    session.signingKey = text && text.trim() ? text : null;
    setLoaded(!!session.signingKey);
    onChange && onChange(session.signingKey);
  };
  const onFile = (e) => {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    const r = new FileReader();
    r.onload = () => set(String(r.result || ''));
    r.readAsText(f);
  };

  return (
    <div className="subcard" style={{ margin: '0 0 12px' }}>
      <h4>Your signing key (required)</h4>
      <small style={{ display: 'block', marginBottom: 8, color: 'var(--text-muted)' }}>
        Load the <b>.sig.private</b> file from your offline media. It is used in memory to sign this
        action and is never stored by the server.
      </small>
      <input type="file" onChange={onFile} />
      <textarea
        rows={2}
        placeholder="…or paste the base64 key"
        value={paste}
        onChange={(e) => { setPaste(e.target.value); set(e.target.value); }}
        style={{ width: '100%', marginTop: 6, fontFamily: 'var(--font-mono)', fontSize: 11 }}
      />
      <small style={{ color: loaded ? 'var(--green)' : 'var(--amber)' }}>
        {loaded ? 'Signing key loaded for this session' : 'No signing key loaded'}
      </small>
      {loaded && (
        <button type="button" className="ghost-btn small" style={{ marginLeft: 8 }}
          onClick={() => { setPaste(''); set(''); }}>Clear</button>
      )}
    </div>
  );
}
