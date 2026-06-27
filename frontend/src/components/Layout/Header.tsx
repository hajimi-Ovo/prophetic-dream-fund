import {
	BulbOutlined,
	DashboardOutlined,
	FundOutlined,
	MenuOutlined,
	WalletOutlined,
} from "@ant-design/icons";
import { Layout as AntLayout, Button, Menu, Typography } from "antd";
import type { MenuProps } from "antd";
import { useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";

const { Header: AntHeader } = AntLayout;

const menuItems: MenuProps["items"] = [
	{
		key: "/",
		icon: <DashboardOutlined />,
		label: <NavLink to="/">首页</NavLink>,
	},
	{
		key: "/holdings",
		icon: <WalletOutlined />,
		label: <NavLink to="/holdings">我的基金</NavLink>,
	},
	{
		key: "/market",
		icon: <FundOutlined />,
		label: <NavLink to="/market">基金行情</NavLink>,
	},
	{
		key: "/recommend",
		icon: <BulbOutlined />,
		label: <NavLink to="/recommend">智能推荐</NavLink>,
	},
];

function Header() {
	const location = useLocation();
	const navigate = useNavigate();
	const [mobileMenuVisible, setMobileMenuVisible] = useState(false);

	const selectedKey =
		location.pathname === "/" ? "/" : `/${location.pathname.split("/")[1]}`;

	const handleMenuClick: MenuProps["onClick"] = (e) => {
		navigate(e.key);
		setMobileMenuVisible(false);
	};

	return (
		<AntHeader
			style={{
				display: "flex",
				alignItems: "center",
				justifyContent: "space-between",
				padding: "0 24px",
				background: "#001529",
				position: "sticky",
				top: 0,
				zIndex: 100,
			}}
		>
			<div style={{ display: "flex", alignItems: "center", gap: 16 }}>
				<Typography.Title
					level={4}
					style={{ color: "#fff", margin: 0, whiteSpace: "nowrap" }}
				>
					预知梦基金
				</Typography.Title>
			</div>

			{/* Desktop Menu */}
			<Menu
				theme="dark"
				mode="horizontal"
				selectedKeys={[selectedKey]}
				items={menuItems}
				onClick={handleMenuClick}
				style={{
					flex: 1,
					justifyContent: "flex-end",
					borderBottom: "none",
					minWidth: 0,
				}}
				className="desktop-menu"
			/>

			{/* Mobile Hamburger */}
			<div className="mobile-menu-trigger">
				<Button
					type="text"
					icon={<MenuOutlined />}
					onClick={() => setMobileMenuVisible(!mobileMenuVisible)}
					style={{ color: "#fff" }}
				/>
			</div>

			{/* Mobile Dropdown Menu */}
			{mobileMenuVisible && (
				<div
					style={{
						position: "absolute",
						top: 64,
						left: 0,
						right: 0,
						background: "#001529",
						zIndex: 99,
					}}
				>
					<Menu
						theme="dark"
						mode="vertical"
						selectedKeys={[selectedKey]}
						items={menuItems}
						onClick={handleMenuClick}
					/>
				</div>
			)}
		</AntHeader>
	);
}

export default Header;
