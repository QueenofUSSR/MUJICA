<template>
  <div class="page">
    <h2>MCP</h2>

    <section class="card">
      <h3>1) MCP Config JSON</h3>
      <textarea v-model="configText" rows="12" class="textarea"></textarea>
      <div class="row">
        <button @click="saveConfig">Save Config</button>
        <button @click="loadConfig">Load Config</button>
      </div>
    </section>

    <section class="card">
      <h3>2) List Tools</h3>
      <div class="row">
        <input v-model="serverName" placeholder="server name (e.g. demo)" />
        <button @click="listTools">List Tools</button>
      </div>
      <pre class="pre">{{ JSON.stringify(toolsResp, null, 2) }}</pre>
    </section>

    <section class="card">
      <h3>3) Call Tool</h3>
      <div class="row">
        <input v-model="callServer" placeholder="server (demo)" />
        <input v-model="callTool" placeholder="tool (echo/add)" />
      </div>
      <textarea v-model="callArgsText" rows="6" class="textarea" placeholder='args JSON, e.g. {"text":"hi"}'></textarea>
      <div class="row">
        <button @click="callToolApi">Call</button>
      </div>
      <pre class="pre">{{ JSON.stringify(callResp, null, 2) }}</pre>
    </section>
  </div>
</template>

<script>
import axios from "../utils/axios";

export default {
  name: "MCPView",
  data() {
    return {
      configText: `{
  "mcpServers": {
    "demo": {
      "command": "python",
      "args": ["backend/scripts/mcp_demo_server.py"],
      "env": {}
    }
  }
}`,
      serverName: "demo",
      toolsResp: null,
      callServer: "demo",
      callTool: "echo",
      callArgsText: `{"text":"hello mcp"}`,
      callResp: null
    };
  },
  methods: {
    async saveConfig() {
      const cfg = JSON.parse(this.configText);
      const res = await axios.post("/mcp/config", { config: cfg });
      this.callResp = res.data;
    },
    async loadConfig() {
      const res = await axios.get("/mcp/config");
      this.configText = JSON.stringify(res.data.config || {}, null, 2);
    },
    async listTools() {
      const res = await axios.get(`/mcp/tools/${this.serverName}`);
      this.toolsResp = res.data;
    },
    async callToolApi() {
      const args = JSON.parse(this.callArgsText || "{}");
      const res = await axios.post("/mcp/call", {
        server: this.callServer,
        tool: this.callTool,
        args
      });
      this.callResp = res.data;
    }
  }
};
</script>

<style scoped>
.page { padding: 16px; }
.card { padding: 12px; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 12px; }
.row { display: flex; gap: 8px; margin: 8px 0; }
.textarea { width: 100%; font-family: monospace; }
.pre { background: #f7f7f7; padding: 10px; overflow: auto; }
</style>
