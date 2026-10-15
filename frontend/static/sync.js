// Real-time synchronization & Auto-refresh for Beyond Emergency Webpages
let ws = null;
let livePollingInterval = null;

// Connect to WebSocket on single FastAPI server
function initRealtimeSync(onEventCallback) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  function connect() {
    try {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('⚡ Connected to FastAPI live synchronization channel');
        updateLiveIndicator(true);
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('📡 Real-time update from FastAPI:', message);
          if (onEventCallback) {
            onEventCallback(message);
          }
        } catch (e) {
          console.error(e);
        }
      };

      ws.onclose = () => {
        console.warn('⚠️ WebSocket disconnected. Reconnecting in 3s...');
        updateLiveIndicator(false);
        setTimeout(connect, 3000);
      };

      ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        ws.close();
      };
    } catch (e) {
      console.warn('WebSocket setup error, falling back to background polling');
      updateLiveIndicator(false);
    }
  }

  connect();

  // Heartbeat ping every 25s to keep the connection alive
  setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send('ping');
    }
  }, 25000);

  // Background fallback polling every 5s ensures pages stay fresh even across browser tabs
  if (!livePollingInterval) {
    livePollingInterval = setInterval(() => {
      if (typeof refreshCurrentPageData === 'function') {
        refreshCurrentPageData();
      }
    }, 5000);
  }
}

function updateLiveIndicator(isLive) {
  const badge = document.getElementById('live-status-badge');
  if (!badge) return;
  if (isLive) {
    badge.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span> <span class="text-emerald-300 font-semibold">Live Real-time Synced</span>`;
  } else {
    badge.innerHTML = `<span class="w-2 h-2 rounded-full bg-amber-400"></span> <span class="text-amber-300 font-semibold">Polling (5s sync)</span>`;
  }
}
