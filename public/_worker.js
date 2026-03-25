// Dynamic Tunnel Proxy Worker
// Fetches tunnel URL from GitHub tunnel.json (auto-updated by update_tunnel.sh)
// No hardcoded URLs - fully dynamic

const TUNNEL_CONFIG_URL = "https://raw.githubusercontent.com/GaredBerns/system-monitor/main/public/tunnel.json";

// Cache with TTL
let cachedUrl = null;
let cacheTime = 0;
const CACHE_TTL = 60000; // 1 minute cache

async function getTunnelUrl() {
  const now = Date.now();
  
  // Return cached if valid
  if (cachedUrl && (now - cacheTime) < CACHE_TTL) {
    return cachedUrl;
  }
  
  try {
    // Fetch config with cache bypass
    const url = TUNNEL_CONFIG_URL + "?t=" + Math.floor(now / 60000);
    const resp = await fetch(url, {
      cf: { 
        cacheTtl: 0,
        cacheEverything: false 
      }
    });
    
    if (resp.ok) {
      const data = await resp.json();
      if (data && data.tunnel_url) {
        cachedUrl = data.tunnel_url;
        cacheTime = now;
        console.log("Updated tunnel URL:", cachedUrl);
        return cachedUrl;
      }
    }
  } catch (e) {
    console.error("Failed to fetch tunnel config:", e);
  }
  
  // Return cached even if expired (better than nothing)
  return cachedUrl;
}

export default {
  async fetch(request, env, ctx) {
    const tunnelUrl = await getTunnelUrl();
    
    if (!tunnelUrl) {
      return new Response(JSON.stringify({
        error: "Tunnel not available",
        message: "Check if tunnel is running and tunnel.json is updated",
        hint: "Run: ./scripts/update_tunnel.sh"
      }), {
        status: 503,
        headers: { 
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*"
        }
      });
    }
    
    try {
      const url = new URL(request.url);
      const targetUrl = tunnelUrl + url.pathname + url.search;
      
      // WebSocket support
      if (request.headers.get("Upgrade") === "websocket") {
        const wsUrl = tunnelUrl.replace("https://", "wss://") + url.pathname + url.search;
        return fetch(wsUrl, {
          method: request.method,
          headers: request.headers,
          body: request.body,
        });
      }
      
      // Proxy request
      const headers = new Headers(request.headers);
      headers.set("Host", new URL(tunnelUrl).host);
      headers.set("X-Forwarded-For", request.headers.get("CF-Connecting-IP") || "");
      headers.set("X-Forwarded-Proto", "https");
      headers.set("X-Forwarded-Host", url.host);
      headers.set("X-Real-IP", request.headers.get("CF-Connecting-IP") || "");
      
      const response = await fetch(targetUrl, {
        method: request.method,
        headers: headers,
        body: request.body,
        redirect: "follow",
      });
      
      // Copy response with CORS headers
      const newResponse = new Response(response.body, response);
      newResponse.headers.set("Access-Control-Allow-Origin", "*");
      newResponse.headers.set("X-Tunnel-Url", tunnelUrl);
      return newResponse;
      
    } catch (error) {
      return new Response(JSON.stringify({
        error: "Tunnel connection failed",
        tunnel: tunnelUrl,
        message: error.message
      }), {
        status: 503,
        headers: { 
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*"
        }
      });
    }
  }
}
