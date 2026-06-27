import { addToWatchlist } from "@/api/watchlist";
import { useMarketStore } from "@/stores/useMarketStore";
import { formatPercent } from "@/utils/format";
import { ArrowLeftOutlined, StarOutlined } from "@ant-design/icons";
import {
	Alert,
	Button,
	Card,
	Col,
	Row,
	Space,
	Spin,
	Statistic,
	Typography,
	message,
} from "antd";
import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import FundInfo from "./FundInfo";
import HoldingsBreakdown from "./HoldingsBreakdown";
import ManagerCard from "./ManagerCard";
import NavChart from "./NavChart";

const { Title, Text } = Typography;

function FundDetailPage() {
	const { code } = useParams<{ code: string }>();
	const navigate = useNavigate();
	const {
		fundDetail,
		portfolio,
		loading,
		error,
		fetchFundDetail,
		fetchPortfolio,
	} = useMarketStore();

	useEffect(() => {
		if (code) {
			fetchFundDetail(code);
			fetchPortfolio(code);
		}
	}, [code, fetchFundDetail, fetchPortfolio]);

	const handleAddToWatchlist = async () => {
		if (!code) return;
		try {
			await addToWatchlist({ fund_code: code });
			message.success("已添加到自选");
		} catch {
			message.error("添加自选失败");
		}
	};

	if (!code) {
		return (
			<div style={{ textAlign: "center", padding: 60 }}>
				<Text type="secondary">无效的基金代码</Text>
			</div>
		);
	}

	return (
		<div>
			{/* Header */}
			<div
				style={{
					display: "flex",
					justifyContent: "space-between",
					alignItems: "center",
					flexWrap: "wrap",
					gap: 12,
					marginBottom: 16,
				}}
			>
				<Space>
					<Button
						icon={<ArrowLeftOutlined />}
						onClick={() => navigate("/market")}
						type="text"
					>
						返回
					</Button>
					<Title level={3} style={{ margin: 0 }}>
						{fundDetail?.basic.name || "基金详情"}
					</Title>
					{fundDetail && (
						<Text type="secondary" style={{ fontSize: 16 }}>
							{fundDetail.basic.code}
						</Text>
					)}
				</Space>

				<Button
					type="primary"
					icon={<StarOutlined />}
					onClick={handleAddToWatchlist}
				>
					添加自选
				</Button>
			</div>

			{/* Error */}
			{error && (
				<Alert
					message={error}
					type="error"
					showIcon
					closable
					style={{ marginBottom: 16 }}
				/>
			)}

			{/* Loading */}
			{loading && !fundDetail && (
				<div style={{ textAlign: "center", padding: 80 }}>
					<Spin size="large" />
				</div>
			)}

			{/* Fund detail content */}
			{fundDetail && (
				<>
					{/* Basic info */}
					<FundInfo detail={fundDetail} />

					{/* Nav chart */}
					<NavChart code={code} />

					{/* Manager info */}
					{fundDetail.manager && <ManagerCard manager={fundDetail.manager} />}

					{/* Risk metrics */}
					{fundDetail.risk_metrics && (
						<Card title="风险指标" style={{ marginTop: 16 }}>
							<Row gutter={[16, 16]}>
								<Col xs={12} sm={8} md={4}>
									<Statistic
										title="最大回撤"
										value={
											fundDetail.risk_metrics.max_drawdown !== undefined
												? formatPercent(fundDetail.risk_metrics.max_drawdown)
												: "--"
										}
										valueStyle={{
											color: "#f5222d",
											fontSize: 18,
										}}
									/>
								</Col>
								<Col xs={12} sm={8} md={4}>
									<Statistic
										title="夏普比率"
										value={
											fundDetail.risk_metrics.sharpe_ratio?.toFixed(2) ?? "--"
										}
										valueStyle={{ fontSize: 18 }}
									/>
								</Col>
								<Col xs={12} sm={8} md={4}>
									<Statistic
										title="波动率"
										value={
											fundDetail.risk_metrics.volatility !== undefined
												? formatPercent(fundDetail.risk_metrics.volatility)
												: "--"
										}
										valueStyle={{ fontSize: 18 }}
									/>
								</Col>
								<Col xs={12} sm={8} md={4}>
									<Statistic
										title="Alpha"
										value={fundDetail.risk_metrics.alpha?.toFixed(4) ?? "--"}
										valueStyle={{ fontSize: 18 }}
									/>
								</Col>
								<Col xs={12} sm={8} md={4}>
									<Statistic
										title="Beta"
										value={fundDetail.risk_metrics.beta?.toFixed(2) ?? "--"}
										valueStyle={{ fontSize: 18 }}
									/>
								</Col>
							</Row>
						</Card>
					)}

					{/* Holdings */}
					<HoldingsBreakdown portfolio={portfolio} />
				</>
			)}

			{/* Not found state */}
			{!loading && !fundDetail && !error && (
				<div style={{ textAlign: "center", padding: 80, color: "#999" }}>
					未找到该基金信息
				</div>
			)}
		</div>
	);
}

export default FundDetailPage;
