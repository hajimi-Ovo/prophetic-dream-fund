import { useRecommendStore } from "@/stores/useRecommendStore";
import { Card, Progress, Spin, Tag, Typography } from "antd";
import { useEffect } from "react";

const { Text } = Typography;

interface TimingAdviceProps {
	fundCode: string;
	fundName: string;
}

const SIGNAL_COLORS: Record<string, string> = {
	green: "#52c41a",
	yellow: "#faad14",
	red: "#f5222d",
};

const SIGNAL_LABELS: Record<string, string> = {
	green: "买入信号",
	yellow: "观望信号",
	red: "卖出信号",
};

function TimingAdvice({ fundCode, fundName }: TimingAdviceProps) {
	const { timingAdvice, fetchTimingAdvice, loading, error } =
		useRecommendStore();

	useEffect(() => {
		fetchTimingAdvice(fundCode);
	}, [fundCode, fetchTimingAdvice]);

	// Look up the specific fund's timing advice from the record
	const advice = timingAdvice[fundCode];

	if (loading) {
		return (
			<Card size="small">
				<div style={{ textAlign: "center", padding: 20 }}>
					<Spin size="small" />
				</div>
			</Card>
		);
	}

	if (error || !advice) {
		return (
			<Card size="small">
				<Text type="danger">{error || "暂无择时数据"}</Text>
			</Card>
		);
	}

	return (
		<Card size="small" title={`${fundName} - 择时建议`}>
			<div style={{ textAlign: "center", marginBottom: 16 }}>
				<div
					style={{
						display: "flex",
						width: 60,
						height: 60,
						borderRadius: "50%",
						backgroundColor: SIGNAL_COLORS[advice.signal] || "#8c8c8c",
						alignItems: "center",
						justifyContent: "center",
						marginBottom: 8,
					}}
				>
					<Text
						strong
						style={{
							color: "#fff",
							fontSize: 16,
						}}
					>
						{SIGNAL_LABELS[advice.signal] || advice.signal}
					</Text>
				</div>
				<br />
				<Text strong>{advice.signal_label}</Text>
			</div>

			<div style={{ marginBottom: 12 }}>
				<div style={{ display: "flex", justifyContent: "space-between" }}>
					<Text type="secondary">估值百分位</Text>
					<Text>
						{advice.valuation_percentile != null
							? `${advice.valuation_percentile.toFixed(1)}%`
							: "--"}
					</Text>
				</div>
				<Progress
					percent={
						advice.valuation_percentile != null
							? Number(advice.valuation_percentile.toFixed(0))
							: 0
					}
					showInfo={false}
					strokeColor={
						advice.valuation_percentile < 30
							? "#52c41a"
							: advice.valuation_percentile < 70
								? "#faad14"
								: "#f5222d"
					}
				/>
			</div>

			<div style={{ marginBottom: 8 }}>
				<Text type="secondary">趋势信号：</Text>
				<Text style={{ marginLeft: 8 }}>{advice.trend_signal}</Text>
			</div>

			{advice.reasons && advice.reasons.length > 0 && (
				<div>
					<Text type="secondary">分析理由：</Text>
					<div style={{ marginTop: 4 }}>
						{advice.reasons.map((reason: string, i: number) => (
							<Tag key={i} style={{ marginBottom: 4 }}>
								{reason}
							</Tag>
						))}
					</div>
				</div>
			)}
		</Card>
	);
}

export default TimingAdvice;
