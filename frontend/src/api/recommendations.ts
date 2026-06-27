import type { ApiResponse } from "@/types/common";
import type {
	BacktestResponse,
	PortfolioPlanResponse,
	RecommendItem,
	RiskAssessmentRequest,
	RiskAssessmentResponse,
	TimingAdviceResponse,
} from "@/types/recommendation";
import { get, post } from "./client";

export async function submitRiskAssessment(
	data: RiskAssessmentRequest,
): Promise<ApiResponse<RiskAssessmentResponse>> {
	return post<RiskAssessmentResponse>("/recommend/risk-assessment", data);
}

export async function getRiskAssessment(): Promise<
	ApiResponse<RiskAssessmentResponse>
> {
	return get<RiskAssessmentResponse>("/recommend/risk-assessment");
}

export async function getRecommendedFunds(
	strategy?: string,
	limit?: number,
): Promise<ApiResponse<RecommendItem[]>> {
	const params = new URLSearchParams();
	if (strategy) params.append("strategy", strategy);
	if (limit) params.append("limit", String(limit));
	const qs = params.toString();
	return get<RecommendItem[]>(`/recommend/funds${qs ? `?${qs}` : ""}`);
}

export async function getTimingAdvice(
	fundCode: string,
): Promise<ApiResponse<TimingAdviceResponse>> {
	return get<TimingAdviceResponse>(`/recommend/timing/${fundCode}`);
}

export async function getPortfolioPlan(
	totalAmount: number,
): Promise<ApiResponse<PortfolioPlanResponse>> {
	return get<PortfolioPlanResponse>(
		`/recommend/portfolio?total_amount=${totalAmount}`,
	);
}

export async function getBacktest(
	strategy: string,
	period: string,
): Promise<ApiResponse<BacktestResponse>> {
	return get<BacktestResponse>(
		`/recommend/backtest?strategy=${strategy}&period=${period}`,
	);
}
