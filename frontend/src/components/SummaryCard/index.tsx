import {
	ArrowDownOutlined,
	ArrowUpOutlined,
	MinusOutlined,
	ReloadOutlined,
} from "@ant-design/icons";
import { Button, Card, Skeleton, Typography } from "antd";

const { Text, Title } = Typography;

interface SummaryCardProps {
	title: string;
	value: string | number;
	subtitle?: string;
	trend?: "up" | "down" | "neutral";
	loading?: boolean;
	error?: string | null;
	onRetry?: () => void;
}

function SummaryCard({
	title,
	value,
	subtitle,
	trend,
	loading = false,
	error = null,
	onRetry,
}: SummaryCardProps) {
	// Loading state
	if (loading) {
		return (
			<Card>
				<Skeleton active paragraph={{ rows: 2 }} />
			</Card>
		);
	}

	// Error state
	if (error) {
		return (
			<Card>
				<div style={{ textAlign: "center", padding: "16px 0" }}>
					<Text type="danger">{error}</Text>
					{onRetry && (
						<div style={{ marginTop: 8 }}>
							<Button size="small" icon={<ReloadOutlined />} onClick={onRetry}>
								重试
							</Button>
						</div>
					)}
				</div>
			</Card>
		);
	}

	// Determine trend color and icon
	const trendColor =
		trend === "up" ? "#cf1322" : trend === "down" ? "#3f8600" : "#8c8c8c";

	const TrendIcon =
		trend === "up"
			? ArrowUpOutlined
			: trend === "down"
				? ArrowDownOutlined
				: MinusOutlined;

	return (
		<Card hoverable>
			<div>
				<Text type="secondary" style={{ fontSize: 14 }}>
					{title}
				</Text>
			</div>
			<div
				style={{
					marginTop: 8,
					display: "flex",
					alignItems: "baseline",
					gap: 8,
				}}
			>
				<Title level={3} style={{ margin: 0 }}>
					{value}
				</Title>
				{trend && (
					<span style={{ color: trendColor, fontSize: 14 }}>
						<TrendIcon style={{ marginRight: 2 }} />
					</span>
				)}
			</div>
			{subtitle && (
				<div style={{ marginTop: 4 }}>
					<Text type="secondary" style={{ fontSize: 12 }}>
						{subtitle}
					</Text>
				</div>
			)}
		</Card>
	);
}

export default SummaryCard;
