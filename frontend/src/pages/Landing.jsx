import React, { useEffect, useRef, useState } from 'react';
import { logoSrc as logo } from '../components/Logo';
import { Icon } from '../icons';
import { api } from '../api';
import { AppLink } from '../components/AppLink';
import { useAuthedRecipient } from '../lib/app';

// Navigation: Home / Features / How It Works / Security / About + Officer Login.
const NAV_LINKS = [
  { label: 'Home', href: '#home', id: 'home' },
  { label: 'Features', href: '#features', id: 'features' },
  { label: 'How It Works', href: '#workflow', id: 'workflow' },
  { label: 'Security', href: '#security', id: 'security' },
  { label: 'About', href: '#about', id: 'about' },
];

const CAPABILITIES = [
  { icon: 'lock', title: 'End-to-End Protection', desc: 'Secure documents with post-quantum cryptography.' },
  { icon: 'ledger', title: 'Immutable Provenance', desc: 'Every action recorded on a tamper-proof ledger.' },
  { icon: 'fingerprint', title: 'Invisible Attribution', desc: 'Cryptographic watermarking for source identification.' },
  { icon: 'shieldCheck', title: 'Leak Investigation', desc: 'Trace and attribute leaked documents with forensic reports.' },
];

const WORKFLOW = [
  { icon: 'documents', name: 'Protect', desc: 'Encrypt & watermark' },
  { icon: 'users', name: 'Distribute', desc: 'Authorize recipients' },
  { icon: 'eye', name: 'Monitor', desc: 'Track decryption events' },
  { icon: 'search', name: 'Investigate', desc: 'Trace leaks & generate reports' },
];

const SECURITY_ITEMS = [
  { name: 'ML-KEM-768', desc: 'Post-quantum key encapsulation' },
  { name: 'ML-DSA-65', desc: 'Post-quantum digital signatures' },
  { name: 'SHA-256', desc: 'Content hashing and integrity' },
  { name: 'Immutable Ledger', desc: 'Tamper-evident local event chain' },
];

function useBackendStatus() {
  const [status, setStatus] = useState({ state: 'loading', crypto: null });
  useEffect(() => {
    let alive = true;
    Promise.all([
      api.system.health().then(() => true).catch(() => false),
      api.system.cryptoStatus().catch(() => null),
    ]).then(([up, crypto]) => {
      if (alive) setStatus({ state: up ? 'up' : 'down', crypto: up ? crypto : null });
    });
    return () => { alive = false; };
  }, []);
  return status;
}

function useReveal() {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === 'undefined') return undefined;
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && e.target.classList.add('revealed')),
      { threshold: 0.12 }
    );
    el.querySelectorAll('.reveal').forEach((n) => io.observe(n));
    return () => io.disconnect();
  }, []);
  return ref;
}

