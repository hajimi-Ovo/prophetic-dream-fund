import type { NavHistoryPoint } from "@/types/fund";
import type { EChartsOption } from "echarts";

/**
 * Create ECharts option for a net asset value (NAV) line chart.
 */
export function createNavLineOption(
	data: NavHistoryPoint[],
	title?: string,
): EChartsOption {
	return {
		title: title
			? {
					text: title,
					left: "center",
					textStyle: { fontSize: 14 },
				}
			: undefined,
		tooltip: {
			trigger: "axis",
			formatter: (params: unknown) => {
				const items = params as Array<{
					axisValueLabel: string;
					value: number;
					seriesName: string;
				}>;
				if (!items || items.length === 0) return "";
				let result = `<div>${items[0].axisValueLabel}</div>`;
				for (const item of items) {
					const val =
						item.value !== null && item.value !== undefined
							? item.value.toFixed(4)
							: "--";
					result += `<div>${item.seriesName}: ${val}</div>`;
				}
				return result;
			},
		},
		legend: {
			data: data.some((d) => d.accumulated_nav !== undefined)
				? ["单位净值", "累计净值"]
				: ["单位净值"],
			bottom: 0,
		},
		grid: {
			left: "3%",
			right: "4%",
			bottom: "12%",
			top: title ? "15%" : "8%",
			containLabel: true,
		},
		xAxis: {
			type: "category",
			data: data.map((d) => d.date),
			boundaryGap: false,
		},
		yAxis: {
			type: "value",
			name: "净值",
			scale: true,
		},
		series: [
			{
				name: "单位净值",
				type: "line",
				data: data.map((d) => d.nav),
				smooth: true,
				showSymbol: false,
				lineStyle: { color: "#1677ff", width: 2 },
				itemStyle: { color: "#1677ff" },
				areaStyle: {
					color: {
						type: "linear",
						x: 0,
						y: 0,
						x2: 0,
						y2: 1,
						colorStops: [
							{ offset: 0, color: "rgba(22, 119, 255, 0.25)" },
							{ offset: 1, color: "rgba(22, 119, 255, 0.02)" },
						],
					},
				},
			},
			...(data.some((d) => d.accumulated_nav !== undefined)
				? [
						{
							name: "累计净值" as const,
							type: "line" as const,
							data: data.map((d) => d.accumulated_nav),
							smooth: true,
							showSymbol: false,
							lineStyle: {
								color: "#52c41a",
								width: 2,
								type: "dashed" as const,
							},
							itemStyle: { color: "#52c41a" },
						},
					]
				: []),
		],
	};
}

/**
 * Create ECharts option for a comparison overlay chart (two funds).
 */
export function createCompareOverlayOption(
	seriesA: { name: string; data: NavHistoryPoint[] },
	seriesB: { name: string; data: NavHistoryPoint[] },
): EChartsOption {
	const allDates = Array.from(
		new Set([
			...seriesA.data.map((d) => d.date),
			...seriesB.data.map((d) => d.date),
		]),
	).sort();

	return {
		tooltip: {
			trigger: "axis",
			formatter: (params: unknown) => {
				const items = params as Array<{
					axisValueLabel: string;
					value: number;
					seriesName: string;
				}>;
				if (!items || items.length === 0) return "";
				let result = `<div>${items[0].axisValueLabel}</div>`;
				for (const item of items) {
					const val =
						item.value !== null && item.value !== undefined
							? item.value.toFixed(4)
							: "--";
					result += `<div>${item.seriesName}: ${val}</div>`;
				}
				return result;
			},
		},
		legend: {
			data: [seriesA.name, seriesB.name],
			bottom: 0,
		},
		grid: {
			left: "3%",
			right: "4%",
			bottom: "12%",
			top: "8%",
			containLabel: true,
		},
		xAxis: {
			type: "category",
			data: allDates,
			boundaryGap: false,
		},
		yAxis: {
			type: "value",
			name: "净值",
			scale: true,
		},
		series: [
			{
				name: seriesA.name,
				type: "line",
				data: allDates.map((date) => {
					const point = seriesA.data.find((d) => d.date === date);
					return point ? point.nav : null;
				}),
				smooth: true,
				showSymbol: false,
				connectNulls: true,
				lineStyle: { color: "#1677ff", width: 2 },
				itemStyle: { color: "#1677ff" },
			},
			{
				name: seriesB.name,
				type: "line",
				data: allDates.map((date) => {
					const point = seriesB.data.find((d) => d.date === date);
					return point ? point.nav : null;
				}),
				smooth: true,
				showSymbol: false,
				connectNulls: true,
				lineStyle: { color: "#f5222d", width: 2 },
				itemStyle: { color: "#f5222d" },
			},
		],
	};
}

/**
 * Create ECharts option for a pie chart (e.g., asset allocation).
 */
export function createPieOption(
	data: { name: string; value: number }[],
): EChartsOption {
	return {
		tooltip: {
			trigger: "item",
			formatter: "{b}: {c} ({d}%)",
		},
		legend: {
			orient: "vertical",
			left: "left",
		},
		series: [
			{
				type: "pie",
				radius: ["40%", "70%"],
				data,
				emphasis: {
					itemStyle: {
						shadowBlur: 10,
						shadowOffsetX: 0,
						shadowColor: "rgba(0, 0, 0, 0.5)",
					},
				},
				label: {
					formatter: "{b}: {d}%",
				},
			},
		],
	};
}

/**
 * Create ECharts option for a returns chart with optional benchmark comparison.
 */
export function createReturnsChartOption(
	data: { date: string; returns: number }[],
	benchmark?: { date: string; returns: number }[],
): EChartsOption {
	return {
		tooltip: {
			trigger: "axis",
			valueFormatter: (value: unknown) =>
				typeof value === "number" && !Number.isNaN(value)
					? `${value.toFixed(2)}%`
					: `${value ?? "--"}`,
		},
		legend: {
			data: benchmark ? ["组合收益", "基准收益"] : ["组合收益"],
		},
		xAxis: {
			type: "category",
			data: data.map((d) => d.date),
		},
		yAxis: {
			type: "value",
			name: "收益率",
			axisLabel: {
				formatter: "{value}%",
			},
		},
		series: [
			{
				name: "组合收益",
				type: "line",
				data: data.map((d) => d.returns),
				smooth: true,
				areaStyle: {
					opacity: 0.1,
				},
			},
			...(benchmark
				? [
						{
							name: "基准收益" as const,
							type: "line" as const,
							data: benchmark.map((b) => b.returns),
							smooth: true,
							lineStyle: { type: "dashed" as const },
						},
					]
				: []),
		],
	};
}
