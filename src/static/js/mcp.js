/* Browser MCP client — streamable HTTP JSON-RPC to /mcp */
(function (global) {
  const MCP_URL = "/mcp";
  let nextId = 1;

  async function rpc(method, params) {
    const id = nextId++;
    const res = await fetch(MCP_URL, {
      method: "POST",
      headers: {
        Accept: "application/json, text/event-stream",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        jsonrpc: "2.0",
        method,
        params: params || {},
        id,
      }),
    });
    const text = await res.text();
    let data;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      throw new Error("MCP returned non-JSON: " + text.slice(0, 200));
    }
    if (!res.ok) {
      throw new Error((data && data.error && data.error.message) || res.statusText);
    }
    if (data && data.error) {
      throw new Error(data.error.message || JSON.stringify(data.error));
    }
    return data && data.result;
  }

  function parseToolPayload(result) {
    if (!result) return null;
    if (result.isError) {
      const msg =
        (result.content && result.content[0] && result.content[0].text) ||
        "MCP tool error";
      throw new Error(msg);
    }
    const block = (result.content || []).find((c) => c.type === "text") || result.content?.[0];
    if (!block || block.text == null) return result;
    try {
      return JSON.parse(block.text);
    } catch {
      return { raw: block.text };
    }
  }

  async function callTool(name, args) {
    const result = await rpc("tools/call", {
      name,
      arguments: args || {},
    });
    const payload = parseToolPayload(result);
    if (payload && payload.error) {
      const err = new Error(payload.error);
      err.data = payload;
      throw err;
    }
    return payload;
  }

  global.HireLoopMCP = { callTool, rpc };
})(window);
