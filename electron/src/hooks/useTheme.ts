import { useState, useEffect, useCallback } from "react";

export type ThemeMode = "light" | "dark" | "system";
// Also provide as a value export for bundlers that strip type-only exports
export const ThemeModeValues: ThemeMode[] = ["light", "dark", "system"];

const STORAGE_KEY = "hcompress-theme";

export function useTheme() {
  const [mode, setModeState] = useState<ThemeMode>(() => {
    return (localStorage.getItem(STORAGE_KEY) as ThemeMode) || "system";
  });

  const setMode = useCallback((m: ThemeMode) => {
    setModeState(m);
    localStorage.setItem(STORAGE_KEY, m);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", mode);
  }, [mode]);

  return { mode, setMode };
}
