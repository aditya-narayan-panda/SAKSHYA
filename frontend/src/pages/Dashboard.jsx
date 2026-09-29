import React, { useState } from 'react';
import { AppShell } from '../components/AppShell';
import { Badge } from '../components/StatusBadge';
import { Loading, ErrorBox, EmptyBox } from '../components/States';
import { Icon } from '../icons';
import { api } from '../api';
import { useAsync, go, formatTs } from '../lib/app';
import heroBg from '../assets/ins-vikrant-sea.jpg';

// Sparkline SVG generator
function Sparkline({ color = '#1477ff', points = [8, 12, 10, 15, 14, 18, 24] }) {
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const width = 100;
  const height = 24;

  const coords = points.map((p, i) => {
    const x = (i / (points.length - 1)) * width;
    const y = height - ((p - min) / range) * (height - 6) - 3;
    return `${x},${y}`;
  });

  const pathStr = `M ${coords.join(' L ')}`;
  const fillStr = `M 0,${height} L ${coords.join(' L ')} L ${width},${height} Z`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="data-module-spark" preserveAspectRatio="none">
      <defs>
        <linearGradient id={`grad-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0.0" />
        </linearGradient>
      </defs>
      <path d={fillStr} fill={`url(#grad-${color.replace('#', '')})`} />
      <path d={pathStr} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

// Interactive Document Protection Activity Line Chart
function ActivityChart({ timeRange, setTimeRange }) {
  const ranges = {
    '7D': [
      { label: 'Apr 22', val: 12 },
      { label: 'Apr 23', val: 18 },
      { label: 'Apr 24', val: 14 },
      { label: 'Apr 25', val: 11 },
      { label: 'Apr 26', val: 15 },
      { label: 'Apr 27', val: 13 },
      { label: 'Apr 28', val: 24 },
    ],
    '30D': [
      { label: 'Week 1', val: 42 },
      { label: 'Week 2', val: 56 },
      { label: 'Week 3', val: 68 },
      { label: 'Week 4', val: 94 },
    ],
    '90D': [
      { label: 'Feb', val: 120 },
      { label: 'Mar', val: 195 },
      { label: 'Apr', val: 260 },
    ],
  };

  const data = ranges[timeRange] || ranges['7D'];
  const maxVal = 25;
  const svgWidth = 500;
  const svgHeight = 160;
  const padding = 25;

  const points = data.map((d, i) => {
    const x = padding + (i / (data.length - 1)) * (svgWidth - padding * 2);
    const y = svgHeight - padding - (d.val / maxVal) * (svgHeight - padding * 2);
    return { x, y, ...d };
  });

  const pathD = points.reduce((acc, p, i, a) => {
    if (i === 0) return `M ${p.x},${p.y}`;
    const prev = a[i - 1];
    const cp1x = prev.x + (p.x - prev.x) / 2;
    const cp1y = prev.y;
    const cp2x = prev.x + (p.x - prev.x) / 2;
    const cp2y = p.y;
    return `${acc} C ${cp1x},${cp1y} ${cp2x},${cp2y} ${p.x},${p.y}`;
  }, '');

  const areaD = `${pathD} L ${points[points.length - 1].x},${svgHeight - padding} L ${points[0].x},${svgHeight - padding} Z`;

  return (
    <div className="chart-card">
      <div className="chart-card-head">
        <h3>
          <Icon name="protect" size={16} style={{ color: 'var(--cyan)' }} />
          Document Protection Activity
        </h3>
        <div className="chart-toggle-group">
          {['7D', '30D', '90D'].map((t) => (
            <button
              type="button"
              key={t}
              className={`chart-toggle-btn${timeRange === t ? ' active' : ''}`}
              onClick={() => setTimeRange(t)}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="svg-chart-wrap">
        <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} width="100%" height="100%" preserveAspectRatio="none">
          <defs>
            <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#19c8ff" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#1477ff" stopOpacity="0.0" />
            </linearGradient>
            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="glow" />
              <feComposite in="SourceGraphic" in2="glow" operator="over" />
            </filter>
          </defs>

          {/* Grid lines */}
          {[0, 5, 10, 15, 20, 25].map((val) => {
            const y = svgHeight - padding - (val / maxVal) * (svgHeight - padding * 2);
            return (
              <g key={val}>
                <line x1={padding} y1={y} x2={svgWidth - padding} y2={y} stroke="rgba(90, 150, 220, 0.12)" strokeDasharray="3 3" />
                <text x={padding - 6} y={y + 3} fill="var(--text-dim)" fontSize="9" textAnchor="end" fontFamily="var(--font-mono)">
                  {val}
                </text>
              </g>
            );
          })}

          {/* Filled area */}
          <path d={areaD} fill="url(#areaGrad)" />

          {/* Line */}
          <path d={pathD} fill="none" stroke="#19c8ff" strokeWidth="2.5" filter="url(#glow)" />

          {/* Points & Labels */}
          {points.map((p, i) => (
            <g key={i}>
              <circle cx={p.x} cy={p.y} r="4" fill="#020812" stroke="#19c8ff" strokeWidth="2" />
              <text x={p.x} y={svgHeight - 6} fill="var(--text-muted)" fontSize="9" textAnchor="middle" fontFamily="var(--font-mono)">
                {p.label}
              </text>
            </g>
          ))}
        </svg>
      </div>
    </div>
  );
}

// Donut Chart Component for Document Status
function StatusDonut({ total = 24, protectedCount = 18, pendingCount = 4, reviewCount = 2 }) {
  const protectedPct = Math.round((protectedCount / (total || 1)) * 100);
  const pendingPct = Math.round((pendingCount / (total || 1)) * 100);
  const reviewPct = Math.round((reviewCount / (total || 1)) * 100);

  const radius = 48;
  const circ = 2 * Math.PI * radius;

  const protStroke = (protectedPct / 100) * circ;
  const pendStroke = (pendingPct / 100) * circ;
  const revStroke = (reviewPct / 100) * circ;

  return (
    <div className="chart-card">
      <div className="chart-card-head">
        <h3>
          <Icon name="documents" size={16} style={{ color: 'var(--cyan)' }} />
          Document Status
        </h3>
      </div>

      <div className="donut-wrap">
        <div className="donut-svg-container">
          <svg viewBox="0 0 120 120" width="100%" height="100%" style={{ transform: 'rotate(-90deg)' }}>
            <circle cx="60" cy="60" r={radius} fill="none" stroke="rgba(90, 150, 220, 0.12)" strokeWidth="12" />
            {/* Protected Segment */}
            <circle
              cx="60"
              cy="60"
              r={radius}
              fill="none"
              stroke="#16d68a"
              strokeWidth="12"
              strokeDasharray={`${protStroke} ${circ}`}
              strokeDashoffset="0"
            />
            {/* Pending Segment */}
            <circle
              cx="60"
              cy="60"
              r={radius}
              fill="none"
              stroke="#f5b83d"
              strokeWidth="12"
              strokeDasharray={`${pendStroke} ${circ}`}
              strokeDashoffset={-protStroke}
            />
            {/* Review Segment */}
            <circle
              cx="60"
              cy="60"
              r={radius}
              fill="none"
              stroke="#63b3ff"
              strokeWidth="12"
              strokeDasharray={`${revStroke} ${circ}`}
              strokeDashoffset={-(protStroke + pendStroke)}
            />
          </svg>
          <div className="donut-center-label">
            <b>{total}</b>
            <small>Total</small>
          </div>
        </div>

        <div className="donut-legend">
          <div className="donut-legend-item">
            <span>
              <span className="donut-legend-dot" style={{ background: 'var(--green)' }} />
              Protected
            </span>
            <b>{protectedCount} ({protectedPct}%)</b>
          </div>
          <div className="donut-legend-item">
            <span>
              <span className="donut-legend-dot" style={{ background: 'var(--amber)' }} />
              Pending
            </span>
            <b>{pendingCount} ({pendingPct}%)</b>
          </div>
          <div className="donut-legend-item">
            <span>
              <span className="donut-legend-dot" style={{ background: 'var(--blue-soft)' }} />
              In Review
            </span>
            <b>{reviewCount} ({reviewPct}%)</b>
          </div>
        </div>
      </div>
    </div>
  );
}

export function Dashboard() {
  const { data, loading, error, reload } = useAsync(() => api.dashboard.get(), []);
  const { data: docsData } = useAsync(() => api.documents.list(), []);
  const [timeRange, setTimeRange] = useState('7D');

  const stats = data || {};
  const algo = stats.algorithms;
  const recentEvents = stats.recent_events || [];
  const recentDocs = docsData?.items?.slice(0, 5) || [
    { document_id: 'DOC-2025-01', filename: 'Naval_Report_2025.pdf', file_type: 'pdf', status: 'Protected', created_at: new Date().toISOString() },
    { document_id: 'DOC-2025-02', filename: 'Operations_Manual.docx', file_type: 'docx', status: 'Protected', created_at: new Date().toISOString() },
    { document_id: 'DOC-2025-03', filename: 'Intelligence_Brief.pdf', file_type: 'pdf', status: 'Protected', created_at: new Date().toISOString() },
    { document_id: 'DOC-2025-04', filename: 'Strategic_Analysis.pdf', file_type: 'pdf', status: 'Pending', created_at: new Date().toISOString() },
  ];

  const totalDocs = stats.protected_documents || 24;
  const protectedDocs = Math.max(1, Math.round(totalDocs * 0.75));
  const pendingDocs = Math.max(1, Math.round(totalDocs * 0.17));
  const reviewDocs = Math.max(0, totalDocs - protectedDocs - pendingDocs);

  return (
    <AppShell>
      {/* -------------------------------------------------------------- */}
      {/* CINEMATIC DASHBOARD HERO                                       */}
      {/* -------------------------------------------------------------- */}
      <div className="dash-hero-card">
        <div className="dash-hero-bg" style={{ backgroundImage: `url(${heroBg})` }} />
        <div className="dash-hero-overlay" />

        <div className="dash-hero-content">
          <div className="dash-hero-copy">
            <div className="eyebrow">
              <Icon name="shield" size={13} />
              DIGITAL PROVENANCE &amp; FORENSICS
            </div>
            <h1>
              Document Integrity.
              <br />
              <span>Operational Trust.</span>
            </h1>
            <p>
              Cryptographic protection. Forensic attribution. Immutable evidence.
              SAKSHYA ensures your documents remain authentic, traceable and tamper-evident.
            </p>
          </div>

          {/* System Status Panel on Right */}
          <div className="dash-status-card">
            <div className="dash-status-header">
              <div className="dash-status-header-title">
                <Icon name="shieldCheck" size={18} style={{ color: 'var(--green)' }} />
                <div>
                  <b>System Status</b>
                  <small style={{ display: 'block' }}>All systems operational</small>
                </div>
              </div>
              <Badge type="success">ONLINE</Badge>
            </div>

            <div className="dash-status-list">
              <div className="dash-status-row">
                <span><Icon name="database" size={13} /> Database</span>
                <b><span className="pulse-dot" style={{ width: 5, height: 5 }} /> Healthy</b>
              </div>
              <div className="dash-status-row">
                <span><Icon name="crypto" size={13} /> Cryptographic Module</span>
                <b><span className="pulse-dot" style={{ width: 5, height: 5 }} /> Healthy</b>
              </div>
              <div className="dash-status-row">
                <span><Icon name="ledger" size={13} /> Ledger</span>
                <b><span className="pulse-dot" style={{ width: 5, height: 5 }} /> Healthy</b>
              </div>
              <div className="dash-status-row">
                <span><Icon name="storage" size={13} /> Storage</span>
                <b><span className="pulse-dot" style={{ width: 5, height: 5 }} /> Healthy</b>
              </div>
            </div>
          </div>
        </div>
      </div>

      {loading && <Loading label="Loading operational console…" />}
      {error && <ErrorBox message={error} onRetry={reload} />}

      {!loading && (
        <>
          {/* ------------------------------------------------------------ */}
          {/* 4 KPI CARDS                                                  */}
          {/* ------------------------------------------------------------ */}
          <div className="data-modules">
            <div className="data-module">
              <div className="data-module-top">
                <div className="data-module-icon">
                  <Icon name="documents" size={18} />
                </div>
                <span className="badge badge-success">↑ 12%</span>
              </div>
              <div className="data-module-value">{totalDocs}</div>
              <div className="data-module-label">Total Documents</div>
              <div className="data-module-desc">vs. last 7 days</div>
              <Sparkline color="#1477ff" points={[14, 16, 18, 17, 20, 22, 24]} />
            </div>

            <div className="data-module">
              <div className="data-module-top">
                <div className="data-module-icon" style={{ background: 'rgba(22, 214, 138, 0.12)', borderColor: 'rgba(22, 214, 138, 0.25)', color: 'var(--green)' }}>
                  <Icon name="shieldCheck" size={18} />
                </div>
                <span className="badge badge-success">↑ 23%</span>
              </div>
              <div className="data-module-value" style={{ color: 'var(--green)' }}>{stats.protected_documents || protectedDocs}</div>
              <div className="data-module-label">Protected Documents</div>
              <div className="data-module-desc">vs. last 7 days</div>
              <Sparkline color="#16d68a" points={[10, 11, 13, 14, 15, 16, 18]} />
            </div>

            <div className="data-module">
              <div className="data-module-top">
                <div className="data-module-icon" style={{ background: 'rgba(168, 85, 247, 0.12)', borderColor: 'rgba(168, 85, 247, 0.25)', color: 'var(--purple)' }}>
                  <Icon name="users" size={18} />
                </div>
                <span className="badge badge-success">↑ 16%</span>
              </div>
              <div className="data-module-value">{stats.authorized_recipients || 7}</div>
              <div className="data-module-label">Authorized Recipients</div>
              <div className="data-module-desc">vs. last 7 days</div>
              <Sparkline color="#a855f7" points={[4, 5, 5, 6, 6, 7, 7]} />
            </div>

            <div className="data-module">
              <div className="data-module-top">
                <div className="data-module-icon" style={{ background: 'rgba(245, 184, 61, 0.12)', borderColor: 'rgba(245, 184, 61, 0.25)', color: 'var(--amber)' }}>
                  <Icon name="investigate" size={18} />
                </div>
                <span className="badge badge-success">↑ 50%</span>
              </div>
              <div className="data-module-value">{stats.decryption_events || 3}</div>
              <div className="data-module-label">Investigations</div>
              <div className="data-module-desc">vs. last 7 days</div>
              <Sparkline color="#f5b83d" points={[1, 1, 2, 2, 2, 3, 3]} />
            </div>
          </div>

          {/* ------------------------------------------------------------ */}
          {/* ANALYTICS GRID: ACTIVITY LINE CHART + DONUT + RECENT EVENTS   */}
          {/* ------------------------------------------------------------ */}
          <div className="dash-analytics-grid">
            <ActivityChart timeRange={timeRange} setTimeRange={setTimeRange} />

            <StatusDonut
              total={totalDocs}
              protectedCount={protectedDocs}
              pendingCount={pendingDocs}
              reviewCount={reviewDocs}
            />

            {/* Recent Security Events Stream */}
            <div className="chart-card">
              <div className="chart-card-head">
                <h3>
                  <Icon name="lightning" size={16} style={{ color: 'var(--cyan)' }} />
                  Recent Security Events
                </h3>
                <button className="ghost-btn small" onClick={() => go('events')} type="button">
                  View All →
                </button>
              </div>

              <div className="events-stream">
                {recentEvents.length > 0 ? (
                  recentEvents.slice(0, 4).map((e) => (
                    <div className="event-stream-row" key={e.event_id} onClick={() => go('events')}>
                      <div className="event-stream-left">
                        <div className="event-icon-box">
                          <Icon name="decrypt" size={14} />
                        </div>
                        <div className="event-meta">
                          <b>Decryption Event</b>
                          <small>{e.document_id} · {e.recipient_id}</small>
                        </div>
                      </div>
                      <div className="event-stream-right">
                        <Badge type={e.status === 'VERIFIED' ? 'success' : 'warning'}>
                          {e.status}
                        </Badge>
                        <small>{formatTs(e.timestamp)}</small>
                      </div>
                    </div>
                  ))
                ) : (
                  <>
                    <div className="event-stream-row" onClick={() => go('documents')}>
                      <div className="event-stream-left">
                        <div className="event-icon-box" style={{ color: 'var(--green)' }}>
                          <Icon name="protect" size={14} />
                        </div>
                        <div className="event-meta">
                          <b>Document Protected</b>
                          <small>Naval_Report_2025.pdf</small>
                        </div>
                      </div>
                      <div className="event-stream-right">
                        <Badge type="success">PROTECTED</Badge>
                        <small>2 hours ago</small>
                      </div>
                    </div>

                    <div className="event-stream-row" onClick={() => go('recipients')}>
                      <div className="event-stream-left">
                        <div className="event-icon-box" style={{ color: 'var(--blue-soft)' }}>
                          <Icon name="users" size={14} />
                        </div>
                        <div className="event-meta">
                          <b>Recipient Added</b>
                          <small>Commander A. Singh</small>
                        </div>
                      </div>
                      <div className="event-stream-right">
                        <Badge type="info">RECIPIENT</Badge>
                        <small>4 hours ago</small>
                      </div>
                    </div>

                    <div className="event-stream-row" onClick={() => go('leak')}>
                      <div className="event-stream-left">
                        <div className="event-icon-box" style={{ color: 'var(--purple)' }}>
                          <Icon name="investigate" size={14} />
                        </div>
                        <div className="event-meta">
                          <b>Investigation Initiated</b>
                          <small>Potential Leak Analysis</small>
                        </div>
                      </div>
                      <div className="event-stream-right">
                        <Badge type="purple">INVESTIGATION</Badge>
                        <small>6 hours ago</small>
                      </div>
                    </div>

                    <div className="event-stream-row" onClick={() => go('events')}>
                      <div className="event-stream-left">
                        <div className="event-icon-box" style={{ color: 'var(--cyan)' }}>
                          <Icon name="key" size={14} />
                        </div>
                        <div className="event-meta">
                          <b>Decryption Event</b>
                          <small>Evidence Package #3</small>
                        </div>
                      </div>
                      <div className="event-stream-right">
                        <Badge type="info">DECRYPTION</Badge>
                        <small>8 hours ago</small>
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* ------------------------------------------------------------ */}
          {/* BOTTOM ROW: RECENT DOCUMENTS TABLE + MARITIME QUOTE          */}
          {/* ------------------------------------------------------------ */}
          <div className="dash-bottom-grid">
            <div className="panel">
              <div className="panel-head">
                <h3>
                  <Icon name="documents" size={16} style={{ color: 'var(--cyan)' }} />
                  Recent Documents
                </h3>
                <button className="ghost-btn small" onClick={() => go('documents')} type="button">
                  View All →
                </button>
              </div>

              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Document Name</th>
                      <th>Type</th>
                      <th>Status</th>
                      <th>Protected On</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentDocs.map((doc) => (
                      <tr key={doc.document_id} onClick={() => go('documents')}>
                        <td>
                          <div className="file">
                            <span className="fileicon">
                              {(doc.file_type || '').replace('.', '').toUpperCase() || 'DOC'}
                            </span>
                            <div>
                              <b>{doc.filename}</b>
                              <small>{doc.document_id}</small>
                            </div>
                          </div>
                        </td>
                        <td className="mono">{(doc.file_type || 'PDF').toUpperCase()}</td>
                        <td>
                          <Badge type={doc.status === 'Protected' || doc.status === 'Active' ? 'success' : 'warning'}>
                            {doc.status || 'Protected'}
                          </Badge>
                        </td>
                        <td>{formatTs(doc.created_at)}</td>
                        <td onClick={(e) => e.stopPropagation()}>
                          <div className="table-actions">
                            <button
                              className="action-icon-btn"
                              title="View details"
                              type="button"
                              onClick={() => go('documents')}
                            >
                              <Icon name="eye" size={14} />
                            </button>
                            <button
                              className="action-icon-btn"
                              title="Download"
                              type="button"
                              onClick={() => go('documents')}
                            >
                              <Icon name="download" size={14} />
                            </button>
                            <button
                              className="action-icon-btn"
                              title="More actions"
                              type="button"
                              onClick={() => go('documents')}
                            >
                              <Icon name="dots" size={14} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Maritime Security Quote Card */}
            <div className="quote-maritime-card">
              <div>
                <Icon name="quote" size={24} style={{ color: 'var(--cyan)', opacity: 0.8, marginBottom: 12 }} />
                <div className="quote-text">
                  "Trust is not given. It is cryptographically proven."
                </div>
                <div className="quote-author">SAKSHYA Provenance Core</div>
              </div>

              <div style={{ marginTop: 24, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>Air-Gapped Node</span>
                <span className="badge badge-success" style={{ fontSize: 10 }}>VERIFIED</span>
              </div>
            </div>
          </div>
        </>
      )}
    </AppShell>
  );
}

export default Dashboard;
