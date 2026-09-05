const API_BASE_URL = "http://127.0.0.1:5000";

export const fetchStatus = async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/status`);
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch status:", error);
        return { status: "OFFLINE", tickers: {}, logs: [], account: { acc_no: "", name: "", balance: 0 } };
    }
};

export const refreshAccount = async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/account/refresh`, { method: "POST" });
        return await response.json();
    } catch (error) {
        console.error("Failed to refresh account:", error);
        return { status: "ERROR", message: error.message };
    }
};

export const fetchAiNotices = async (category = null, limit = 100) => {
    try {
        const params = new URLSearchParams({ limit });
        if (category) params.set("category", category);
        const response = await fetch(`${API_BASE_URL}/ai-notices?${params}`);
        const data = await response.json();
        return data.notices || [];
    } catch (error) {
        console.error("Failed to fetch AI notices:", error);
        return [];
    }
};

export const updateAccount = async (accountData) => {
    try {
        const response = await fetch(`${API_BASE_URL}/account`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(accountData),
        });
        return await response.json();
    } catch (error) {
        console.error("Failed to update account:", error);
        return { status: "ERROR" };
    }
};

export const tryLogin = async (mode = "REAL", assetType = "STOCK") => {
    try {
        const response = await fetch(`${API_BASE_URL}/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode, asset_type: assetType }),
        });
        return await response.json();
    } catch (error) {
        return { status: "ERROR", message: error.message };
    }
};

export const startSimulation = async (ticker, config) => {
    try {
        const response = await fetch(`${API_BASE_URL}/simulation/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker, config }),
        });
        return await response.json();
    } catch (error) {
        console.error("Failed to start simulation:", error);
    }
};

export const analyzeSimulation = async (ticker, config) => {
    try {
        const response = await fetch(`${API_BASE_URL}/simulation/analyze`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker, config }),
        });
        return await response.json();
    } catch (error) {
        console.error("Failed to analyze simulation:", error);
    }
};

export const stopSimulation = async (ticker) => {
    try {
        const response = await fetch(`${API_BASE_URL}/simulation/stop`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker }),
        });
        return await response.json();
    } catch (error) {
        console.error("Failed to stop simulation:", error);
    }
};

export const addTicker = async (ticker, rule = "DEFAULT") => {
    try {
        const response = await fetch(`${API_BASE_URL}/add_ticker`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker, buy_rule: rule }),
        });
        return await response.json();
    } catch (error) {
        console.error("Failed to add ticker:", error);
    }
};

export const removeTicker = async (ticker) => {
    try {
        await fetch(`${API_BASE_URL}/remove_ticker`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker }),
        });
    } catch (error) {
        console.error("Failed to remove ticker:", error);
    }
};

export const updateTickerRule = async (ticker, rule_name) => {
    try {
        await fetch(`${API_BASE_URL}/set_rule`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker, rule_name }),
        });
    } catch (error) {
        console.error("Failed to update rule:", error);
    }
};

export const pauseTicker = async (ticker) => {
    try {
        await fetch(`${API_BASE_URL}/pause_ticker`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker }),
        });
    } catch (error) {
        console.error("Failed to pause ticker:", error);
    }
};

export const resumeTicker = async (ticker) => {
    try {
        await fetch(`${API_BASE_URL}/resume_ticker`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker }),
        });
    } catch (error) {
        console.error("Failed to resume ticker:", error);
    }
};

