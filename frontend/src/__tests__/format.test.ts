import { describe, expect, it } from "vitest";
import {
	formatCurrency,
	formatDate,
	formatLargeNumber,
	formatPercent,
} from "../utils/format";

describe("formatCurrency", () => {
	it("formats positive amounts", () => {
		expect(formatCurrency(1234.56)).toBe("¥1,234.56");
	});

	it("formats zero", () => {
		expect(formatCurrency(0)).toBe("¥0.00");
	});

	it("formats large amounts", () => {
		expect(formatCurrency(1000000)).toBe("¥1,000,000.00");
	});
});

describe("formatPercent", () => {
	it("formats positive percentages", () => {
		expect(formatPercent(0.1234)).toBe("+12.34%");
	});

	it("formats negative percentages", () => {
		expect(formatPercent(-0.052)).toBe("-5.20%");
	});

	it("formats with custom decimals", () => {
		expect(formatPercent(0.1, 1)).toBe("+10.0%");
	});
});

describe("formatDate", () => {
	it("formats ISO date string", () => {
		expect(formatDate("2026-06-27")).toBe("2026-06-27");
	});
});

describe("formatLargeNumber", () => {
	it("formats numbers in yi", () => {
		expect(formatLargeNumber(123000000)).toBe("1.23亿");
	});

	it("formats numbers in wan", () => {
		expect(formatLargeNumber(523000)).toBe("52.30万");
	});

	it("returns plain number for small values", () => {
		expect(formatLargeNumber(123)).toBe("123.00");
	});
});
