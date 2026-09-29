import React from 'react';
import { Icon } from '../icons';

export function SearchBox({ value, onChange, placeholder }) {
  return (
    <div className="search-box">
      <Icon name="search" size={14} />
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
    </div>
  );
}

export function Pager({ shown, total, noun }) {
  return (
    <div className="pager">
      Showing 1–{shown} of {total}
      {noun ? ` ${noun}` : ''}
    </div>
  );
}
