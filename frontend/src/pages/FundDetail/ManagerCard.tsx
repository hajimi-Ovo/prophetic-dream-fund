import type { FundManager } from "@/types/fund";
import { formatDate, formatPercent } from "@/utils/format";
import { UserOutlined } from "@ant-design/icons";
import { Card, Descriptions, Typography } from "antd";

const { Text } = Typography;

interface ManagerCardProps {
	manager: FundManager;
}

function ManagerCard({ manager }: ManagerCardProps) {
	return (
		<Card
			title={
				<span>
					<UserOutlined style={{ marginRight: 8 }} />
					基金经理
				</span>
			}
			style={{ marginTop: 16 }}
		>
			<Descriptions column={{ xs: 1, sm: 2 }} size="small">
				<Descriptions.Item label="姓名">
					<Text strong>{manager.name}</Text>
				</Descriptions.Item>
				{manager.start_date && (
					<Descriptions.Item label="任职日期">
						{formatDate(manager.start_date)}
					</Descriptions.Item>
				)}
				{manager.tenure_return !== undefined && (
					<Descriptions.Item label="任职回报">
						<Text
							strong
							style={{
								color:
									manager.tenure_return > 0
										? "#52c41a"
										: manager.tenure_return < 0
											? "#f5222d"
											: undefined,
							}}
						>
							{formatPercent(manager.tenure_return)}
						</Text>
					</Descriptions.Item>
				)}
			</Descriptions>
			{manager.description && (
				<div style={{ marginTop: 12 }}>
					<Text type="secondary">{manager.description}</Text>
				</div>
			)}
		</Card>
	);
}

export default ManagerCard;
