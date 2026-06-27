import type { ApiResponse } from "@/types/common";
import type { WatchlistCreate, WatchlistItem } from "@/types/holding";
import { del, get, post } from "./client";

export async function getWatchlist(): Promise<ApiResponse<WatchlistItem[]>> {
	return get<WatchlistItem[]>("/watchlist");
}

export async function addToWatchlist(
	data: WatchlistCreate,
): Promise<ApiResponse<WatchlistItem>> {
	return post<WatchlistItem>("/watchlist", data);
}

export async function removeFromWatchlist(fundCode: string): Promise<void> {
	await del(`/watchlist/${fundCode}`);
}
