<template>
  <div class="account-container">
    <div class="account-left">
      <h1 class="account-title">账号管理</h1>
      <div class="account-avatar" @click="openAvatarPicker" @mouseenter="showAvatarTip = true"
           @mouseleave="showAvatarTip = false">
        <img :src="authStore.user?.avatar" alt="用户头像" class="avatar-image-large"/>
        <div v-if="showAvatarTip" class="avatar-tip">更换头像</div>
      </div>
      <button class="change-password-btn" @click="openPasswordModal">
        <span>更改密码</span>
      </button>
    </div>
    <div class="account-right">
      <div class="account-info">
        <div class="info-item" v-for="item in infoItems" :key="item.field">
          <div class="info-label">
            <font-awesome-icon :icon="item.icon" class="menu-icon"/>
            <span>{{ item.label }}</span>
          </div>
          <div class="info-value">
            <span>{{ user[item.field] }}</span>
          </div>
          <button v-if="item.editable" class="edit-btn" @click="openEditModal(item.field)">
            <font-awesome-icon icon="edit"/>
            <span>编辑</span>
          </button>
        </div>
      </div>
    </div>
    <!-- 编辑信息模态框 -->
    <div class="modal-overlay" v-if="showEditModal" @click.self="closeEditModal">
      <div class="edit-modal">
        <div class="modal-header">
          <h2>{{ modalTitle }}</h2>
        </div>
        <div class="input-group">
          <label>{{ fieldLabel }}</label>
          <input
              type="text"
              class="input-field"
              v-model="editValue"
              :placeholder="`请输入${fieldLabel}`"
          >
          <div class="verification-code-group" v-if="currentField === 'phone' || currentField === 'email'">
            <input
                type="text"
                class="input-field"
                v-model="verificationCode"
                placeholder="请输入验证码"
            >
            <button
                class="send-code-btn"
                @click="sendVerificationCode"
                :disabled="isSendingCode"
            >
              {{ isSendingCode ? `${countdown}秒后重试` : '发送验证码' }}
            </button>
          </div>
        </div>
        <div class="modal-actions">
          <button class="submit-btn" @click="submitEdit">
            <font-awesome-icon icon="check"/>
            <span>提交</span>
          </button>
        </div>
      </div>
    </div>
    <!-- 更改密码模态框 -->
    <div class="modal-overlay" v-if="showPasswordModal" @click.self="closePasswordModal">
      <div class="edit-modal">
        <div class="modal-header">
          <h2>更改密码</h2>
        </div>
        <div class="input-group">
          <label>当前密码</label>
          <input
              type="password"
              class="input-field"
              v-model="currentPassword"
              placeholder="请输入当前密码"
          >
        </div>
        <div class="input-group">
          <label>新密码</label>
          <input
              type="password"
              class="input-field"
              v-model="newPassword"
              placeholder="请输入新密码"
          >
        </div>
        <div class="input-group">
          <label>确认新密码</label>
          <input
              type="password"
              class="input-field"
              v-model="confirmPassword"
              placeholder="请再次输入新密码"
          >
        </div>
        <div class="modal-actions">
          <button class="action-btn" @click="closePasswordModal">
            <font-awesome-icon icon="times"/>
            <span>取消</span>
          </button>
          <button class="submit-btn" @click="submitPassword">
            <font-awesome-icon icon="check"/>
            <span>提交</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import {computed, ref} from 'vue';
import {useAuthStore} from '@/stores/authStore';
import apiClient from '@/utils/axios';
import {showError, showInfo, showSuccess} from '@/utils/toast.js';
import {
  faBullhorn,
  faCalendarAlt,
  faChartBar,
  faChartLine,
  faCheck,
  faCheckCircle,
  faEdit,
  faEnvelope,
  faIndustry,
  faPhone,
  faTags,
  faUser,
  faUserCog,
  faUserTag
} from '@fortawesome/free-solid-svg-icons';
import {library} from "@fortawesome/fontawesome-svg-core";

