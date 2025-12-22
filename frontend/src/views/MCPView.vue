<template>
  <div class="page">
    <h2>MCP 管理中心</h2>
    <section class="card">
      <div class="card-header">
        <div>
          <h3>模板与安装</h3>
          <p class="card-sub">选择模版，自动安装/注册 MCP Server</p>
        </div>
        <button class="ghost-btn" @click="fetchRegistry" :disabled="loading.registry">
          {{ loading.registry ? '刷新中…' : '刷新模板' }}
        </button>
      </div>
      <div class="templates-grid">
        <article class="template" v-for="tpl in templates" :key="tpl.id">
          <div class="template-head">
            <div>
              <h4>{{ tpl.title }}</h4>
              <p>{{ tpl.description }}</p>
            </div>
            <span class="badge" :class="tpl.installed ? 'badge-success' : 'badge-warning'">
              {{ tpl.installed ? `已安装${tpl.installedVersion ? ' · v' + tpl.installedVersion : ''}` : '未安装' }}
            </span>
          </div>
          <ul class="template-meta">
            <li><strong>ID：</strong>{{ tpl.id }}</li>
            <li v-if="tpl.package"><strong>包：</strong>{{ tpl.package }}</li>
            <li v-if="tpl.homepage"><strong>主页：</strong><a :href="tpl.homepage" target="_blank">{{ tpl.homepage }}</a></li>
          </ul>
          <div class="template-actions">
            <button
              class="btn"
              :disabled="loading.install === tpl.id || tpl.installed"
              @click="installTemplate(tpl)"
            >{{ tpl.installed ? '已安装' : loading.install === tpl.id ? '安装中…' : '安装模板' }}</button>
            <button
              v-if="tpl.installed && tpl.package"
              class="btn ghost"
              :disabled="loading.uninstall === tpl.id"
              @click="uninstallTemplate(tpl)"
            >{{ loading.uninstall === tpl.id ? '卸载中…' : '卸载包' }}</button>
            <button
              class="btn secondary"
              :disabled="loading.register || (!tpl.installed && tpl.requires_install)"
              @click="openRegisterForm(tpl)"
            >配置服务器</button>
          </div>
        </article>
        <p v-if="!templates.length" class="empty">暂无模板，可刷新或稍后再试。</p>
      </div>
    </section>

    <section class="card">
      <h3>注册服务器</h3>
      <p class="card-sub">为选中的模版生成 server 配置（command/args/env 支持 JSON）</p>
      <div class="register-form" v-if="registerForm.template_id">
        <div class="form-row">
          <label>模板 ID</label>
          <input v-model="registerForm.template_id" readonly />
        </div>
        <div class="form-row">
          <label>Server 名称</label>
          <input v-model="registerForm.server_name" placeholder="如 demo-local" />
        </div>
        <div class="form-row">
          <label>Command (可选)</label>
          <input v-model="registerForm.command" placeholder="默认使用模板内 command" />
        </div>
        <div class="form-row">
          <label>Args JSON</label>
          <textarea v-model="registerForm.argsInput" rows="4"></textarea>
        </div>
        <div class="form-row">
          <label>Env JSON</label>
          <textarea v-model="registerForm.envInput" rows="4"></textarea>
        </div>
        <div class="form-row">
          <button class="btn" :disabled="loading.register" @click="submitRegister">
            {{ loading.register ? '注册中…' : '注册 Server' }}
          </button>
          <button class="btn ghost" @click="clearRegisterForm" :disabled="loading.register">清空</button>
        </div>
      </div>
      <p v-else class="empty">请先在上方选择要注册的模版。</p>
    </section>

    <section class="card">
      <h3>当前配置 JSON</h3>
      <textarea v-model="configText" rows="12" class="textarea"></textarea>
      <div class="row">
        <button @click="saveConfig">保存配置</button>
      </div>
      <div class="row">
        <button @click="loadConfig">重新载入</button>
      </div>
    </section>

    <section class="card">
      <h3>工具列表调试</h3>
      <div class="row">
        <input v-model="serverName" placeholder="server name (e.g. demo)" />
        <button @click="listTools" style="width: fit-content;">获取工具</button>
      </div>
      <pre class="pre" v-if="toolsResp">{{ JSON.stringify(toolsResp, null, 2) }}</pre>
    </section>

    <section class="card">
      <h3>调用工具</h3>
      <div class="row">
        <input v-model="callServer" placeholder="server (demo)" />
        <input v-model="callTool" placeholder="tool (echo/add)" />
      </div>
      <textarea v-model="callArgsText" rows="6" class="textarea" placeholder='args JSON, 如 {"text":"hi"}'></textarea>
      <div class="row">
        <button @click="callToolApi">发送调用</button>
      </div>
      <pre class="pre" v-if="callResp">{{ JSON.stringify(callResp, null, 2) }}</pre>
    </section>

    <transition name="fade">
      <div v-if="info.message" class="toast" :class="info.type">{{ info.message }}</div>
    </transition>
  </div>
