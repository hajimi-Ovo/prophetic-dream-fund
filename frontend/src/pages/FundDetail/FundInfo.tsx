import type { FundDetail } from "@/types/fund";
import { FUND_TYPES } from "@/utils/constants";
import { formatPercent } from "@/utils/format";
import { Descriptions, Tag, Typography } from "antd";
import type { DescriptionsProps } from "antd";

const { Text } = Typography;

interface FundInfoProps {
	detail: FundDetail;
}

function FundInfo({ detail }: FundInfoProps) {
	const { basic, nav } = detail;

	const dailyReturnColor =
		nav.daily_return === undefined || nav.daily_return === 0
			? undefined
			: nav.daily_return > 0
				? "#52c41a"
				: "#f5222d";

	const items: DescriptionsProps["items"] = [
		{
			key: "code",
			label: "基金代码",
			children: basic.code,
		},
		{
			key: "type",
			label: "基金类型",
			children: <Tag color="blue">{FUND_TYPES[basic.type] || basic.type}</Tag>,
		},
		{
			key: "nav",
			label: "最新净值",
			children: (
				<Text strong style={{ fontSize: 24 }}>
					{nav.latest_nav != null ? nav.latest_nav.toFixed(4) : "--"}
				</Text>
			),
		},
		{
			key: "accumulated_nav",
			label: "累计净值",
			children: nav.accumulated_nav?.toFixed(4) ?? "--",
		},
		{
			key: "daily_return",
			label: "日收益",
			children: (
				<Text strong style={{ color: dailyReturnColor, fontSize: 16 }}>
					{nav.daily_return !== undefined
						? formatPercent(nav.daily_return)
						: "--"}
				</Text>
			),
		},
		{
			key: "scale",
			label: "基金规模",
			children:
				basic.scale !== undefined ? `${basic.scale.toFixed(2)} 亿` : "--",
		},
		{
			key: "fee_rate",
			label: "费率",
			children:
				basic.fee_rate !== undefined
					? `${(basic.fee_rate * 100).toFixed(2)}%`
					: "--",
		},
		{
			key: "company",
			label: "基金公司",
			children: basic.company || "--",
		},
		{
			key: "ytd_return",
			label: "今年以来收益",
			children:
				basic.ytd_return !== undefined ? formatPercent(basic.ytd_return) : "--",
		},
		{
			key: "one_year_return",
			label: "近一年收益",
			children:
				basic.one_year_return !== undefined
					? formatPercent(basic.one_year_return)
					: "--",
		},
	];

	return (
		<Descriptions
			title="基本信息"
			bordered
			column={{ xs: 1, sm: 2, md: 3 }}
			items={items}
			style={{ background: "#fff", borderRadius: 8, padding: 16 }}
		/>
	);
}

export default FundInfo;
