import type { ApiResponse } from "@/types/common";
import type {
	Holding,
	HoldingCreate,
	HoldingListResponse,
	HoldingUpdate,
} from "@/types/holding";
import { del, get, post, put } from "./client";

export async function getHoldings(): Promise<ApiResponse<HoldingListResponse>> {
	return get<HoldingListResponse>("/holdings");
}

export async function getHolding(id: number): Promise<ApiResponse<Holding>> {
	return get<Holding>(`/holdings/${id}`);
}

export async function createHolding(
	data: HoldingCreate,
): Promise<ApiResponse<Holding>> {
	return post<Holding>("/holdings", data);
}

export async function updateHolding(
	id: number,
	data: HoldingUpdate,
): Promise<ApiResponse<Holding>> {
	return put<Holding>(`/holdings/${id}`, data);
}

export async function deleteHolding(id: number): Promise<void> {
	await del(`/holdings/${id}`);
}
