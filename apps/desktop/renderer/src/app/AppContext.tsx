import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import { type AppInfo, type CoreStatus, getBridge, type UiState } from '../lib/bridge';

interface AppContextValue {
  info: AppInfo;
  ui: UiState;
  updateUi: (patch: Partial<UiState>) => Promise<void>;
  coreStatus: CoreStatus;
  restartCore: () => Promise<void>;
}

const AppContext = createContext<AppContextValue | null>(null);

export interface AppProviderProps {
  /** Loaded before the first render so the right screen and theme show immediately. */
  initialInfo: AppInfo;
  initialCoreStatus: CoreStatus;
  children: ReactNode;
}

/** App-wide state that comes from the main process: identity, UI preferences, core status. */
export function AppProvider({ initialInfo, initialCoreStatus, children }: AppProviderProps) {
  const [ui, setUi] = useState(initialInfo.ui);
  const [coreStatus, setCoreStatus] = useState(initialCoreStatus);

  useEffect(() => {
    const bridge = getBridge();
    const unsubscribe = bridge.core.onStatus(setCoreStatus);
    // Catch a change that happened between the initial read and subscribing.
    void bridge.core.status().then(setCoreStatus);
    return unsubscribe;
  }, []);

  const updateUi = useCallback(async (patch: Partial<UiState>) => {
    setUi(await getBridge().app.updateUiState(patch));
  }, []);

  const restartCore = useCallback(async () => {
    setCoreStatus(await getBridge().core.restart());
  }, []);

  const value = useMemo(
    () => ({ info: initialInfo, ui, updateUi, coreStatus, restartCore }),
    [initialInfo, ui, updateUi, coreStatus, restartCore],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const value = useContext(AppContext);
  if (!value) throw new Error('useApp must be used inside <AppProvider>.');
  return value;
}