export const fetchStrategies = async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/strategies`);
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch strategies:", error);
        return [];
    }
};

export const saveStrategy = async (name, content) => {
    try {
        const response = await fetch(`${API_BASE_URL}/strategies`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, content }),
        });
        return await response.json();
    } catch (error) {
        console.error("Failed to save strategy:", error);
        return { status: "ERROR" };
    }
};

export const deleteStrategy = async (name) => {
    try {
        const response = await fetch(`${API_BASE_URL}/strategies/${name}`, {
            method: "DELETE",
        });
        return await response.json();
    } catch (error) {
        console.error("Failed to delete strategy:", error);
        return { status: "ERROR" };
    }
};

// --- 백테스트 결과 관련 ---
export const fetchBacktestResults = async (limit = 100) => {
    try {
        const response = await fetch(`${API_BASE_URL}/backtest/results?limit=${limit}`);
        return await response.json();
    } catch (error) {
        console.error("Error fetching backtest results:", error);
        return [];
    }
};

export const fetchBacktestDetail = async (id) => {
    try {
        const response = await fetch(`${API_BASE_URL}/backtest/results/${id}`);
        return await response.json();
    } catch (error) {
        console.error("Error fetching backtest detail:", error);
        return null;
    }
};

export const deleteBacktestResult = async (id) => {
    try {
        const response = await fetch(`${API_BASE_URL}/backtest/results/${id}`, {
            method: 'DELETE',
        });
        return await response.json();
    } catch (error) {
        console.error("Error deleting backtest result:", error);
        return { status: "ERROR" };
    }
};

export const fetchTickerHistory = async (ticker) => {
    try {
        const response = await fetch(`${API_BASE_URL}/ticker_history/${ticker}`);
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch ticker history:", error);
        return { history: [], signals: { buy: [], sell: [] } };
    }
};

// --- Collector API ---
export const startCollector = async (params) => {
    try {
        const response = await fetch(`${API_BASE_URL}/collector/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(params),
        });
        return await response.json();
    } catch (error) {
        console.error("Failed to start collector:", error);
        return { status: "ERROR", message: error.message };
    }
};

export const stopCollector = async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/collector/stop`, {
            method: "POST"
        });
        return await response.json();
    } catch (error) {
        console.error("Failed to stop collector:", error);
        return { status: "ERROR" };
    }
};

export const fetchCollectorStatus = async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/collector/status`);
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch collector status:", error);
        return { is_running: false, progress: {}, logs: [] };
    }
};

export const fetchCollectorPreview = async (ticker, interval = '일봉', date = null) => {
    try {
        let url = `${API_BASE_URL}/collector/preview/${ticker}?interval=${interval}`;
        if (date) url += `&date=${date}`;
        const response = await fetch(url);
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch collector preview:", error);
        return [];
    }
};

export const fetchCollectedDates = async (ticker, interval = '5분') => {
    try {
        const response = await fetch(`${API_BASE_URL}/collector/dates/${ticker}?interval=${interval}`);
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch collected dates:", error);
        return [];
    }
};

export const fetchCollectedTickers = async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/collector/tickers`);
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch collected tickers:", error);
        return [];
    }
};

export const searchCollectorTicker = async (query, source = "KRX") => {
    try {
        const response = await fetch(`${API_BASE_URL}/collector/search?q=${query}&source=${source}`);
        return await response.json();
    } catch (error) {
        console.error("Failed to search collector ticker:", error);
        return [];
    }
};
export const fetchDateStatus = async (ticker, interval, year, month, source = "Yahoo") => {
    try {
        const response = await fetch(`${API_BASE_URL}/collector/date_status?ticker=${ticker}&interval=${interval}&year=${year}&month=${month}&source=${source}`);
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch date status:", error);
        return { ticker, interval, month_status: {} };
    }
};

export const deleteCollectorData = async (ticker, date = null, interval = null) => {
    try {
        let url = `${API_BASE_URL}/collector/delete/${ticker}?`;
        if (date) url += `date=${date}&`;
        if (interval) url += `interval=${interval}`;
        const response = await fetch(url, {
            method: "DELETE"
        });
        return await response.json();
    } catch (error) {
        console.error("Failed to delete collector data:", error);
        return { status: "ERROR", message: error.message };
    }
};
export const fetchTrades = async (date, accNo) => {
    try {
        let url = `${API_BASE_URL}/trades?`;
        if (date) url += `date=${date}&`;
        if (accNo) url += `acc_no=${accNo}`;
        const response = await fetch(url);
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch trades:", error);
        return [];
    }
};

export const fetchTradesSummary = async (year, month, accNo) => {
    try {
        let url = `${API_BASE_URL}/trades/summary?`;
        if (year) url += `year=${year}&`;
        if (month) url += `month=${month}&`;
        if (accNo) url += `acc_no=${accNo}`;
        const response = await fetch(url);
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch trades summary:", error);
        return {};
    }
};

export const fetchDailyProfitTotal = async (date, accNo) => {
    try {
        let url = `${API_BASE_URL}/trades/daily-total?date=${date}`;
        if (accNo) url += `&acc_no=${accNo}`;
        const response = await fetch(url);
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch daily profit total:", error);
        return null;
    }
};

export const exportTradesToGSheet = async (date, accNo) => {
    try {
        const response = await fetch(`${API_BASE_URL}/trades/export-gsheet`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date, acc_no: accNo })
        });
        return await response.json();
    } catch (error) {
        console.error("Failed to export trades to Google Sheet:", error);
        return { status: "ERROR", message: error.message };
    }
};

export const syncTradesFromKiwoom = async (date, accNo) => {
    try {
        const response = await fetch(`${API_BASE_URL}/trades/sync`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date, acc_no: accNo })
        });
        return await response.json();
    } catch (error) {
        console.error("Failed to sync trades:", error);
        return { status: "ERROR", message: error.message };
    }
};

// --- Claude CLI / Antigravity CLI 연동 ---
export const fetchCliTasks = async (limit = 50, triggerType = null) => {
    try {
        let url = `${API_BASE_URL}/cli/tasks?limit=${limit}`;
        if (triggerType) url += `&trigger_type=${triggerType}`;
        const response = await fetch(url);
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch CLI tasks:", error);
        return [];
    }
};

export const fetchCliTaskDetail = async (taskId) => {
    try {
        const response = await fetch(`${API_BASE_URL}/cli/tasks/${taskId}`);
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch CLI task detail:", error);
        return null;
    }
};

export const deleteCliTask = async (taskId) => {
    try {
        const response = await fetch(`${API_BASE_URL}/cli/tasks/${taskId}`, { method: "DELETE" });
        return await response.json();
    } catch (error) {
        console.error("Failed to delete CLI task:", error);
        return { status: "ERROR", message: error.message };
    }
};

export const deleteCliTasksBulk = async (ids) => {
    try {
        const response = await fetch(`${API_BASE_URL}/cli/tasks/delete-bulk`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ids }),
        });
        return await response.json();
    } catch (error) {
        console.error("Failed to bulk delete CLI tasks:", error);
        return { status: "ERROR", message: error.message };
    }
};

// --- AI 추천 종목 ---
export const fetchAiPicks = async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-picks`);
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch AI picks:", error);
        return [];
    }
};

