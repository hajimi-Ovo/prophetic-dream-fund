import { useHoldingStore } from "@/stores/useHoldingStore";
import type { Holding } from "@/types/holding";
import { formatCurrency, formatPercent } from "@/utils/format";
import { Button, Card, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

const { Text } = Typography;

function HoldingsTable() {
	const navigate = useNavigate();
	const { holdings, fetchHoldings, loading, error } = useHoldingStore();

	useEffect(() => {
		fetchHoldings();
	}, [fetchHoldings]);

	const topHoldings = holdings.slice(0, 5);

	const columns: ColumnsType<Holding> = [
		{
			title: "基金名称",
			dataIndex: "fund_name",
			key: "fund_name",
			width: 200,
		},
		{
			title: "持有金额",
			dataIndex: "amount",
			key: "amount",
			render: (v: number) => formatCurrency(v),
		},
		{
			title: "收益金额",
			dataIndex: "profit_loss",
			key: "profit_loss",
			render: (v: number) => {
				const color = v >= 0 ? "#cf1322" : "#3f8600";
				return <Text style={{ color }}>{formatCurrency(v)}</Text>;
			},
		},
		{
			title: "收益率",
			dataIndex: "profit_loss_ratio",
			key: "profit_loss_ratio",
			render: (v: number) => {
				const color = v >= 0 ? "#cf1322" : "#3f8600";
				return <Text style={{ color }}>{formatPercent(v)}</Text>;
			},
		},
		{
			title: "占比",
			dataIndex: "holding_ratio",
			key: "holding_ratio",
			render: (v: number) => formatPercent(v),
		},
	];

	const totalAmount = topHoldings.reduce((sum, h) => sum + h.amount, 0);
	const totalProfit = topHoldings.reduce((sum, h) => sum + h.profit_loss, 0);

	const footerData: Partial<Holding> & { key: string; fund_name: string } = {
		key: "total",
		fund_name: "合计",
		amount: totalAmount,
		profit_loss: totalProfit,
		profit_loss_ratio: totalAmount
			? totalProfit / (totalAmount - totalProfit)
			: 0,
		holding_ratio: 1,
	};

	const dataSource =
		topHoldings.length > 0 ? [...topHoldings, footerData as Holding] : [];

	return (
		<Card
			title="持仓概览"
			extra={
				<Button type="link" onClick={() => navigate("/holdings")}>
					查看全部 →
				</Button>
			}
			style={{ marginTop: 16 }}
		>
			{error && <Text type="danger">{error}</Text>}
			<Table
				columns={columns}
				dataSource={dataSource}
				loading={loading}
				rowKey="id"
				pagination={false}
				size="small"
				scroll={{ x: 600 }}
				onRow={(record) => {
					const row = record as Holding & { key?: string };
					if (row.key === "total") {
						return { style: { fontWeight: "bold" } };
					}
					return {};
				}}
			/>
		</Card>
	);
}

export default HoldingsTable;
