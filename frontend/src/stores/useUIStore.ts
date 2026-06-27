import { create } from "zustand";

interface UIState {
	// Sidebar
	sidebarCollapsed: boolean;
	toggleSidebar: () => void;
	setSidebarCollapsed: (collapsed: boolean) => void;

	// Theme
	theme: "light" | "dark";
	setTheme: (theme: "light" | "dark") => void;

	// Global loading
	globalLoading: boolean;
	setGlobalLoading: (loading: boolean) => void;

	// Page-specific loading states
	loadingStates: Record<string, boolean>;
	setPageLoading: (page: string, loading: boolean) => void;
}

export const useUIStore = create<UIState>((set) => ({
	sidebarCollapsed: false,
	toggleSidebar: () =>
		set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
	setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),

	theme: "light",
	setTheme: (theme) => set({ theme }),

	globalLoading: false,
	setGlobalLoading: (globalLoading) => set({ globalLoading }),

	loadingStates: {},
	setPageLoading: (page, loading) =>
		set((state) => ({
			loadingStates: { ...state.loadingStates, [page]: loading },
		})),
}));
