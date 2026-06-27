import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { BrowserRouter } from "react-router-dom";
import AppRoutes from "./router";

function App() {
	return (
		<ConfigProvider locale={zhCN}>
			<BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
				<AppRoutes />
			</BrowserRouter>
		</ConfigProvider>
	);
}

export default App;
