import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

const rootElement = document.getElementById("root");

if (!rootElement) {
	throw new Error(
		'Root element not found. Ensure there is a <div id="root"></div> in your index.html.',
	);
}

ReactDOM.createRoot(rootElement).render(
	<React.StrictMode>
		<App />
	</React.StrictMode>,
);
