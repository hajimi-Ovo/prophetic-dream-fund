import type { FundPortfolioItem } from "@/types/fund";
import { Card, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";

const { Text } = Typography;

interface HoldingsBreakdownProps {
	portfolio: FundPortfolioItem[];
}

function HoldingsBreakdown({ portfolio }: HoldingsBreakdownProps) {
	const columns: ColumnsType<FundPortfolioItem> = [
		{
			title: "股票代码",
			dataIndex: "stock_code",
			key: "stock_code",
			width: 120,
		},
		{
			title: "股票名称",
			dataIndex: "stock_name",
			key: "stock_name",
		},
		{
			title: "占比",
			dataIndex: "ratio",
			key: "ratio",
			width: 100,
			render: (ratio: number) => `${(ratio * 100).toFixed(2)}%`,
		},
	];

	return (
		<Card title="持仓明细" style={{ marginTop: 16 }}>
			{portfolio.length > 0 ? (
				<Table
					columns={columns}
					dataSource={portfolio}
					rowKey="stock_code"
					pagination={false}
					size="small"
				/>
			) : (
				<div style={{ textAlign: "center", padding: 40, color: "#999" }}>
					<Text type="secondary">暂无持仓数据</Text>
				</div>
			)}
		</Card>
	);
}

export default HoldingsBreakdown;
