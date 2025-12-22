<template>
  <div class="login-container">
    <!-- 左侧面板 - 图片/信息展示区 -->
    <div class="left-panel">
      <div class="logo">
        <div class="logo-icon">🤖</div>
        <div class="logo-text">Multi-Agent</div>
      </div>

      <div class="features">
        <div class="feature">
          <span class="feature-icon">✓</span>
          <span>多智能体任务协作与调度</span>
        </div>
        <div class="feature">
          <span class="feature-icon">✓</span>
          <span>AI 聊天与知识检索</span>
        </div>
        <div class="feature">
          <span class="feature-icon">✓</span>
          <span>任务可视化、实时日志与结果整合</span>
        </div>
        <div class="feature">
          <span class="feature-icon">✓</span>
          <span>用户可控的中断/接管与权限管理</span>
        </div>
        <div class="feature">
          <span class="feature-icon">✓</span>
          <span>可扩展的模型与工具接入</span>
        </div>
      </div>

      <div class="tagline">
        一个支持多智能体协作、AI 聊天和任务编排的平台<br>
        将复杂任务拆解为可执行子任务并集中管理
      </div>
    </div>

    <!-- 右侧面板 - 表单区域 -->
    <div class="form-container">
      <div class="mode-switch">
        <button
          class="mode-btn"
          :class="{ active: isLoginMode }"
          @click="switchMode(true)"
        >
          登录
        </button>
        <button
          class="mode-btn"
          :class="{ active: !isLoginMode }"
          @click="switchMode(false)"
        >
          注册
        </button>
      </div>
      <!-- 登录表单 -->
      <div v-if="isLoginMode" class="register-form">
        <div class="form-row">
          <label class="form-label">用户名</label>
          <input
              v-model="loginForm.username"
              type="text"
              placeholder="请输入用户名或ID"
              required
              :class="{'input-error': loginError}"
          >
        </div>

        <div class="form-row">
          <label class="form-label">密码</label>
          <div class="password-wrapper">
            <input v-model="loginForm.password" :type="showPassword ? 'text' : 'password'"
                placeholder="请输入密码" required :class="{'input-error': loginError}">
            <button type="button" class="password-toggle" @click="showPassword = !showPassword">
              <i :class="showPassword ? 'fas fa-eye' : 'fas fa-eye-slash'"></i>
            </button>
          </div>
        </div>
        <div v-if="loginError" class="error-message">
          {{ loginError }}
        </div>
      </div>

      <div v-else class="register-form">
        <div class="form-row">
          <label class="form-label">用户名</label>
          <input
            v-model="registerForm.username"
            type="text"
            placeholder="请输入用户名"
            required
          />
        </div>
        <div class="form-row">
          <label class="form-label">密码</label>
          <div class="password-wrapper">
            <input
              v-model="registerForm.password"
              :type="showPassword ? 'text' : 'password'"
              placeholder="请输入密码"
              required
            />
            <button type="button" class="password-toggle" @click="showPassword = !showPassword">
              <i :class="showPassword ? 'fas fa-eye' : 'fas fa-eye-slash'"></i>
            </button>
          </div>
        </div>
        <div class="form-row">
          <label class="form-label">确认密码</label>
          <input
            v-model="registerForm.confirmPassword"
            :type="showPassword ? 'text' : 'password'"
            placeholder="请再次输入密码"
            required
          />
        </div>
        <div class="form-row contact-row">
          <label class="form-label">联系方式</label>
          <input
            v-model="registerForm.contact"
            type="text"
            placeholder="请输入邮箱或手机号"
            required
          />
          <button class="verify-btn" :disabled="countdown > 0 || sendingCode" @click="sendVerification">
            {{ countdown > 0 ? `${countdown}s` : sendingCode ? '发送中...' : '发送验证码' }}
          </button>
        </div>
        <div class="form-row">
          <label class="form-label">验证码</label>
          <input
            v-model="registerForm.verificationCode"
            type="text"
            placeholder="请输入验证码"
            required
          />
        </div>
        <div v-if="registerError" class="error-message">
          {{ registerError }}
        </div>
      </div>

      <button
        class="btn"
        @click="isLoginMode ? handleLogin() : handleRegister()"
      >
        {{ isLoginMode ? '登录' : '注册并登录' }}
      </button>
      <div class="links" v-if="isLoginMode">
        <a href="#" @click="forgetPassword">忘记密码</a>
      </div>
    </div>

    <div class="footer">
      &copy; 2025 Collaborative AI Hub | 多智能体协作平台
    </div>
  </div>