export const fetchAiPickStocks = async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-picks/stocks`);
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch AI pick stocks:", error);
        return [];
    }
};

export const fetchAiPickModels = async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-picks/models`);
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch AI pick models:", error);
        return null;
    }
};

export const createAiPick = async (name, prompt, model) => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-picks`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, prompt, model }),
        });
        return await response.json();
    } catch (error) {
        return { status: "ERROR", message: error.message };
    }
};

export const updateAiPick = async (id, name, prompt, model) => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-picks/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, prompt, model }),
        });
        return await response.json();
    } catch (error) {
        return { status: "ERROR", message: error.message };
    }
};

export const deleteAiPick = async (id) => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-picks/${id}`, { method: "DELETE" });
        return await response.json();
    } catch (error) {
        return { status: "ERROR", message: error.message };
    }
};

export const runAiPick = async (id) => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-picks/${id}/run`, { method: "POST" });
        return await response.json();
    } catch (error) {
        return { status: "ERROR", message: error.message };
    }
};

export const fetchAiPickResult = async (id) => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-picks/${id}/result`);
        return await response.json();
    } catch (error) {
        return null;
    }
};

export const runAiPickCompare = async (id) => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-picks/${id}/compare`, { method: "POST" });
        return await response.json();
    } catch (error) {
        return { status: "ERROR", message: error.message };
    }
};

export const exportAiPickComparisonToGSheet = async (id) => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-picks/${id}/comparison/export-gsheet`, {
            method: "POST",
        });
        return await response.json();
    } catch (error) {
        return { status: "ERROR", message: error.message };
    }
};

export const fetchAiPickComparison = async (id) => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-picks/${id}/comparison`);
        return await response.json();
    } catch (error) {
        return null;
    }
};

// --- AI 매매 (종목별 매매 전략) ---
export const fetchAiTrades = async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-trades`);
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch AI trades:", error);
        return [];
    }
};

export const createAiTrade = async (name, prompt, model) => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-trades`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, prompt, model }),
        });
        return await response.json();
    } catch (error) {
        return { status: "ERROR", message: error.message };
    }
};

export const updateAiTrade = async (id, name, prompt, model) => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-trades/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, prompt, model }),
        });
        return await response.json();
    } catch (error) {
        return { status: "ERROR", message: error.message };
    }
};

export const deleteAiTrade = async (id) => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-trades/${id}`, { method: "DELETE" });
        return await response.json();
    } catch (error) {
        return { status: "ERROR", message: error.message };
    }
};

