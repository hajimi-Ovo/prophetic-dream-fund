import {
	getAllocation,
	getDashboardSummary,
	getReturnsChart,
	getRiskMetrics,
} from "@/api/dashboard";
import {
	createHolding,
	deleteHolding,
	getHoldings,
	updateHolding,
} from "@/api/holdings";
import {
	addToWatchlist,
	getWatchlist,
	removeFromWatchlist,
} from "@/api/watchlist";
import type {
	AllocationItem,
	DashboardSummary,
	Holding,
	HoldingCreate,
	HoldingUpdate,
	ReturnsChartData,
	RiskMetrics,
	WatchlistCreate,
	WatchlistItem,
} from "@/types/holding";
import { create } from "zustand";

interface HoldingState {
	holdings: Holding[];
	summary: DashboardSummary | null;
	allocations: AllocationItem[];
	riskMetrics: RiskMetrics | null;
	returnsData: ReturnsChartData[];
	watchlist: WatchlistItem[];
	loading: boolean;
	error: string | null;

	fetchHoldings: () => Promise<void>;
	addHolding: (data: HoldingCreate) => Promise<Holding | null>;
	updateHolding: (id: number, data: HoldingUpdate) => Promise<Holding | null>;
	deleteHolding: (id: number) => Promise<boolean>;
	fetchSummary: () => Promise<void>;
	fetchReturnsChart: (period?: string) => Promise<void>;
	fetchAllocation: () => Promise<void>;
	fetchRiskMetrics: () => Promise<void>;
	fetchWatchlist: () => Promise<void>;
	addToWatchlist: (data: WatchlistCreate) => Promise<WatchlistItem | null>;
	removeFromWatchlist: (fundCode: string) => Promise<boolean>;
	reset: () => void;
}

const initialState = {
	holdings: [],
	summary: null,
	allocations: [],
	riskMetrics: null,
	returnsData: [],
	watchlist: [],
	loading: false,
	error: null,
};

export const useHoldingStore = create<HoldingState>((set) => ({
	...initialState,

	fetchHoldings: async () => {
		set({ loading: true, error: null });
		try {
			const res = await getHoldings();
			set({
				holdings: res.data?.items ?? [],
				summary: res.data?.summary ?? null,
				loading: false,
			});
		} catch (err) {
			const msg = err instanceof Error ? err.message : "加载持仓数据失败";
			set({ error: msg, loading: false });
		}
	},

	addHolding: async (data: HoldingCreate) => {
		set({ loading: true, error: null });
		try {
			const res = await createHolding(data);
			const holding = res.data;
			if (holding) {
				set((state) => ({
					holdings: [...state.holdings, holding],
					loading: false,
				}));
			}
			return holding ?? null;
		} catch (err) {
			const msg = err instanceof Error ? err.message : "添加持仓失败";
			set({ error: msg, loading: false });
			return null;
		}
	},

	updateHolding: async (id: number, data: HoldingUpdate) => {
		set({ loading: true, error: null });
		try {
			const res = await updateHolding(id, data);
			const holding = res.data;
			if (holding) {
				set((state) => ({
					holdings: state.holdings.map((h) => (h.id === id ? holding : h)),
					loading: false,
				}));
			}
			return holding ?? null;
		} catch (err) {
			const msg = err instanceof Error ? err.message : "更新持仓失败";
			set({ error: msg, loading: false });
			return null;
		}
	},

	deleteHolding: async (id: number) => {
		set({ loading: true, error: null });
		try {
			await deleteHolding(id);
			set((state) => ({
				holdings: state.holdings.filter((h) => h.id !== id),
				loading: false,
			}));
			return true;
		} catch (err) {
			const msg = err instanceof Error ? err.message : "删除持仓失败";
			set({ error: msg, loading: false });
			return false;
		}
	},

	fetchSummary: async () => {
		set({ error: null });
		try {
			const res = await getDashboardSummary();
			set({ summary: res.data ?? null });
		} catch (err) {
			const msg = err instanceof Error ? err.message : "加载概览数据失败";
			set({ error: msg });
		}
	},

	fetchReturnsChart: async (period?: string) => {
		set({ error: null });
		try {
			const res = await getReturnsChart(period);
			// Backend returns { period, points, benchmark_points }
			const data = res.data as unknown as Record<string, unknown> | null;
			set({
				returnsData: (data?.points as ReturnsChartData[]) ?? [],
			});
		} catch (err) {
			const msg = err instanceof Error ? err.message : "加载收益数据失败";
			set({ error: msg });
		}
	},

	fetchAllocation: async () => {
		set({ error: null });
		try {
			const res = await getAllocation();
			// Backend returns { items: [...] }
			const data = res.data as unknown as Record<string, unknown> | null;
			set({ allocations: (data?.items as AllocationItem[]) ?? [] });
		} catch (err) {
			const msg = err instanceof Error ? err.message : "加载配置数据失败";
			set({ error: msg });
		}
	},

	fetchRiskMetrics: async () => {
		set({ error: null });
		try {
			const res = await getRiskMetrics();
			set({ riskMetrics: res.data ?? null });
		} catch (err) {
			const msg = err instanceof Error ? err.message : "加载风险指标失败";
			set({ error: msg });
		}
	},

	fetchWatchlist: async () => {
		set({ error: null });
		try {
			const res = await getWatchlist();
			// Backend returns { items: [...] }
			const data = res.data as unknown as Record<string, unknown> | null;
			set({ watchlist: (data?.items as WatchlistItem[]) ?? [] });
		} catch (err) {
			const msg = err instanceof Error ? err.message : "加载自选列表失败";
			set({ error: msg });
		}
	},

	addToWatchlist: async (data: WatchlistCreate) => {
		set({ error: null });
		try {
			const res = await addToWatchlist(data);
			const item = res.data;
			if (item) {
				set((state) => ({ watchlist: [...state.watchlist, item] }));
			}
			return item ?? null;
		} catch (err) {
			const msg = err instanceof Error ? err.message : "添加自选失败";
			set({ error: msg });
			return null;
		}
	},

	removeFromWatchlist: async (fundCode: string) => {
		set({ error: null });
		try {
			await removeFromWatchlist(fundCode);
			set((state) => ({
				watchlist: state.watchlist.filter((w) => w.fund_code !== fundCode),
			}));
			return true;
		} catch (err) {
			const msg = err instanceof Error ? err.message : "删除自选失败";
			set({ error: msg });
			return false;
		}
	},

	reset: () => set(initialState),
}));
