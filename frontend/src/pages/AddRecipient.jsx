import React, { useState } from 'react';
import { AppShell } from '../components/AppShell';
import { PageHeader } from '../components/PageHeader';
import { SectionHead } from '../components/SectionPanel';
import { Badge } from '../components/StatusBadge';
import { Icon } from '../icons';
import { api } from '../api';
import { go } from '../lib/app';

function downloadTextFile(filename, text) {
  const url = URL.createObjectURL(new Blob([text], { type: 'application/octet-stream' }));
  const a = document.createElement('a');
  a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function AddRecipient() {
  const [form, setForm] = useState({ name: '', organization: '', department: '', role: '', email: '', access_role: 'officer' });
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState(null);
  const [err, setErr] = useState(null);

  const update = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const handleGenerate = async () => {
    if (!form.name.trim()) {
      setErr('Officer/Recipient name is required.');
      return;
    }
    setCreating(true);
    setErr(null);
    try {
      const recipient = await api.recipients.create(form);
      setCreated(recipient);
    } catch (e) {
      setErr(e.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <AppShell>
      <PageHeader
        eyebrow="Identities"
        title="Add New Recipient"
        description="Provision an authorized officer identity and generate post-quantum cryptographic key pairs."
      />

      <div className="stepper">
        <b style={{ background: created ? 'var(--green)' : 'var(--blue)' }}>1</b>
        <span>Identity Details</span>
        <i><Icon name="chevronRight" size={12} /></i>
        <b style={{ background: created ? 'var(--green)' : 'var(--blue)' }}>2</b>
        <span>Key Generation</span>
        <i><Icon name="chevronRight" size={12} /></i>
        <span style={{ background: created ? 'var(--blue)' : undefined, color: created ? 'var(--text-inverse)' : undefined }}>3</span>
        <span>Credentials Issued</span>
      </div>

      <div className="add-grid">
        <section className="panel">
          <SectionHead n={1} title="Identity Specifications" sub="Enter authorized personnel identification." />

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 20 }}>
            <label>
              Recipient Full Name *
              <input
                value={form.name}
                onChange={(e) => update('name', e.target.value)}
                placeholder="e.g. Commander Vikram Rathore"
                disabled={!!created}
              />
            </label>

            <label>
              Organization / Command
              <input
                value={form.organization}
                onChange={(e) => update('organization', e.target.value)}
                placeholder="e.g. Naval Command HQ"
                disabled={!!created}
              />
            </label>

            <label>
              Department / Unit
              <input
                value={form.department}
                onChange={(e) => update('department', e.target.value)}
                placeholder="e.g. Maritime Strategic Intelligence"
                disabled={!!created}
              />
            </label>

            <label>
              Role / Designation
              <input
                value={form.role}
                onChange={(e) => update('role', e.target.value)}
                placeholder="e.g. Intelligence Analyst"
                disabled={!!created}
              />
            </label>

            <label style={{ gridColumn: 'span 2' }}>
              Access Role
              <select value={form.access_role} onChange={(e) => update('access_role', e.target.value)} disabled={!!created}>
                <option value="officer">Officer — protect, decrypt, view (holds a signing key)</option>
                <option value="auditor">Auditor — leak investigation &amp; reports only</option>
              </select>
            </label>

            <label style={{ gridColumn: 'span 2' }}>
              Secure Contact Channel (Optional)
              <input
                value={form.email}
                onChange={(e) => update('email', e.target.value)}
                placeholder="v.rathore@navy.gov.in (classified local intranet)"
                disabled={!!created}
              />
            </label>
          </div>

          <SectionHead n={2} title="Post-Quantum Key Pair Generation" sub="Generates lattice-based key exchange and signature keys." />

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 16 }}>
            <div className="crypto">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                <Icon name="key" size={16} style={{ color: 'var(--cyan)' }} />
                <Badge type={created ? 'success' : 'neutral'}>{created ? 'GENERATED' : 'READY'}</Badge>
              </div>
              <b>Key Encapsulation Mechanism</b>
              <strong>ML-KEM-768</strong>
              <small>NIST FIPS 203 Lattice Standard</small>
            </div>

            <div className="crypto">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                <Icon name="signature" size={16} style={{ color: 'var(--cyan)' }} />
                <Badge type={created ? 'success' : 'neutral'}>{created ? 'GENERATED' : 'READY'}</Badge>
              </div>
              <b>Digital Signature Algorithm</b>
              <strong>ML-DSA-65</strong>
              <small>NIST FIPS 204 Lattice Standard</small>
            </div>
          </div>

          {err && (
            <div className="state-box error" style={{ marginBottom: 16 }}>
              <Icon name="alert" size={14} />
              <span>{err}</span>
            </div>
          )}

          {!created && (
            <button
              className="primary wide lg"
              disabled={creating || !form.name.trim()}
              onClick={handleGenerate}
              type="button"
            >
              <Icon name="key" size={15} />
              {creating ? 'Generating Quantum-Safe Keys…' : 'Generate Keys & Provision Identity'}
            </button>
          )}

          {created && (
            <div className="success-note big" style={{ flexDirection: 'column', alignItems: 'flex-start', marginTop: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Icon name="shieldCheck" size={18} style={{ color: 'var(--green)' }} />
                <b>Identity Provisioned Successfully — {created.recipient_id}</b>
              </div>
              <small>
                ML-KEM-768 and ML-DSA-65 key pairs generated in local air-gapped secure enclave. Signing private key is exported once to the recipient and never stored by the server.
              </small>

              {created.key_bundle && (
                <div className="subcard" style={{ width: '100%', marginTop: 14 }}>
                  <h4 style={{ color: 'var(--red)' }}>Private Keys — One-Time Download</h4>
                  <small style={{ display: 'block', color: 'var(--text-muted)', margin: '6px 0 10px' }}>
                    The server does <b>not</b> keep the signing key. Save both files to offline media (USB) now — they
                    cannot be shown again. You will load the .sig.private file at every decrypt.
                  </small>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button type="button" className="primary" onClick={() => downloadTextFile(created.key_bundle.sig_filename, created.key_bundle.sig_private_file)}>
                      <Icon name="key" size={13} /> {created.key_bundle.sig_filename}
                    </button>
                    <button type="button" className="ghost-btn" onClick={() => downloadTextFile(created.key_bundle.kem_filename, created.key_bundle.kem_private_file)}>
                      <Icon name="key" size={13} /> {created.key_bundle.kem_filename}
                    </button>
                  </div>
                </div>
              )}

              {created.initial_password && (
                <div className="subcard" style={{ width: '100%', marginTop: 14 }}>
                  <h4 style={{ color: 'var(--amber)' }}>Initial Workstation Credentials — Shown Once</h4>
                  <div className="kv" style={{ margin: '8px 0 0' }}>
                    <b>Officer ID</b>
                    <span className="mono link">{created.recipient_id}</span>
                    <b>Initial Password</b>
                    <span className="mono" style={{ color: 'var(--navy-dark)', fontSize: 13, background: 'var(--blue-light)', border: '1px solid var(--blue-border)', padding: '2px 8px', borderRadius: 4, fontWeight: 700 }}>
                      {created.initial_password}
                    </span>
                  </div>
                  <small style={{ color: 'var(--text-muted)', display: 'block', marginTop: 8, fontSize: 11.5 }}>
                    Securely transmit these credentials to {created.name}. For security, plaintext passwords are never stored.
                  </small>
                </div>
              )}
            </div>
          )}

          <div className="row-end">
            <button className="outline" onClick={() => go('recipients')} type="button">
              {created ? 'Return to Directory' : 'Cancel'}
            </button>
            {created && (
              <button className="primary" onClick={() => go('protect')} type="button">
                <Icon name="protect" size={13} /> Protect Document for {created.name}
              </button>
            )}
          </div>
        </section>

        <aside>
          <div className="panel" style={{ marginBottom: 20 }}>
            <h3 style={{ marginBottom: 14 }}>Cryptographic Standards</h3>
            <div className="subcard" style={{ marginTop: 0 }}>
              <h4>Key Exchange</h4>
              <p>Standard <strong>ML-KEM-768 (Kyber)</strong></p>
              <p>Security Level <strong>NIST Level 3 (AES-192 equivalent)</strong></p>
            </div>
            <div className="subcard">
              <h4>Digital Signatures</h4>
              <p>Standard <strong>ML-DSA-65 (Dilithium)</strong></p>
              <p>Security Level <strong>NIST Level 3</strong></p>
            </div>
          </div>

          <div className="panel">
            <h3 style={{ marginBottom: 14 }}>Identity Security Enforcements</h3>
            {[
              'Keys are generated locally inside isolated enclave',
              'Private keys are encrypted with master KEK and never exposed',
              'Public keys are registered for multi-party encapsulation',
              'All future decryption operations are signed and ledgered',
            ].map((rule) => (
              <p key={rule} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 12, color: 'var(--text-secondary)', margin: '8px 0' }}>
                <Icon name="check" size={13} style={{ color: 'var(--green)', marginTop: 2, flexShrink: 0 }} />
                {rule}
              </p>
            ))}
          </div>
        </aside>
      </div>
    </AppShell>
  );
}

export default AddRecipient;
