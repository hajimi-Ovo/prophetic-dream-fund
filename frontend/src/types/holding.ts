export interface Holding {
	id: number;
	fund_code: string;
	fund_name: string;
	fund_type: string;
	buy_date: string;
	amount: number;
	shares: number;
	buy_nav: number;
	latest_nav: number;
	market_value: number;
	profit_loss: number;
	profit_loss_ratio: number;
	holding_ratio: number;
	created_at: string;
	updated_at: string;
}

export interface HoldingCreate {
	fund_code: string;
	fund_name?: string;
	buy_date?: string;
	amount: number;
	shares: number;
	buy_nav?: number;
}

export interface HoldingUpdate {
	fund_name?: string;
	buy_date?: string;
	amount?: number;
	shares?: number;
	buy_nav?: number;
}

export interface HoldingResponse {
	data: Holding;
}

export interface HoldingListResponse {
	items: Holding[];
	total: number;
	summary: DashboardSummary;
}

export interface WatchlistItem {
	id: number;
	fund_code: string;
	fund_name: string;
	fund_type: string;
	latest_nav: number;
	daily_return: number;
	daily_return_ratio: number;
	added_at: string;
}

export interface WatchlistCreate {
	fund_code: string;
	fund_name?: string;
}

export interface WatchlistResponse {
	data: WatchlistItem;
}

export interface DashboardSummary {
	total_asset: number;
	total_profit: number;
	total_profit_ratio: number;
	today_profit: number;
	today_profit_ratio: number;
	holding_count: number;
}

export interface AllocationItem {
	fund_type: string;
	market_value: number;
	ratio: number;
	count: number;
}

export interface ReturnsChartData {
	date: string;
	returns: number;
	benchmark_returns?: number;
}

export interface RiskMetrics {
	volatility: number;
	sharpe_ratio: number;
	max_drawdown: number;
	beta: number;
	alpha: number;
	information_ratio?: number;
}
