import { useMarketStore } from "@/stores/useMarketStore";
import { createNavLineOption } from "@/utils/chart-options";
import { Space, Spin, Tabs, Typography } from "antd";
import ReactECharts from "echarts-for-react";
import { useEffect, useState } from "react";

const { Text } = Typography;

const PERIOD_TABS = [
	{ key: "1m", label: "1月" },
	{ key: "3m", label: "3月" },
	{ key: "6m", label: "6月" },
	{ key: "1y", label: "1年" },
	{ key: "all", label: "全部" },
];

interface NavChartProps {
	code: string;
}

function NavChart({ code }: NavChartProps) {
	const { navHistory, fetchNavHistory, loading } = useMarketStore();
	const [activePeriod, setActivePeriod] = useState("1m");

	useEffect(() => {
		fetchNavHistory(code, activePeriod);
	}, [code, activePeriod, fetchNavHistory]);

	const chartOption =
		navHistory && navHistory.points.length > 0
			? createNavLineOption(navHistory.points, "净值走势")
			: null;

	return (
		<div
			style={{
				background: "#fff",
				borderRadius: 8,
				padding: 16,
				marginTop: 16,
			}}
		>
			<Space
				style={{
					marginBottom: 12,
					justifyContent: "space-between",
					width: "100%",
				}}
			>
				<Text strong>净值走势</Text>
			</Space>

			<Tabs
				activeKey={activePeriod}
				onChange={setActivePeriod}
				items={PERIOD_TABS}
				size="small"
				style={{ marginBottom: 12 }}
			/>

			{loading && (
				<div style={{ textAlign: "center", padding: 60 }}>
					<Spin />
				</div>
			)}

			{!loading && chartOption && (
				<ReactECharts option={chartOption} style={{ height: 400 }} notMerge />
			)}

			{!loading && !chartOption && (
				<div style={{ textAlign: "center", padding: 60, color: "#999" }}>
					暂无净值数据
				</div>
			)}
		</div>
	);
}

export default NavChart;
