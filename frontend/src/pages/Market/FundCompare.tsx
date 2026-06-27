import { useMarketStore } from "@/stores/useMarketStore";
import { createCompareOverlayOption } from "@/utils/chart-options";
import { formatPercent } from "@/utils/format";
import { SwapOutlined } from "@ant-design/icons";
import {
	Button,
	Col,
	Collapse,
	Row,
	Select,
	Space,
	Spin,
	Table,
	Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import ReactECharts from "echarts-for-react";
import { useState } from "react";

const { Text } = Typography;

interface CompareRow {
	metric: string;
	valueA: string | number;
	valueB: string | number;
}

function FundCompare() {
	const {
		fundList,
		compareList,
		compareOverlay,
		compareFunds,
		clearCompare,
		loading,
	} = useMarketStore();
	const [codeA, setCodeA] = useState<string | undefined>(undefined);
	const [codeB, setCodeB] = useState<string | undefined>(undefined);

	const fundOptions = fundList.map((f) => ({
		value: f.code,
		label: `${f.code} ${f.name}`,
	}));

	const handleCompare = () => {
		if (codeA && codeB) {
			compareFunds([codeA, codeB]);
		}
	};

	const fundA = compareList[0];
	const fundB = compareList[1];

	const tableColumns: ColumnsType<CompareRow> = [
		{
			title: "指标",
			dataIndex: "metric",
			key: "metric",
			width: 140,
		},
		{
			title: fundA ? `${fundA.name} (${fundA.code})` : "基金 A",
			dataIndex: "valueA",
			key: "valueA",
		},
		{
			title: fundB ? `${fundB.name} (${fundB.code})` : "基金 B",
			dataIndex: "valueB",
			key: "valueB",
		},
	];

	const tableData: CompareRow[] =
		fundA && fundB
			? [
					{
						metric: "最新净值",
						valueA: fundA.latest_nav?.toFixed(4) ?? "--",
						valueB: fundB.latest_nav?.toFixed(4) ?? "--",
					},
					{
						metric: "日收益",
						valueA: formatPercent(fundA.daily_return ?? 0),
						valueB: formatPercent(fundB.daily_return ?? 0),
					},
					{
						metric: "近一年收益",
						valueA: formatPercent(fundA.one_year_return ?? 0),
						valueB: formatPercent(fundB.one_year_return ?? 0),
					},
					{
						metric: "最大回撤",
						valueA:
							fundA.max_drawdown !== undefined
								? formatPercent(fundA.max_drawdown)
								: "--",
						valueB:
							fundB.max_drawdown !== undefined
								? formatPercent(fundB.max_drawdown)
								: "--",
					},
					{
						metric: "夏普比率",
						valueA: fundA.sharpe_ratio?.toFixed(2) ?? "--",
						valueB: fundB.sharpe_ratio?.toFixed(2) ?? "--",
					},
				]
			: [];

	const overlayKeys = Object.keys(compareOverlay);
	const hasChart = overlayKeys.length >= 2;

	const chartOption =
		hasChart && overlayKeys[0] && overlayKeys[1]
			? createCompareOverlayOption(
					{ name: overlayKeys[0], data: compareOverlay[overlayKeys[0]] },
					{ name: overlayKeys[1], data: compareOverlay[overlayKeys[1]] },
				)
			: null;

	return (
		<Collapse
			items={[
				{
					key: "compare",
					label: (
						<Space>
							<SwapOutlined />
							<span>基金对比</span>
						</Space>
					),
					children: (
						<div style={{ padding: "8px 0" }}>
							<Row
								gutter={[16, 12]}
								align="middle"
								style={{ marginBottom: 16 }}
							>
								<Col xs={24} sm={10}>
									<Select
										placeholder="选择基金 A"
										showSearch
										filterOption={(input, option) =>
											(option?.label as string)
												?.toLowerCase()
												.includes(input.toLowerCase())
										}
										style={{ width: "100%" }}
										value={codeA}
										onChange={setCodeA}
										options={fundOptions}
									/>
								</Col>
								<Col xs={24} sm={10}>
									<Select
										placeholder="选择基金 B"
										showSearch
										filterOption={(input, option) =>
											(option?.label as string)
												?.toLowerCase()
												.includes(input.toLowerCase())
										}
										style={{ width: "100%" }}
										value={codeB}
										onChange={setCodeB}
										options={fundOptions}
									/>
								</Col>
								<Col xs={12} sm={4}>
									<Space>
										<Button
											type="primary"
											onClick={handleCompare}
											loading={loading}
											disabled={!codeA || !codeB}
										>
											对比
										</Button>
										{compareList.length > 0 && (
											<Button onClick={clearCompare}>清除</Button>
										)}
									</Space>
								</Col>
							</Row>

							{loading && (
								<div style={{ textAlign: "center", padding: 40 }}>
									<Spin />
								</div>
							)}

							{!loading && compareList.length > 0 && (
								<>
									<Table
										columns={tableColumns}
										dataSource={tableData}
										pagination={false}
										rowKey="metric"
										size="small"
										style={{ marginBottom: 16 }}
									/>

									{chartOption && (
										<ReactECharts
											option={chartOption}
											style={{ height: 350 }}
											notMerge
										/>
									)}
								</>
							)}

							{!loading && compareList.length === 0 && (
								<Text type="secondary">
									选择两支基金后点击"对比"按钮查看对比结果
								</Text>
							)}
						</div>
					),
				},
			]}
			style={{ marginTop: 16 }}
		/>
	);
}

export default FundCompare;
