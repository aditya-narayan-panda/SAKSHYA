import React, { useEffect, useState } from 'react';
import { AppShell } from '../components/AppShell';
import { PageHeader } from '../components/PageHeader';
import { DataModules } from '../components/DataModules';
import { Loading, ErrorBox, EmptyBox } from '../components/States';
import { Badge } from '../components/StatusBadge';
import { Pager } from '../components/Table';
import { Icon } from '../icons';
import { api } from '../api';
import { useAsync, session, formatTs } from '../lib/app';

export function Reports() {
  const { data, loading, error, reload } = useAsync(() => api.reports.list(), []);
  const { data: invData } = useAsync(() => api.investigations.list(), []);
  const reports = data?.items || [];
  const investigations = (invData?.items || []).filter((i) => i.status === 'IDENTIFIED');
  const [selectedInv, setSelectedInv] = useState('');

  useEffect(() => {
    if (!selectedInv && investigations.length) {
      const preferred =
        session.lastInvestigation &&
        investigations.some((i) => i.investigation_id === session.lastInvestigation)
          ? session.lastInvestigation
          : investigations[0].investigation_id;
      setSelectedInv(preferred);
    }
  }, [investigations, selectedInv]);

  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState(null);
  const [selectedReport, setSelectedReport] = useState(null);

  useEffect(() => {
    if (
      (!selectedReport || !reports.some((r) => r.report_id === selectedReport.report_id)) &&
      reports.length
    ) {
      setSelectedReport(reports[0]);
    }
  }, [reports, selectedReport]);

  const handleGenerate = async () => {
    if (!selectedInv) {
      setGenError('No identified leak investigation available. Run a Leak Investigation first.');
      return;
    }
    setGenerating(true);
    setGenError(null);
    try {
      await api.reports.create(selectedInv);
      await reload();
    } catch (e) {
      setGenError(e.message);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <AppShell>
      <PageHeader
        eyebrow="Reporting"
        title="Forensic Attribution Reports"
        description="Compile and export cryptographically verifiable forensic reports for leak attribution and legal submission."
        action={
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            {investigations.length > 0 && (
              <select
                className="select"
                value={selectedInv}
                onChange={(e) => setSelectedInv(e.target.value)}
                style={{ width: 'auto', minWidth: 260 }}
              >
                {investigations.map((i) => (
                  <option key={i.investigation_id} value={i.investigation_id}>
                    {i.investigation_id} — {i.uploaded_filename} ({i.matched_recipient_id})
                  </option>
                ))}
              </select>
            )}
            <button
              className="primary"
              disabled={generating || !selectedInv}
              onClick={handleGenerate}
              type="button"
            >
              <Icon name="plus" size={13} />
              {generating ? 'Compiling Report…' : 'Generate Report'}
            </button>
          </div>
        }
      />

      {genError && (
        <div className="state-box error" style={{ marginBottom: 16 }}>
          <Icon name="alert" size={14} />
          <span>{genError}</span>
        </div>
      )}

      {loading && <Loading label="Loading forensic report archives…" />}
      {error && <ErrorBox message={error} onRetry={reload} />}

      {!loading && !error && (
        <>
          <DataModules
            items={[
              { value: reports.length, label: 'Total Reports', description: 'Generated case files', icon: 'reports' },
              { value: reports.filter((r) => r.status === 'GENERATED').length, label: 'Verified Dossiers', description: 'Ready to export', tone: 'success', icon: 'shieldCheck' },
              { value: investigations.length, label: 'Identified Investigations', description: 'Available for reporting', icon: 'investigate' },
              { value: 0, label: 'Failed Reports', description: 'Zero integrity flaws', icon: 'checkCircle' },
            ]}
          />

          <div className="split-list">
            <section>
              {reports.length === 0 ? (
                <EmptyBox message="No forensic reports compiled yet. Run a Leak Investigation first to generate attribution records." />
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Report ID</th>
                        <th>Type</th>
                        <th>Document</th>
                        <th>Event ID</th>
                        <th>Generated On</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reports.map((r, i) => (
                        <tr
                          key={r.report_id}
                          className={selectedReport?.report_id === r.report_id ? 'selected-row' : ''}
                          onClick={() => setSelectedReport(r)}
                          style={{
                            background: selectedReport?.report_id === r.report_id ? 'rgba(20, 119, 255, 0.12)' : undefined,
                          }}
                        >
                          <td>{i + 1}</td>
                          <td className="link">{r.report_id}</td>
                          <td>{r.report_type}</td>
                          <td style={{ color: '#fff' }}>{r.document_id || '—'}</td>
                          <td className="link">{r.event_id || '—'}</td>
                          <td>{formatTs(r.generated_at)}</td>
                          <td>
                            <Badge type="success">{r.status}</Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <Pager shown={reports.length} total={reports.length} noun="reports" />
            </section>

            {selectedReport ? (
              <ReportDetail report={selectedReport} />
            ) : (
              <div className="detail">
                <EmptyBox message="Select a forensic report from the table to preview and download." />
              </div>
            )}
          </div>
        </>
      )}
    </AppShell>
  );
}

function ReportDetail({ report }) {
  const [dlError, setDlError] = useState(null);
  const [dlBusy, setDlBusy] = useState(null);

  const handleDownload = async (format) => {
    setDlError(null);
    setDlBusy(format);
    let url = null;
    try {
      const blob = await api.reports.downloadBlob(report.report_id, format);
      url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${report.report_id}.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (e) {
      setDlError(e.message || 'Download failed');
    } finally {
      if (url) URL.revokeObjectURL(url);
      setDlBusy(null);
    }
  };

  return (
    <aside className="detail">
      <div className="detail-title">
        <span className="fileicon">PDF</span>
        <div>
          <h3>
            Forensic Report <Badge type="success">{report.status}</Badge>
          </h3>
          <small className="mono">{report.report_id}</small>
        </div>
      </div>

      <div
        style={{
          background: 'linear-gradient(135deg, rgba(6, 20, 38, 0.9) 0%, rgba(20, 119, 255, 0.15) 100%)',
          border: '1px solid var(--border-strong)',
          borderRadius: 'var(--radius-sm)',
          padding: 18,
          marginBottom: 16,
          textAlign: 'center',
        }}
      >
        <b style={{ letterSpacing: '0.1em', fontSize: 13, color: 'var(--cyan)' }}>SAKSHYA DIGITAL FORENSICS</b>
        <div style={{ fontSize: 15, fontWeight: 700, color: '#fff', margin: '4px 0' }}>
          OFFICIAL ATTRIBUTION DOSSIER
        </div>
        <small style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
          {report.report_id} · CLASSIFIED
        </small>
      </div>

      <div className="kv">
        <b>Report Type</b>
        <span>{report.report_type}</span>
        <b>Origin Document</b>
        <span className="mono link">{report.document_id || '—'}</span>
        <b>Decryption Event</b>
        <span className="mono link">{report.event_id || '—'}</span>
        <b>Generated On</b>
        <span>{formatTs(report.generated_at)}</span>
        <b>Integrity State</b>
        <span><Badge type="success">CRYPTOGRAPHICALLY SIGNED</Badge></span>
      </div>

      {dlError && (
        <div className="state-box error" style={{ marginBottom: 12 }}>
          <Icon name="alert" size={14} />
          <span>{dlError}</span>
        </div>
      )}

      <div className="button-row" style={{ marginTop: 8 }}>
        <button
          className="primary"
          disabled={dlBusy !== null}
          onClick={() => handleDownload('pdf')}
          type="button"
          style={{ flex: 1 }}
        >
          <Icon name="download" size={14} />
          {dlBusy === 'pdf' ? 'Exporting PDF…' : 'Download PDF Report'}
        </button>

        <button
          className="outline"
          disabled={dlBusy !== null}
          onClick={() => handleDownload('json')}
          type="button"
          style={{ flex: 1 }}
        >
          <Icon name="externalLink" size={14} />
          {dlBusy === 'json' ? 'Exporting JSON…' : 'Export JSON Data'}
        </button>
      </div>
    </aside>
  );
}

export default Reports;
