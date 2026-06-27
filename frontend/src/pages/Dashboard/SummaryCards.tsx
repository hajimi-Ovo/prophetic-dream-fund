import SummaryCard from "@/components/SummaryCard";
import { useHoldingStore } from "@/stores/useHoldingStore";
import { formatCurrency, formatPercent } from "@/utils/format";
import { Col, Row } from "antd";
import { useEffect } from "react";

function SummaryCards() {
	const { summary, fetchSummary, loading, error } = useHoldingStore();

	useEffect(() => {
		fetchSummary();
	}, [fetchSummary]);

	const profitTrend =
		summary && summary.total_profit >= 0
			? "up"
			: summary && summary.total_profit < 0
				? "down"
				: "neutral";

	const todayTrend =
		summary && summary.today_profit >= 0
			? "up"
			: summary && summary.today_profit < 0
				? "down"
				: "neutral";

	return (
		<Row gutter={[16, 16]}>
			<Col xs={24} sm={8}>
				<SummaryCard
					title="总资产"
					value={summary ? formatCurrency(summary.total_asset) : "—"}
					subtitle={`持有 ${summary?.holding_count ?? 0} 只基金`}
					loading={loading}
					error={error}
					onRetry={fetchSummary}
				/>
			</Col>
			<Col xs={24} sm={8}>
				<SummaryCard
					title="累计收益"
					value={summary ? `${formatCurrency(summary.total_profit)}` : "—"}
					subtitle={
						summary
							? `收益率 ${formatPercent(summary.total_profit_ratio)}`
							: undefined
					}
					trend={profitTrend}
					loading={loading}
					error={error}
					onRetry={fetchSummary}
				/>
			</Col>
			<Col xs={24} sm={8}>
				<SummaryCard
					title="今日收益"
					value={summary ? `${formatCurrency(summary.today_profit)}` : "—"}
					subtitle={
						summary
							? `收益率 ${formatPercent(summary.today_profit_ratio)}`
							: undefined
					}
					trend={todayTrend}
					loading={loading}
					error={error}
					onRetry={fetchSummary}
				/>
			</Col>
		</Row>
	);
}

export default SummaryCards;
