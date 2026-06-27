import { useHoldingStore } from "@/stores/useHoldingStore";
import { FUND_TYPES, FUND_TYPE_COLORS } from "@/utils/constants";
import { formatCurrency, formatPercent } from "@/utils/format";
import { Card, Spin, Typography } from "antd";
import type { EChartsOption } from "echarts";
import ReactECharts from "echarts-for-react";
import { useEffect } from "react";

const { Text } = Typography;

function AllocationPie() {
	const { allocations, fetchAllocation, loading, error } = useHoldingStore();

	useEffect(() => {
		fetchAllocation();
	}, [fetchAllocation]);

	const option: EChartsOption = {
		tooltip: {
			trigger: "item",
			// eslint-disable-next-line @typescript-eslint/no-explicit-any
				formatter: (params: any) =>
					`${params.name}: ${formatCurrency(params.value)} (${params.percent != null ? params.percent.toFixed(1) : "0.0"}%)`,
		},
		legend: {
			orient: "vertical",
			left: "left",
			top: "middle",
			formatter: (name: string) => {
				const item = allocations.find((a) => FUND_TYPES[a.fund_type] === name);
				return item ? `${name}  ${formatPercent(item.ratio)}` : name;
			},
		},
		series: [
			{
				type: "pie",
				radius: ["45%", "75%"],
				center: ["55%", "50%"],
				data: allocations.map((a) => ({
					name: FUND_TYPES[a.fund_type] || a.fund_type,
					value: a.market_value,
					itemStyle: {
						color: FUND_TYPE_COLORS[a.fund_type] || "#8c8c8c",
					},
				})),
				emphasis: {
					itemStyle: {
						shadowBlur: 10,
						shadowOffsetX: 0,
						shadowColor: "rgba(0, 0, 0, 0.5)",
					},
				},
				label: {
					formatter: "{b}\n{d}%",
				},
			},
		],
	};

	return (
		<Card title="资产配置" style={{ marginTop: 16 }}>
			{loading && (
				<div style={{ textAlign: "center", padding: 80 }}>
					<Spin size="large" />
				</div>
			)}
			{error && !loading && (
				<div style={{ textAlign: "center", padding: 60 }}>
					<Text type="danger">{error}</Text>
				</div>
			)}
			{!loading && !error && allocations.length === 0 && (
				<div style={{ textAlign: "center", padding: 60, color: "#999" }}>
					暂无配置数据
				</div>
			)}
			{!loading && !error && allocations.length > 0 && (
				<ReactECharts option={option} style={{ height: 350 }} />
			)}
		</Card>
	);
}

export default AllocationPie;
