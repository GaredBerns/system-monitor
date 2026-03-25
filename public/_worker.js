// Simple Worker - Tunnel URL from environment or fallback
// Update via: wrangler pages deploy public/ --project-name gbctwoserver

// Fallback tunnel URL (update manually if needed)
const FALLBACK_URL = "https://inventory-analytical-governing-houses.trycloudflare.com";

export default {
  async fetch(request, env, ctx) {
    // Get tunnel URL from env or use fallback
    const tunnelUrl = env.TUNNEL_URL || FALLBACK_URL;
    
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
      
      return fetch(targetUrl, {
        method: request.method,
        headers: headers,
        body: request.body,
        redirect: "follow",
      });
      
    } catch (error) {
      return new Response("Tunnel unavailable: " + tunnelUrl, {
        status: 503,
        headers: { "Content-Type": "text/plain" }
      });
    }
  }
}
