// worker.js (支持 offset 参数)
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    
    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    // === 1. 论文搜索路由 ===
    if (url.pathname === "/arxiv") {
      const userQuery = url.searchParams.get("search_query");
      // 获取前端传来的 offset (偏移量)，默认为 0
      const offset = url.searchParams.get("offset") || "0";
      
      // Semantic Scholar API: 每次取 100 篇，通过 offset 翻页
      const targetUrl = `https://api.semanticscholar.org/graph/v1/paper/search?query=${encodeURIComponent(userQuery)}&offset=${offset}&limit=100&fields=title,authors,abstract,year,url,externalIds,openAccessPdf,publicationDate`;
      
      const response = await fetch(targetUrl);
      
      // 如果 API 报错 (比如 429)，透传给前端
      if (!response.ok) {
        return new Response(response.statusText, { status: response.status, headers: corsHeaders });
      }

      const data = await response.json();

      return new Response(JSON.stringify(data), {
        headers: {
          ...corsHeaders,
          "Content-Type": "application/json",
        },
      });
    } 
    
    // === 2. Moonshot 摘要路由 (保持不变) ===
    else if (url.pathname === "/moonshot") {
      if (request.method !== "POST") return new Response("Method not allowed", { status: 405, headers: corsHeaders });
      
      const apiKey = env.MOONSHOT_API_KEY; 
      if (!apiKey) return new Response("Server Error: API Key missing", { status: 500, headers: corsHeaders });

      const requestBody = await request.json();

      const moonshotResponse = await fetch('https://api.moonshot.cn/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${apiKey}` },
        body: JSON.stringify(requestBody)
      });

      const data = await moonshotResponse.json();

      return new Response(JSON.stringify(data), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    return new Response("Not Found", { status: 404, headers: corsHeaders });
  },
};