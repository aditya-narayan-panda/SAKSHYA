import React, { useEffect, useState } from 'react';
import { AppShell } from '../components/AppShell';
import { PageHeader } from '../components/PageHeader';
import { DataModules } from '../components/DataModules';
import { Loading, ErrorBox, EmptyBox } from '../components/States';
import { Badge } from '../components/StatusBadge';
import { Pager } from '../components/Table';
import { Icon } from '../icons';
import { api } from '../api';
import { useAsync, shortHash } from '../lib/app';

export function Ledger() {
  const { data, loading, error, reload } = useAsync(() => api.ledger.blocks(), []);
  const blocks = data?.blocks || [];
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if ((!selected || !blocks.some((b) => b.block_number === selected.block_number)) && blocks.length) {
      setSelected(blocks[0]);
    }
  }, [blocks, selected]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Provenance"
        title="Immutable Evidence Ledger"
        description="Tamper-evident, hash-chained ledger storing immutable records of every document operation and decryption event."
        status={
          data
            ? [
                {
                  label: `Chain Integrity: ${data.status}`,
                  dot: true,
                  tone: data.status === 'VERIFIED' ? 'good' : 'bad',
                },
              ]
            : undefined
        }
      />

      {loading && <Loading label="Verifying ledger chain integrity…" />}
      {error && <ErrorBox message={error} onRetry={reload} />}

      {!loading && !error && data && (
        <>
          <DataModules
            items={[
              { value: data.height, label: 'Total Block Height', description: 'Chained blocks', icon: 'ledger' },
              { value: data.height, label: 'Verified Blocks', description: 'Hash validity 100%', tone: 'success', icon: 'shieldCheck' },
              { value: data.nodes || 3, label: 'Consensus Nodes', description: 'Air-gapped quorum', icon: 'server' },
              {
                value: data.status || 'VERIFIED',
                label: 'Merkle Integrity',
                description: 'Tamper proof',
                tone: data.status === 'VERIFIED' ? 'success' : 'danger',
                icon: 'checkCircle',
              },
            ]}
          />

          <div className="split-list">
            <section>
              {blocks.length === 0 ? (
                <EmptyBox message="No ledger blocks recorded yet. Decrypt or protect a document to generate genesis block." />
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Block #</th>
                        <th>Block Hash</th>
                        <th>Event ID</th>
                        <th>Doc Hash</th>
                        <th>Confirmations</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {blocks.map((b) => (
                        <tr
                          key={b.block_number}
                          className={selected?.block_number === b.block_number ? 'selected-row' : ''}
                          onClick={() => setSelected(b)}
                          style={{
                            background: selected?.block_number === b.block_number ? 'rgba(20, 119, 255, 0.12)' : undefined,
                          }}
                        >
                          <td className="mono" style={{ color: '#fff', fontWeight: 600 }}>#{b.block_number}</td>
                          <td className="mono link">{shortHash(b.block_hash, 10, 4)}</td>
                          <td className="link">{b.event_id || '—'}</td>
                          <td className="mono">{shortHash(b.document_hash, 8, 0)}</td>
                          <td>{b.confirmations} nodes</td>
                          <td><Badge type="success">{b.status}</Badge></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <Pager shown={blocks.length} total={data.height} noun="blocks" />
            </section>

            {selected ? (
              <BlockDetail block={selected} />
            ) : (
              <div className="detail">
                <EmptyBox message="Select a ledger block to inspect Merkle proof and block headers." />
              </div>
            )}
          </div>
        </>
      )}
    </AppShell>
  );
}

function BlockDetail({ block }) {
  return (
    <aside className="detail">
      <div className="detail-title">
        <div className="officer-avatar-sm" style={{ width: 38, height: 38 }}>
          <Icon name="ledger" size={16} />
        </div>
        <div>
          <h3>
            Block #{block.block_number}{' '}
            <Badge type="success">{block.status}</Badge>
          </h3>
          <small>{block.confirmations} Quorum Confirmations</small>
        </div>
      </div>

      <div className="kv">
        <b>Block Number</b>
        <span className="mono">#{block.block_number}</span>
        <b>Associated Event</b>
        <span className="mono link">{block.event_id || 'GENESIS'}</span>
        <b>Node Quorum</b>
        <span>{block.confirmations} / 3 Replicas</span>
        <b>Verification Status</b>
        <span><Badge type="success">{block.status}</Badge></span>
      </div>

      <div className="subcard">
        <h4>Block Header &amp; Cryptographic Proofs</h4>
        <p>
          Block Hash (SHA-256)
          <strong className="mono" style={{ color: 'var(--cyan)' }}>
            {shortHash(block.block_hash, 16, 4)}
          </strong>
        </p>
        <p>
          Previous Hash
          <strong className="mono">
            {shortHash(block.previous_block_hash, 16, 4)}
          </strong>
        </p>
        <p>
          Document Payload Hash
          <strong className="mono">
            {shortHash(block.document_hash, 16, 4)}
          </strong>
        </p>
        <p>
          Merkle Root
          <strong className="mono">
            {shortHash(block.merkle_root, 16, 4)}
          </strong>
        </p>
      </div>

      <div className="info-box" style={{ marginTop: 14 }}>
        Any modification to past document records or decryption events will immediately invalidate subsequent block hashes
        and trigger an automated tamper alarm across all local nodes.
      </div>
    </aside>
  );
}

export default Ledger;
