import '@adle/design-system/base.css';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from './App';
import { AppProvider } from './app/AppContext';
import { RouterProvider } from './app/router';
import { getBridge } from './lib/bridge';

async function boot(): Promise<void> {
  const container = document.getElementById('root');
  if (!container) throw new Error('Root element missing.');

  // Read identity and preferences before the first render so the right screen
  // (welcome or library) appears immediately, with no flash of the other.
  const bridge = getBridge();
  const [info, coreStatus] = await Promise.all([bridge.app.info(), bridge.core.status()]);

  createRoot(container).render(
    <StrictMode>
      <AppProvider initialInfo={info} initialCoreStatus={coreStatus}>
        <RouterProvider initial={{ name: 'home' }}>
          <App />
        </RouterProvider>
      </AppProvider>
    </StrictMode>,
  );
}

boot().catch((error: unknown) => {
  // Last-resort message: without the bridge nothing else can render.
  const message = error instanceof Error ? error.message : 'Adle could not start.';
  const fallback = document.createElement('p');
  fallback.setAttribute('role', 'alert');
  fallback.textContent = `Adle could not start. ${message}`;
  document.body.replaceChildren(fallback);
});
