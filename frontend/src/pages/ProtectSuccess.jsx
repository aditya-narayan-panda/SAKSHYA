import React from 'react';
import { AppShell } from '../components/AppShell';
import { PageHeader } from '../components/PageHeader';
import { SectionHead } from '../components/SectionPanel';
import { EmptyBox } from '../components/States';
import { Badge } from '../components/StatusBadge';
import { Icon } from '../icons';
import { go, session, shortHash } from '../lib/app';

export function ProtectSuccess() {
  const result = session.lastProtect;

  if (!result) {
    return (
      <AppShell>
        <PageHeader eyebrow="Document Operations" title="Document Protection Result" />
        <EmptyBox message="No recent protection operation found in session." />
        <button className="primary" style={{ marginTop: 16 }} onClick={() => go('protect')} type="button">
          <Icon name="protect" size={14} /> Protect Document
        </button>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Document Operations"
        title="Document Protected Successfully"
        description="The document has been encrypted with AES-256-GCM and encapsulated for authorized recipients with ML-KEM-768."
      />

      <div className="stepper" style={{ borderColor: 'var(--green-border)', background: 'rgba(22, 214, 138, 0.06)' }}>
        <span style={{ background: 'var(--green)', color: '#FFFFFF' }}><Icon name="check" size={12} /></span>
        <span style={{ color: 'var(--green)' }}>Document Intake</span>
        <i><Icon name="chevronRight" size={12} /></i>
        <span style={{ background: 'var(--green)', color: '#FFFFFF' }}><Icon name="check" size={12} /></span>
        <span style={{ color: 'var(--green)' }}>Encryption Complete</span>
        <i><Icon name="chevronRight" size={12} /></i>
        <span style={{ background: 'var(--green)', color: '#FFFFFF' }}><Icon name="check" size={12} /></span>
        <span style={{ color: 'var(--green)' }}>Recipients Assigned</span>
        <i><Icon name="chevronRight" size={12} /></i>
        <b style={{ background: 'var(--blue)' }}><Icon name="protect" size={12} /></b>
        <b style={{ color: '#fff' }}>Protected &amp; Ready</b>
      </div>

      <div className="success-grid">
        <section>
          <div className="panel" style={{ marginBottom: 20 }}>
            <div className="doc-preview large">
              <span className="fileicon">{(result.filename.split('.').pop() || 'DOC').toUpperCase()}</span>
              <div>
                <b style={{ fontSize: 16 }}>{result.filename}</b>
                <small>{(result.fileMeta?.size / 1024).toFixed(0)} KB · Encrypted Payload</small>
              </div>
            </div>

            <div className="kv">
              <b>Document ID</b>
              <span className="mono link">{result.document_id}</span>
              <b>Payload Filename</b>
              <span>{result.filename}</span>
              <b>Encrypted Size</b>
              <span>{(result.fileMeta?.size / 1024).toFixed(0)} KB</span>
              <b>Integrity Hash (SHA-256)</b>
              <span className="mono">{shortHash(result.sha256_hash, 16, 6)}</span>
            </div>
          </div>

          <div className="panel">
            <SectionHead title="Protection Summary" sub="Cryptographic parameters and operational posture." />
            <div className="crypto-grid" style={{ marginBottom: 16 }}>
              <div className="crypto">
                <Icon name="users" size={16} />
                <b>Authorized Recipients</b>
                <strong>{result.recipients} Officers</strong>
                <small>Separate key encapsulations</small>
              </div>
              <div className="crypto">
                <Icon name="protect" size={16} />
                <b>Encryption Cipher</b>
                <strong>{result.encryption}</strong>
                <small>Authenticated payload security</small>
              </div>
              <div className="crypto">
                <Icon name="key" size={16} />
                <b>KEM Protocol</b>
                <strong>{result.key_encapsulation}</strong>
                <small>Post-quantum lattice exchange</small>
              </div>
              <div className="crypto">
                <Icon name="hash" size={16} />
                <b>Integrity Standard</b>
                <strong>{result.integrity}</strong>
                <small>Tamper-evident verification</small>
              </div>
            </div>

            <div className="success-note big">
              <Icon name="shieldCheck" size={20} style={{ color: 'var(--green)', flexShrink: 0 }} />
              <div>
                <b>Document is now locked and ready for distribution.</b>
                <p style={{ margin: '4px 0 0', color: 'var(--text-secondary)', fontSize: 12 }}>
                  Only the assigned recipients can decrypt this file. Each authorized decryption is uniquely watermarked,
                  signed by the officer's key pair, and permanently committed to the immutable ledger.
                </p>
              </div>
            </div>

            <div className="button-row" style={{ marginTop: 20 }}>
              <button className="primary" onClick={() => go('documents')} type="button">
                <Icon name="documents" size={14} /> View in Documents
              </button>
              <button className="outline" onClick={() => go('protect')} type="button">
                <Icon name="plus" size={14} /> Protect Another Document
              </button>
              <button className="outline" onClick={() => go('dashboard')} type="button">
                <Icon name="dashboard" size={14} /> Return to Console
              </button>
            </div>
          </div>
        </section>

        <aside>
          <div className="panel" style={{ marginBottom: 20 }}>
            <div className="panel-head">
              <h3>Authorized Officers</h3>
              <button className="ghost-btn small" onClick={() => go('recipients')} type="button">
                View All →
              </button>
            </div>

            {(result.recipientDetails || []).map((r) => (
              <div
                key={r.recipient_id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 10px',
                  background: 'rgba(2, 8, 18, 0.5)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  marginBottom: 8,
                }}
              >
                <div>
                  <b style={{ color: '#fff', fontSize: 12.5, display: 'block' }}>{r.name}</b>
                  <small style={{ color: 'var(--cyan)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                    {r.recipient_id}
                  </small>
                </div>
                <small style={{ color: 'var(--text-muted)', fontSize: 11 }}>{r.organization}</small>
              </div>
            ))}
          </div>

          <div className="panel">
            <div className="panel-head">
              <h3>Operational Posture</h3>
              <Badge type="success">PROTECTED</Badge>
            </div>
            {[
              'Document encrypted and payload sealed',
              'Per-recipient ML-KEM-768 key capsules generated',
              'Document integrity fingerprint computed',
              'Ready for authorized recipient decryption',
            ].map((msg) => (
              <p
                key={msg}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  fontSize: 12,
                  color: 'var(--text-secondary)',
                  margin: '8px 0',
                }}
              >
                <Icon name="check" size={13} style={{ color: 'var(--green)', flexShrink: 0 }} />
                {msg}
              </p>
            ))}
          </div>
        </aside>
      </div>
    </AppShell>
  );
}

export default ProtectSuccess;
