import { useMarketStore } from "@/stores/useMarketStore";
import { SearchOutlined } from "@ant-design/icons";
import { Input } from "antd";
import { useEffect, useRef, useState } from "react";

function SearchBar() {
	const { searchFunds, loading } = useMarketStore();
	const [value, setValue] = useState("");
	const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	useEffect(() => {
		return () => {
			if (timerRef.current) {
				clearTimeout(timerRef.current);
			}
		};
	}, []);

	const handleSearch = (keyword: string) => {
		const trimmed = keyword.trim();
		if (trimmed) {
			searchFunds(trimmed);
		}
	};

	const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		const newValue = e.target.value;
		setValue(newValue);

		if (timerRef.current) {
			clearTimeout(timerRef.current);
		}

		timerRef.current = setTimeout(() => {
			handleSearch(newValue);
		}, 300);
	};

	return (
		<Input.Search
			placeholder="搜索基金代码或名称..."
			allowClear
			enterButton={<SearchOutlined />}
			loading={loading}
			value={value}
			onChange={handleChange}
			onSearch={handleSearch}
			size="large"
			style={{ maxWidth: 480, width: "100%" }}
		/>
	);
}

export default SearchBar;
