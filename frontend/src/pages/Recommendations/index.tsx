import {
	BarChartOutlined,
	ExperimentOutlined,
	PieChartOutlined,
	StarOutlined,
} from "@ant-design/icons";
import { Tabs, Typography } from "antd";
import BacktestChart from "./BacktestChart";
import PortfolioPlan from "./PortfolioPlan";
import RecommendList from "./RecommendList";
import RiskQuestionnaire from "./RiskQuestionnaire";

const { Title } = Typography;

const TAB_ITEMS = [
	{
		key: "risk",
		label: (
			<span>
				<ExperimentOutlined />
				风险问卷
			</span>
		),
		children: <RiskQuestionnaire />,
	},
	{
		key: "recommend",
		label: (
			<span>
				<StarOutlined />
				推荐基金
			</span>
		),
		children: <RecommendList />,
	},
	{
		key: "portfolio",
		label: (
			<span>
				<PieChartOutlined />
				投资组合
			</span>
		),
		children: <PortfolioPlan />,
	},
	{
		key: "backtest",
		label: (
			<span>
				<BarChartOutlined />
				历史回测
			</span>
		),
		children: <BacktestChart />,
	},
];

function Recommendations() {
	return (
		<div>
			<Title level={3} style={{ marginBottom: 16 }}>
				智能推荐
			</Title>
			<Tabs defaultActiveKey="risk" items={TAB_ITEMS} size="large" />
		</div>
	);
}

export default Recommendations;
