import {
	compareFunds as compareFundsApi,
	filterFunds as filterFundsApi,
	getFundDetail as getFundDetailApi,
	getFundPortfolio as getFundPortfolioApi,
	getNavHistory as getNavHistoryApi,
	searchFunds as searchFundsApi,
} from "@/api/funds";
import type {
	FundBasic,
	FundCompareItem,
	FundDetail,
	FundFilterParams,
	FundPortfolioItem,
	NavHistoryPoint,
	NavHistoryResponse,
} from "@/types/fund";
import { create } from "zustand";

interface MarketState {
	// Search & Filter
	fundList: FundBasic[];
	searchKeyword: string;
	filters: FundFilterParams;
	total: number;
	page: number;

	// Detail
	fundDetail: FundDetail | null;
	navHistory: NavHistoryResponse | null;
	portfolio: FundPortfolioItem[];

	// Compare
	compareList: FundCompareItem[];
	compareOverlay: Record<string, NavHistoryPoint[]>;

	// State
	loading: boolean;
	error: string | null;

	// Actions
	searchFunds: (keyword: string, page?: number) => Promise<void>;
	filterFunds: (filters: FundFilterParams) => Promise<void>;
	setFilters: (filters: Partial<FundFilterParams>) => void;
	fetchFundDetail: (code: string) => Promise<void>;
	fetchNavHistory: (code: string, period: string) => Promise<void>;
	fetchPortfolio: (code: string) => Promise<void>;
	compareFunds: (codes: string[]) => Promise<void>;
	clearCompare: () => void;
	reset: () => void;
}

const initialState = {
	fundList: [] as FundBasic[],
	searchKeyword: "",
	filters: {} as FundFilterParams,
	total: 0,
	page: 1,
	fundDetail: null as FundDetail | null,
	navHistory: null as NavHistoryResponse | null,
	portfolio: [] as FundPortfolioItem[],
	compareList: [] as FundCompareItem[],
	compareOverlay: {} as Record<string, NavHistoryPoint[]>,
	loading: false,
	error: null as string | null,
};

export const useMarketStore = create<MarketState>((set) => ({
	...initialState,

	searchFunds: async (keyword: string, page = 1) => {
		set({ loading: true, error: null, searchKeyword: keyword, page });
		try {
			const res = await searchFundsApi(keyword, page);
			set({
				fundList: res.data?.items ?? [],
				total: res.data?.total ?? 0,
				page: res.data?.page ?? 1,
				loading: false,
			});
		} catch {
			set({ error: "搜索基金失败，请稍后重试", loading: false });
		}
	},

	filterFunds: async (filters: FundFilterParams) => {
		set({ loading: true, error: null, filters });
		try {
			const res = await filterFundsApi(filters);
			set({
				fundList: res.data?.items ?? [],
				total: res.data?.total ?? 0,
				page: res.data?.page ?? 1,
				loading: false,
			});
		} catch {
			set({ error: "筛选基金失败，请稍后重试", loading: false });
		}
	},

	setFilters: (partial: Partial<FundFilterParams>) => {
		set((state) => ({
			filters: { ...state.filters, ...partial },
		}));
	},

	fetchFundDetail: async (code: string) => {
		set({ loading: true, error: null });
		try {
			const res = await getFundDetailApi(code);
			set({ fundDetail: res.data ?? null, loading: false });
		} catch {
			set({ error: "获取基金详情失败，请稍后重试", loading: false });
		}
	},

	fetchNavHistory: async (code: string, period: string) => {
		set({ loading: true, error: null });
		try {
			const res = await getNavHistoryApi(code, period);
			set({ navHistory: res.data ?? null, loading: false });
		} catch {
			set({ error: "获取净值历史失败，请稍后重试", loading: false });
		}
	},

	fetchPortfolio: async (code: string) => {
		set({ loading: true, error: null });
		try {
			const res = await getFundPortfolioApi(code);
			set({ portfolio: res.data ?? [], loading: false });
		} catch {
			set({ error: "获取持仓数据失败，请稍后重试", loading: false });
		}
	},

	compareFunds: async (codes: string[]) => {
		set({ loading: true, error: null });
		try {
			const res = await compareFundsApi(codes);
			set({
				compareList: res.data?.funds ?? [],
				compareOverlay: res.data?.overlay_points ?? {},
				loading: false,
			});
		} catch {
			set({ error: "基金对比失败，请稍后重试", loading: false });
		}
	},

	clearCompare: () => {
		set({
			compareList: [],
			compareOverlay: {},
		});
	},

	reset: () => set(initialState),
}));
