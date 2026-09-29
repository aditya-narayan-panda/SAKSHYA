import React, { useState } from 'react';
import { AppShell } from '../components/AppShell';
import { PageHeader } from '../components/PageHeader';
import { SectionHead } from '../components/SectionPanel';
import { Loading, ErrorBox, EmptyBox } from '../components/States';
import { Badge } from '../components/StatusBadge';
import { SearchBox } from '../components/Table';
import { Icon } from '../icons';
import { api } from '../api';
import { useAsync, go, session } from '../lib/app';

const CRYPTO_SPEC = [
  { icon: 'protect', title: 'Document Encryption', val: 'AES-256-GCM', desc: 'Hardware-accelerated authenticated symmetric encryption' },
  { icon: 'key', title: 'Key Encapsulation', val: 'ML-KEM-768', desc: 'Post-quantum lattice-based key exchange mechanism' },
  { icon: 'signature', title: 'Digital Signature', val: 'ML-DSA-65', desc: 'Generated at decryption time per recipient key pair' },
  { icon: 'hash', title: 'Integrity Hash', val: 'SHA-256', desc: 'Cryptographic hash for immutable tamper detection' },
];

export function Protect() {
  const [file, setFile] = useState(null);
  const { data, loading, error, reload } = useAsync(() => api.recipients.list(), []);
  const allRecipients = (data?.items || []).filter((r) => r.status === 'Active');
  const [q, setQ] = useState('');
  const filteredRecipients = allRecipients.filter(
    (r) => r.name.toLowerCase().includes(q.toLowerCase()) || r.recipient_id.toLowerCase().includes(q.toLowerCase()),
  );
  const [sel, setSel] = useState([]);
  const toggle = (id) => setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  const handleProtect = async () => {
    if (!file) { setSubmitError('Please choose a document to upload.'); return; }
    if (sel.length === 0) { setSubmitError('Select at least one authorized recipient.'); return; }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const result = await api.protection.protect(file, sel);
      session.lastProtect = {
        ...result,
        recipientDetails: sel.map((id) => allRecipients.find((r) => r.recipient_id === id)).filter(Boolean),
        fileMeta: { name: file.name, size: file.size },
      };
      go('protect-success');
    } catch (e) {
      setSubmitError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AppShell>
      <PageHeader
        eyebrow="Document Operations"
        title="Protect New Document"
        description="Encrypt documents and assign authorized recipient identities using post-quantum cryptography."
      />

      <div className="stepper">
        <b>1</b> Upload Document <i><Icon name="chevronRight" size={12} /></i>
        <span>2</span> Select Recipients <i><Icon name="chevronRight" size={12} /></i>
        <span>3</span> Configure Security <i><Icon name="chevronRight" size={12} /></i>
        <span>4</span> Review &amp; Protect
      </div>

      <div className="protect-grid">
        <section>
          {/* Step 1: Upload */}
          <div className="panel" style={{ marginBottom: 20 }}>
            <SectionHead n={1} title="Document Intake" sub="Select mission-critical document to protect and distribute." />
            <label className="dropzone">
              <input type="file" accept=".pdf,.docx" onChange={(e) => setFile(e.target.files[0])} />
              <Icon name="upload" size={26} style={{ color: 'var(--cyan)' }} />
              <b>{file ? file.name : 'Drag and drop document to secure intake'}</b>
              <small>or click to browse local filesystem</small>
              <button type="button" className="primary" style={{ marginTop: 6, pointerEvents: 'none' }}>
                Select File
              </button>
              <small>Supported formats: PDF (full watermark), DOCX (metadata-only) — TXT/XLSX cannot be protected (Max 25 MB)</small>
            </label>
            {file && (
              <div className="success-note" style={{ marginTop: 12 }}>
                <Icon name="check" size={14} />
                <span><b>{file.name}</b> ready for cryptographic encapsulation · {(file.size / 1024).toFixed(0)} KB</span>
              </div>
            )}
          </div>

          {/* Step 2: Recipients */}
          <div className="panel" style={{ marginBottom: 20 }}>
            <SectionHead n={2} title="Authorize Recipients" sub="Choose officer identities authorized to decrypt this document." />
            <SearchBox value={q} onChange={setQ} placeholder="Filter recipients by name or ID…" />

            {loading && <Loading label="Loading authorized recipients…" />}
            {error && <ErrorBox message={error} onRetry={reload} />}

            {!loading && !error && (
              filteredRecipients.length === 0 ? (
                <EmptyBox message="No active recipients found. Register an officer before protecting documents." />
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th style={{ width: 40 }}></th>
                        <th>Recipient ID</th>
                        <th>Name</th>
                        <th>Organization</th>
                        <th>Key Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredRecipients.slice(0, 8).map((r) => (
                        <tr
                          key={r.recipient_id}
                          onClick={() => toggle(r.recipient_id)}
                          style={{
                            background: sel.includes(r.recipient_id) ? 'rgba(20, 119, 255, 0.12)' : undefined,
                          }}
                        >
                          <td onClick={(e) => e.stopPropagation()}>
                            <input
                              type="checkbox"
                              checked={sel.includes(r.recipient_id)}
                              onChange={() => toggle(r.recipient_id)}
                              style={{ width: 16, height: 16, accentColor: 'var(--blue)' }}
                            />
                          </td>
                          <td className="link">{r.recipient_id}</td>
                          <td style={{ color: '#fff', fontWeight: 500 }}>{r.name}</td>
                          <td>{r.organization}</td>
                          <td><Badge type="success">{r.key_status}</Badge></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            )}

            <div className="row-end">
              <span style={{ fontSize: 12.5, color: 'var(--cyan)', fontFamily: 'var(--font-mono)' }}>
                {sel.length} recipient{sel.length === 1 ? '' : 's'} authorized
              </span>
              <button className="outline" onClick={() => go('add-recipient')} type="button">
                <Icon name="userPlus" size={13} /> Add New Recipient
              </button>
            </div>
          </div>

          {/* Step 3: Security config */}
          <div className="panel">
            <SectionHead n={3} title="Cryptographic Parameters" sub="Enforced defence-grade cryptographic standards." />
            <div className="crypto-grid">
              {CRYPTO_SPEC.map((x) => (
                <div className="crypto" key={x.title}>
                  <Icon name={x.icon} size={16} />
                  <b>{x.title}</b>
                  <strong>{x.val}</strong>
                  <small>{x.desc}</small>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Aside: Review Card */}
        <aside className="panel review" style={{ height: 'fit-content' }}>
          <SectionHead n={4} title="Review &amp; Enforce" sub="Confirm encapsulation parameters." />

          <div className="subcard">
            <h4>Document Payload</h4>
            <p>File Name <strong style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis' }}>{file?.name || 'No file selected'}</strong></p>
            <p>File Size <strong>{file ? `${(file.size / 1024).toFixed(0)} KB` : '—'}</strong></p>
          </div>

          <div className="subcard">
            <h4>Authorized Officers ({sel.length})</h4>
            {sel.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', margin: 0, borderBottom: 'none' }}>No recipients selected</p>
            ) : (
              sel.map((id) => {
                const r = allRecipients.find((x) => x.recipient_id === id);
                return (
                  <p key={id}>
                    <span className="mono link">{id}</span>
                    <strong style={{ color: '#fff' }}>{r?.name}</strong>
                  </p>
                );
              })
            )}
          </div>

          <div className="subcard">
            <h4>Security Enforcements</h4>
            <p>Encryption <strong>AES-256-GCM</strong></p>
            <p>Key Exchange <strong>ML-KEM-768</strong></p>
            <p>Integrity Hash <strong>SHA-256</strong></p>
            <p>Watermarking <strong>Imperceptible &amp; Visible</strong></p>
          </div>

          <div className="info-box">
            The document will be encapsulated and can only be decrypted by the authorized recipients. Each decryption
            will embed a unique forensic watermark, produce a digital signature, and record an immutable ledger event.
          </div>

          {submitError && (
            <div className="state-box error" style={{ margin: '10px 0' }}>
              <Icon name="alert" size={14} />
              <span>{submitError}</span>
            </div>
          )}

          <button
            className="primary wide lg"
            disabled={submitting || !file || sel.length === 0}
            onClick={handleProtect}
            type="button"
            style={{ marginTop: 12 }}
          >
            <Icon name="protect" size={15} />
            {submitting ? 'Encapsulating Document…' : 'Protect Document'}
          </button>
        </aside>
      </div>
    </AppShell>
  );
}

export default Protect;