export const runAiTrade = async (id, ticker, tickerName) => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-trades/${id}/run`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker, ticker_name: tickerName }),
        });
        return await response.json();
    } catch (error) {
        return { status: "ERROR", message: error.message };
    }
};

export const fetchAiTradeResult = async (id) => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-trades/${id}/result`);
        return await response.json();
    } catch (error) {
        return null;
    }
};

// 현재 보유 종목을 구글 시트 '보유종목' 탭에 업로드
export const exportHoldingsToGSheet = async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/holdings/export-gsheet`, {
            method: "POST",
        });
        return await response.json();
    } catch (error) {
        return { status: "ERROR", message: error.message };
    }
};

// --- AI 캘린더 (날짜별 주요 일정 + 일정 기반 매매 타이밍) ---
export const fetchAiCalendars = async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-calendar`);
        return await response.json();
    } catch (error) {
        return [];
    }
};

export const createAiCalendar = async (name, prompt, model) => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-calendar`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, prompt, model }),
        });
        return await response.json();
    } catch (error) {
        return { status: "ERROR", message: error.message };
    }
};

export const updateAiCalendar = async (id, name, prompt, model) => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-calendar/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, prompt, model }),
        });
        return await response.json();
    } catch (error) {
        return { status: "ERROR", message: error.message };
    }
};

export const deleteAiCalendar = async (id) => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-calendar/${id}`, { method: "DELETE" });
        return await response.json();
    } catch (error) {
        return { status: "ERROR", message: error.message };
    }
};

export const runAiCalendar = async (id) => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-calendar/${id}/run`, { method: "POST" });
        return await response.json();
    } catch (error) {
        return { status: "ERROR", message: error.message };
    }
};

export const fetchAiCalendarResult = async (id) => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-calendar/${id}/result`);
        return await response.json();
    } catch (error) {
        return null;
    }
};

// 보유 종목 전체를 한 프로파일로 순차 분석
export const runAiTradeBatch = async (id, items) => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-trades/${id}/run-batch`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ items }),
        });
        return await response.json();
    } catch (error) {
        return { status: "ERROR", message: error.message };
    }
};

export const fetchAiTradeBatchStatus = async (id) => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-trades/${id}/batch-status`);
        return await response.json();
    } catch (error) {
        return { running: false, total: 0, done: 0 };
    }
};

// 완료된 매매 전략을 종목코드별로 조회 (보유 종목에서 해당 종목 전략 표시용)
export const fetchAiTradeStrategies = async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-trades/strategies`);
        return await response.json();
    } catch (error) {
        return {};
    }
};

// 매매 전략을 구글 시트에 업로드 (탭 이름 = 프로파일명, 같은 종목이면 갱신)
export const exportAiTradeToGSheet = async (id) => {
    try {
        const response = await fetch(`${API_BASE_URL}/ai-trades/${id}/export-gsheet`, {
            method: "POST",
        });
        return await response.json();
    } catch (error) {
        return { status: "ERROR", message: error.message };
    }
};

// --- 도우미 채팅 (Claude CLI 기반) ---
export const fetchChatHistory = async (limit = 50) => {
    try {
        const response = await fetch(`${API_BASE_URL}/cli/chat/history?limit=${limit}`);
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch chat history:", error);
        return [];
    }
};

export const saveChatMessage = async (role, text) => {
    try {
        await fetch(`${API_BASE_URL}/cli/chat/message`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ role, text }),
        });
    } catch (error) {
        console.error("Failed to save chat message:", error);
    }
};

export const clearChatHistory = async () => {
    try {
        await fetch(`${API_BASE_URL}/cli/chat/clear`, { method: "POST" });
    } catch (error) {
        console.error("Failed to clear chat history:", error);
    }
};

// SSE 스트리밍 채팅: onEvent(event, data) 콜백으로 delta/replace/done/error 전달
export const streamChat = async (message, history, onEvent) => {
    const response = await fetch(`${API_BASE_URL}/cli/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, history }),
    });
    if (!response.ok || !response.body) throw new Error("스트리밍 응답 실패");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    let event = "";
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() || "";
        for (const line of lines) {
            if (line.startsWith("event: ")) { event = line.slice(7).trim(); continue; }
            if (!line.startsWith("data: ")) { event = ""; continue; }
            let data;
            try { data = JSON.parse(line.slice(6)); } catch { event = ""; continue; }
            if (event) onEvent(event, data);
            event = "";
        }
    }
};
