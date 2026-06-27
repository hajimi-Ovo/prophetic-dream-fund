import type { ApiResponse } from "@/types/common";
import type {
	AllocationItem,
	DashboardSummary,
	ReturnsChartData,
	RiskMetrics,
} from "@/types/holding";
import { get } from "./client";

export async function getDashboardSummary(): Promise<
	ApiResponse<DashboardSummary>
> {
	return get<DashboardSummary>("/dashboard/summary");
}

export async function getReturnsChart(
	period?: string,
): Promise<ApiResponse<ReturnsChartData[]>> {
	const params = period ? `?period=${period}` : "";
	return get<ReturnsChartData[]>(`/dashboard/returns-chart${params}`);
}

export async function getAllocation(): Promise<ApiResponse<AllocationItem[]>> {
	return get<AllocationItem[]>("/dashboard/allocation");
}

export async function getRiskMetrics(): Promise<ApiResponse<RiskMetrics>> {
	return get<RiskMetrics>("/dashboard/risk-metrics");
}
