import {
	CameraOutlined,
	CheckOutlined,
	CloseOutlined,
} from "@ant-design/icons";
import type { OcrHoldingItem } from "@/api/ocr";
import { confirmOcrResults, uploadOcrImage } from "@/api/ocr";
import { useHoldingStore } from "@/stores/useHoldingStore";
import {
	Button,
	Col,
	DatePicker,
	Form,
	message,
	Modal,
	Row,
	Space,
	Table,
	Typography,
} from "antd";
import dayjs from "dayjs";
import { useRef, useState } from "react";
import HoldingsList from "./HoldingsList";
import WatchlistPanel from "./WatchlistPanel";

const { Title, Text } = Typography;

function Holdings() {
	const { fetchHoldings } = useHoldingStore();
	const fileInputRef = useRef<HTMLInputElement>(null);

	// OCR flow state
	const [ocrLoading, setOcrLoading] = useState(false);
	const [ocrResult, setOcrResult] = useState<OcrHoldingItem[] | null>(null);
	const [ocrModalOpen, setOcrModalOpen] = useState(false);
	const [confirmLoading, setConfirmLoading] = useState(false);
	const [form] = Form.useForm();

	const handleUploadClick = () => {
		fileInputRef.current?.click();
	};

	const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
		const file = e.target.files?.[0];
		if (!file) return;

		setOcrLoading(true);
		try {
			const result = await uploadOcrImage(file);
			if (result.items && result.items.length > 0) {
				setOcrResult(result.items);
				setOcrModalOpen(true);
			} else {
				message.warning("未能识别出基金持仓信息，请尝试手动录入");
			}
		} catch {
			message.error("OCR 识别失败，请重试");
		} finally {
			setOcrLoading(false);
			// Reset file input so the same file can be re-selected
			if (fileInputRef.current) {
				fileInputRef.current.value = "";
			}
		}
	};

	const handleConfirmOcr = async () => {
		if (!ocrResult) return;

		try {
			await form.validateFields();
			const buyDate = form.getFieldValue("buy_date");
			const buyDateStr = buyDate
				? dayjs(buyDate).format("YYYY-MM-DD")
				: undefined;

			setConfirmLoading(true);
			const response = await confirmOcrResults(
				ocrResult
					.filter((item) => item.fund_code)
					.map((item) => ({
						fund_code: item.fund_code!,
						fund_name: item.fund_name,
						amount: item.amount ?? "0",
						shares: item.shares ?? "0",
					})),
				buyDateStr,
			);

			if (response.created_count > 0) {
				message.success(`成功创建 ${response.created_count} 条持仓记录`);
				fetchHoldings();
			}
			if (response.error_count > 0) {
				message.warning(`${response.error_count} 条记录创建失败`);
			}

			setOcrModalOpen(false);
			setOcrResult(null);
			form.resetFields();
		} catch {
			// Validation error — antd Form shows inline error
		} finally {
			setConfirmLoading(false);
		}
	};

	const ocrColumns = [
		{
			title: "基金代码",
			dataIndex: "fund_code",
			key: "fund_code",
			width: 110,
		},
		{
			title: "基金名称",
			dataIndex: "fund_name",
			key: "fund_name",
			width: 200,
			render: (v: string | null) => v ?? <Text type="secondary">未识别</Text>,
		},
		{
			title: "买入金额",
			dataIndex: "amount",
			key: "amount",
			width: 120,
			render: (v: string | null) =>
				v ? `¥${Number(v).toLocaleString()}` : <Text type="secondary">—</Text>,
		},
		{
			title: "持有份额",
			dataIndex: "shares",
			key: "shares",
			width: 120,
			render: (v: string | null) =>
				v ? `${Number(v).toLocaleString()} 份` : <Text type="secondary">—</Text>,
		},
		{
			title: "置信度",
			dataIndex: "confidence",
			key: "confidence",
			width: 80,
			render: (v: number) => (v != null ? `${(v * 100).toFixed(0)}%` : "--"),
		},
		{
			title: "原始识别",
			dataIndex: "raw_line",
			key: "raw_line",
			ellipsis: true,
		},
	];

	return (
		<div>
			<div
				style={{
					display: "flex",
					justifyContent: "space-between",
					alignItems: "center",
					marginBottom: 16,
				}}
			>
				<Title level={3} style={{ margin: 0 }}>
					持仓管理
				</Title>
				<Space>
					{/* Hidden file input for OCR upload */}
					<input
						ref={fileInputRef}
						type="file"
						accept="image/*"
						style={{ display: "none" }}
						onChange={handleFileChange}
					/>
					<Button
						icon={<CameraOutlined />}
						loading={ocrLoading}
						onClick={handleUploadClick}
					>
						截图识别
					</Button>
				</Space>
			</div>

			<Row gutter={[16, 16]}>
				<Col xs={24} lg={16}>
					<HoldingsList />
				</Col>
				<Col xs={24} lg={8}>
					<WatchlistPanel />
				</Col>
			</Row>

			{/* OCR Result Confirmation Modal */}
			<Modal
				title="识别结果确认"
				open={ocrModalOpen}
				onOk={handleConfirmOcr}
				onCancel={() => {
					setOcrModalOpen(false);
					setOcrResult(null);
					form.resetFields();
				}}
				okText="确认导入"
				cancelText="取消"
				confirmLoading={confirmLoading}
				width={900}
				okButtonProps={{ icon: <CheckOutlined /> }}
				cancelButtonProps={{ icon: <CloseOutlined /> }}
			>
				<Form form={form} layout="inline" style={{ marginBottom: 16 }}>
					<Form.Item
						name="buy_date"
						label="买入日期"
						rules={[{ required: true, message: "请选择买入日期" }]}
						initialValue={dayjs()}
					>
						<DatePicker style={{ width: 160 }} />
					</Form.Item>
				</Form>

				<Text type="secondary" style={{ display: "block", marginBottom: 12 }}>
					请检查识别结果，确认无误后点击「确认导入」。不正确的行可以在导入后手动编辑。
				</Text>

				<Table
					columns={ocrColumns}
					dataSource={ocrResult ?? []}
					rowKey={(record, index) =>
						record.fund_code ?? `row-${index}`
					}
					scroll={{ x: 750 }}
					pagination={false}
					size="small"
				/>
			</Modal>
		</div>
	);
}

export default Holdings;