library.add(faUser, faIndustry, faUserTag, faPhone, faEnvelope, faBullhorn, faCalendarAlt, faChartBar, faChartLine, faCheckCircle, faTags, faUserCog, faCheck, faEdit);
const infoItems = [
  {field: 'username', label: '用户名', icon: faUser, editable: true},
  {field: 'phone', label: '电话', icon: faPhone, editable: true},
  {field: 'email', label: '邮箱', icon: faEnvelope, editable: true}
];

const authStore = useAuthStore();
// 账号信息相关
const user = ref({
  username: authStore.user?.username || '未设置',
  phone: authStore.user?.phone || '未设置',
  email: authStore.user?.email || '未设置',
  avatar: authStore.user?.avatar || '/default-avatar.jpg'
});


// 打开头像选择器
const openAvatarPicker = () => {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/png, image/jpeg, image/jpg, image/gif';
  input.onchange = async (e) => {
    const file = e.target.files[0];
    if (file) {
      await uploadAvatar(file);
    }
  };
  input.click();
};

// 上传头像到后端
const uploadAvatar = async (file) => {
  const formData = new FormData();
  formData.append('avatar', file);
  try {
    const response = await apiClient.patch('/user/avatar', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    if (response.data.status === 'success') {
      authStore.updateAvatar(response.data.avatar);
      user.value.avatar = authStore.user.avatar;
      showSuccess('头像上传成功！');
    } else {
      showError('头像上传失败，请稍后重试');
    }
  } catch (error) {
    console.error('上传头像失败:', error);
  }
};

// 编辑模态框状态
const showEditModal = ref(false);
const currentField = ref('');
const editValue = ref('');
const verificationCode = ref('');
const isSendingCode = ref(false);
const countdown = ref(0);
const modalTitle = computed(() => {
  switch (currentField.value) {
    case 'username':
      return '编辑用户名';
    case 'phone':
      return '编辑电话';
    case 'email':
      return '编辑邮箱';
    default:
      return '编辑信息';
  }
});
const fieldLabel = computed(() => {
  switch (currentField.value) {
    case 'username':
      return '新用户名';
    case 'phone':
      return '新电话';
    case 'email':
      return '新邮箱';
    default:
      return '新内容';
  }
});

// 密码模态框状态
const showPasswordModal = ref(false);
const currentPassword = ref('');
const newPassword = ref('');
const confirmPassword = ref('');

// 鼠标悬停头像时显示"更换头像"提示文字
const showAvatarTip = ref(false);

// 打开编辑模态框
const openEditModal = (field) => {
  currentField.value = field;
  editValue.value = '';
  showEditModal.value = true;
};

// 关闭编辑模态框
const closeEditModal = () => {
  showEditModal.value = false;
  editValue.value = '';
};

const sendVerificationCode = async () => {
  if (!editValue.value.trim()) {
    showError('输入内容不能为空');
    return;
  }
  showInfo('已发送验证码...有效期5分钟');
  try {
    const data = currentField.value === 'phone' ? {phone: editValue.value.trim()} : {email: editValue.value.trim()}
    await apiClient.post('/auth/verification', data);
  } catch (error) {
    console.error('验证码发送失败：', error);
    showError('验证码发送失败：' + error.response.data.detail);
  }
}

// 提交编辑
const submitEdit = async () => {
  if (!editValue.value.trim()) {
    showError('输入内容不能为空');
    return;
  }
  if (currentField.value === 'phone' && !/^\d{10,15}$/.test(editValue.value.trim())) {
    showError('请输入有效的电话号码');
    return;
  }
  if (currentField.value === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(editValue.value.trim())) {
    showError('请输入有效的邮箱地址');
    return;
  }
  showInfo('正在更改' + currentField.value + '...请稍等', false, 20000);
  try {
    let response;
    if (currentField.value === 'username') {
      response = await apiClient.patch('/user/username', editValue.value.trim());
    } else {
      if (!verificationCode.value.trim()) {
        showError('请输入验证码');
        return;
      }
      if (currentField.value === 'phone') {
        response = await apiClient.patch('/user/phone', {
          new_phone: editValue.value.trim(),
          code: verificationCode.value.trim()
        });
      } else if (currentField.value === 'email') {
        response = await apiClient.patch('/user/email', {
          new_email: editValue.value.trim(),
          code: verificationCode.value.trim()
        });
      }
    }
    console.log('用户信息更新结果：', response.data);
    if (response.data.status === 'success') {
      user.value[currentField.value] = editValue.value;
      authStore.user[currentField.value] = editValue.value;
      const token = response.data.new_token;
      if (token) {
        authStore.setAuth(token, response.data.user)
      }
      closeEditModal();
      showSuccess(`${fieldLabel.value}更新成功！`);
    } else {
      showError(response.data.message || '更新失败，请稍后重试');
    }
  } catch (error) {
    console.error('更新失败：', error);
    showError('更新失败：' + error.response.data.detail);
  }
};

// 打开密码模态框
const openPasswordModal = () => {
  showPasswordModal.value = true;
};

// 关闭密码模态框
const closePasswordModal = () => {
  showPasswordModal.value = false;
  currentPassword.value = '';
  newPassword.value = '';
  confirmPassword.value = '';
};

// 提交密码更改
const submitPassword = async () => {
  if (!currentPassword.value || !newPassword.value || !confirmPassword.value) {
    showError('所有字段都必须填写');
    return;
  }
  if (newPassword.value !== confirmPassword.value) {
    showError('两次输入的密码不一致');
    return;
  }
  if (newPassword.value.length < 6) {
    showError('密码长度至少为6位');
    return;
  }
  showInfo('正在更新密码...');
  try {
    const response = await apiClient.post('/user/password', {
      current_password: currentPassword.value,
      new_password: newPassword.value
    });
    if (response.data.status === 'success') {
      showSuccess('密码更新成功！');
      closePasswordModal();
    }
  } catch (error) {
    console.log(error.response.data);
    showError('密码更新失败，请稍后重试：' + error.response.data.detail);
  }
};
</script>

<style scoped>
.dashboard {
  padding: 3rem;
  min-height: 100%;
  display: flex;
  flex-direction: column;
  animation: gradientFlow 8s ease infinite;
  position: relative;
  overflow: hidden;
}

.account-container {
  display: flex;
  flex-direction: row;
  width: 100%;
  min-height: 100vh;
  background: rgba(30, 30, 40, 0.85);
  border-radius: 0;
  box-shadow: none;
  padding: 0;
  margin: 0;
  overflow: hidden;
}

.account-left {
  flex: 0 0 380px;
  background: linear-gradient(135deg, rgba(71, 118, 230, 0.25) 0%, rgba(142, 84, 233, 0.18) 100%),
  rgba(40, 50, 80, 0.55);
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(12px);
  border-right: 2px solid rgba(255, 255, 255, 0.12);
  box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.18);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
  padding: 10% 0 18% 0;
  width: auto;
  height: 100vh;
  position: relative;
}

