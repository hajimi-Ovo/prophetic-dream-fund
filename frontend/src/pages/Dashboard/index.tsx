import {
	ArrowRightOutlined,
	FundOutlined,
	PieChartOutlined,
} from "@ant-design/icons";
import { Card, Col, Row, Typography } from "antd";
import { useNavigate } from "react-router-dom";
import AllocationPie from "./AllocationPie";
import HoldingsTable from "./HoldingsTable";
import ReturnsChart from "./ReturnsChart";
import SummaryCards from "./SummaryCards";

const { Title, Text } = Typography;

function Dashboard() {
	const navigate = useNavigate();

	return (
		<div>
			<Title level={3} style={{ marginBottom: 16 }}>
				投资概览
			</Title>

			{/* Summary Cards */}
			<SummaryCards />

			{/* Returns Chart */}
			<ReturnsChart />

			{/* Holdings Table + Allocation Pie */}
			<Row gutter={[16, 16]} style={{ marginTop: 16 }}>
				<Col xs={24} lg={14}>
					<HoldingsTable />
				</Col>
				<Col xs={24} lg={10}>
					<AllocationPie />
				</Col>
			</Row>

			{/* Recommendation Entry */}
			<Row gutter={[16, 16]} style={{ marginTop: 16 }}>
				<Col xs={24} sm={12}>
					<Card
						hoverable
						onClick={() => navigate("/recommend")}
						style={{ cursor: "pointer" }}
					>
						<div style={{ display: "flex", alignItems: "center", gap: 12 }}>
							<FundOutlined style={{ fontSize: 32, color: "#1677ff" }} />
							<div style={{ flex: 1 }}>
								<Text strong style={{ fontSize: 16 }}>
									查看推荐基金
								</Text>
								<br />
								<Text type="secondary">基于AI分析的个性化基金推荐</Text>
							</div>
							<ArrowRightOutlined style={{ color: "#999" }} />
						</div>
					</Card>
				</Col>
				<Col xs={24} sm={12}>
					<Card
						hoverable
						onClick={() => navigate("/recommend")}
						style={{ cursor: "pointer" }}
					>
						<div style={{ display: "flex", alignItems: "center", gap: 12 }}>
							<PieChartOutlined style={{ fontSize: 32, color: "#52c41a" }} />
							<div style={{ flex: 1 }}>
								<Text strong style={{ fontSize: 16 }}>
									投资组合建议
								</Text>
								<br />
								<Text type="secondary">优化配置，科学分散风险</Text>
							</div>
							<ArrowRightOutlined style={{ color: "#999" }} />
						</div>
					</Card>
				</Col>
			</Row>
		</div>
	);
}

export default Dashboard;
