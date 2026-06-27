import type {
	ApiResponse,
	PaginatedData,
	PaginatedResponse,
} from "@/types/common";
import type {
	CompareResult,
	FundBasic,
	FundDetail,
	FundFilterParams,
	FundPortfolioItem,
	NavHistoryResponse,
} from "@/types/fund";
import { get } from "./client";

export async function searchFunds(
	keyword: string,
	page = 1,
	page_size = 20,
): Promise<PaginatedResponse<FundBasic>> {
	return get<PaginatedData<FundBasic>>(
		`/funds/search?keyword=${encodeURIComponent(keyword)}&page=${page}&page_size=${page_size}`,
	);
}

export async function filterFunds(
	params: FundFilterParams,
): Promise<PaginatedResponse<FundBasic>> {
	const query = new URLSearchParams();
	for (const [k, v] of Object.entries(params)) {
		if (v !== undefined && v !== "") {
			query.append(k, String(v));
		}
	}
	return get<PaginatedData<FundBasic>>(`/funds/filter?${query.toString()}`);
}

export async function getFundDetail(
	code: string,
): Promise<ApiResponse<FundDetail>> {
	return get<FundDetail>(`/funds/${code}`);
}

export async function getNavHistory(
	code: string,
	period = "1m",
): Promise<ApiResponse<NavHistoryResponse>> {
	return get<NavHistoryResponse>(`/funds/${code}/nav-history?period=${period}`);
}

export async function getFundPortfolio(
	code: string,
): Promise<ApiResponse<FundPortfolioItem[]>> {
	return get<FundPortfolioItem[]>(`/funds/${code}/portfolio`);
}

export async function compareFunds(
	codes: string[],
): Promise<ApiResponse<CompareResult>> {
	return get<CompareResult>(`/funds/compare?codes=${codes.join(",")}`);
}
