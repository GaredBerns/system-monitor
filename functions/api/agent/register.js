export async function onRequest(context) {
  const { request } = context;
  
  // CORS headers
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Content-Type': 'application/json'
  };
  
  // Handle OPTIONS preflight
  if (request.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }
  
  if (request.method === 'POST') {
    try {
      const body = await request.json();
      
      // Generate agent ID if not provided
      const agent_id = body.agent_id || crypto.randomUUID();
      
      return new Response(JSON.stringify({
        success: true,
        agent_id: agent_id,
        message: 'Agent registered successfully',
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
