export interface RiskAssessmentRequest {
	risk_tolerance: string;
	investment_horizon: string;
	return_expectation: string;
}

export interface RiskAssessmentResponse {
	risk_level: string;
	risk_score: number;
	investment_horizon: string;
	return_expectation: string;
	max_drawdown_tolerance: number;
	assessed_at: string;
	allocation_suggestions: AllocationSuggestion[];
}

export interface AllocationSuggestion {
	fund_type: string;
	ratio: number;
	description: string;
}

export interface RecommendItem {
	id: number;
	fund_code: string;
	fund_name: string;
	fund_type: string;
	score: number;
	rank: number;
	reasons: string[];
	suggested_action: "buy" | "wait" | "hold" | "sell";
	suggested_amount: number;
	expected_return: number;
	risk_level: string;
}

export interface TimingAdviceResponse {
	fund_code: string;
	fund_name: string;
	signal: "green" | "yellow" | "red";
	signal_label: string;
	valuation_percentile: number;
	trend_signal: string;
	reasons: string[];
	suggested_action: string;
	indicators: TimingIndicator[];
}

export interface TimingIndicator {
	name: string;
	value: number;
	signal: "bullish" | "bearish" | "neutral";
	label: string;
}

export interface PortfolioPlanResponse {
	risk_level: string;
	total_amount: number;
	expected_return: number;
	expected_risk: number;
	max_drawdown: number;
	allocations: PortfolioAllocationItem[];
	rebalance_suggestions: RebalanceSuggestion[];
}

export interface PortfolioAllocationItem {
	fund_type: string;
	fund_name: string;
	fund_code: string;
	ratio: number;
	amount: number;
	reason: string;
}

export interface RebalanceSuggestion {
	fund_code: string;
	fund_name: string;
	current_ratio: number;
	target_ratio: number;
	action: "buy" | "sell";
	amount: number;
}

export interface BacktestResponse {
	annual_return: number;
	total_return: number;
	volatility: number;
	sharpe_ratio: number;
	max_drawdown: number;
	win_rate: number;
	nav_points: BacktestNavPoint[];
}

export interface BacktestNavPoint {
	date: string;
	strategy_nav: number;
	benchmark_nav: number;
}
