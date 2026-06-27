import { useMarketStore } from "@/stores/useMarketStore";
import {
	Alert,
	Button,
	Col,
	Drawer,
	Grid,
	Pagination,
	Row,
	Spin,
	Typography,
} from "antd";
import { FilterOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import FilterPanel from "./FilterPanel";
import FundCard from "./FundCard";
import FundCompare from "./FundCompare";
import SearchBar from "./SearchBar";

const { Title } = Typography;
const { useBreakpoint } = Grid;

function Market() {
	const {
		fundList,
		loading,
		error,
		total,
		page,
		searchKeyword,
		filters,
		searchFunds,
		filterFunds,
	} = useMarketStore();

	const screens = useBreakpoint();
	const isMobile = !screens.lg; // lg = 992px; below that is mobile
	const [drawerOpen, setDrawerOpen] = useState(false);

	// Initial load
	useEffect(() => {
		searchFunds("", 1);
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, []);

	const handlePageChange = (newPage: number) => {
		if (searchKeyword) {
			searchFunds(searchKeyword, newPage);
		} else {
			filterFunds({ ...filters, page: newPage });
		}
	};

	const filterContent = <FilterPanel />;

	return (
		<div>
			<Title level={2} style={{ marginBottom: 16 }}>
				基金行情
			</Title>

			{/* Search bar */}
			<div style={{ marginBottom: 16 }}>
				<SearchBar />
			</div>

			{/* Filter panel: inline on desktop, inside Drawer on mobile */}
			{isMobile ? (
				<div style={{ marginBottom: 16 }}>
					<Button
						icon={<FilterOutlined />}
						onClick={() => setDrawerOpen(true)}
						block
					>
						筛选条件
					</Button>
					<Drawer
						title="筛选条件"
						placement="right"
						width={300}
						open={drawerOpen}
						onClose={() => setDrawerOpen(false)}
					>
						{filterContent}
					</Drawer>
				</div>
			) : (
				filterContent
			)}

			{/* Error message */}
			{error && (
				<Alert
					message={error}
					type="error"
					showIcon
					closable
					style={{ marginBottom: 16 }}
				/>
			)}

			{/* Loading state */}
			{loading && (
				<div style={{ textAlign: "center", padding: 60 }}>
					<Spin size="large" />
				</div>
			)}

			{/* Fund list */}
			{!loading && (
				<>
					<Row gutter={[16, 16]}>
						{fundList.map((fund) => (
							<Col key={fund.code} xs={24} sm={12} md={8} lg={6}>
								<FundCard fund={fund} />
							</Col>
						))}
					</Row>

					{fundList.length === 0 && !error && (
						<div style={{ textAlign: "center", padding: 60, color: "#999" }}>
							暂无基金数据，请尝试调整筛选条件
						</div>
					)}

					{/* Pagination */}
					{total > 0 && (
						<div
							style={{
								display: "flex",
								justifyContent: "center",
								marginTop: 24,
							}}
						>
							<Pagination
								current={page}
								total={total}
								pageSize={20}
								onChange={handlePageChange}
								showSizeChanger={false}
								showTotal={(t) => `共 ${t} 只基金`}
							/>
						</div>
					)}

					{/* Compare section */}
					{fundList.length > 0 && <FundCompare />}
				</>
			)}
		</div>
	);
}

export default Market;
