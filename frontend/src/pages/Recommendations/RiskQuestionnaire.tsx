import { useRecommendStore } from "@/stores/useRecommendStore";
import type { RiskAssessmentRequest } from "@/types/recommendation";
import { RISK_LEVELS } from "@/utils/constants";
import { formatPercent } from "@/utils/format";
import {
	Button,
	Card,
	Col,
	Progress,
	Radio,
	Row,
	Space,
	Spin,
	Tag,
	Typography,
} from "antd";
import { useState } from "react";

const { Text, Paragraph } = Typography;

const QUESTIONS = [
	{
		key: "risk_tolerance",
		label: "您的风险承受能力",
		description: "选择您能接受的最大投资回撤幅度",
		options: [
			{
				value: "conservative",
				label: "保守型",
				desc: "不接受本金损失，追求稳定收益",
			},
			{
				value: "moderate",
				label: "稳健型",
				desc: "接受适度波动，追求稳健增长",
			},
			{
				value: "aggressive",
				label: "进取型",
				desc: "接受较大波动，追求高收益",
			},
		],
	},
	{
		key: "investment_horizon",
		label: "您的投资期限",
		description: "您计划投资多长时间",
		options: [
			{ value: "short", label: "短期", desc: "1年以内" },
			{ value: "medium", label: "中期", desc: "1-3年" },
			{ value: "long", label: "长期", desc: "3年以上" },
		],
	},
	{
		key: "return_expectation",
		label: "您的收益期望",
		description: "您期望的年化收益率范围",
		options: [
			{ value: "conservative", label: "保守收益", desc: "年化3%-6%" },
			{ value: "moderate", label: "稳健收益", desc: "年化6%-12%" },
			{ value: "aggressive", label: "进取收益", desc: "年化12%以上" },
		],
	},
];

function RiskQuestionnaire() {
	const { riskAssessment, submitRiskAssessment, loading } = useRecommendStore();
	const [answers, setAnswers] = useState<RiskAssessmentRequest>({
		risk_tolerance: "",
		investment_horizon: "",
		return_expectation: "",
	});

	const allAnswered =
		answers.risk_tolerance !== "" &&
		answers.investment_horizon !== "" &&
		answers.return_expectation !== "";

	const handleSubmit = () => {
		if (allAnswered) {
			submitRiskAssessment(answers);
		}
	};

	const handleReset = () => {
		useRecommendStore.getState().reset();
		setAnswers({
			risk_tolerance: "",
			investment_horizon: "",
			return_expectation: "",
		});
	};

	return (
		<div>
			{!riskAssessment ? (
				<Card title="风险测评问卷">
					<Paragraph type="secondary">
						请回答以下问题，系统将根据您的回答评估风险等级，并提供个性化的投资建议。
					</Paragraph>

					{QUESTIONS.map((q) => (
						<Card
							key={q.key}
							size="small"
							style={{ marginBottom: 16 }}
							title={q.label}
						>
							<Text type="secondary">{q.description}</Text>
							<Radio.Group
								style={{ display: "block", marginTop: 12 }}
								value={answers[q.key as keyof RiskAssessmentRequest]}
								onChange={(e) =>
									setAnswers((prev) => ({ ...prev, [q.key]: e.target.value }))
								}
							>
								<Space direction="vertical">
									{q.options.map((opt) => (
										<Radio key={opt.value} value={opt.value}>
											<Text strong>{opt.label}</Text>
											<Text
												type="secondary"
												style={{ marginLeft: 8, fontSize: 12 }}
											>
												— {opt.desc}
											</Text>
										</Radio>
									))}
								</Space>
							</Radio.Group>
						</Card>
					))}

					<div style={{ textAlign: "center", marginTop: 24 }}>
						<Button
							type="primary"
							size="large"
							disabled={!allAnswered}
							loading={loading}
							onClick={handleSubmit}
						>
							提交测评
						</Button>
					</div>
				</Card>
			) : (
				<Card
					title="风险评估结果"
					extra={
						<Button size="small" onClick={handleReset}>
							重新测评
						</Button>
					}
				>
					{loading && (
						<div style={{ textAlign: "center", padding: 60 }}>
							<Spin size="large" />
						</div>
					)}

					{!loading && riskAssessment && (
						<>
							<Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
								<Col xs={24} sm={8}>
									<Card size="small">
										<Text type="secondary">风险等级</Text>
										<br />
										<Tag
											color="blue"
											style={{
												fontSize: 18,
												padding: "4px 16px",
												marginTop: 8,
											}}
										>
											{RISK_LEVELS[riskAssessment.risk_level] ||
												riskAssessment.risk_level}
										</Tag>
									</Card>
								</Col>
								<Col xs={24} sm={8}>
									<Card size="small">
										<Text type="secondary">风险评分</Text>
										<br />
										<Progress
											type="circle"
											percent={riskAssessment.risk_score}
											size={60}
											style={{ marginTop: 8 }}
										/>
									</Card>
								</Col>
								<Col xs={24} sm={8}>
									<Card size="small">
										<Text type="secondary">最大回撤容忍度</Text>
										<br />
										<Text strong style={{ fontSize: 20 }}>
											{riskAssessment.max_drawdown_tolerance != null
						? riskAssessment.max_drawdown_tolerance.toFixed(1)
						: "--"}
					%
										</Text>
									</Card>
								</Col>
							</Row>

							{riskAssessment.allocation_suggestions &&
								riskAssessment.allocation_suggestions.length > 0 && (
									<Card size="small" title="建议配置">
										{riskAssessment.allocation_suggestions.map((item) => (
											<div
												key={item.fund_type}
												style={{
													display: "flex",
													alignItems: "center",
													marginBottom: 12,
												}}
											>
												<Text style={{ width: 80 }}>{item.description}</Text>
												<Progress
													percent={Number((item.ratio * 100).toFixed(0))}
													style={{ flex: 1, margin: "0 12px" }}
												/>
												<Text>{formatPercent(item.ratio)}</Text>
											</div>
										))}
									</Card>
								)}
						</>
					)}
				</Card>
			)}
		</div>
	);
}

export default RiskQuestionnaire;
