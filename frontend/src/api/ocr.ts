import { post } from "./client";

export interface OcrHoldingItem {
	fund_code: string | null;
	fund_name: string | null;
	amount: string | null;
	shares: string | null;
	confidence: number;
	raw_line: string;
}

export interface OcrResult {
	raw_text: string;
	items: OcrHoldingItem[];
	overall_confidence: number;
}

export interface OcrConfirmItem {
	fund_code: string;
	fund_name?: string | null;
	amount: string;
	shares?: string | null;
}

export interface OcrConfirmResponse {
	created_count: number;
	error_count: number;
	items: unknown[];
	errors: unknown[];
}

/** Upload an image for OCR processing */
export async function uploadOcrImage(file: File): Promise<OcrResult> {
	const formData = new FormData();
	formData.append("file", file);

	return post<OcrResult>("/holdings/ocr", formData, {
		headers: {
			// Let the browser set the correct multipart boundary
		},
	}).then((res) => res.data);
}

/** Confirm OCR results and batch-create holdings */
export async function confirmOcrResults(
	items: OcrConfirmItem[],
	buyDate?: string,
): Promise<OcrConfirmResponse> {
	return post<OcrConfirmResponse>("/holdings/ocr/confirm", {
		items,
		buy_date: buyDate,
	}).then((res) => res.data);
}
