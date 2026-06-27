/** Fund type codes mapped to Chinese names */
export const FUND_TYPES: Record<string, string> = {
	stock: "股票型",
	mixed: "混合型",
	bond: "债券型",
	money: "货币型",
	index: "指数型",
	qdii: "QDII",
	other: "其他",
};

/** Color mapping for fund types (used in charts) */
export const FUND_TYPE_COLORS: Record<string, string> = {
	stock: "#f5222d",
	mixed: "#fa8c16",
	bond: "#52c41a",
	money: "#1890ff",
	index: "#722ed1",
	qdii: "#13c2c2",
	other: "#8c8c8c",
};

/** Risk level mapping */
export const RISK_LEVELS: Record<string, string> = {
	conservative: "保守型",
	moderate: "稳健型",
	aggressive: "进取型",
};

/** Investment horizon mapping */
export const INVESTMENT_HORIZONS: Record<string, string> = {
	short: "短期 (1年以内)",
	medium: "中期 (1-3年)",
	long: "长期 (3年以上)",
};

/** Return expectation mapping */
export const RETURN_EXPECTATIONS: Record<string, string> = {
	conservative: "保守收益 (3%-6%)",
	moderate: "稳健收益 (6%-12%)",
	aggressive: "进取收益 (12%以上)",
};

/** Time period options for charts */
export const PERIOD_OPTIONS = [
	{ label: "近1月", value: "1M" },
	{ label: "近3月", value: "3M" },
	{ label: "近6月", value: "6M" },
	{ label: "近1年", value: "1Y" },
	{ label: "近3年", value: "3Y" },
	{ label: "近5年", value: "5Y" },
	{ label: "成立以来", value: "ALL" },
] as const;
