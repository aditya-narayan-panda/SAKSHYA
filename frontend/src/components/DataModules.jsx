import React from 'react';
import { Icon } from '../icons';

// items: [{ value, label, description, tone, icon, change, sparkline }]
export function DataModules({ items }) {
  return (
    <div className="data-modules">
      {items.map((it) => {
        let defaultIcon = 'protect';
        if (it.label.toLowerCase().includes('document')) defaultIcon = 'documents';
        else if (it.label.toLowerCase().includes('recipient')) defaultIcon = 'users';
        else if (it.label.toLowerCase().includes('event') || it.label.toLowerCase().includes('decryption')) defaultIcon = 'events';
        else if (it.label.toLowerCase().includes('ledger') || it.label.toLowerCase().includes('block')) defaultIcon = 'ledger';
        else if (it.label.toLowerCase().includes('investigation')) defaultIcon = 'investigate';
        else if (it.label.toLowerCase().includes('report')) defaultIcon = 'reports';

        const iconName = it.icon || defaultIcon;

        return (
          <div className="data-module" key={it.label}>
            <div className="data-module-top">
              <div className="data-module-icon">
                <Icon name={iconName} size={18} />
              </div>
              {it.change && (
                <span className="badge badge-success" style={{ fontSize: 10, padding: '2px 6px' }}>
                  {it.change}
                </span>
              )}
            </div>
            <div className={`data-module-value ${it.tone || ''}`}>{it.value}</div>
            <div className="data-module-label">{it.label}</div>
            {it.description && <div className="data-module-desc">{it.description}</div>}
          </div>
        );
      })}
    </div>
  );
}

export default DataModules;
