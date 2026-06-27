import { useHoldingStore } from "@/stores/useHoldingStore";
import { createReturnsChartOption } from "@/utils/chart-options";
import { Card, Radio, Spin, Typography } from "antd";
import ReactECharts from "echarts-for-react";
import { useEffect, useState } from "react";

const { Text } = Typography;

const PERIODS = [
	{ label: "1月", value: "1M" },
	{ label: "3月", value: "3M" },
	{ label: "6月", value: "6M" },
	{ label: "1年", value: "1Y" },
	{ label: "全部", value: "ALL" },
];

function ReturnsChart() {
	const { returnsData, fetchReturnsChart, loading, error } = useHoldingStore();
	const [period, setPeriod] = useState("1M");

	useEffect(() => {
		fetchReturnsChart(period);
	}, [period, fetchReturnsChart]);

	const option =
		returnsData.length > 0
			? createReturnsChartOption(
					returnsData.map((d) => ({ date: d.date, returns: d.returns })),
					returnsData.some((d) => d.benchmark_returns !== undefined)
						? returnsData
								.filter((d) => d.benchmark_returns !== undefined)
								.map((d) => ({ date: d.date, returns: d.benchmark_returns! }))
						: undefined,
				)
			: null;

	return (
		<Card
			title="收益走势"
			extra={
				<Radio.Group
					value={period}
					onChange={(e) => setPeriod(e.target.value)}
					size="small"
					optionType="button"
					buttonStyle="solid"
				>
					{PERIODS.map((p) => (
						<Radio.Button key={p.value} value={p.value}>
							{p.label}
						</Radio.Button>
					))}
				</Radio.Group>
			}
			style={{ marginTop: 16 }}
		>
			{loading && (
				<div style={{ textAlign: "center", padding: 100 }}>
					<Spin size="large" />
				</div>
			)}
			{error && !loading && (
				<div style={{ textAlign: "center", padding: 60 }}>
					<Text type="danger">{error}</Text>
				</div>
			)}
			{!loading && !error && option && (
				<ReactECharts option={option} style={{ height: 350 }} />
			)}
			{!loading && !error && !option && (
				<div style={{ textAlign: "center", padding: 60, color: "#999" }}>
					暂无收益数据
				</div>
			)}
		</Card>
	);
}

export default ReturnsChart;