</template>

<script>
import axios from "../utils/axios";

export default {
  name: "MCPView",
  data() {
    return {
      configText: "{}",
      serverName: "demo",
      toolsResp: null,
      callServer: "demo",
      callTool: "echo",
      callArgsText: '{"text":"hello mcp"}',
      callResp: null,
      templates: [],
      loading: {
        registry: false,
        install: null,
        uninstall: null,
        register: false,
      },
      registerForm: {
        template_id: "",
        server_name: "",
        command: "",
        argsInput: "",
        envInput: "{}",
      },
      info: {
        message: "",
        type: "success",
      },
    };
  },
  created() {
    this.loadConfig();
    this.fetchRegistry();
  },
  methods: {
    setInfo(message, type = "success") {
      this.info = { message, type };
      if (message) {
        clearTimeout(this._infoTimer);
        this._infoTimer = setTimeout(() => {
          this.info.message = "";
        }, 3500);
      }
    },
    async fetchRegistry() {
      try {
        this.loading.registry = true;
        const res = await axios.get("/mcp/registry");
        this.templates = res.data.templates || [];
      } catch (err) {
        console.error(err);
        this.setInfo("获取模板失败", "error");
      } finally {
        this.loading.registry = false;
      }
    },
    async installTemplate(tpl) {
      try {
        this.loading.install = tpl.id;
        await axios.post("/mcp/registry/install", { template_id: tpl.id });
        this.setInfo(`模板 ${tpl.title} 安装完成`);
        await this.fetchRegistry();
      } catch (err) {
        console.error(err);
        this.setInfo(`安装 ${tpl.id} 失败`, "error");
      } finally {
        this.loading.install = null;
      }
    },
    async uninstallTemplate(tpl) {
      if (!tpl.package) {
        this.setInfo("该模板未定义 pip 包", "error");
        return;
      }
      try {
        this.loading.uninstall = tpl.id;
        await axios.post("/mcp/registry/uninstall", { package: tpl.package });
        this.setInfo(`包 ${tpl.package} 已卸载`);
        await this.fetchRegistry();
      } catch (err) {
        console.error(err);
        this.setInfo("卸载失败", "error");
      } finally {
        this.loading.uninstall = null;
      }
    },
    openRegisterForm(tpl) {
      if (!tpl.installed && tpl.requires_install) {
        this.setInfo("请先安装该模板", "error");
        return;
      }
      this.registerForm = {
        template_id: tpl.id,
        server_name: tpl.default_server_name || tpl.id,
        command: tpl.command || "",
        argsInput: JSON.stringify(tpl.args || [], null, 2),
        envInput: JSON.stringify(tpl.env || {}, null, 2),
      };
      this.setInfo(`已选择模板 ${tpl.title}`);
    },
    clearRegisterForm() {
      this.registerForm = {
        template_id: "",
        server_name: "",
        command: "",
        argsInput: "",
        envInput: "{}",
      };
    },
    parseJsonInput(input, fallback) {
      const text = (input || "").trim();
      if (!text) return fallback;
      try {
        return JSON.parse(text);
      } catch (err) {
        throw new Error("JSON 解析失败: " + err.message);
      }
    },
    async submitRegister() {
      if (!this.registerForm.template_id || !this.registerForm.server_name) {
        this.setInfo("请完善模板 ID 和 Server 名称", "error");
        return;
      }
      let args, env;
      try {
        args = this.parseJsonInput(this.registerForm.argsInput, undefined);
        env = this.parseJsonInput(this.registerForm.envInput, undefined);
      } catch (err) {
        this.setInfo(err.message, "error");
        return;
      }
      const payload = {
        template_id: this.registerForm.template_id,
        server_name: this.registerForm.server_name,
        command: this.registerForm.command || undefined,
        args,
        env,
      };
      try {
        this.loading.register = true;
        await axios.post("/mcp/registry/register", payload);
        this.setInfo("Server 注册成功");
        await this.loadConfig();
      } catch (err) {
        console.error(err);
        this.setInfo("注册失败", "error");
      } finally {
        this.loading.register = false;
      }
    },
    async saveConfig() {
      try {
        const cfg = JSON.parse(this.configText || "{}");
        const res = await axios.post("/mcp/config", { config: cfg });
        this.callResp = res.data;
        this.setInfo("配置已保存");
      } catch (err) {
        console.error(err);
        this.setInfo("配置保存失败，请确认 JSON", "error");
      }
    },
    async loadConfig() {
      try {
        const res = await axios.get("/mcp/config");
        this.configText = JSON.stringify(res.data.config || {}, null, 2);
      } catch (err) {
        console.error(err);
        this.setInfo("加载配置失败", "error");
      }
    },
    async listTools() {
      try {
        const res = await axios.get(`/mcp/tools/${this.serverName}`);
        this.toolsResp = res.data;
      } catch (err) {
        console.error(err);
        this.setInfo("获取工具失败", "error");
      }
    },
    async callToolApi() {
      try {
        const args = JSON.parse(this.callArgsText || "{}");
        const res = await axios.post("/mcp/call", {
          server: this.callServer,
          tool: this.callTool,
          args,
        });
        this.callResp = res.data;
      } catch (err) {
        console.error(err);
        this.setInfo("调用失败，请检查 JSON 或 Server", "error");
      }
    },
  },
};
</script>