</template>

<script>
import {useAuthStore} from '@/stores/authStore';
import apiClient from "@/utils/axios.js";
import {handleError, showError, showInfo} from "@/utils/toast.js";

export default {
  name: 'LoginView',
  data() {
    return {
      showPassword: false,
      loginError: '',
      loginForm: {
        username: '',
        password: '',
      },
      isLoginMode: true,
      sendingCode: false,
      countdown: 0,
      registerForm: {
        username: '',
        password: '',
        confirmPassword: '',
        contact: '',
        verificationCode: ''
      },
      registerError: '',
      timerId: null
    }
  },
  beforeUnmount() {
    if (this.timerId) {
      clearInterval(this.timerId)
    }
  },
  methods: {
    switchMode(isLogin) {
      this.isLoginMode = isLogin
      this.loginError = ''
      this.registerError = ''
    },
    async handleLogin() {
      this.loginError = '';
      if (!this.loginForm.username || !this.loginForm.password) {
        this.loginError = '请输入用户名和密码';
        return;
      }
      const payload = {
        username: this.loginForm.username,
        password: this.loginForm.password
      }
      try {
        const response = await apiClient.post('/auth/login', payload);
        if (response.data.status === 'success') {
          const { token, user } = response.data;
          useAuthStore().initAuth(token, user);
        }else {
          showError('登录失败: ' + response.data.message);
        }
      } catch (error) {
        this.loginError = '用户名或密码错误';
        handleError(error)
        console.error('登录失败:', error);
      }
    },

    forgetPassword() {
      showInfo('请联系管理员重置密码。');
    },

    async handleRegister() {
      this.registerError = ''
      const { username, password, confirmPassword, contact, verificationCode } = this.registerForm
      if (!username || !password || !contact || !verificationCode) {
        this.registerError = '请完整填写所有字段'
        return
      }
      if (password !== confirmPassword) {
        this.registerError = '两次输入的密码不一致'
        return
      }
      const { email, phone, error } = this.parseContact(contact)
      if (error) {
        this.registerError = error
        return
      }
      try {
        const payload = {
          username,
          password,
          phone,
          email,
          verificationCode
        }
        const response = await apiClient.post('/auth/register', payload)
        if (response.data.token) {
          const { token, user } = response.data
          await useAuthStore().initAuth(token, user)
        } else {
          this.registerError = response.data.message || '注册失败'
        }
      } catch (error) {
        this.registerError = error.response?.data?.detail || '注册失败，请稍后重试'
        handleError(error)
      }
    },
    parseContact(value) {
      const emailPattern = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/
      const phonePattern = /^1[3-9]\d{9}$/
      if (emailPattern.test(value)) {
        return { email: value, phone: null }
      }
      if (phonePattern.test(value)) {
        return { phone: value, email: null }
      }
      return { error: '请输入正确的邮箱或手机号' }
    },
    async sendVerification() {
      this.registerError = ''
      const contact = this.registerForm.contact
      if (!contact) {
        this.registerError = '请先输入联系方式'
        return
      }
      const { email, phone, error } = this.parseContact(contact)
      if (error) {
        this.registerError = error
        return
      }
      this.sendingCode = true
      try {
        await apiClient.post('/auth/verification', { email, phone })
        showInfo('验证码已发送，请注意查收')
        this.startCountdown()
      } catch (error) {
        this.registerError = error.response?.data?.detail || '验证码发送失败'
        handleError(error)
      } finally {
        this.sendingCode = false
      }
    },
    startCountdown() {
      this.countdown = 60
      if (this.timerId) {
        clearInterval(this.timerId)
      }
      this.timerId = setInterval(() => {
        if (this.countdown > 0) {
          this.countdown -= 1
        } else {
          clearInterval(this.timerId)
          this.timerId = null
        }
      }, 1000)
    }
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  flex-direction: row;
  background: radial-gradient(
      circle at top left,
      rgba(26, 42, 108, 0.9),
      rgba(145, 25, 25, 0.6),
      rgba(26, 42, 108, 0.9),
      rgba(164, 90, 6, 0.6),
      rgba(26, 42, 108, 0.9)
  );
  background-size: 400% 400%;
  animation: gradientBG 30s ease infinite;
  color: #fff;
  position: relative;
  padding: 20px;
  backdrop-filter: blur(10px);
  overflow: hidden;
  width: 100%;
  height: 100vh;
}

@keyframes gradientBG {
  0% {
    background-position: 0 0;
  }
  50% {
    background-position: 100% 100%;
  }
  100% {
    background-position: 0 0;
  }
}

.left-panel {
  flex: 1;
  padding: 40px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  max-width: 45%;
}

.logo {
  display: flex;
  align-items: center;
  margin-bottom: 30px;
}

.logo-icon {
  font-size: 42px;
  margin-right: 15px;
  color: #4CAF50;
}

.logo-text {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 1px;
}

.tagline {
  font-size: 18px;
  margin-top: auto;
  line-height: 1.6;
  opacity: 0.9;
}

.features {
  margin-bottom: 40px;
}

.feature {
  display: flex;
  align-items: center;
  margin-bottom: 15px;
  font-size: 16px;
}

.feature-icon {
  margin-right: 10px;
  color: #4CAF50;
}

.form-container {
  background: rgba(255, 255, 255, 0.1);
  padding: 40px;
  border-radius: 15px;
  width: 100%;
  max-width: 500px;
  min-height: 280px;
  position: relative;
}

.register-form {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 100%;
}

.form-row {
  display: flex;
  align-items: center;
  flex-grow: 1;
  margin-bottom: 15px;
  width: 100%;
}

.form-label {
  width: 80px;
  color: #1a1a34;
  font-weight: 700;
  margin-right: 15px;
  flex-shrink: 0;
  font-size: 20px;
}

input, select {
  flex: 1;
  padding: 12px;
  border: none;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.9);
  font-size: 16px;
  transition: all 0.3s ease;
}

