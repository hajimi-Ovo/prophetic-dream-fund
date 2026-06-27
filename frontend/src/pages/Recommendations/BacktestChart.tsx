import { useRecommendStore } from "@/stores/useRecommendStore";
import { formatPercent } from "@/utils/format";
import { Button, Card, Col, Row, Select, Spin, Typography } from "antd";
import type { EChartsOption } from "echarts";
import ReactECharts from "echarts-for-react";
import { useState } from "react";

const { Text } = Typography;

const STRATEGY_OPTIONS = [
	{ value: "risk_based", label: "基于风险" },
	{ value: "market_based", label: "基于市场" },
	{ value: "hybrid", label: "混合策略" },
];

const PERIOD_OPTIONS = [
	{ value: "1Y", label: "近1年" },
	{ value: "3Y", label: "近3年" },
	{ value: "5Y", label: "近5年" },
];

function BacktestChart() {
	const { backtestResult, fetchBacktest, loading, error } = useRecommendStore();
	const [strategy, setStrategy] = useState("risk_based");
	const [period, setPeriod] = useState("1Y");

	const handleRun = () => {
		fetchBacktest(strategy, period);
	};

	const chartOption: EChartsOption | null = backtestResult
		? {
				tooltip: {
					trigger: "axis",
					valueFormatter: (value: unknown) =>
						typeof value === "number" ? value.toFixed(4) : `${value}`,
				},
				legend: {
					data: ["策略净值", "基准净值"],
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
					data: backtestResult.nav_points.map((p) => p.date),
					boundaryGap: false,
				},
				yAxis: {
					type: "value",
					name: "净值",
					scale: true,
				},
				series: [
					{
						name: "策略净值",
						type: "line",
						data: backtestResult.nav_points.map((p) => p.strategy_nav),
						smooth: true,
						showSymbol: false,
						lineStyle: { color: "#1677ff", width: 2 },
						itemStyle: { color: "#1677ff" },
					},
					{
						name: "基准净值",
						type: "line",
						data: backtestResult.nav_points.map((p) => p.benchmark_nav),
						smooth: true,
						showSymbol: false,
						lineStyle: {
							color: "#999",
							width: 2,
							type: "dashed",
						},
						itemStyle: { color: "#999" },
					},
				],
			}
		: null;

	return (
		<div>
			<Card title="历史回测">
				<div
					style={{
						marginBottom: 24,
						display: "flex",
						alignItems: "center",
						gap: 16,
						flexWrap: "wrap",
					}}
				>
					<Text strong>策略：</Text>
					<Select
						value={strategy}
						onChange={setStrategy}
						options={STRATEGY_OPTIONS}
						style={{ width: 140 }}
					/>
					<Text strong>周期：</Text>
					<Select
						value={period}
						onChange={setPeriod}
						options={PERIOD_OPTIONS}
						style={{ width: 120 }}
					/>
					<Button type="primary" onClick={handleRun} loading={loading}>
						开始回测
					</Button>
				</div>

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

				{!loading && !error && !backtestResult && (
					<div style={{ textAlign: "center", padding: 60, color: "#999" }}>
						选择策略和周期，点击"开始回测"查看结果
					</div>
				)}

				{backtestResult && !loading && (
					<>
						{/* Metrics Cards */}
						<Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
							<Col xs={12} sm={8} md={4}>
								<Card size="small">
									<Text type="secondary">累计收益</Text>
									<br />
									<Text strong style={{ fontSize: 16, color: "#cf1322" }}>
										{formatPercent(backtestResult.total_return)}
									</Text>
								</Card>
							</Col>
							<Col xs={12} sm={8} md={4}>
								<Card size="small">
									<Text type="secondary">年化收益</Text>
									<br />
									<Text strong style={{ fontSize: 16, color: "#cf1322" }}>
										{formatPercent(backtestResult.annual_return)}
									</Text>
								</Card>
							</Col>
							<Col xs={12} sm={8} md={4}>
								<Card size="small">
									<Text type="secondary">最大回撤</Text>
									<br />
									<Text strong style={{ fontSize: 16, color: "#f5222d" }}>
										{formatPercent(backtestResult.max_drawdown)}
									</Text>
								</Card>
							</Col>
							<Col xs={12} sm={8} md={4}>
								<Card size="small">
									<Text type="secondary">夏普比率</Text>
									<br />
									<Text strong style={{ fontSize: 16 }}>
										{backtestResult.sharpe_ratio != null ? backtestResult.sharpe_ratio.toFixed(2) : "--"}
									</Text>
								</Card>
							</Col>
							<Col xs={12} sm={8} md={4}>
								<Card size="small">
									<Text type="secondary">胜率</Text>
									<br />
									<Text strong style={{ fontSize: 16 }}>
										{formatPercent(backtestResult.win_rate)}
									</Text>
								</Card>
							</Col>
						</Row>

						{/* Chart */}
						{chartOption && (
							<ReactECharts option={chartOption} style={{ height: 400 }} />
						)}
					</>
				)}
			</Card>
		</div>
	);
}

export default BacktestChart;
