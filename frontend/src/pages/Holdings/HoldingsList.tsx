import { useHoldingStore } from "@/stores/useHoldingStore";
import type { Holding } from "@/types/holding";
import { formatCurrency, formatPercent } from "@/utils/format";
import { DeleteOutlined, EditOutlined, PlusOutlined } from "@ant-design/icons";
import { Button, Popconfirm, Space, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useState } from "react";
import ManualEntryForm from "./ManualEntryForm";

const { Text } = Typography;

function HoldingsList() {
	const { holdings, fetchHoldings, deleteHolding } = useHoldingStore();
	const [formOpen, setFormOpen] = useState(false);
	const [editRecord, setEditRecord] = useState<Holding | null>(null);

	useEffect(() => {
		fetchHoldings();
	}, [fetchHoldings]);

	const handleDelete = async (id: number) => {
		await deleteHolding(id);
	};

	const handleEdit = (record: Holding) => {
		setEditRecord(record);
		setFormOpen(true);
	};

	const handleAdd = () => {
		setEditRecord(null);
		setFormOpen(true);
	};

	const columns: ColumnsType<Holding> = [
		{
			title: "基金名称",
			dataIndex: "fund_name",
			key: "fund_name",
			width: 160,
			fixed: "left",
		},
		{
			title: "买入金额",
			dataIndex: "amount",
			key: "amount",
			width: 110,
			render: (v: number) => formatCurrency(v),
		},
		{
			title: "持有份额",
			dataIndex: "shares",
			key: "shares",
			width: 100,
			render: (v: number) => (v != null ? v.toFixed(2) : "--"),
		},
		{
			title: "买入净值",
			dataIndex: "buy_nav",
			key: "buy_nav",
			width: 100,
			render: (v: number) => v?.toFixed(4) ?? "—",
		},
		{
			title: "最新净值",
			dataIndex: "latest_nav",
			key: "latest_nav",
			width: 100,
			render: (v: number) => v?.toFixed(4) ?? "—",
		},
		{
			title: "市值",
			dataIndex: "market_value",
			key: "market_value",
			width: 110,
			render: (v: number) => formatCurrency(v),
		},
		{
			title: "收益金额",
			dataIndex: "profit_loss",
			key: "profit_loss",
			width: 110,
			render: (v: number) => {
				const color = v >= 0 ? "#cf1322" : "#3f8600";
				return <Text style={{ color }}>{formatCurrency(v)}</Text>;
			},
		},
		{
			title: "收益率",
			dataIndex: "profit_loss_ratio",
			key: "profit_loss_ratio",
			width: 90,
			render: (v: number) => {
				const color = v >= 0 ? "#cf1322" : "#3f8600";
				return <Text style={{ color }}>{formatPercent(v)}</Text>;
			},
		},
		{
			title: "占比",
			dataIndex: "holding_ratio",
			key: "holding_ratio",
			width: 80,
			render: (v: number) => formatPercent(v),
		},
		{
			title: "操作",
			key: "actions",
			width: 120,
			fixed: "right",
			render: (_: unknown, record: Holding) => (
				<Space size="small">
					<Button
						type="link"
						size="small"
						icon={<EditOutlined />}
						onClick={() => handleEdit(record)}
					>
						编辑
					</Button>
					<Popconfirm
						title="确认删除该持仓？"
						description="删除后无法恢复"
						onConfirm={() => handleDelete(record.id)}
						okText="确认"
						cancelText="取消"
					>
						<Button type="link" size="small" danger icon={<DeleteOutlined />}>
							删除
						</Button>
					</Popconfirm>
				</Space>
			),
		},
	];

	const totalAmount = holdings.reduce((s, h) => s + h.amount, 0);
	const totalMarketValue = holdings.reduce((s, h) => s + h.market_value, 0);
	const totalProfit = holdings.reduce((s, h) => s + h.profit_loss, 0);

	return (
		<div>
			<div
				style={{
					marginBottom: 16,
					display: "flex",
					justifyContent: "space-between",
					alignItems: "center",
				}}
			>
				<Text type="secondary">
					共 {holdings.length} 只基金，总市值 {formatCurrency(totalMarketValue)}
				</Text>
				<Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
					手动录入
				</Button>
			</div>

			<Table
				columns={columns}
				dataSource={holdings}
				rowKey="id"
				scroll={{ x: 800 }}
				pagination={{ pageSize: 10, showTotal: (t) => `共 ${t} 条` }}
				summary={() => (
					<Table.Summary.Row>
						<Table.Summary.Cell index={0}>
							<Text strong>合计</Text>
						</Table.Summary.Cell>
						<Table.Summary.Cell index={1}>
							<Text strong>{formatCurrency(totalAmount)}</Text>
						</Table.Summary.Cell>
						<Table.Summary.Cell index={2}>—</Table.Summary.Cell>
						<Table.Summary.Cell index={3}>—</Table.Summary.Cell>
						<Table.Summary.Cell index={4}>—</Table.Summary.Cell>
						<Table.Summary.Cell index={5}>
							<Text strong>{formatCurrency(totalMarketValue)}</Text>
						</Table.Summary.Cell>
						<Table.Summary.Cell index={6}>
							<Text
								strong
								style={{ color: totalProfit >= 0 ? "#cf1322" : "#3f8600" }}
							>
								{formatCurrency(totalProfit)}
							</Text>
						</Table.Summary.Cell>
						<Table.Summary.Cell index={7}>
							<Text
								strong
								style={{ color: totalProfit >= 0 ? "#cf1322" : "#3f8600" }}
							>
								{totalAmount > 0
									? formatPercent(totalProfit / totalAmount)
									: "0.00%"}
							</Text>
						</Table.Summary.Cell>
						<Table.Summary.Cell index={8}>100%</Table.Summary.Cell>
						<Table.Summary.Cell index={9}>—</Table.Summary.Cell>
					</Table.Summary.Row>
				)}
			/>

			<ManualEntryForm
				open={formOpen}
				editData={editRecord}
				onClose={() => {
					setFormOpen(false);
					setEditRecord(null);
				}}
			/>
		</div>
	);
}

export default HoldingsList;