.account-avatar {
  width: 180px;
  height: 180px;
  background: linear-gradient(135deg, #4776E6, #8E54E9);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 32px rgba(71, 118, 230, 0.5);
  margin-bottom: 32px;
  position: relative;
  overflow: hidden;
  cursor: pointer;
}

.account-avatar::after {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0);
  border-radius: 50%;
  pointer-events: none;
  transition: background 0.3s;
  z-index: 1;
}

.account-avatar:hover::after {
  background: rgba(0, 0, 0, 0.35);
}

.avatar-image-large {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 50%;
  transition: box-shadow 0.3s, filter 0.3s, transform 0.3s;
  position: relative;
  z-index: 2;
}

.account-avatar:hover .avatar-image-large {
  box-shadow: 0 0 32px 0 #4776E6, 0 0 12px 2px #8E54E9;
  filter: brightness(1.08) saturate(1.18);
  transform: scale(1.06);
}

.avatar-tip {
  position: absolute;
  left: 50%;
  bottom: 18px;
  transform: translateX(-50%) translateY(20px);
  background: rgba(30, 34, 50, 0.92);
  color: #fff;
  padding: 8px 22px;
  border-radius: 16px;
  font-size: 1.08rem;
  font-weight: 500;
  letter-spacing: 1px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25), 0 2px 8px #4776E6;
  pointer-events: none;
  z-index: 3;
  opacity: 0;
  white-space: nowrap;
  min-width: 80px;
  max-width: 90%;
  text-align: center;
  transition: opacity 0.25s, transform 0.25s;
}

