import React from 'react';
import logoSrc from '../assets/sakshya-logo.png';

// Single source of truth for the SAKSHYA brand mark.
// Import { logoSrc } for raw <img> use, or <Logo /> for the component.
export { logoSrc };

export function Logo({ className = '', alt = 'SAKSHYA', ...rest }) {
  return <img src={logoSrc} alt={alt} className={className} {...rest} />;
}

export default Logo;