input:focus, select:focus {
  outline: none;
  box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.3);
}

.password-wrapper {
  position: relative;
  flex: 1;
  display: flex;
}

.password-toggle {
  position: absolute;
  right: 12px;
  top: -40%;
  background: none;
  border: none;
  color: #666;
  cursor: pointer;
  font-size: 18px;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: all 0.3s ease;
}

.password-toggle:hover {
  background: rgba(0, 0, 0, 0.1);
}

.btn {
  width: 80%;
  background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  display: block;
  margin: 30px auto 0 auto;
  padding: 12px 24px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  position: relative;
  overflow: hidden;
  z-index: 1;
}

.btn::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(45deg, transparent, rgba(255, 255, 255, 0.3), transparent);
  animation: electricFlow 4s linear infinite;
  z-index: -1;
}

@keyframes electricFlow {
  0% {
    transform: translateX(-100%);
    opacity: 0;
  }
  20% {
    opacity: 1;
  }
  100% {
    transform: translateX(100%);
    opacity: 0;
  }
}

.btn::after {
  content: '';
  position: absolute;
  top: -2px;
  left: -2px;
  right: -2px;
  bottom: -2px;
  border-radius: 10px;
  background: linear-gradient(45deg, #6a11cb, #2575fc, #6a11cb);
  background-size: 500% 500%;
  z-index: -2;
  opacity: 0;
  animation: electricGlow 5s infinite alternate;
}

@keyframes electricGlow {
  0% {
    box-shadow: 0 0 5px #6a11cb, 0 0 10px #2575fc;
  }
  100% {
    box-shadow: 0 0 15px #6a11cb, 0 0 20px #2575fc;
  }
}

.btn:hover {
  background: linear-gradient(45deg, #4a00e0, #8e2de2, #4a00e0);
  animation: enhancedElectricGlow 0.5s infinite alternate;
}

@keyframes enhancedElectricGlow {
  0% {
    box-shadow: 0 0 10px #4a00e0, 0 0 20px #8e2de2;
  }
  100% {
    box-shadow: 0 0 20px #4a00e0, 0 0 30px #8e2de2;
  }
}

.btn:active {
  background: linear-gradient(135deg, #f10f11 0%, #dc7b1a 100%);
  transform: scale(0.98);
}

.btn:hover::before {
  left: 100%;
}

.btn::after {
  content: '';
  position: absolute;
  top: -2px;
  left: -2px;
  right: -2px;
  bottom: -2px;
  background: linear-gradient(45deg, #4CAF50, #388E3C, #4CAF50);
  border-radius: 10px;
  z-index: -2;
  opacity: 0;
  transition: all 0.3s ease;
}

.btn:hover::after {
  opacity: 1;
  animation: borderGlow 1.5s infinite;
}

@keyframes borderGlow {
  0% {
    box-shadow: 0 0 5px #4CAF50, 0 0 10px #4CAF50;
  }
  50% {
    box-shadow: 0 0 15px #4CAF50, 0 0 20px #4CAF50;
  }
  100% {
    box-shadow: 0 0 5px #4CAF50, 0 0 10px #4CAF50;
  }
}

.btn:hover {
  transform: translateY(-2px) scale(1.02);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
  text-shadow: 0 0 5px rgba(255, 255, 255, 0.8);
}

.btn:active {
  transform: translateY(0) scale(0.98);
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
}

.btn::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(255, 255, 255, 0.2);
  transform: translateX(-100%);
  transition: transform 0.5s ease;
}

.btn:hover::after {
  transform: translateX(0);
}

.links {
  display: flex;
  justify-content: flex-end;
  position: absolute;
  bottom: 8px;
  left: 20px;
  right: 20px;
}

.links a {
  color: #245226;
  text-decoration: none;
  font-weight: 500;
  transition: all 0.3s ease;
  cursor: pointer;
  font-size: 14px;
}

.links a:hover {
  text-decoration: underline;
}

.error-message {
  color: #ff5252;
  font-size: 14px;
  margin-top: 5px;
  margin-left: 95px;
}

.input-error {
  border: 1px solid #ff5252;
  box-shadow: 0 0 0 2px rgba(255, 82, 82, 0.2);
}

.footer {
  position: absolute;
  bottom: 20px;
  left: 0;
  width: 100%;
  text-align: center;
  font-size: 14px;
  opacity: 0.7;
}

.mode-switch {
  display: flex;
  justify-content: space-between;
  margin-bottom: 20px;
}
.mode-btn {
  flex: 1;
  padding: 10px 0;
  border: none;
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
  cursor: pointer;
  transition: background 0.3s;
}
.mode-btn.active {
  background: rgba(255, 255, 255, 0.4);
  font-weight: 600;
}
.contact-row {
  gap: 10px;
}
.verify-btn {
  padding: 10px 16px;
  border: none;
  background: #4CAF50;
  color: #fff;
  border-radius: 8px;
  cursor: pointer;
  width: fit-content;
  white-space: nowrap;
}
.verify-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 响应式设计 */
@media (max-width: 900px) {
  .login-container {
    flex-direction: column;
    padding: 10px;
  }

  .left-panel {
    max-width: 100%;
    padding: 20px;
    margin-bottom: 20px;
  }

  .logo-text {
    font-size: 24px;
  }

  .tagline {
    font-size: 16px;
    margin-top: 20px;
  }

  .features {
    margin-bottom: 20px;
  }

  .feature {
    font-size: 14px;
  }

  .form-container {
    max-width: 100%;
    width: 100%;
    padding: 30px 20px;
    min-height: auto;
  }

  .form-row {
    flex-direction: column;
    align-items: stretch;
    margin-bottom: 20px;
  }

  .form-label {
    width: 100%;
    margin-bottom: 8px;
    margin-right: 0;
    text-align: left;
  }

  input {
    width: 100%;
    padding: 15px;
    font-size: 16px;
    min-height: 50px;
    box-sizing: border-box;
  }

  .password-wrapper {
    width: 100%;
  }

  .password-toggle {
    right: 15px;
  }

  .btn {
    width: 100%;
    padding: 15px 24px;
    font-size: 18px;
    margin-top: 20px;
  }

  .error-message {
    margin-left: 0;
    text-align: center;
    margin-top: 10px;
  }

  .links {
    position: static;
    justify-content: center;
    margin-top: 20px;
  }

  .footer {
    position: static;
    margin-top: 20px;
    padding: 10px;
  }
}

@media (max-width: 600px) {
  .login-container {
    padding: 5px;
    border-radius: 10px;
  }

  .left-panel {
    padding: 15px;
  }

  .logo {
    justify-content: center;
    text-align: center;
  }

  .logo-icon {
    font-size: 36px;
  }

  .logo-text {
    font-size: 22px;
  }

  .tagline {
    font-size: 14px;
    text-align: center;
  }

  .features {
    text-align: center;
  }

  .feature {
    justify-content: center;
    font-size: 13px;
  }

  .form-container {
    padding: 20px 15px;
  }

  input {
    padding: 12px;
    font-size: 16px;
    min-height: 48px;
  }

  .btn {
    padding: 12px 20px;
    font-size: 16px;
  }

  .form-label {
    font-size: 14px;
  }
}

@media (max-width: 400px) {
  .left-panel {
    padding: 10px;
  }

  .form-container {
    padding: 15px 10px;
  }

  .logo-text {
    font-size: 20px;
  }

  .tagline {
    font-size: 13px;
  }

  input {
    padding: 10px;
    min-height: 44px;
  }
}
</style>
