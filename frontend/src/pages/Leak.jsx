import React, { useState } from 'react';
import { AppShell } from '../components/AppShell';
import { PageHeader } from '../components/PageHeader';
import { SectionHead } from '../components/SectionPanel';
import { Loading, EmptyBox } from '../components/States';
import { Badge } from '../components/StatusBadge';
import { EvidenceChain } from '../components/EvidenceChain';
import { Icon } from '../icons';
import { api } from '../api';
import { useAsync, go, session, formatTs, shortHash } from '../lib/app';

export function Leak() {
  const [file, setFile] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState(null);
  const [err, setErr] = useState(null);
  const { data, loading, reload } = useAsync(() => api.investigations.list(), []);
  const previous = data?.items || [];

  const start = async () => {
    if (!file) {
      setErr('Please choose a leaked document to analyze.');
      return;
    }
    setAnalyzing(true);
    setErr(null);
    setResult(null);
    try {
      const res = await api.investigations.create(file);
      setResult(res);
      session.lastInvestigation = res.investigation_id;
      reload();
    } catch (e) {
      setErr(e.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const chainSteps = [
    { label: 'Leaked document payload received', state: file ? 'done' : 'pending' },
    {
      label: 'Forensic watermark extracted',
      state: result?.watermark_id ? 'done' : result ? 'failed' : analyzing ? 'active' : 'pending',
      detail: result?.watermark_id,
    },
    {
      label: 'Authorized recipient identified',
      state: result?.matched_event_id ? 'done' : result ? 'failed' : 'pending',
      detail: result?.matched_recipient_id,
    },
    {
      label: 'ML-DSA-65 digital signature verified',
      state: result?.signature_valid ? 'done' : result ? 'failed' : 'pending',
    },
    {
      label: 'Immutable ledger block verified',
      state: result?.ledger_verified ? 'done' : result ? 'failed' : 'pending',
    },
    {
      label: 'Cryptographic provenance confirmed',
      state: result?.status === 'IDENTIFIED' ? 'done' : result ? 'failed' : 'pending',
    },
  ];

  return (
    <AppShell>
      <PageHeader
        eyebrow="Provenance"
        title="Leak Investigation"
        description="Extract embedded forensic watermarks, verify ML-DSA signatures, and attribute leaked copies to the authorized recipient via the immutable ledger."
      />

      <div className="leak-grid">
        <section>
          {/* Step 1: Upload Leaked File */}
          <div className="panel" style={{ marginBottom: 20 }}>
            <SectionHead
              n={1}
              title="Upload Suspected Leaked Document"
              sub="Upload intercepted document, PDF export, or forensic image scan."
            />
            <label className="dropzone">
              <input type="file" onChange={(e) => setFile(e.target.files[0])} />
              <Icon name="investigate" size={26} style={{ color: 'var(--cyan)' }} />
              <b>{file ? file.name : 'Drag and drop leaked document for forensic intake'}</b>
              <small>or browse local evidence directory</small>
              <button type="button" className="primary" style={{ marginTop: 6, pointerEvents: 'none' }}>
                Select Evidence File
              </button>
              <small>Supported formats: PDF (full dual-channel watermark), DOCX (metadata-only)</small>
            </label>

            {err && (
              <div className="state-box error" style={{ marginTop: 12 }}>
                <Icon name="alert" size={14} />
                <span>{err}</span>
              </div>
            )}

            <button
              className="primary wide lg"
              disabled={analyzing || !file}
              onClick={start}
              type="button"
              style={{ marginTop: 14 }}
            >
              <Icon name="investigate" size={15} />
              {analyzing ? 'Extracting Watermarks & Verifying Ledger…' : 'Start Forensic Investigation'}
            </button>
          </div>

          {/* Evidence Chain */}
          <div className="panel" style={{ marginBottom: 20 }}>
            <SectionHead
              title="Forensic Evidence Pipeline"
              sub="Six-stage automated verification chain against immutable ledger."
            />
            <EvidenceChain steps={chainSteps} />
          </div>

          {/* Previous Investigations */}
          <div className="panel">
            <div className="panel-head">
              <h3>Investigation Case Records</h3>
              <button className="ghost-btn small" onClick={() => go('reports')} type="button">
                Forensic Reports →
              </button>
            </div>

            {loading ? (
              <Loading label="Loading investigation archives…" />
            ) : previous.length === 0 ? (
              <EmptyBox message="No previous leak investigations recorded in current session." />
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Filename</th>
                      <th>Attributed Officer</th>
                      <th>Event ID</th>
                      <th>Timestamp</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {previous.map((r) => (
                      <tr key={r.investigation_id}>
                        <td style={{ color: '#fff' }}>{r.uploaded_filename}</td>
                        <td className="mono link">{r.matched_recipient_id || '—'}</td>
                        <td className="link">{r.matched_event_id || '—'}</td>
                        <td>{formatTs(r.created_at)}</td>
                        <td>
                          <Badge type={r.status === 'IDENTIFIED' ? 'success' : 'danger'}>
                            {r.status}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>

        {/* Aside: Attribution Result */}
        <aside className="panel attribution" style={{ height: 'fit-content' }}>
          <SectionHead n={2} title="Attribution Finding" sub="Verified digital provenance output." />

          {!result && (
            <EmptyBox message="Upload and analyze a leaked document to view attributable officer identity and evidence trail." />
          )}

          {result && result.status === 'IDENTIFIED' && (
            <>
              <div className="result-banner">
                <Icon name="shieldCheck" size={24} style={{ color: 'var(--green)', flexShrink: 0 }} />
                <div>
                  <h3>Attribution Cryptographically Proven</h3>
                  <p>
                    The document copy matches an authorized recipient's decryption record.
                    All digital signatures and ledger hashes match 100%.
                  </p>
                </div>
              </div>

              <div className="recipient-result">
                <div className="avatar">
                  <Icon name="user" size={20} />
                </div>
                <div>
                  <small>Attributed Officer</small>
                  <h2>{result.matched_recipient_id}</h2>
                  <span>Origin Document: {result.matched_document_id}</span>
                </div>
              </div>

              <div className="subcard">
                <h4>Forensic Verification Facts</h4>
                <p>Payload Hash <strong className="mono">{shortHash(result.document_hash, 14, 0)}</strong></p>
                <p>Extracted Watermark <strong className="mono">{result.watermark_id}</strong></p>
                <p>Decryption Event <strong className="link">{result.matched_event_id}</strong></p>
                <p>
                  ML-DSA Signature{' '}
                  <Badge type={result.signature_valid ? 'success' : 'danger'}>
                    {result.signature_valid ? 'VALID' : 'INVALID'}
                  </Badge>
                </p>
                <p>
                  Ledger Verification{' '}
                  <Badge type={result.ledger_verified ? 'success' : 'danger'}>
                    {result.ledger_verified ? 'VERIFIED' : 'FAILED'}
                  </Badge>
                </p>
              </div>

              <div className="button-row" style={{ marginTop: 16 }}>
                <button className="primary" onClick={() => go('reports')} type="button" style={{ flex: 1 }}>
                  <Icon name="reports" size={13} /> Generate PDF Report
                </button>
                <button className="outline" onClick={() => go('ledger')} type="button" style={{ flex: 1 }}>
                  <Icon name="ledger" size={13} /> Inspect Ledger Block
                </button>
              </div>
            </>
          )}

          {result && result.status !== 'IDENTIFIED' && (
            <div className="result-banner" style={{ background: 'var(--red-bg)', borderColor: 'var(--red-border)' }}>
              <Icon name="fileWarning" size={24} style={{ color: 'var(--red)', flexShrink: 0 }} />
              <div>
                <h3 style={{ color: 'var(--red)' }}>
                  {result.status === 'UNATTRIBUTED' ? 'No Decryption Event Match' : 'Attribution Unconfirmed'}
                </h3>
                <p style={{ color: '#ffb3ba' }}>
                  {result.watermark_id
                    ? 'A watermark was detected but signature verification or ledger quorum did not pass.'
                    : 'No forensic watermark was found. This copy was either never processed through SAKSHYA or watermarks were completely stripped.'}
                </p>
              </div>
            </div>
          )}
        </aside>
      </div>
    </AppShell>
  );
}

export default Leak;
