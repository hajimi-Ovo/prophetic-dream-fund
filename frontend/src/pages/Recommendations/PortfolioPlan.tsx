import { useRecommendStore } from "@/stores/useRecommendStore";
import type {
	PortfolioAllocationItem,
	RebalanceSuggestion,
} from "@/types/recommendation";
import { FUND_TYPES, FUND_TYPE_COLORS } from "@/utils/constants";
import { formatCurrency, formatPercent } from "@/utils/format";
import {
	Button,
	Card,
	Col,
	InputNumber,
	Row,
	Table,
	Tag,
	Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import type { EChartsOption } from "echarts";
import ReactECharts from "echarts-for-react";
import { useState } from "react";

const { Text, Paragraph } = Typography;

function PortfolioPlan() {
	const { portfolioPlan, fetchPortfolioPlan, loading, error } =
		useRecommendStore();
	const [amount, setAmount] = useState<number>(100000);

	const handleGenerate = () => {
		if (amount > 0) {
			fetchPortfolioPlan(amount);
		}
	};

	const pieOption: EChartsOption | null = portfolioPlan
		? {
				tooltip: {
					trigger: "item",
					formatter: "{b}: {c} ({d}%)",
				},
				legend: {
					orient: "vertical",
					left: "left",
					top: "middle",
				},
				series: [
					{
						type: "pie",
						radius: ["40%", "70%"],
						center: ["55%", "50%"],
						data: portfolioPlan.allocations.map(
							(a: PortfolioAllocationItem) => ({
								name: a.fund_name,
								value: a.amount,
								itemStyle: {
									color: FUND_TYPE_COLORS[a.fund_type] || "#8c8c8c",
								},
							}),
						),
						label: {
							formatter: "{b}\n{d}%",
						},
					},
				],
			}
		: null;

	const allocationColumns: ColumnsType<PortfolioAllocationItem> = [
		{ title: "基金名称", dataIndex: "fund_name", key: "fund_name" },
		{
			title: "类型",
			dataIndex: "fund_type",
			key: "fund_type",
			render: (v: string) => FUND_TYPES[v] || v,
		},
		{
			title: "配置比例",
			dataIndex: "ratio",
			key: "ratio",
			render: (v: number) => formatPercent(v),
		},
		{
			title: "配置金额",
			dataIndex: "amount",
			key: "amount",
			render: (v: number) => formatCurrency(v),
		},
		{
			title: "配置理由",
			dataIndex: "reason",
			key: "reason",
			ellipsis: true,
		},
	];

	const rebalanceColumns: ColumnsType<RebalanceSuggestion> = [
		{ title: "基金名称", dataIndex: "fund_name", key: "fund_name" },
		{
			title: "当前比例",
			dataIndex: "current_ratio",
			key: "current_ratio",
			render: (v: number) => formatPercent(v),
		},
		{
			title: "目标比例",
			dataIndex: "target_ratio",
			key: "target_ratio",
			render: (v: number) => formatPercent(v),
		},
		{
			title: "操作",
			dataIndex: "action",
			key: "action",
			render: (v: string) => (
				<Tag color={v === "buy" ? "green" : "red"}>
					{v === "buy" ? "买入" : "卖出"}
				</Tag>
			),
		},
		{
			title: "调整金额",
			key: "amount",
			render: (_: unknown, record: RebalanceSuggestion) =>
				formatCurrency(record.amount),
		},
	];

	return (
		<div>
			<Card title="投资组合方案">
				<div
					style={{
						marginBottom: 24,
						display: "flex",
						alignItems: "center",
						gap: 16,
					}}
				>
					<Text strong>投资总额：</Text>
					<InputNumber
						value={amount}
						onChange={(v) => setAmount(v ?? 0)}
						min={1000}
						step={10000}
						precision={0}
						style={{ width: 160 }}
						addonAfter="元"
					/>
					<Button type="primary" onClick={handleGenerate} loading={loading}>
						生成方案
					</Button>
				</div>

				{error && <Text type="danger">{error}</Text>}

				{portfolioPlan && !loading && (
					<>
						{/* Metrics Cards */}
						<Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
							<Col xs={12} sm={6}>
								<Card size="small">
									<Text type="secondary">预期收益</Text>
									<br />
									<Text strong style={{ fontSize: 18, color: "#cf1322" }}>
										{formatPercent(portfolioPlan.expected_return)}
									</Text>
								</Card>
							</Col>
							<Col xs={12} sm={6}>
								<Card size="small">
									<Text type="secondary">预期风险</Text>
									<br />
									<Text strong style={{ fontSize: 18 }}>
										{formatPercent(portfolioPlan.expected_risk)}
									</Text>
								</Card>
							</Col>
							<Col xs={12} sm={6}>
								<Card size="small">
									<Text type="secondary">最大回撤</Text>
									<br />
									<Text strong style={{ fontSize: 18, color: "#f5222d" }}>
										{formatPercent(portfolioPlan.max_drawdown)}
									</Text>
								</Card>
							</Col>
							<Col xs={12} sm={6}>
								<Card size="small">
									<Text type="secondary">风险等级</Text>
									<br />
									<Tag color="blue" style={{ fontSize: 14, marginTop: 4 }}>
										{portfolioPlan.risk_level}
									</Tag>
								</Card>
							</Col>
						</Row>

						{/* Allocation Pie + Table */}
						<Row gutter={[16, 16]}>
							<Col xs={24} md={12}>
								<Card size="small" title="配置饼图">
									{pieOption && (
										<ReactECharts option={pieOption} style={{ height: 300 }} />
									)}
								</Card>
							</Col>
							<Col xs={24} md={12}>
								<Card size="small" title="配置明细">
									<Table
										columns={allocationColumns}
										dataSource={portfolioPlan.allocations}
										rowKey="fund_code"
										pagination={false}
										size="small"
										scroll={{ x: 500 }}
									/>
								</Card>
							</Col>
						</Row>

						{/* Rebalance Suggestions */}
						{portfolioPlan.rebalance_suggestions &&
							portfolioPlan.rebalance_suggestions.length > 0 && (
								<Card size="small" title="再平衡建议" style={{ marginTop: 16 }}>
									<Paragraph type="secondary">
										基于您现有持仓与目标配置的差异，建议进行以下调整：
									</Paragraph>
									<Table
										columns={rebalanceColumns}
										dataSource={portfolioPlan.rebalance_suggestions}
										rowKey="fund_code"
										pagination={false}
										size="small"
										scroll={{ x: 600 }}
									/>
								</Card>
							)}
					</>
				)}
			</Card>
		</div>
	);
}

export default PortfolioPlan;
