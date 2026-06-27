export interface FundBasic {
	code: string;
	name: string;
	type: string;
	scale?: number;
	fee_rate?: number;
	company?: string;
	latest_nav?: number;
	daily_return?: number;
	ytd_return?: number;
	one_year_return?: number;
}

export interface FundNavInfo {
	latest_nav: number;
	accumulated_nav?: number;
	daily_return?: number;
	weekly_return?: number;
	monthly_return?: number;
	three_month_return?: number;
	six_month_return?: number;
	ytd_return?: number;
	one_year_return?: number;
	three_year_return?: number;
	five_year_return?: number;
}

export interface FundManager {
	name: string;
	start_date?: string;
	tenure_return?: number;
	description?: string;
}

export interface FundRiskMetrics {
	max_drawdown?: number;
	sharpe_ratio?: number;
	volatility?: number;
	alpha?: number;
	beta?: number;
}

export interface FundDetail {
	basic: FundBasic;
	nav: FundNavInfo;
	manager?: FundManager;
	risk_metrics?: FundRiskMetrics;
}

export interface NavHistoryPoint {
	date: string;
	nav: number;
	accumulated_nav?: number;
}

export interface NavHistoryResponse {
	period: string;
	points: NavHistoryPoint[];
}

export interface FundFilterParams {
	type?: string;
	min_scale?: number;
	max_scale?: number;
	max_fee?: number;
	manager?: string;
	company?: string;
	sort_by?: string;
	order?: "asc" | "desc";
	page?: number;
	page_size?: number;
}

export interface CompareResult {
	funds: FundCompareItem[];
	overlay_points: Record<string, NavHistoryPoint[]>;
}

export interface FundCompareItem {
	code: string;
	name: string;
	latest_nav?: number;
	daily_return?: number;
	one_year_return?: number;
	max_drawdown?: number;
	sharpe_ratio?: number;
}

export interface FundPortfolioItem {
	stock_code: string;
	stock_name: string;
	ratio: number;
}
