import React, { useEffect, useState } from 'react';
import { AppShell } from '../components/AppShell';
import { PageHeader } from '../components/PageHeader';
import { DataModules } from '../components/DataModules';
import { Loading, ErrorBox, EmptyBox } from '../components/States';
import { Badge } from '../components/StatusBadge';
import { SearchBox, Pager } from '../components/Table';
import { Icon } from '../icons';
import { api } from '../api';
import { useAsync, go, formatTs } from '../lib/app';

export function Recipients() {
  const [q, setQ] = useState('');
  const { data, loading, error, reload } = useAsync(() => api.recipients.list(), []);
  const all = data?.items || [];
  const rows = all.filter(
    (r) =>
      r.name.toLowerCase().includes(q.toLowerCase()) ||
      r.recipient_id.toLowerCase().includes(q.toLowerCase()) ||
      (r.organization && r.organization.toLowerCase().includes(q.toLowerCase()))
  );
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
    if ((!selectedId || !rows.some((r) => r.recipient_id === selectedId)) && rows.length) {
      setSelectedId(rows[0].recipient_id);
    }
  }, [rows, selectedId]);

  const selected = rows.find((r) => r.recipient_id === selectedId);
  const activeCount = all.filter((r) => r.status === 'Active').length;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Identities"
        title="Authorized Recipients"
        description="Officer identities, organization units, and post-quantum cryptographic keys for secure decryption."
        action={
          <button className="primary" onClick={() => go('add-recipient')} type="button">
            <Icon name="userPlus" size={14} />
            Add Recipient
          </button>
        }
      />

      {loading && <Loading label="Loading recipient directory…" />}
      {error && <ErrorBox message={error} onRetry={reload} />}

      {!loading && !error && (
        <>
          <DataModules
            items={[
              { value: all.length, label: 'Total Recipients', description: 'Registered identities', icon: 'users' },
              { value: activeCount, label: 'Active Recipients', description: 'Authorized access', tone: 'success', icon: 'shieldCheck' },
              { value: all.length - activeCount, label: 'Revoked / Inactive', description: 'Keys invalidated', tone: all.length - activeCount > 0 ? 'danger' : undefined, icon: 'banOff' },
              { value: all.length, label: 'PQC Key Pairs', description: 'ML-KEM-768 / ML-DSA-65', tone: 'success', icon: 'key' },
            ]}
          />

          <div className="split-list">
            <section>
              <SearchBox value={q} onChange={setQ} placeholder="Search by name, officer ID, or unit…" />
              {rows.length === 0 ? (
                <EmptyBox message="No recipients match your search. Add a new recipient to register cryptographic keys." />
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Name</th>
                        <th>Recipient ID</th>
                        <th>Organization / Role</th>
                        <th>Status</th>
                        <th>Registered</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r, i) => (
                        <tr
                          key={r.recipient_id}
                          className={r.recipient_id === selectedId ? 'selected-row' : ''}
                          onClick={() => setSelectedId(r.recipient_id)}
                          style={{
                            background: r.recipient_id === selectedId ? 'rgba(20, 119, 255, 0.12)' : undefined,
                          }}
                        >
                          <td>{i + 1}</td>
                          <td style={{ color: '#fff', fontWeight: 500 }}>{r.name}</td>
                          <td className="link">{r.recipient_id}</td>
                          <td>
                            {r.organization}
                            {r.role ? ` · ${r.role}` : ''}
                          </td>
                          <td>
                            <Badge type={r.status === 'Active' ? 'success' : 'danger'}>
                              {r.status}
                            </Badge>
                          </td>
                          <td>{formatTs(r.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <Pager shown={rows.length} total={all.length} noun="recipients" />
            </section>

            {selected ? (
              <RecipientDetail recipient={selected} onChanged={reload} />
            ) : (
              <div className="detail">
                <EmptyBox message="Select an officer identity to view cryptographic details." />
              </div>
            )}
          </div>
        </>
      )}
    </AppShell>
  );
}

function RecipientDetail({ recipient, onChanged }) {
  const { data: settings } = useAsync(() => api.system.settings(), []);
  const [revoking, setRevoking] = useState(false);
  const [revokeError, setRevokeError] = useState(null);

  const handleRevoke = async () => {
    if (!window.confirm(`Are you sure you want to revoke recipient ${recipient.recipient_id}?`)) return;
    setRevoking(true);
    setRevokeError(null);
    try {
      await api.recipients.revoke(recipient.recipient_id);
      onChanged && onChanged();
    } catch (e) {
      setRevokeError(e.message);
    } finally {
      setRevoking(false);
    }
  };

  const kemAlgo = settings?.cryptographic_algorithms?.key_encapsulation || 'ML-KEM-768';
  const sigAlgo = settings?.cryptographic_algorithms?.digital_signature || 'ML-DSA-65';

  return (
    <aside className="detail">
      <div className="detail-title">
        <div className="officer-avatar-sm" style={{ width: 38, height: 38, fontSize: 13 }}>
          <Icon name="user" size={18} />
        </div>
        <div>
          <h3>
            {recipient.name}{' '}
            <Badge type={recipient.status === 'Active' ? 'success' : 'danger'}>
              {recipient.status}
            </Badge>
          </h3>
          <small className="mono">{recipient.recipient_id}</small>
        </div>
      </div>

      <div className="kv">
        <b>Organization</b>
        <span>{recipient.organization || '—'}</span>
        <b>Department</b>
        <span>{recipient.department || '—'}</span>
        <b>Role / Designation</b>
        <span>{recipient.role || 'Officer'}</span>
        <b>Registered On</b>
        <span>{formatTs(recipient.created_at)}</span>
        <b>Key Status</b>
        <span><Badge type="success">{recipient.key_status || 'Active'}</Badge></span>
      </div>

      <div className="subcard">
        <h4>Cryptographic Credentials</h4>
        <p>Key Encapsulation (KEM) <strong>{kemAlgo}</strong></p>
        <p>Digital Signature <strong>{sigAlgo}</strong></p>
        <p>Key Storage <strong>Air-Gapped Local Vault</strong></p>
      </div>

      {revokeError && (
        <div className="state-box error" style={{ marginTop: 12 }}>
          <Icon name="alert" size={14} />
          <span>{revokeError}</span>
        </div>
      )}

      <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <button className="primary wide" onClick={() => go('documents')} type="button">
          <Icon name="documents" size={13} /> View Associated Documents
        </button>

        <button className="outline wide" onClick={() => go('events')} type="button">
          <Icon name="events" size={13} /> View Decryption Logs
        </button>

        {recipient.status === 'Active' && (
          <button
            className="outline wide"
            disabled={revoking}
            onClick={handleRevoke}
            type="button"
            style={{ color: 'var(--red)', borderColor: 'var(--red-border)', marginTop: 4 }}
          >
            <Icon name="banOff" size={13} />
            {revoking ? 'Revoking Access…' : 'Revoke Recipient Access'}
          </button>
        )}
      </div>
    </aside>
  );
}

export default Recipients;