<style scoped>
.page {
  padding: 24px;
  color: #1d1d1f;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(239, 244, 255, 0.9));
  min-height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.card {
  padding: 18px 22px;
  border: 1px solid rgba(30, 64, 175, 0.15);
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.08);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.card-sub {
  margin: 6px 0 0;
  color: #475569;
  font-size: 0.9rem;
}

.templates-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
  margin-top: 16px;
}

.template {
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 14px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: #f8fafc;
}

.template-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.template-head h4 {
  margin: 0 0 4px;
}

.template-head p {
  margin: 0;
  color: #475569;
  font-size: 0.9rem;
}

.template-meta {
  padding-left: 20px;
  margin: 0;
  color: #475569;
  font-size: 0.85rem;
}

.template-meta li {
  margin: 2px 0;
}

.template-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.badge {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
}

.badge-success {
  background: rgba(16, 185, 129, 0.15);
  color: #047857;
}

.badge-warning {
  background: rgba(251, 191, 36, 0.2);
  color: #92400e;
}

.register-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 14px;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-row label {
  font-weight: 600;
  color: #1e293b;
}

input,
textarea {
  border: 1px solid rgba(148, 163, 184, 0.6);
  border-radius: 10px;
  padding: 10px 12px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  background: rgba(248, 250, 252, 0.9);
  color: #0f172a;
  width: 100%;
  box-sizing: border-box;
}

input:focus,
textarea:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
}

.row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 12px 0;
  align-items: center;
}

.row input {
  flex: 1 1 auto;
  min-width: 220px;
}

.row button {
  flex: 0 0 auto;
  min-width: 140px;
}

button {
  border: none;
  border-radius: 12px;
  padding: 10px 16px;
  background: linear-gradient(135deg, #2563eb, #9333ea);
  color: #fff;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.2s ease;
  min-width: 140px;
  display: inline-flex;
  justify-content: center;
  align-items: center;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 10px 20px rgba(99, 102, 241, 0.25);
}

.btn {
  min-width: 110px;
  text-align: center;
}

.btn.secondary {
  background: linear-gradient(135deg, #0f172a, #475569);
}

.btn.ghost,
.ghost-btn {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.5);
  color: #1e293b;
  width: fit-content;
}

.ghost-btn {
  padding: 8px 14px;
  border-radius: 10px;
}

.pre {
  background: #0f172a;
  color: #e2e8f0;
  padding: 14px;
  border-radius: 12px;
  overflow: auto;
  font-size: 0.92rem;
  max-height: 260px;
  box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.2);
}

.empty {
  color: #94a3b8;
  text-align: center;
  margin: 12px 0;
}

.toast {
  position: fixed;
  right: 28px;
  bottom: 28px;
  padding: 12px 18px;
  border-radius: 12px;
  box-shadow: 0 10px 20px rgba(15, 23, 42, 0.2);
  font-weight: 600;
}

.toast.success {
  background: rgba(16, 185, 129, 0.9);
  color: #ecfdf5;
}

.toast.error {
  background: rgba(239, 68, 68, 0.9);
  color: #fef2f2;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 640px) {
  .page {
    padding: 16px;
  }
  .row {
    flex-direction: column;
  }
  .templates-grid {
    grid-template-columns: 1fr;
  }
}
</style>
