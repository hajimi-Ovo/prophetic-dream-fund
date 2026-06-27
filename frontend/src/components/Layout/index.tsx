import { Layout as AntLayout } from "antd";
import { Outlet } from "react-router-dom";
import Header from "./Header";

const { Content, Footer } = AntLayout;

function Layout() {
	return (
		<AntLayout style={{ minHeight: "100vh" }}>
			<Header />
			<Content style={{ padding: "24px", background: "#f5f5f5" }}>
				<Outlet />
			</Content>
			<Footer style={{ textAlign: "center", background: "#f0f0f0" }}>
				预知梦基金 ©2026
			</Footer>
		</AntLayout>
	);
}

export default Layout;
