import React, { useCallback, useEffect, useState } from 'react';
import { AppShell } from '../components/AppShell';
import { PageHeader } from '../components/PageHeader';
import { DataModules } from '../components/DataModules';
import { Loading, ErrorBox, EmptyBox } from '../components/States';
import { Badge } from '../components/StatusBadge';
import { SearchBox, Pager } from '../components/Table';
import { Icon } from '../icons';
import { api } from '../api';
import { useAsync, useAuthedRecipient, go, formatTs, shortHash, session } from '../lib/app';
import { SigningKeyInput } from '../components/SigningKeyInput';

export function Documents() {
  const [q, setQ] = useState('');
  const { data, loading, error, reload } = useAsync(() => api.documents.list(), []);
  const docs = data?.items || [];
  const filtered = docs.filter((d) => d.filename.toLowerCase().includes(q.toLowerCase()) || d.document_id.toLowerCase().includes(q.toLowerCase()));
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
    if ((!selectedId || !filtered.some((d) => d.document_id === selectedId)) && filtered.length) {
      setSelectedId(filtered[0].document_id);
    }
  }, [filtered, selectedId]);

  const selectedDoc = filtered.find((d) => d.document_id === selectedId);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Document Operations"
        title="Protected Documents"
        description="Encrypted documents distributed under post-quantum cryptographic protection and forensic watermarking."
        action={
          <button className="primary" onClick={() => go('protect')} type="button">
            <Icon name="plus" size={14} />
            Protect New Document
          </button>
        }
      />

      {loading && <Loading label="Loading documents…" />}
      {error && <ErrorBox message={error} onRetry={reload} />}

      {!loading && !error && (
        <>
          <DataModules
            items={[
              { value: docs.length, label: 'Total Documents', description: 'Registered assets' },
              { value: docs.filter((d) => d.status !== 'DRAFT').length, label: 'Encrypted & Active', description: 'AES-256-GCM', tone: 'success' },
              { value: docs.reduce((s, d) => s + d.recipients, 0), label: 'Recipient Assignments', description: 'Distribution links' },
            ]}
          />

          <div className="split-list">
            <section>
              <SearchBox value={q} onChange={setQ} placeholder="Search documents by name or ID…" />
              {filtered.length === 0 ? (
                <EmptyBox message="No documents match your query. Protect a document to get started." />
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Document</th>
                        <th>Status</th>
                        <th>Recipients</th>
                        <th>Decryptions</th>
                        <th>Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((d) => (
                        <tr
                          key={d.document_id}
                          className={d.document_id === selectedId ? 'selected-row' : ''}
                          onClick={() => setSelectedId(d.document_id)}
                          style={{
                            background: d.document_id === selectedId ? 'rgba(20, 119, 255, 0.12)' : undefined,
                            borderColor: d.document_id === selectedId ? 'var(--blue-bright)' : undefined,
                          }}
                        >
                          <td>
                            <div className="file">
                              <span className="fileicon">{(d.file_type || '').replace('.', '').toUpperCase() || 'DOC'}</span>
                              <div>
                                <b>{d.filename}</b>
                                <small>{d.document_id}</small>
                              </div>
                            </div>
                          </td>
                          <td>
                            <Badge type="success">{d.status}</Badge>
                          </td>
                          <td>{d.recipients}</td>
                          <td>{d.decryptions}</td>
                          <td>{formatTs(d.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <Pager shown={filtered.length} total={docs.length} noun="documents" />
            </section>

            {selectedDoc ? (
              <DocumentDetail doc={selectedDoc} onChanged={reload} />
            ) : (
              <div className="detail">
                <EmptyBox message="Select a document from the list to inspect forensic and cryptographic details." />
              </div>
            )}
          </div>
        </>
      )}
    </AppShell>
  );
}

function DocumentDetail({ doc, onChanged }) {
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState(null);
  const [decrypting, setDecrypting] = useState(false);
  const [decryptResult, setDecryptResult] = useState(null);
  const [decryptError, setDecryptError] = useState(null);
  const [viewing, setViewing] = useState(false);
  const [renderReceipt, setRenderReceipt] = useState(null);
  const [renderError, setRenderError] = useState(null);
  const [signingKey, setSigningKey] = useState(session.signingKey);
  const [applyVisible, setApplyVisible] = useState(false);
  const recipient = useAuthedRecipient();

  const loadDetail = useCallback(() => {
    setDetailError(null);
    api.documents.get(doc.document_id).then(setDetail).catch((e) => setDetailError(e.message));
  }, [doc.document_id]);

  useEffect(() => {
    setDetail(null);
    setDecryptResult(null);
    setDecryptError(null);
    setRenderReceipt(null);
    loadDetail();
  }, [doc.document_id, loadDetail]);

  const isAuthorized = !!(detail && recipient && detail.recipient_ids.includes(recipient.recipient_id));

  const handleDecrypt = async () => {
    setDecrypting(true);
    setDecryptError(null);
    setDecryptResult(null);
    setRenderReceipt(null);
    try {
      const result = await api.decryption.decrypt(doc.document_id, signingKey, applyVisible);
      setDecryptResult(result);
      loadDetail();
      onChanged && onChanged();
    } catch (e) {
      setDecryptError(e.message);
    } finally {
      setDecrypting(false);
    }
  };

  const handleViewAndLog = async () => {
    if (!decryptResult) return;
    setViewing(true);
    setRenderError(null);
    try {
      const blob = await api.decryption.downloadBlob(decryptResult.event_id);
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
      const receipt = await api.decryption.recordRender(decryptResult.event_id, signingKey);
      setRenderReceipt(receipt);
    } catch (e) {
      setRenderError(e.message);
    } finally {
      setViewing(false);
    }
  };

  const kindLabel = (doc.file_type || '').replace('.', '').toUpperCase() || 'DOC';

  return (
    <aside className="detail">
      <div className="detail-title">
        <span className="fileicon">{kindLabel}</span>
        <div>
          <h3>{doc.filename}</h3>
          <small>{doc.document_id}</small>
        </div>
      </div>

      <div className="doc-preview">
        <span className="fileicon">{kindLabel}</span>
        <div>
          <b>{doc.filename}</b>
          <small>{(doc.file_size / 1024).toFixed(0)} KB · {kindLabel} document</small>
        </div>
      </div>

      <div className="kv">
        <b>Document ID</b>
        <span className="mono">{doc.document_id}</span>
        <b>Created At</b>
        <span>{formatTs(doc.created_at)}</span>
        <b>Status</b>
        <span><Badge type="success">{doc.status}</Badge></span>
      </div>

      <div className="subcard">
        <h4>Cryptographic Protection</h4>
        <p>Document Encryption <strong>AES-256-GCM</strong></p>
        <p>Key Encapsulation <strong>ML-KEM-768</strong></p>
        <p>Integrity Protection <strong>SHA-256</strong></p>
      </div>

      {detailError && <ErrorBox message={detailError} onRetry={loadDetail} />}

      {detail && (
        <div className="subcard" style={{ marginTop: 14 }}>
          <h4>Decrypt Document</h4>
          {detail.recipient_ids.length === 0 ? (
            <p style={{ color: 'var(--red)', margin: 0, borderBottom: 'none' }}>
              No authorized recipients on this document.
            </p>
          ) : !isAuthorized ? (
            <p style={{ color: 'var(--red)', margin: 0, borderBottom: 'none' }}>
              You are logged in as <b>{recipient?.recipient_id}</b>, who is not on the authorized recipient list for this file.
            </p>
          ) : (
            <>
              <p style={{ margin: '0 0 10px', borderBottom: 'none' }}>
                Decrypting as <b>{recipient.name}</b> <small className="link" style={{ marginLeft: 6 }}>{recipient.recipient_id}</small>
              </p>
              <SigningKeyInput onChange={setSigningKey} />
              <label style={{ display: 'flex', gap: 8, alignItems: 'center', margin: '0 0 10px', fontSize: 12.5 }}>
                <input type="checkbox" checked={applyVisible} onChange={(e) => setApplyVisible(e.target.checked)} />
                Add a visible screenshot-deterrent stamp (off by default — the copy stays visually identical)
              </label>
              <button className="primary wide" disabled={decrypting || !signingKey} onClick={handleDecrypt} type="button">
                <Icon name="key" size={14} />
                {decrypting ? 'Decrypting & Watermarking…' : 'Decrypt Document'}
              </button>
            </>
          )}

          {decryptError && (
            <div className="state-box error" style={{ marginTop: 10 }}>
              <Icon name="alert" size={14} />
              <span>{decryptError}</span>
            </div>
          )}

          {decryptResult && (
            <div className="success-note big" style={{ marginTop: 12, flexDirection: 'column', alignItems: 'flex-start' }}>
              <b>Decrypted — Event {decryptResult.event_id}</b>
              <small>
                Watermark ID: {decryptResult.watermark_id}{' '}
                {decryptResult.watermark_channel ? `(${decryptResult.watermark_channel})` : ''}
              </small>
              {decryptResult.visible_watermark_applied && (
                <small>Visible forensic screenshot stamp &amp; micro-pattern applied</small>
              )}
              <small>
                Ledger Block #{decryptResult.ledger_block?.block_number} · {decryptResult.ledger_block?.confirmations} confirmations
              </small>
              <button className="outline" style={{ marginTop: 10, width: '100%' }} disabled={viewing} onClick={handleViewAndLog} type="button">
                <Icon name="eye" size={13} />
                {viewing ? 'Opening…' : 'View Decrypted File (logs rendering receipt)'}
              </button>
            </div>
          )}

          {renderError && (
            <div className="state-box error" style={{ marginTop: 10 }}>
              <Icon name="alert" size={14} />
              <span>{renderError}</span>
            </div>
          )}

          {renderReceipt && (
            <div className="subcard" style={{ marginTop: 12 }}>
              <h4>Rendering Receipt</h4>
              <div className="kv">
                <b>Receipt ID</b>
                <span className="mono">{renderReceipt.render_id}</span>
                <b>Rendered By</b>
                <span>{renderReceipt.recipient_id}</span>
                <b>Rendered At</b>
                <span>{formatTs(renderReceipt.timestamp)}</span>
                <b>Ledger Block</b>
                <span>#{renderReceipt.ledger_block?.block_number} · {renderReceipt.ledger_block?.confirmations} confirmed</span>
                <b>Signature</b>
                <span>{renderReceipt.signature_algorithm}</span>
              </div>
              <small style={{ color: 'var(--text-muted)', fontSize: 11, display: 'block', marginTop: 4 }}>
                Signed with recipient key and committed to ledger.
              </small>
            </div>
          )}
        </div>
      )}

      <div className="detail-actions">
        <button className="primary" onClick={() => go('recipients')} type="button" style={{ flex: 1 }}>
          <Icon name="users" size={13} />
          Recipients
        </button>
        <button className="outline" onClick={() => go('events')} type="button" style={{ flex: 1 }}>
          <Icon name="events" size={13} />
          Events
        </button>
      </div>
    </aside>
  );
}

export default Documents;