export function Landing() {
  const recipient = useAuthedRecipient();
  const [menu, setMenu] = useState(false);
  const [activeSection, setActiveSection] = useState('home');
  const { state: backendState, crypto } = useBackendStatus();
  const rootRef = useReveal();

  const closeMenu = () => setMenu(false);
  const primaryTo = recipient ? 'dashboard' : 'login';

  const scrollTo = (id) => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="ld" id="home" ref={rootRef}>
      {/* ---------------- Header ---------------- */}
      <header className="ld-header">
        <div className="ld-wrap ld-header-row">
          <AppLink to="" className="ld-brand" onNavigate={closeMenu} aria-label="SAKSHYA Home">
            <img src={logo} alt="SAKSHYA" />
            <span className="ld-brand-text">
              <b>SAKSHYA</b>
              <small>
                Cryptographic Document Attribution
                <br />
                &amp; Provenance System
              </small>
            </span>
          </AppLink>

          <nav className={`ld-links${menu ? ' open' : ''}`} aria-label="Primary Navigation">
            {NAV_LINKS.map((link) => (
              <a
                key={link.id}
                href={link.href}
                className={activeSection === link.id ? 'active' : ''}
                onClick={() => {
                  setActiveSection(link.id);
                  closeMenu();
                }}
              >
                {link.label}
              </a>
            ))}
          </nav>

          <div className="ld-header-actions">
            <AppLink to={primaryTo} className="ld-login-btn">
              <Icon name="user" size={18} />
              {recipient ? 'Officer Dashboard' : 'Officer Login'}
              <Icon name="arrowRight" size={18} strokeWidth={2} />
            </AppLink>
            <button
              className="ld-burger"
              type="button"
              aria-label={menu ? 'Close menu' : 'Open menu'}
              onClick={() => setMenu((m) => !m)}
            >
              <Icon name={menu ? 'x' : 'menu'} size={24} />
            </button>
          </div>
        </div>
      </header>

      {/* ---------------- Hero ---------------- */}
      <section className="ld-hero">
        <div className="ld-hero-bg" aria-hidden="true" />
        <div className="ld-wrap ld-hero-inner">
          <div className="ld-pill">
            <span className="ld-pill-dot" />
            <span>Trusted &bull; Secure &bull; Tamper-Proof &bull; Accountable</span>
          </div>
          <h1>
            Cryptographic Document{' '}
            <br />
            Attribution <span>&amp; Provenance System</span>
          </h1>
          <p className="ld-hero-sub">
            SAKSHYA ensures the origin, integrity, and accountability of sensitive documents using post-quantum
            cryptography, immutable ledger, and invisible watermarking.
          </p>
          <div className="ld-cta-row">
            <AppLink to={primaryTo} className="ld-btn ld-btn-primary">
              Get Started
              <Icon name="arrowRight" size={18} strokeWidth={2} />
            </AppLink>
            <button type="button" className="ld-btn ld-btn-outline" onClick={() => scrollTo('workflow')}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M6 3.5v17a1 1 0 0 0 1.5.86l14-8.5a1 1 0 0 0 0-1.72l-14-8.5A1 1 0 0 0 6 3.5z" />
              </svg>
              Watch Demo
            </button>
          </div>
        </div>
      </section>

      {/* ---------------- Capabilities + How it works ---------------- */}
      <section className="ld-wrap ld-below" id="features">
        <div className="ld-cap-grid">
          {CAPABILITIES.map((cap) => (
            <div className="ld-cap reveal" key={cap.title}>
              <span className="ld-icon-circle">
                <Icon name={cap.icon} size={26} strokeWidth={1.6} />
              </span>
              <div className="ld-cap-text">
                <h3>{cap.title}</h3>
                <p>{cap.desc}</p>
              </div>
              <Icon name="chevronRight" size={18} className="ld-cap-chev" />
            </div>
          ))}
        </div>

        <div className="ld-how reveal" id="workflow">
          <div className="ld-how-intro">
            <h2>How SAKSHYA Works</h2>
            <span className="ld-how-rule" aria-hidden="true" />
            <p>From protection to provenance &mdash; a complete lifecycle for secure document management.</p>
          </div>
          <div className="ld-how-flow" role="list">
            {WORKFLOW.map((step, i) => (
              <React.Fragment key={step.name}>
                <div className="ld-stage" role="listitem">
                  <span className="ld-icon-circle ld-icon-circle-sm">
                    <Icon name={step.icon} size={24} strokeWidth={1.6} />
                  </span>
                  <b>
                    {i + 1}. {step.name}
                  </b>
                  <small>{step.desc}</small>
                </div>
                {i < WORKFLOW.length - 1 && (
                  <span className="ld-stage-link" aria-hidden="true">
                    <Icon name="arrowRight" size={26} strokeWidth={1.5} />
                  </span>
                )}
              </React.Fragment>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------- Security + live status ---------------- */}
      <section className="ld-wrap ld-security" id="security">
        <div className="ld-section-head reveal">
          <h2>Built Around Verifiable Security</h2>
          <p>Only the cryptography this platform actually runs &mdash; verified live below.</p>
        </div>
        <div className="ld-sec-grid">
          {SECURITY_ITEMS.map((item) => (
            <div className="ld-sec-item reveal" key={item.name}>
              <code>{item.name}</code>
              <span>{item.desc}</span>
            </div>
          ))}
        </div>
        <div className="ld-live-grid reveal">
          <div className="ld-live-card">
            <small>Backend</small>
            <b className={backendState === 'up' ? 'ok' : backendState === 'down' ? 'bad' : ''}>
              {backendState === 'up' ? 'Operational' : backendState === 'down' ? 'Offline' : 'Checking…'}
            </b>
          </div>
          <div className="ld-live-card">
            <small>Key Encapsulation</small>
            <b>{crypto ? crypto.kem : '—'}</b>
          </div>
          <div className="ld-live-card">
            <small>Digital Signature</small>
            <b>{crypto ? crypto.signature : '—'}</b>
          </div>
          <div className="ld-live-card">
            <small>Ledger</small>
            <b>{crypto ? 'Local • Verified' : '—'}</b>
          </div>
        </div>
      </section>

      {/* ---------------- Footer ---------------- */}
      <footer className="ld-footer" id="about">
        <div className="ld-wrap">
          <div className="ld-footer-row">
            <div className="ld-footer-brand">
              <img src={logo} alt="SAKSHYA" />
              <p>
                SAKSHYA is a defence-grade cryptographic document attribution and digital provenance platform
                engineered for classified sovereign infrastructure.
              </p>
            </div>
            <div className="ld-footer-col">
              <b>Navigation</b>
              <a href="#features">Features</a>
              <a href="#workflow">How It Works</a>
              <a href="#security">Security</a>
            </div>
            <div className="ld-footer-col">
              <b>Officer Portal</b>
              <AppLink to={primaryTo}>{recipient ? 'Operational Console' : 'Officer Login'}</AppLink>
              <span>Air-Gapped Local Console</span>
            </div>
          </div>
          <div className="ld-footer-bottom">
            <div>&copy; {new Date().getFullYear()} SAKSHYA Platform. Sovereign Cryptographic Attribution System.</div>
            <div className="ld-mono">CLASSIFIED WORKSTATION &bull; SAKSHYA v2.0.0</div>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default Landing;