.account-avatar:hover .avatar-tip {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}

.account-title {
  font-size: 2.8rem;
  color: #fff;
  font-weight: 700;
  text-align: center;
  text-shadow: 0 0 12px rgba(71, 118, 230, 0.5);
}

.change-password-btn {
  width: 80%;
  padding: 1.1rem;
  background: linear-gradient(135deg, rgba(231, 76, 60, 0.2), rgba(192, 57, 43, 0.3));
  color: #e74c3c;
  border: 1px solid rgba(231, 76, 60, 0.4);
  border-radius: 8px;
  cursor: pointer;
  font-size: 1.2rem;
  font-weight: 500;
  transition: all 0.3s ease;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  margin-bottom: 0;
}

.account-right {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-start;
  padding: 0 48px;
  height: 100%;
  background: transparent;
}

.account-info {
  width: 100%;
  max-width: 600px;
  margin: 10% auto;

}

.info-item {
  display: grid;
  grid-template-columns: minmax(120px, auto) 1fr minmax(100px, auto);
  align-items: center;
  padding: 1.2rem 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  gap: 10px;
}

.info-label {
  font-weight: 500;
  color: rgba(255, 255, 255, 0.7);
  display: flex;
  align-items: center;
  gap: 8px;
}

.info-label i {
  font-size: 1.2rem;
  color: #8E54E9;
}

