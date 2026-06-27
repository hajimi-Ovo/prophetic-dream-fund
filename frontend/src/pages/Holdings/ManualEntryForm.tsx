import { useHoldingStore } from "@/stores/useHoldingStore";
import type { Holding, HoldingCreate, HoldingUpdate } from "@/types/holding";
import {
	DatePicker,
	Form,
	Input,
	InputNumber,
	Modal,
	message,
} from "antd";
import dayjs from "dayjs";
import { useEffect } from "react";

interface ManualEntryFormProps {
	open: boolean;
	editData?: Holding | null;
	onClose: () => void;
}

function ManualEntryForm({ open, editData, onClose }: ManualEntryFormProps) {
	const [form] = Form.useForm();
	const { addHolding, updateHolding, loading } = useHoldingStore();
	const isEdit = !!editData;

	useEffect(() => {
		if (open) {
			if (editData) {
				form.setFieldsValue({
					fund_code: editData.fund_code,
					fund_name: editData.fund_name,
					buy_date: editData.buy_date ? dayjs(editData.buy_date) : undefined,
					amount: editData.amount,
					shares: editData.shares,
					buy_nav: editData.buy_nav,
				});
			} else {
				form.resetFields();
			}
		}
	}, [open, editData, form]);

	const handleSubmit = async () => {
		try {
			const values = await form.validateFields();
			const data: HoldingCreate = {
				fund_code: values.fund_code,
				fund_name: values.fund_name || undefined,
				buy_date: values.buy_date
					? values.buy_date.format("YYYY-MM-DD")
					: undefined,
				amount: values.amount,
				shares: values.shares,
				buy_nav: values.buy_nav || undefined,
			};

			if (isEdit && editData) {
				const updateData: HoldingUpdate = {
					fund_name: values.fund_name || undefined,
					buy_date: values.buy_date
						? values.buy_date.format("YYYY-MM-DD")
						: undefined,
					amount: values.amount,
					shares: values.shares,
					buy_nav: values.buy_nav || undefined,
				};
				const result = await updateHolding(editData.id, updateData);
				if (result) {
					message.success("持仓更新成功");
					onClose();
				}
			} else {
				const result = await addHolding(data);
				if (result) {
					message.success("持仓添加成功");
					onClose();
				}
			}
		} catch {
			// Validation error, do nothing
		}
	};

	return (
		<Modal
			title={isEdit ? "编辑持仓" : "手动录入"}
			open={open}
			onCancel={onClose}
			onOk={handleSubmit}
			confirmLoading={loading}
			destroyOnHidden
			width={520}
			okText={isEdit ? "保存" : "添加"}
			cancelText="取消"
		>
			<Form form={form} layout="vertical" style={{ marginTop: 16 }}>
				<Form.Item
					name="fund_code"
					label="基金代码"
					rules={[{ required: true, message: "请输入基金代码" }]}
				>
					<Input placeholder="例如: 000001" disabled={isEdit} />
				</Form.Item>

				<Form.Item name="fund_name" label="基金名称">
					<Input placeholder="例如: 华夏成长混合" />
				</Form.Item>

				<Form.Item name="buy_date" label="买入日期">
					<DatePicker style={{ width: "100%" }} placeholder="选择买入日期" />
				</Form.Item>

				<Form.Item
					name="amount"
					label="买入金额 (元)"
					rules={[
						{ required: true, message: "请输入买入金额" },
						{
							type: "number",
							min: 0.01,
							message: "金额必须大于0",
						},
					]}
				>
					<InputNumber
						style={{ width: "100%" }}
						min={0.01}
						precision={2}
						placeholder="0.00"
						addonAfter="元"
					/>
				</Form.Item>

				<Form.Item
					name="shares"
					label="买入份额"
					rules={[
						{ required: true, message: "请输入买入份额" },
						{
							type: "number",
							min: 0.01,
							message: "份额必须大于0",
						},
					]}
				>
					<InputNumber
						style={{ width: "100%" }}
						min={0.01}
						precision={2}
						placeholder="0.00"
						addonAfter="份"
					/>
				</Form.Item>

				<Form.Item name="buy_nav" label="买入净值 (选填)">
					<InputNumber
						style={{ width: "100%" }}
						min={0.0001}
						precision={4}
						placeholder="0.0000"
					/>
				</Form.Item>
			</Form>
		</Modal>
	);
}

export default ManualEntryForm;
