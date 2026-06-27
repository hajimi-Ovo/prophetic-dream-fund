import dayjs from "dayjs";

/**
 * Format a number as Chinese Yuan currency string.
 * Returns "--" if the input is null or undefined.
 * @example formatCurrency(1234.56) => "¥1,234.56"
 */
export function formatCurrency(amount: number | null | undefined): string {
	if (amount === null || amount === undefined) return "--";
	const formatted = Math.abs(amount).toLocaleString("zh-CN", {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2,
	});
	return amount < 0 ? `-¥${formatted}` : `¥${formatted}`;
}

/**
 * Format a ratio as percentage with sign.
 * Returns "--" if the input is null or undefined.
 * @example formatPercent(0.1234) => "+12.34%"
 * @example formatPercent(-0.052) => "-5.20%"
 */
export function formatPercent(ratio: number | null | undefined, decimals = 2): string {
	if (ratio === null || ratio === undefined) return "--";
	const percentage = (ratio * 100).toFixed(decimals);
	const num = Number.parseFloat(percentage);
	return num > 0 ? `+${percentage}%` : `${percentage}%`;
}

/**
 * Format a date as YYYY-MM-DD string.
 * Returns "--" if the input is null or undefined.
 * @example formatDate("2026-06-27") => "2026-06-27"
 */
export function formatDate(date: string | Date | null | undefined): string {
	if (!date) return "--";
	return dayjs(date).format("YYYY-MM-DD");
}

/**
 * Format a large number with Chinese units (亿/万).
 * Returns "--" if the input is null or undefined.
 * @example formatLargeNumber(123000000) => "1.23亿"
 * @example formatLargeNumber(523000) => "52.30万"
 * @example formatLargeNumber(500) => "500.00"
 */
export function formatLargeNumber(num: number | null | undefined): string {
	if (num === null || num === undefined) return "--";
	const absNum = Math.abs(num);
	const sign = num < 0 ? "-" : "";

	if (absNum >= 100000000) {
		return `${sign}${(absNum / 100000000).toFixed(2)}亿`;
	}
	if (absNum >= 10000) {
		return `${sign}${(absNum / 10000).toFixed(2)}万`;
	}
	return `${sign}${absNum.toFixed(2)}`;
}
