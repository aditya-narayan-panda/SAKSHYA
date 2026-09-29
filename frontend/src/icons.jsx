import React from 'react';

// A small, self-contained set of stroke-based SVG icons in the Lucide visual
// language (24x24 viewbox, round joins, currentColor). No external icon
// package is installed in this project, so these are authored locally —
// this keeps the "no emoji / no unicode glyphs as icons" rule without adding
// a new dependency. Usage: <Icon name="ledger" size={16} />
const paths = {
  dashboard: 'M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v5H3z',
  documents: 'M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z|M14 2v6h6|M8 13h8|M8 17h8|M8 9h2',
  protect: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
  shield: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
  shieldCheck: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z|M9 12l2 2 4-4',
  shieldAlert: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z|M12 8v4|M12 16h.01',
  decrypt: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z|M9.5 12.2l1.8 1.8 3.2-3.6',
  users: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2|M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8|M23 21v-2a4 4 0 0 0-3-3.87|M16 3.13a4 4 0 0 1 0 7.75',
  user: 'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2|M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8',
  userPlus: 'M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2|M8.5 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8|M20 8v6|M23 11h-6',
  search: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16|M21 21l-4.3-4.3',
  events: 'M12 8v5l3 2|M22 12a10 10 0 1 1-4.2-8.14',
  ledger: 'M21 16.5V7.5a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 7.5v9a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4a2 2 0 0 0 1-1.73z|M3.3 7l8.7 5 8.7-5|M12 22V12',
  investigate: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16|M21 21l-4.3-4.3|M8 11h6|M11 8v6',
  reports: 'M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z|M14 2v6h6|M9 13l2 2 4-4',
  crypto: 'M15.5 7.5a4 4 0 1 1-4-4|M11.5 3.5 12 3l4 4-4 4-4-4z|M2 22l7-7|M13.5 15.5 17 19l3-3-3.5-3.5|M9 15l2 2',
  system: 'M12 2v4|M12 18v4|M4.9 4.9l2.8 2.8|M16.3 16.3l2.8 2.8|M2 12h4|M18 12h4|M4.9 19.1l2.8-2.8|M16.3 7.7l2.8-2.8|M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z',
  settings: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z|M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9c.63.24 1.4.57 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z',
  logout: 'M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4|M16 17l5-5-5-5|M21 12H9',
  key: 'M21 2l-9.6 9.6|M15.5 7.5l3 3L22 7l-3-3z|M7.5 15.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z',
  lock: 'M19 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2z|M7 11V7a5 5 0 0 1 10 0v4',
  bell: 'M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9|M13.73 21a2 2 0 0 1-3.46 0',
  fingerprint: 'M12 3a7 7 0 0 0-7 7c0 3-1 5-1 5|M12 3a7 7 0 0 1 7 7c0 6 2 8 2 8|M12 8a3 3 0 0 0-3 3c0 5-2 7-2 7|M12 8a3 3 0 0 1 3 3c0 2 .5 4 1.5 5.5|M8.5 20.5A9.5 9.5 0 0 0 12 21',
  download: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4|M7 10l5 5 5-5|M12 15V3',
  upload: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4|M17 8l-5-5-5 5|M12 3v12',
  alert: 'M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z|M12 9v4|M12 17h.01',
  info: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z|M12 16v-4|M12 8h.01',
  check: 'M20 6L9 17l-5-5',
  checkCircle: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z|M9 12l2 2 4-4',
  x: 'M18 6L6 18|M6 6l12 12',
  refresh: 'M23 4v6h-6|M1 20v-6h6|M3.5 9a9 9 0 0 1 14.85-3.36L23 10|M1 14l4.65 4.36A9 9 0 0 0 20.5 15',
  menu: 'M3 12h18|M3 6h18|M3 18h18',
  chevronRight: 'M9 18l6-6-6-6',
  chevronDown: 'M6 9l6 6 6-6',
  chevronUp: 'M18 15l-6-6-6 6',
  arrowRight: 'M5 12h14|M12 5l7 7-7 7',
  plus: 'M12 5v14|M5 12h14',
  eye: 'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z|M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
  externalLink: 'M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6|M15 3h6v6|M10 14L21 3',
  fileWarning: 'M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z|M14 2v6h6|M12 11v4|M12 18h.01',
  signature: 'M3 17s2-1 4-1 3 2 5 2 3-2 5-2 4 1 4 1|M4 12l6-9 2 4 3-3 5 8',
  hash: 'M4 9h16|M4 15h16|M10 3L8 21|M16 3l-2 18',
  clock: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z|M12 6v6l4 2',
  banOff: 'M4 4l16 16|M12 3a9 9 0 0 1 9 9c0 1.8-.5 3.5-1.4 5|M6.4 6.4A9 9 0 0 0 3 12a9 9 0 0 0 9 9c1.8 0 3.5-.5 5-1.4',
  server: 'M2 3h20v6H2z|M2 15h20v6H2z|M6 7h.01|M6 19h.01',
  database: 'M12 3c4.97 0 9 1.34 9 3v12c0 1.66-4.03 3-9 3s-9-1.34-9-3V6c0-1.66 4.03-3 9-3z|M21 10c0 1.66-4.03 3-9 3s-9-1.34-9-3|M21 14c0 1.66-4.03 3-9 3s-9-1.34-9-3',
  storage: 'M22 12H2|M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z|M6 16h.01|M10 16h.01',
  layers: 'M12 2l9 5-9 5-9-5z|M3 12l9 5 9-5|M3 17l9 5 9-5',
  dots: 'M12 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2z|M19 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2z|M5 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2z',
  quote: 'M3 21c3 0 7-1 7-8V5c0-1.25-.75-2-2-2H4c-1.25 0-2 .75-2 2v6c0 1.25.75 2 2 2 0 4-2 6-2 6z|M15 21c3 0 7-1 7-8V5c0-1.25-.75-2-2-2h-4c-1.25 0-2 .75-2 2v6c0 1.25.75 2 2 2 0 4-2 6-2 6z',
  wifiOff: 'M1 1l22 22|M16.72 11.06A10.94 10.94 0 0 1 19 12.55|M5 12.55a10.94 10.94 0 0 1 5.17-2.39|M10.71 5.05A16 16 0 0 1 22.58 9|M1.42 9a15.91 15.91 0 0 1 4.7-2.88|M8.53 16.11a6 6 0 0 1 6.95 0|M12 20h.01',
  activity: 'M22 12h-4l-3 9L9 3l-3 9H2',
  lightning: 'M13 2L3 14h9l-1 8 10-12h-9l1-8z',
  helm: 'M12 4.5A7.5 7.5 0 1 1 11.9 4.5|M12 10a2 2 0 1 1-0.1 0|M12 2.5V10|M12 14v7.5|M2.5 12H10|M14 12h7.5|M5.6 5.6l4.5 4.5|M18.4 5.6l-4.5 4.5|M5.6 18.4l4.5-4.5|M18.4 18.4l-4.5-4.5',
};

export function Icon({ name, size = 16, strokeWidth = 1.8, className = '', ...rest }) {
  const d = paths[name];
  if (!d) return null;
  return (
    <svg
      className={`icon-svg ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {d.split('|').map((seg, i) => (
        <path key={i} d={seg} />
      ))}
    </svg>
  );
}

export default Icon;
