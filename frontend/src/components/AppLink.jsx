import React from 'react';
import { go } from '../lib/app';

// Real <a href> (so right-click / open-in-new-tab / copy-link work) that
// navigates client-side. `to` uses the same form as go(): 'login', 'dashboard',
// or '' for the landing page.
export function AppLink({ to, className, children, onNavigate, ...rest }) {
  const href = to ? `/${to}` : '/';
  const handleClick = (e) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    if (onNavigate) onNavigate();
    go(to);
  };
  return (
    <a href={href} className={className} onClick={handleClick} {...rest}>
      {children}
    </a>
  );
}

export default AppLink;
