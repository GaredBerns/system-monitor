// Cloudflare Worker - Dynamic Tunnel Proxy
// Reads tunnel URL from tunnel.json in same directory
// Auto-updates every 30 seconds

const TUNNEL_CONFIG_URL = "https://raw.githubusercontent.com/GaredBerns/system-monitor/main/public/tunnel.json";
const FALLBACK_URL = "https://sublime-ide-hill-rotary.trycloudflare.com";

// Cache with short TTL
let cachedUrl = null;
let cacheTime = 0;
const CACHE_TTL = 30000; // 30 seconds

async function getTunnelUrl() {
  const now = Date.now();
  
  // Return cached if valid
  if (cachedUrl && (now - cacheTime) < CACHE_TTL) {
    return cachedUrl;
  }
  
  try {
    // Fetch with cache bypass
    const url = TUNNEL_CONFIG_URL + "?t=" + Math.floor(now / 30000);
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
        return cachedUrl;
      }
    }
  } catch (e) {
    // Fall through to fallback
  }
  
  return cachedUrl || FALLBACK_URL;
}

export default {
  async fetch(request, env, ctx) {
    try {
      const tunnelUrl = await getTunnelUrl();
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
      
      return fetch(targetUrl, {
        method: request.method,
        headers: headers,
        body: request.body,
        redirect: "follow",
      });
      
    } catch (error) {
      return new Response("Service unavailable. Tunnel may be restarting.", {
        status: 503,
        headers: { "Content-Type": "text/plain" }
      });
    }
  }
}
