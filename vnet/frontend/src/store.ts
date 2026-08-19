/** Client-side UI state. Anything the server owns lives in TanStack Query. */

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface UiState {
  siteId: number | null;
  selectedDeviceId: string | null;
  selectedLinkId: string | null;
  paletteOpen: boolean;
  setSite: (id: number | null) => void;
  selectDevice: (id: string | null) => void;
  selectLink: (id: string | null) => void;
  setPaletteOpen: (open: boolean) => void;
}

export const useUi = create<UiState>()(
  persist(
    (set) => ({
      siteId: null,
      selectedDeviceId: null,
      selectedLinkId: null,
      paletteOpen: false,
      setSite: (siteId) =>
        set({ siteId, selectedDeviceId: null, selectedLinkId: null }),
      selectDevice: (selectedDeviceId) => set({ selectedDeviceId, selectedLinkId: null }),
      selectLink: (selectedLinkId) => set({ selectedLinkId, selectedDeviceId: null }),
      setPaletteOpen: (paletteOpen) => set({ paletteOpen }),
    }),
    { name: "uvl-ui", partialize: (state) => ({ siteId: state.siteId }) },
  ),
);
