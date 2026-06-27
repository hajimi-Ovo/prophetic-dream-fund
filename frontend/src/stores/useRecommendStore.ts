import {
	getBacktest,
	getPortfolioPlan,
	getRecommendedFunds,
	getRiskAssessment,
	getTimingAdvice,
	submitRiskAssessment,
} from "@/api/recommendations";
import type {
	BacktestResponse,
	PortfolioPlanResponse,
	RecommendItem,
	RiskAssessmentRequest,
	RiskAssessmentResponse,
	TimingAdviceResponse,
} from "@/types/recommendation";
import { create } from "zustand";

interface RecommendState {
	riskAssessment: RiskAssessmentResponse | null;
	recommendations: RecommendItem[];
	timingAdvice: Record<string, TimingAdviceResponse>;
	portfolioPlan: PortfolioPlanResponse | null;
	backtestResult: BacktestResponse | null;
	loading: boolean;
	error: string | null;

	submitRiskAssessment: (data: RiskAssessmentRequest) => Promise<void>;
	fetchRiskAssessment: () => Promise<void>;
	fetchRecommendations: (strategy?: string) => Promise<void>;
	fetchTimingAdvice: (fundCode: string) => Promise<TimingAdviceResponse | null>;
	fetchPortfolioPlan: (amount: number) => Promise<void>;
	fetchBacktest: (strategy: string, period: string) => Promise<void>;
	reset: () => void;
}

const initialState = {
	riskAssessment: null,
	recommendations: [],
	timingAdvice: {},
	portfolioPlan: null,
	backtestResult: null,
	loading: false,
	error: null,
};

export const useRecommendStore = create<RecommendState>((set) => ({
	...initialState,

	submitRiskAssessment: async (data: RiskAssessmentRequest) => {
		set({ loading: true, error: null });
		try {
			const res = await submitRiskAssessment(data);
			set({ riskAssessment: res.data ?? null, loading: false });
		} catch (err) {
			const msg = err instanceof Error ? err.message : "提交问卷失败";
			set({ error: msg, loading: false });
		}
	},

	fetchRiskAssessment: async () => {
		set({ loading: true, error: null });
		try {
			const res = await getRiskAssessment();
			set({ riskAssessment: res.data ?? null, loading: false });
		} catch (err) {
			const msg = err instanceof Error ? err.message : "获取风险画像失败";
			set({ error: msg, loading: false });
		}
	},

	fetchRecommendations: async (strategy?: string) => {
		set({ loading: true, error: null });
		try {
			const res = await getRecommendedFunds(strategy);
			// Backend returns { items: [...], strategy, total }
				const data = res.data as unknown as Record<string, unknown> | null;
			set({
				recommendations: (data?.items as RecommendItem[]) ?? [],
				loading: false,
			});
		} catch (err) {
			const msg = err instanceof Error ? err.message : "获取推荐列表失败";
			set({ error: msg, loading: false });
		}
	},

	fetchTimingAdvice: async (fundCode: string) => {
		set({ error: null });
		try {
			const res = await getTimingAdvice(fundCode);
			const advice = res.data;
			if (advice) {
				set((state) => ({
					timingAdvice: { ...state.timingAdvice, [fundCode]: advice },
				}));
			}
			return advice ?? null;
		} catch (err) {
			const msg = err instanceof Error ? err.message : "获取时机建议失败";
			set({ error: msg });
			return null;
		}
	},

	fetchPortfolioPlan: async (amount: number) => {
		set({ loading: true, error: null });
		try {
			const res = await getPortfolioPlan(amount);
			set({ portfolioPlan: res.data ?? null, loading: false });
		} catch (err) {
			const msg = err instanceof Error ? err.message : "生成组合方案失败";
			set({ error: msg, loading: false });
		}
	},

	fetchBacktest: async (strategy: string, period: string) => {
		set({ loading: true, error: null });
		try {
			const res = await getBacktest(strategy, period);
			set({ backtestResult: res.data ?? null, loading: false });
		} catch (err) {
			const msg = err instanceof Error ? err.message : "回测失败";
			set({ error: msg, loading: false });
		}
	},

	reset: () => set(initialState),
}));
