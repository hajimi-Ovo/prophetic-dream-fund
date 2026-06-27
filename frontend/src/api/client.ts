import type { ApiResponse } from "@/types/common";
import axios, { type AxiosRequestConfig, type AxiosResponse } from "axios";

const apiClient = axios.create({
	baseURL: "/api/v1",
	timeout: 15000,
	headers: {
		"Content-Type": "application/json",
	},
});

// Request interceptor
apiClient.interceptors.request.use(
	(config) => {
		// Ensure Content-Type is set
		if (!config.headers["Content-Type"]) {
			config.headers["Content-Type"] = "application/json";
		}
		return config;
	},
	(error) => {
		return Promise.reject(error);
	},
);

// Response interceptor
apiClient.interceptors.response.use(
	(response: AxiosResponse<ApiResponse<unknown>>) => {
		return response;
	},
	(error) => {
		if (error.response) {
			const { status, data } = error.response;
			const message = data?.message || `请求失败 (${status})`;

			switch (status) {
				case 401:
					// Handle unauthorized
					console.error("未授权访问，请重新登录");
					break;
				case 403:
					console.error("没有访问权限");
					break;
				case 404:
					console.error("请求的资源不存在");
					break;
				case 500:
					console.error("服务器内部错误");
					break;
				default:
					console.error(message);
			}
		} else if (error.request) {
			console.error("网络请求失败，请检查网络连接");
		} else {
			console.error("请求配置错误:", error.message);
		}
		return Promise.reject(error);
	},
);

// Typed HTTP helpers
export async function get<T>(
	url: string,
	config?: AxiosRequestConfig,
): Promise<ApiResponse<T>> {
	const response = await apiClient.get<ApiResponse<T>>(url, config);
	return response.data;
}

export async function post<T>(
	url: string,
	data?: unknown,
	config?: AxiosRequestConfig,
): Promise<ApiResponse<T>> {
	const response = await apiClient.post<ApiResponse<T>>(url, data, config);
	return response.data;
}

export async function put<T>(
	url: string,
	data?: unknown,
	config?: AxiosRequestConfig,
): Promise<ApiResponse<T>> {
	const response = await apiClient.put<ApiResponse<T>>(url, data, config);
	return response.data;
}

export async function del<T>(
	url: string,
	config?: AxiosRequestConfig,
): Promise<ApiResponse<T>> {
	const response = await apiClient.delete<ApiResponse<T>>(url, config);
	return response.data;
}

export default apiClient;
