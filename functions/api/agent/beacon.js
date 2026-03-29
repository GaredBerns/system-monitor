export async function onRequest(context) {
  const { request } = context;
  
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Content-Type': 'application/json'
  };
  
  if (request.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }
  
  if (request.method === 'POST') {
    try {
      const body = await request.json();
      
      return new Response(JSON.stringify({
        success: true,
        tasks: [],
        message: 'Beacon received',
        timestamp: new Date().toISOString()
      }), { headers: corsHeaders });
    } catch (e) {
      return new Response(JSON.stringify({ error: e.message }), { 
        status: 400, 
        headers: corsHeaders 
      });
    }
  }
  
  return new Response('Method not allowed', { status: 405, headers: corsHeaders });
}
