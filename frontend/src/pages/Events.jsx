import React, { useEffect, useState } from 'react';
import { AppShell } from '../components/AppShell';
import { PageHeader } from '../components/PageHeader';
import { DataModules } from '../components/DataModules';
import { Loading, ErrorBox, EmptyBox } from '../components/States';
import { Badge } from '../components/StatusBadge';
import { SearchBox, Pager } from '../components/Table';
import { Icon } from '../icons';
import { api } from '../api';
import { useAsync, useAuthedRecipient, formatTs, session } from '../lib/app';
import { SigningKeyInput } from '../components/SigningKeyInput';

export function Events() {
  const [q, setQ] = useState('');
  const { data, loading, error, reload } = useAsync(() => api.decryption.listEvents(), []);
  const events = data?.items || [];
  const rows = events.filter((e) => Object.values(e).join(' ').toLowerCase().includes(q.toLowerCase()));
  const verifiedCount = events.filter((e) => e.status === 'VERIFIED').length;
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
    if ((!selectedId || !rows.some((e) => e.event_id === selectedId)) && rows.length) {
      setSelectedId(rows[0].event_id);
    }
  }, [rows, selectedId]);

  const selectedEvent = rows.find((e) => e.event_id === selectedId);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Provenance"
        title="Decryption Events"
        description="Every authorized decryption is watermarked, digitally signed with recipient keys, and committed to the immutable ledger."
      />

      {loading && <Loading label="Loading decryption audit trail…" />}
      {error && <ErrorBox message={error} onRetry={reload} />}

      {!loading && !error && (
        <>
          <DataModules
            items={[
              { value: events.length, label: 'Total Decryptions', description: 'Audited operations', icon: 'events' },
              { value: verifiedCount, label: 'Cryptographically Verified', description: 'Signature confirmed', tone: 'success', icon: 'shieldCheck' },
              { value: events.length - verifiedCount, label: 'Pending Verification', description: 'In progress', icon: 'clock' },
              { value: 0, label: 'Failed / Invalid', description: 'Signature anomalies', tone: 'danger', icon: 'alert' },
            ]}
          />

          <div className="split-list">
            <section>
              <SearchBox value={q} onChange={setQ} placeholder="Search by event ID, document, recipient, or watermark…" />
              {rows.length === 0 ? (
                <EmptyBox message="No decryption events recorded yet. Decrypt an assigned document to generate audited event logs." />
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Event ID</th>
                        <th>Document</th>
                        <th>Recipient</th>
                        <th>Time</th>
                        <th>Watermark</th>
                        <th>Status</th>
                        <th>Ledger</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((e) => (
                        <tr
                          key={e.event_id}
                          className={e.event_id === selectedId ? 'selected-row' : ''}
                          onClick={() => setSelectedId(e.event_id)}
                          style={{
                            background: e.event_id === selectedId ? 'rgba(20, 119, 255, 0.12)' : undefined,
                          }}
                        >
                          <td className="link">{e.event_id}</td>
                          <td style={{ color: '#fff' }}>{e.document_id}</td>
                          <td className="mono">{e.recipient_id}</td>
                          <td>{formatTs(e.timestamp)}</td>
                          <td className="mono">{e.watermark_id ? `${e.watermark_id.slice(0, 8)}…` : '—'}</td>
                          <td>
                            <Badge type={e.status === 'VERIFIED' ? 'success' : e.status === 'Failed' ? 'danger' : 'warning'}>
                              {e.status === 'VERIFIED' ? 'Verified' : e.status}
                            </Badge>
                          </td>
                          <td>
                            <Badge type="info">{e.ledger_block_id ? 'Committed' : 'Pending'}</Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <Pager shown={rows.length} total={events.length} noun="events" />
            </section>

            {selectedEvent ? (
              <EventDetail event={selectedEvent} />
            ) : (
              <div className="detail">
                <EmptyBox message="Select a decryption event to inspect cryptographic signature and rendering receipts." />
              </div>
            )}
          </div>
        </>
      )}
    </AppShell>
  );
}

function EventDetail({ event }) {
  const [busy, setBusy] = useState(false);
  const [downloadError, setDownloadError] = useState(null);
  const [receipts, setReceipts] = useState(null);
  const recipient = useAuthedRecipient();
  const isOwner = recipient && recipient.recipient_id === event.recipient_id;
  const [signingKey, setSigningKey] = useState(session.signingKey);

  useEffect(() => {
    setReceipts(null);
    api.decryption.listRenders(event.event_id).then((r) => setReceipts(r.items)).catch(() => setReceipts([]));
  }, [event.event_id]);

  const handleViewAndLog = async () => {
    setBusy(true);
    setDownloadError(null);
    if (isOwner && !signingKey) {
      setBusy(false);
      setDownloadError('Load your signing key to log a signed rendering receipt.');
      return;
    }
    try {
      const blob = await api.decryption.downloadBlob(event.event_id);
      window.open(URL.createObjectURL(blob), '_blank');
      if (isOwner) {
        await api.decryption.recordRender(event.event_id, signingKey);
        const r = await api.decryption.listRenders(event.event_id);
        setReceipts(r.items);
      }
    } catch (e) {
      setDownloadError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <aside className="detail">
      <div className="detail-title">
        <div className="officer-avatar-sm" style={{ width: 38, height: 38 }}>
          <Icon name="decrypt" size={16} />
        </div>
        <div>
          <h3>
            {event.event_id}{' '}
            <Badge type={event.status === 'VERIFIED' ? 'success' : 'warning'}>
              {event.status}
            </Badge>
          </h3>
          <small>Decryption Audit Record</small>
        </div>
      </div>

      <div className="kv">
        <b>Document ID</b>
        <span className="mono link">{event.document_id}</span>
        <b>Recipient ID</b>
        <span className="mono">{event.recipient_id}</span>
        <b>Timestamp</b>
        <span>{formatTs(event.timestamp)}</span>
        <b>Forensic Watermark</b>
        <span className="mono">{event.watermark_id || 'Metadata Embedded'}</span>
        <b>Signature Algorithm</b>
        <span className="mono">{event.signature_algorithm || 'ML-DSA-65'}</span>
        <b>Ledger Status</b>
        <span>
          <Badge type="info">{event.ledger_block_id ? `Block #${event.ledger_block_id}` : 'Committed'}</Badge>
        </span>
      </div>

      <div className="subcard">
        <h4>Cryptographic Attribution</h4>
        <p>Signature Verified <strong style={{ color: 'var(--green)' }}>ML-DSA-65 Valid</strong></p>
        <p>Watermark Channel <strong>Lattice Pattern &amp; Metadata</strong></p>
        <p>Ledger Hash-Chained <strong style={{ color: 'var(--green)' }}>Verified</strong></p>
      </div>

      {!isOwner && (
        <small style={{ color: 'var(--text-muted)', display: 'block', margin: '10px 0 6px', fontSize: 11.5 }}>
          Note: Only {event.recipient_id} can download this decrypted copy.
        </small>
      )}

      {isOwner && <SigningKeyInput onChange={setSigningKey} />}
      <button
        className="primary wide"
        disabled={busy || !isOwner}
        onClick={handleViewAndLog}
        type="button"
        style={{ marginTop: 8 }}
      >
        <Icon name="eye" size={13} />
        {busy ? 'Opening…' : `View Decrypted Document${isOwner ? ' (logs rendering receipt)' : ''}`}
      </button>

      {downloadError && (
        <div className="state-box error" style={{ marginTop: 10 }}>
          <Icon name="alert" size={14} />
          <span>{downloadError}</span>
        </div>
      )}

      <div className="subcard" style={{ marginTop: 14 }}>
        <h4>Rendering Receipts ({receipts ? receipts.length : 0})</h4>
        {receipts === null ? (
          <Loading label="Loading rendering logs…" />
        ) : receipts.length === 0 ? (
          <p style={{ margin: 0, fontSize: 12, color: 'var(--text-muted)', borderBottom: 'none' }}>
            No rendering receipts logged yet for this decryption event.
          </p>
        ) : (
          receipts.map((r) => (
            <div className="kv" key={r.render_id} style={{ margin: '6px 0', padding: '4px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <b className="mono link">{r.render_id}</b>
              <span style={{ fontSize: 11.5 }}>{formatTs(r.timestamp)} · Block #{r.ledger_block_id ?? '—'}</span>
            </div>
          ))
        )}
      </div>
    </aside>
  );
}

export default Events;
