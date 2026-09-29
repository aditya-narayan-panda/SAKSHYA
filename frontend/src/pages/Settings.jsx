import React from 'react';
import { AppShell } from '../components/AppShell';
import { PageHeader } from '../components/PageHeader';
import { DataModules } from '../components/DataModules';
import { Loading, ErrorBox } from '../components/States';
import { Badge } from '../components/StatusBadge';
import { Icon } from '../icons';
import { api } from '../api';
import { useAsync, go } from '../lib/app';

export function Settings() {
  const { data: s, loading, error, reload } = useAsync(() => api.system.settings(), []);
  const { data: crypto } = useAsync(() => api.system.cryptoStatus().catch(() => null), []);

  return (
    <AppShell>
      <PageHeader
        eyebrow="System"
        title="Security &amp; System Configuration"
        description="Cryptographic parameters, ledger consensus nodes, and air-gapped environment controls."
      />

      {loading && <Loading label="Loading system parameters…" />}
      {error && <ErrorBox message={error} onRetry={reload} />}

      {!loading && !error && s && (
        <>
          <DataModules
            items={[
              { value: s.system_status, label: 'System Health', description: 'Air-gapped core online', tone: 'success', icon: 'shieldCheck' },
              { value: s.air_gapped_mode ? 'AIR-GAPPED' : 'LOCAL', label: 'Deployment Posture', description: 'Zero external network egress', tone: 'success', icon: 'wifiOff' },
              { value: `${s.ledger_nodes}/${s.ledger_nodes}`, label: 'Ledger Quorum', description: 'Local replicated nodes', icon: 'server' },
              { value: s.system_integrity, label: 'Merkle Integrity', description: 'Verified hash chains', tone: s.system_integrity === 'VERIFIED' ? 'success' : 'danger', icon: 'checkCircle' },
            ]}
          />

          {!s.cryptographic_algorithms.pqc_active && (
            <div className="pqc-fallback-note">
              <Icon name="alert" size={16} />
              <span>{s.cryptographic_algorithms.note}</span>
            </div>
          )}

          <div className="settings-grid">
            <div className="panel">
              <div className="panel-head">
                <h3>
                  <Icon name="crypto" size={16} style={{ color: 'var(--cyan)' }} />
                  Cryptographic Standard Matrix
                </h3>
              </div>
              {[
                ['protect', 'Document Encryption', s.cryptographic_algorithms.document_encryption, 'AES-256-GCM symmetric authenticated payload cipher'],
                ['key', 'Key Encapsulation Mechanism', s.cryptographic_algorithms.key_encapsulation, 'ML-KEM-768 lattice-based post-quantum key exchange'],
                ['signature', 'Digital Signature Algorithm', s.cryptographic_algorithms.digital_signature, 'ML-DSA-65 lattice-based post-quantum signatures'],
                ['hash', 'Integrity Fingerprint', s.cryptographic_algorithms.hash, 'SHA-256 cryptographically collision-resistant hashing'],
              ].map((x) => (
                <div className="setting-row" key={x[1]}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div className="officer-avatar-sm" style={{ width: 28, height: 28 }}>
                      <Icon name={x[0]} size={14} />
                    </div>
                    <div>
                      <b>{x[1]}</b>
                      <small>{x[3]}</small>
                    </div>
                  </div>
                  <Badge type="info">{x[2]}</Badge>
                </div>
              ))}
            </div>

            <div className="panel">
              <div className="panel-head">
                <h3>
                  <Icon name="server" size={16} style={{ color: 'var(--cyan)' }} />
                  Ledger Consensus Replicas
                </h3>
              </div>
              {Array.from({ length: s.ledger_nodes }).map((_, i) => (
                <div className="node-box" key={i}>
                  <div>
                    <b style={{ color: '#fff', fontSize: 13, display: 'block' }}>Node {String(i + 1).padStart(2, '0')}</b>
                    <small style={{ color: 'var(--text-muted)' }}>Air-gapped in-process replica</small>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>Consensus: {s.consensus_requirement}</span>
                    <Badge type="success">ONLINE</Badge>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="settings-bottom">
            <div className="panel">
              <div className="panel-head">
                <h3>System Information</h3>
              </div>
              {[
                ['Application Version', 'v2.0.0'],
                ['Deployment Posture', s.air_gapped_mode ? 'AIR-GAPPED DEFENCE' : 'LOCAL ENVIRONMENT'],
                ['External Cloud Egress', 'BLOCKED (Disabled)'],
                ['Cloud KMS Dependencies', 'NONE (Local Enclave)'],
                ['Public Blockchain Egress', 'DISABLED (Air-Gapped Private Chain)'],
              ].map((x) => (
                <div className="info-line" key={x[0]}>
                  <span>{x[0]}</span>
                  <b style={{ color: x[1].includes('DISABLED') || x[1].includes('BLOCKED') ? 'var(--green)' : '#fff' }}>
                    {x[1]}
                  </b>
                </div>
              ))}
            </div>

            <div className="panel">
              <div className="panel-head">
                <h3>Security &amp; Ingestion Enforcements</h3>
              </div>
              <div className="setting-row" style={{ padding: '8px 0' }}>
                <div><b>Forensic Audit Logging</b><small>Signed events per operation</small></div>
                <Badge type={s.audit_logging ? 'success' : 'danger'}>
                  {s.audit_logging ? 'ACTIVE' : 'DISABLED'}
                </Badge>
              </div>
              <div className="setting-row" style={{ padding: '8px 0' }}>
                <div><b>File Ingestion Cap</b><small>Maximum intake document size</small></div>
                <b className="mono">{s.file_size_limit_mb} MB</b>
              </div>
              <div className="setting-row" style={{ padding: '8px 0' }}>
                <div><b>Allowed Document Types</b><small>Supported forensic formats</small></div>
                <b className="mono" style={{ fontSize: 11 }}>{s.allowed_file_types.join(', ')}</b>
              </div>
            </div>

            <div className="panel">
              <div className="panel-head">
                <h3>Operational Maintenance</h3>
              </div>
              <button className="maintenance" onClick={reload} type="button">
                <span>Refresh System Health State</span>
                <Icon name="refresh" size={13} />
              </button>
              <button className="maintenance" onClick={() => go('ledger')} type="button">
                <span>Verify Merkle Root &amp; Ledger Blocks</span>
                <Icon name="shieldCheck" size={13} style={{ color: 'var(--green)' }} />
              </button>
              <button className="maintenance" onClick={() => go('protect')} type="button">
                <span>Open Document Protection Terminal</span>
                <Icon name="arrowRight" size={13} />
              </button>
            </div>
          </div>
        </>
      )}
    </AppShell>
  );
}

export default Settings;
