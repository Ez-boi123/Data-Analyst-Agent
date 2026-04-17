"use client";

import { create } from "zustand";

type WorkbenchState = {
  selectedStepId: string;
  drawerOpen: boolean;
  setSelectedStepId: (selectedStepId: string) => void;
  toggleDrawer: () => void;
};

export const useWorkbenchStore = create<WorkbenchState>((set) => ({
  selectedStepId: "step-repair",
  drawerOpen: false,
  setSelectedStepId: (selectedStepId) => set({ selectedStepId }),
  toggleDrawer: () => set((state) => ({ drawerOpen: !state.drawerOpen }))
}));
