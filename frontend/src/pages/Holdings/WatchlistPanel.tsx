import { useHoldingStore } from "@/stores/useHoldingStore";
import type { WatchlistCreate } from "@/types/holding";
import { DeleteOutlined, PlusOutlined, StarFilled } from "@ant-design/icons";
import {
	Button,
	Card,
	Input,
	List,
	Modal,
	Popconfirm,
	Typography,
	message,
} from "antd";
import { useEffect, useState } from "react";

const { Text } = Typography;

function WatchlistPanel() {
	const { watchlist, fetchWatchlist, addToWatchlist, removeFromWatchlist } =
		useHoldingStore();
	const [addOpen, setAddOpen] = useState(false);
	const [fundCode, setFundCode] = useState("");
	const [fundName, setFundName] = useState("");
	const [adding, setAdding] = useState(false);

	useEffect(() => {
		fetchWatchlist();
	}, [fetchWatchlist]);

	const handleAdd = async () => {
		if (!fundCode.trim()) {
			message.warning("请输入基金代码");
			return;
		}
		setAdding(true);
		const data: WatchlistCreate = {
			fund_code: fundCode.trim(),
			fund_name: fundName.trim() || undefined,
		};
		const result = await addToWatchlist(data);
		setAdding(false);
		if (result) {
			message.success("已加入自选");
			setAddOpen(false);
			setFundCode("");
			setFundName("");
		}
	};

	const handleRemove = async (fundCode: string) => {
		await removeFromWatchlist(fundCode);
	};

	const formatDailyReturn = (ratio: number) => {
		const color = ratio >= 0 ? "#cf1322" : "#3f8600";
		const sign = ratio >= 0 ? "+" : "";
		return (
			<Text style={{ color }}>
				{sign}
				{(ratio * 100).toFixed(2)}%
			</Text>
		);
	};

	return (
		<Card
			title={
				<span>
					<StarFilled style={{ color: "#faad14", marginRight: 8 }} />
					自选基金
				</span>
			}
			extra={
				<Button
					type="link"
					size="small"
					icon={<PlusOutlined />}
					onClick={() => setAddOpen(true)}
				>
					添加
				</Button>
			}
			style={{ marginTop: 16 }}
		>
			{watchlist.length === 0 ? (
				<div style={{ textAlign: "center", padding: 40, color: "#999" }}>
					暂无自选基金，点击"添加"加入关注的基金
				</div>
			) : (
				<List
					dataSource={watchlist}
					renderItem={(item) => (
						<List.Item
							actions={[
								<Popconfirm
									key="delete"
									title="确认从自选中移除？"
									onConfirm={() => handleRemove(item.fund_code)}
									okText="确认"
									cancelText="取消"
								>
									<Button
										type="link"
										size="small"
										danger
										icon={<DeleteOutlined />}
									/>
								</Popconfirm>,
							]}
						>
							<List.Item.Meta
								title={
									<Text strong>
										{item.fund_name}{" "}
										<Text type="secondary" style={{ fontSize: 12 }}>
											{item.fund_code}
										</Text>
									</Text>
								}
								description={
									<span>
										<Text style={{ marginRight: 12 }}>
											净值 {item.latest_nav?.toFixed(4) ?? "—"}
										</Text>
										{item.daily_return_ratio !== undefined &&
											formatDailyReturn(item.daily_return_ratio)}
									</span>
								}
							/>
						</List.Item>
					)}
				/>
			)}

			<Modal
				title="添加自选基金"
				open={addOpen}
				onCancel={() => setAddOpen(false)}
				onOk={handleAdd}
				confirmLoading={adding}
				okText="添加"
				cancelText="取消"
				destroyOnHidden
			>
				<div style={{ padding: "16px 0" }}>
					<div style={{ marginBottom: 16 }}>
						<Text>基金代码</Text>
						<Input
							placeholder="请输入基金代码，例如: 000001"
							value={fundCode}
							onChange={(e) => setFundCode(e.target.value)}
							style={{ marginTop: 4 }}
						/>
					</div>
					<div>
						<Text>基金名称 (选填)</Text>
						<Input
							placeholder="例如: 华夏成长混合"
							value={fundName}
							onChange={(e) => setFundName(e.target.value)}
							style={{ marginTop: 4 }}
						/>
					</div>
				</div>
			</Modal>
		</Card>
	);
}

export default WatchlistPanel;
