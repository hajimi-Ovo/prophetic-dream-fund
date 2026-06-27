import { useMarketStore } from "@/stores/useMarketStore";
import { FUND_TYPES } from "@/utils/constants";
import { ReloadOutlined, SearchOutlined } from "@ant-design/icons";
import { Button, Col, InputNumber, Radio, Row, Select, Space } from "antd";

const SORT_OPTIONS = [
	{ label: "净值", value: "latest_nav" },
	{ label: "日收益", value: "daily_return" },
	{ label: "年收益", value: "one_year_return" },
	{ label: "三年收益", value: "three_year_return" },
];

const TYPE_OPTIONS = Object.entries(FUND_TYPES).map(([value, label]) => ({
	value,
	label,
}));

function FilterPanel() {
	const { filters, setFilters, filterFunds, loading } = useMarketStore();

	const handleApply = () => {
		filterFunds({ ...filters, page: 1 });
	};

	const handleReset = () => {
		setFilters({
			type: undefined,
			min_scale: undefined,
			max_scale: undefined,
			max_fee: undefined,
			sort_by: undefined,
			order: undefined,
		});
	};

	return (
		<div
			style={{
				padding: "16px",
				background: "#fff",
				borderRadius: 8,
				marginBottom: 16,
			}}
		>
			<Row gutter={[16, 12]} align="middle">
				<Col xs={24} sm={12} md={6}>
					<Select
						placeholder="基金类型"
						allowClear
						style={{ width: "100%" }}
						value={filters.type}
						onChange={(val) => setFilters({ type: val })}
						options={TYPE_OPTIONS}
					/>
				</Col>
				<Col xs={12} sm={6} md={3}>
					<InputNumber
						placeholder="最小规模(亿)"
						style={{ width: "100%" }}
						value={filters.min_scale}
						onChange={(val) => setFilters({ min_scale: val ?? undefined })}
						min={0}
					/>
				</Col>
				<Col xs={12} sm={6} md={3}>
					<InputNumber
						placeholder="最大规模(亿)"
						style={{ width: "100%" }}
						value={filters.max_scale}
						onChange={(val) => setFilters({ max_scale: val ?? undefined })}
						min={0}
					/>
				</Col>
				<Col xs={12} sm={6} md={3}>
					<InputNumber
						placeholder="最高费率(%)"
						style={{ width: "100%" }}
						value={filters.max_fee}
						onChange={(val) => setFilters({ max_fee: val ?? undefined })}
						min={0}
						max={100}
					/>
				</Col>
				<Col xs={12} sm={6} md={3}>
					<Select
						placeholder="排序方式"
						allowClear
						style={{ width: "100%" }}
						value={filters.sort_by}
						onChange={(val) => setFilters({ sort_by: val })}
						options={SORT_OPTIONS}
					/>
				</Col>
				<Col xs={12} sm={6} md={3}>
					<Radio.Group
						value={filters.order}
						onChange={(e) => setFilters({ order: e.target.value })}
						optionType="button"
						buttonStyle="solid"
						size="small"
					>
						<Radio.Button value="desc">降序</Radio.Button>
						<Radio.Button value="asc">升序</Radio.Button>
					</Radio.Group>
				</Col>
				<Col xs={24} sm={6} md={3}>
					<Space>
						<Button
							type="primary"
							icon={<SearchOutlined />}
							onClick={handleApply}
							loading={loading}
						>
							筛选
						</Button>
						<Button icon={<ReloadOutlined />} onClick={handleReset}>
							重置
						</Button>
					</Space>
				</Col>
			</Row>
		</div>
	);
}

export default FilterPanel;