.info-value {
  color: #fff;
  font-size: 1.1rem;
  padding: 0 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.edit-btn {
  padding: 0.6rem 1rem;
  background: rgba(71, 118, 230, 0.2);
  color: #4776E6;
  border: 1px solid rgba(71, 118, 230, 0.4);
  border-radius: 8px;
  cursor: pointer;
  font-size: 1rem;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 120px;
  max-width: 160px;
  margin-left: auto;
}

.edit-btn:hover {
  background: rgba(71, 118, 230, 0.3);
  transform: translateY(-2px);
  box-shadow: 0 5px 15px rgba(71, 118, 230, 0.3);
}

.edit-btn i {
  font-size: 1rem;
}

/* 编辑模态框样式 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(10px);
}

.edit-modal {
  background: linear-gradient(135deg, #1e3c72, #2a5298);
  border-radius: 16px;
  width: 90%;
  max-width: 500px;
  padding: 2rem;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.edit-modal::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.1) 0%, transparent 70%);
  z-index: -1;
}

.modal-header {
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: center;
  align-items: center;
  position: relative;
}

.close-modal-btn {
  background: transparent;
  border: none;
  color: #e74c3c;
  font-size: 1.2rem;
  cursor: pointer;
  transition: opacity 0.2s ease;
  padding: 0.3rem;
  position: relative;
  width: 20px;
  height: 20px;
}

.close-modal-btn::before,
.close-modal-btn::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 100%;
  height: 2px;
  background-color: #e74c3c;
}

.close-modal-btn::before {
  transform: translate(-50%, -50%) rotate(45deg);
}

.close-modal-btn::after {
  transform: translate(-50%, -50%) rotate(-45deg);
}

.close-modal-btn:hover {
  opacity: 0.8;
}

.modal-header h2 {
  font-size: 1.8rem;
  color: #fff;
  text-align: center;
  text-shadow: 0 0 10px rgba(255, 255, 255, 0.3);
}

.input-group {
  margin-bottom: 1.5rem;
}

.input-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: rgba(255, 255, 255, 0.8);
}

.input-field {
  width: 100%;
  padding: 0.8rem 1.2rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: white;
  font-size: 1rem;
  transition: all 0.3s ease;
}

.input-field:focus {
  outline: none;
  border-color: #4776E6;
  box-shadow: 0 0 0 3px rgba(71, 118, 230, 0.3);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 15px;
  margin-top: 2rem;
}

.submit-btn {
  padding: 0.8rem 1.5rem;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  gap: 8px;
}

.action-btn {
  padding: 0.8rem 1.5rem;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  gap: 8px;
}

.submit-btn {
  background: linear-gradient(135deg, #4776E6, #8E54E9);
  color: white;
  border: none;
  box-shadow: 0 4px 15px rgba(71, 118, 230, 0.4);
}

.submit-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 7px 20px rgba(71, 118, 230, 0.6);
}

.notification i {
  font-size: 1.5rem;
}

.notification.success i {
  color: #2ecc71;
}

.notification.error i {
  color: #e74c3c;
}

/* 深色主题只改变颜色，不改变布局 */
.dark-theme .account-container {
  background: rgba(18, 18, 18, 0.95);
}

.dark-theme .account-left {
  background: linear-gradient(135deg, rgba(71, 118, 230, 0.12) 0%, rgba(142, 84, 233, 0.10) 100%), rgba(40, 50, 80, 0.55);
  border-right: 2px solid rgba(255, 255, 255, 0.08);
}

.dark-theme .account-title {
  color: #bb86fc;
  text-shadow: 0 0 12px rgba(187, 134, 252, 0.2);
}

.dark-theme .account-avatar {
  background: linear-gradient(135deg, #3700b3, #8E54E9);
  box-shadow: 0 0 32px rgba(98, 0, 234, 0.3);
}

.dark-theme .change-password-btn {
  background: linear-gradient(135deg, rgba(98, 0, 234, 0.15), rgba(55, 0, 179, 0.18));
  color: #bb86fc;
  border: 1px solid rgba(98, 0, 234, 0.2);
}

.dark-theme .account-right {
  background: transparent;
}

.dark-theme .info-label {
  color: #bb86fc;
}

.dark-theme .info-value {
  color: #e0e0e0;
}

.dark-theme .edit-btn {
  background: rgba(98, 0, 234, 0.15);
  color: #bb86fc;
  border: 1px solid rgba(98, 0, 234, 0.2);
}

.dark-theme .edit-btn:hover {
  background: rgba(98, 0, 234, 0.25);
}

.dark-theme .modal-overlay {
  background: rgba(18, 18, 18, 0.85);
}

.dark-theme .edit-modal {
  background: linear-gradient(135deg, #232323, #2a2a2a);
  border: 1px solid rgba(187, 134, 252, 0.08);
}

.dark-theme .modal-header h2 {
  color: #bb86fc;
}

.dark-theme .input-group label {
  color: #bb86fc;
}

.dark-theme .input-field {
  background: rgba(30, 30, 40, 0.7);
  color: #e0e0e0;
  border: 1px solid #444;
}

.dark-theme .input-field:focus {
  border-color: #bb86fc;
  box-shadow: 0 0 0 3px rgba(187, 134, 252, 0.2);
}

.dark-theme .submit-btn {
  background: linear-gradient(135deg, #3700b3, #8E54E9);
  color: #fff;
}

.dark-theme .submit-btn:hover {
  background: linear-gradient(135deg, #6200ea, #bb86fc);
}

/* 响应式设计 */
@media (max-width: 900px) {
  .account-container {
    flex-direction: column;
    height: auto;
    min-height: 100vh;
  }

  .account-left {
    background: linear-gradient(135deg, rgba(71, 118, 230, 0.18) 0%, rgba(142, 84, 233, 0.12) 100%), rgba(40, 50, 80, 0.45);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border-right: none;
    border-bottom: 2px solid rgba(255, 255, 255, 0.10);
    box-shadow: 0 4px 16px 0 rgba(31, 38, 135, 0.12);
    /* 其他样式不变 */
  }

  .account-right {
    padding: 0 16px;
    align-items: center;
  }

  .account-info {
    max-width: 100%;
  }
}

@media (max-width: 600px) {
  .account-left {
    background: linear-gradient(135deg, rgba(71, 118, 230, 0.12) 0%, rgba(142, 84, 233, 0.08) 100%), rgba(40, 50, 80, 0.35);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 2px 8px 0 rgba(31, 38, 135, 0.08);
  }

  .account-avatar {
    width: 100px;
    height: 100px;
  }

  .account-title {
    font-size: 2rem;
  }

  .change-password-btn {
    font-size: 1rem;
    padding: 0.8rem;
  }

  .account-right {
    padding: 0 4px;
  }

  .info-item {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .edit-btn {
    width: 100%;
    max-width: none;
    margin-top: 10px;
    margin-left: 0;
  }
}
</style>