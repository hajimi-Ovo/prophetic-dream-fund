import type { FundBasic } from "@/types/fund";
import { FUND_TYPES } from "@/utils/constants";
import { formatPercent } from "@/utils/format";
import { Card, Tag, Typography } from "antd";
import { useNavigate } from "react-router-dom";

const { Text, Title } = Typography;

interface FundCardProps {
	fund: FundBasic;
}

function FundCard({ fund }: FundCardProps) {
	const navigate = useNavigate();

	const typeLabel = FUND_TYPES[fund.type] || fund.type;

	const dailyReturnColor =
		fund.daily_return === undefined || fund.daily_return === 0
			? undefined
			: fund.daily_return > 0
				? "#52c41a"
				: "#f5222d";

	const yearReturnColor =
		fund.one_year_return === undefined || fund.one_year_return === 0
			? undefined
			: fund.one_year_return > 0
				? "#52c41a"
				: "#f5222d";

	return (
		<Card
			hoverable
			onClick={() => navigate(`/market/${fund.code}`)}
			style={{ height: "100%" }}
			styles={{ body: { padding: 16 } }}
		>
			<div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
				{/* Header row: code + type tag */}
				<div
					style={{
						display: "flex",
						justifyContent: "space-between",
						alignItems: "center",
					}}
				>
					<Text type="secondary" style={{ fontSize: 12 }}>
						{fund.code}
					</Text>
					<Tag color="blue">{typeLabel}</Tag>
				</div>

				{/* Fund name */}
				<Title
					level={5}
					style={{
						margin: 0,
						overflow: "hidden",
						textOverflow: "ellipsis",
						whiteSpace: "nowrap",
					}}
					title={fund.name}
				>
					{fund.name}
				</Title>

				{/* Latest NAV */}
				<div
					style={{
						display: "flex",
						justifyContent: "space-between",
						alignItems: "baseline",
					}}
				>
					<Text type="secondary" style={{ fontSize: 12 }}>
						最新净值
					</Text>
					<Text strong style={{ fontSize: 18 }}>
						{fund.latest_nav !== undefined ? fund.latest_nav.toFixed(4) : "--"}
					</Text>
				</div>

				{/* Returns */}
				<div style={{ display: "flex", justifyContent: "space-between" }}>
					<div>
						<Text type="secondary" style={{ fontSize: 12 }}>
							日收益
						</Text>
						<br />
						<Text strong style={{ color: dailyReturnColor, fontSize: 14 }}>
							{fund.daily_return !== undefined
								? formatPercent(fund.daily_return)
								: "--"}
						</Text>
					</div>
					<div style={{ textAlign: "right" }}>
						<Text type="secondary" style={{ fontSize: 12 }}>
							近一年收益
						</Text>
						<br />
						<Text strong style={{ color: yearReturnColor, fontSize: 14 }}>
							{fund.one_year_return !== undefined
								? formatPercent(fund.one_year_return)
								: "--"}
						</Text>
					</div>
				</div>

				{/* Company if available */}
				{fund.company && (
					<Text type="secondary" style={{ fontSize: 12 }}>
						{fund.company}
					</Text>
				)}
			</div>
		</Card>
	);
}

export default FundCard;
