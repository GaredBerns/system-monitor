export async function onRequest(context) {
  const { request, env } = context;
  
  if (request.method === 'GET') {
    return new Response(JSON.stringify({
      status: 'ok',
      timestamp: new Date().toISOString(),
      version: '3.0.0'
    }), {
      headers: { 'Content-Type': 'application/json' }
    });
  }
  
  return new Response('Method not allowed', { status: 405 });
}
