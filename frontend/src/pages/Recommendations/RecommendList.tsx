import { useHoldingStore } from "@/stores/useHoldingStore";
import { useRecommendStore } from "@/stores/useRecommendStore";
import { formatCurrency, formatPercent } from "@/utils/format";
import {
	DollarOutlined,
	InfoCircleOutlined,
	StarOutlined,
} from "@ant-design/icons";
import {
	Button,
	Card,
	Col,
	Row,
	Select,
	Space,
	Spin,
	Tag,
	Typography,
	message,
} from "antd";
import { useEffect, useState } from "react";
import TimingAdvice from "./TimingAdvice";

const { Text } = Typography;

const STRATEGY_OPTIONS = [
	{ value: "risk_based", label: "基于风险" },
	{ value: "market_based", label: "基于市场" },
	{ value: "hybrid", label: "混合策略" },
];

const ACTION_COLORS: Record<string, string> = {
	buy: "green",
	wait: "orange",
	hold: "blue",
	sell: "red",
};

const ACTION_LABELS: Record<string, string> = {
	buy: "建议买入",
	wait: "观望等待",
	hold: "继续持有",
	sell: "建议卖出",
};

function RecommendList() {
	const { recommendations: recommendList, fetchRecommendations, loading, error } =
		useRecommendStore();
	const { addToWatchlist } = useHoldingStore();
	const [strategy, setStrategy] = useState("risk_based");
	const [timingFund, setTimingFund] = useState<string | null>(null);

	useEffect(() => {
		fetchRecommendations(strategy);
	}, [strategy, fetchRecommendations]);

	const handleAddWatchlist = async (fundCode: string, fundName: string) => {
		const result = await addToWatchlist({
			fund_code: fundCode,
			fund_name: fundName,
		});
		if (result) {
			message.success(`已添加 ${fundName} 到自选`);
		}
	};

	return (
		<div>
			<div
				style={{
					marginBottom: 16,
					display: "flex",
					alignItems: "center",
					gap: 12,
				}}
			>
				<Text strong>推荐策略：</Text>
				<Select
					value={strategy}
					onChange={setStrategy}
					options={STRATEGY_OPTIONS}
					style={{ width: 140 }}
				/>
			</div>

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

			{!loading && !error && recommendList.length === 0 && (
				<div style={{ textAlign: "center", padding: 60, color: "#999" }}>
					暂无推荐数据，请先完成风险测评
				</div>
			)}

			{!loading &&
				!error &&
				recommendList.map((item, idx) => (
					<Card
						key={item.fund_code}
						style={{ marginBottom: 16 }}
						title={
							<Space>
								<Tag color="blue" style={{ fontSize: 14 }}>
									#{item.rank || idx + 1}
								</Tag>
								<Text strong style={{ fontSize: 16 }}>
									{item.fund_name}
								</Text>
								<Tag>{item.fund_type}</Tag>
							</Space>
						}
						extra={
							<Space>
								<Tag color={ACTION_COLORS[item.suggested_action] || "default"}>
									{ACTION_LABELS[item.suggested_action] ||
										item.suggested_action}
								</Tag>
								<Text type="secondary" style={{ fontSize: 12 }}>
									评分: {item.score.toFixed(0)}
								</Text>
							</Space>
						}
					>
						<Row gutter={[16, 8]} style={{ marginBottom: 12 }}>
							<Col xs={24} sm={6}>
								<Text type="secondary">预期收益</Text>
								<br />
								<Text strong>{formatPercent(item.expected_return)}</Text>
							</Col>
							<Col xs={24} sm={6}>
								<Text type="secondary">建议金额</Text>
								<br />
								<Text strong>{formatCurrency(item.suggested_amount)}</Text>
							</Col>
							<Col xs={24} sm={6}>
								<Text type="secondary">风险等级</Text>
								<br />
								<Text>{item.risk_level}</Text>
							</Col>
						</Row>

						<div style={{ marginBottom: 12 }}>
							<Text type="secondary">
								<InfoCircleOutlined style={{ marginRight: 4 }} />
								推荐理由：
							</Text>
							<div style={{ marginTop: 4 }}>
								{item.reasons?.map((reason: string, i: number) => (
									<Tag key={i} style={{ marginBottom: 4 }}>
										{reason}
									</Tag>
								))}
							</div>
						</div>

						<Space>
							<Button
								type="primary"
								size="small"
								icon={<StarOutlined />}
								onClick={() =>
									handleAddWatchlist(item.fund_code, item.fund_name)
								}
							>
								加入自选
							</Button>
							<Button
								size="small"
								icon={<DollarOutlined />}
								onClick={() =>
									setTimingFund(
										timingFund === item.fund_code ? null : item.fund_code,
									)
								}
							>
								{timingFund === item.fund_code ? "收起择时" : "买入时机"}
							</Button>
						</Space>

						{timingFund === item.fund_code && (
							<div style={{ marginTop: 16 }}>
								<TimingAdvice
									fundCode={item.fund_code}
									fundName={item.fund_name}
								/>
							</div>
						)}
					</Card>
				))}
		</div>
	);
}

export default RecommendList;
