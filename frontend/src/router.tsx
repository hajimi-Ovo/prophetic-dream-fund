import Layout from "@/components/Layout";
import { Spin } from "antd";
import { Suspense, lazy } from "react";
import { Route, Routes } from "react-router-dom";

const Dashboard = lazy(() => import("@/pages/Dashboard"));
const Holdings = lazy(() => import("@/pages/Holdings"));
const Market = lazy(() => import("@/pages/Market"));
const FundDetail = lazy(() => import("@/pages/FundDetail"));
const Recommendations = lazy(() => import("@/pages/Recommendations"));
const NotFound = lazy(() => import("@/pages/NotFound"));

const LoadingFallback = () => (
	<div
		style={{
			display: "flex",
			justifyContent: "center",
			alignItems: "center",
			minHeight: "400px",
		}}
	>
		<Spin size="large" />
	</div>
);

function AppRoutes() {
	return (
		<Suspense fallback={<LoadingFallback />}>
			<Routes>
				<Route element={<Layout />}>
					<Route path="/" element={<Dashboard />} />
					<Route path="/holdings" element={<Holdings />} />
					<Route path="/market" element={<Market />} />
					<Route path="/market/:code" element={<FundDetail />} />
					<Route path="/recommend" element={<Recommendations />} />
					<Route path="*" element={<NotFound />} />
				</Route>
			</Routes>
		</Suspense>
	);
}

export default AppRoutes;
