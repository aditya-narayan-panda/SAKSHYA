import React from 'react';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

export function AppShell({ children }) {
  return (
    <>
      <Sidebar />
      <div className="content-well">
        <Topbar />
        <main className="main">{children}</main>
      </div>
    </>
  );
}

export default AppShell;
