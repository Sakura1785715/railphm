<template>
  <section class="login-container">
    <aside class="login-left" aria-label="RailPHM brand panel">
      <svg class="train-line-art" viewBox="0 0 980 360" aria-hidden="true">
        <path
          d="M72 238c70-76 164-116 282-120l262-10c80-3 145 18 196 63l62 55c25 22 13 62-20 67l-117 18H160c-61 0-105-21-132-63"
        />
        <path d="M203 177h120m48-4h122m45-7h124m-410 93h406m-529 50h693" />
        <path
          d="M709 127c30 8 60 24 88 48l38 33H669l-50-74 90-7Z"
        />
        <path d="M397 215h95l-20-52h-75v52Zm139 0h94l-28-60h-80l14 60Zm-276 0h92l18-50h-72l-38 50Z" />
        <circle cx="244" cy="311" r="31" />
        <circle cx="244" cy="311" r="12" />
        <circle cx="694" cy="311" r="31" />
        <circle cx="694" cy="311" r="12" />
        <path d="M95 247c33 17 72 25 118 25h489c56 0 108-5 155-16" />
      </svg>

      <div class="brand-content">
        <span class="brand-rule"></span>
        <p class="brand-kicker">RailPHM Platform</p>
        <h1>
          高铁列控设备<br />
          故障预测与<br />
          健康管理系统
        </h1>
        <p class="brand-subtitle">
          High-Speed Train<br />
          PHM System V1.0
        </p>
      </div>

      <p class="system-id">SYSTEM_ID: RAILPHM_ATP_01</p>
    </aside>

    <main class="login-right">
      <section class="login-panel" aria-labelledby="login-title">
        <div class="login-heading">
          <p class="security-label">AUTHORIZED PERSONNEL ONLY</p>
          <h2 id="login-title">Secure Login</h2>
          <p>Please identify yourself to access the RailPHM terminal.</p>
        </div>

        <form class="login-form" @submit.prevent="handleLogin">
          <label class="form-field">
            <span>EMPLOYEE ID / 工号</span>
            <span class="input-shell">
              <span class="input-icon" aria-hidden="true">▣</span>
              <input
                v-model="form.username"
                type="text"
                autocomplete="username"
                placeholder="Enter your ID"
                :disabled="loading"
                @input="clearError"
              />
            </span>
          </label>

          <label class="form-field">
            <span>PASSWORD / 密码</span>
            <span class="input-shell">
              <span class="input-icon input-icon--dot" aria-hidden="true">●</span>
              <input
                v-model="form.password"
                type="password"
                autocomplete="current-password"
                placeholder="••••••••"
                :disabled="loading"
                @input="clearError"
              />
            </span>
          </label>

          <label class="form-field">
            <span>VERIFICATION / 验证码</span>
            <span class="captcha-row">
              <span class="input-shell captcha-input">
                <span class="input-icon" aria-hidden="true">◆</span>
                <input
                  v-model="form.captchaCode"
                  type="text"
                  autocomplete="off"
                  placeholder="Code"
                  :disabled="loading"
                  @input="clearError"
                />
              </span>
              <button
                class="captcha-box"
                type="button"
                :disabled="captchaLoading || loading"
                title="刷新验证码"
                @click="fetchCaptcha"
              >
                <img v-if="captchaImage && !captchaLoading" :src="captchaImage" alt="验证码" />
                <span v-else-if="captchaLoading">加载中...</span>
                <span v-else>{{ captchaError ? '点击重试' : '验证码' }}</span>
              </button>
            </span>
          </label>

          <label class="remember-row">
            <input v-model="form.rememberId" type="checkbox" :disabled="loading" />
            <span>Remember ID</span>
          </label>

          <p v-if="errorMessage" class="error-message" role="alert">{{ errorMessage }}</p>

          <button class="login-button" type="submit" :disabled="loading">
            {{ submitText }}
          </button>
        </form>

        <div class="account-hint" aria-label="test accounts">
          <p>测试账号</p>
          <div>
            <span>admin / 123456</span>
            <strong>系统管理员</strong>
          </div>
          <div>
            <span>ops / 123456</span>
            <strong>运维用户</strong>
          </div>
        </div>

        <p class="security-footnote">
          Protected by Industrial Security Protocols • Internal System Access
        </p>
      </section>
    </main>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getCaptcha, login } from '../api/auth'
import { setStoredUser, setToken } from '../utils/auth'

const REMEMBER_ID_KEY = 'railphm_remember_username'

const route = useRoute()
const router = useRouter()
const rememberedUsername = localStorage.getItem(REMEMBER_ID_KEY)

const form = reactive({
  username: rememberedUsername || 'admin',
  password: '123456',
  captchaId: '',
  captchaCode: '',
  rememberId: Boolean(rememberedUsername)
})

const loading = ref(false)
const captchaImage = ref('')
const captchaLoading = ref(false)
const captchaError = ref('')
const errorMessage = ref('')
const submitText = computed(() => (loading.value ? '登录中...' : '登录 / Login'))

onMounted(() => {
  fetchCaptcha()
})

async function fetchCaptcha() {
  captchaLoading.value = true
  captchaError.value = ''

  try {
    const result = await getCaptcha()
    const data = result?.data || {}

    form.captchaId = data.captcha_id || ''
    captchaImage.value = data.captcha_image || ''
    form.captchaCode = ''

    if (!form.captchaId || !captchaImage.value) {
      throw new Error('验证码响应缺少必要字段')
    }
  } catch {
    form.captchaId = ''
    captchaImage.value = ''
    form.captchaCode = ''
    captchaError.value = '验证码加载失败，请点击重试'
  } finally {
    captchaLoading.value = false
  }
}

async function handleLogin() {
  if (loading.value) {
    return
  }

  errorMessage.value = ''

  if (!form.username.trim()) {
    errorMessage.value = '请输入用户名'
    return
  }

  if (!form.password) {
    errorMessage.value = '请输入密码'
    return
  }

  if (!form.captchaId) {
    errorMessage.value = '请先获取验证码'
    return
  }

  if (!form.captchaCode.trim()) {
    errorMessage.value = '请输入验证码'
    return
  }

  loading.value = true

  try {
    const result = await login({
      username: form.username.trim(),
      password: form.password,
      captcha_id: form.captchaId,
      captcha_code: form.captchaCode.trim()
    })
    const data = result?.data || {}

    if (!data.token || !data.user) {
      throw new Error('登录响应缺少身份信息')
    }

    setToken(data.token)
    setStoredUser(data.user)

    if (form.rememberId) {
      localStorage.setItem(REMEMBER_ID_KEY, form.username.trim())
    } else {
      localStorage.removeItem(REMEMBER_ID_KEY)
    }

    router.replace(resolveRedirectPath())
  } catch (error) {
    errorMessage.value = error?.message || '登录失败，请检查用户名和密码'
    form.captchaCode = ''
    await fetchCaptcha()
  } finally {
    loading.value = false
  }
}

function clearError() {
  if (errorMessage.value) {
    errorMessage.value = ''
  }
}

function resolveRedirectPath() {
  const redirect = route.query.redirect

  if (
    typeof redirect === 'string' &&
    redirect &&
    redirect !== '/login' &&
    redirect.startsWith('/') &&
    !redirect.startsWith('//')
  ) {
    return redirect
  }

  return '/'
}
</script>

<style scoped>
.login-container {
  --login-dark: #111a35;
  --login-primary: #2563eb;
  --login-text-dark: #0f172a;
  --login-text-gray: #64748b;
  --login-border: #e2e8f0;
  --login-muted: #94a3b8;

  display: flex;
  min-height: 100vh;
  width: 100%;
  overflow: hidden;
  background: #ffffff;
  color: var(--login-text-dark);
  font-family: Inter, "Noto Sans SC", system-ui, sans-serif;
}

.login-left {
  position: relative;
  width: 40%;
  min-width: 420px;
  display: flex;
  align-items: center;
  padding: 72px 64px;
  overflow: hidden;
  background:
    linear-gradient(143deg, rgba(37, 99, 235, 0.18), transparent 38%),
    linear-gradient(180deg, rgba(15, 23, 42, 0.18), rgba(15, 23, 42, 0)),
    var(--login-dark);
  color: #ffffff;
}

.login-left::before {
  position: absolute;
  inset: 0;
  content: "";
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: linear-gradient(90deg, rgba(0, 0, 0, 0.9), transparent 86%);
}

.train-line-art {
  position: absolute;
  right: -46%;
  bottom: 4%;
  width: 150%;
  opacity: 0.1;
  transform: rotate(-12deg) translate(2.5rem, 5rem);
  mask-image: linear-gradient(90deg, transparent 0%, #000 22%, #000 78%, transparent 100%);
}

.train-line-art path,
.train-line-art circle {
  fill: none;
  stroke: #ffffff;
  stroke-width: 7;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.brand-content {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 22px;
  max-width: 470px;
}

.brand-rule {
  width: 48px;
  height: 5px;
  background: var(--login-primary);
  border-radius: 999px;
  box-shadow: 0 0 24px rgba(37, 99, 235, 0.8);
}

.brand-kicker {
  margin: 0;
  color: rgba(226, 232, 240, 0.74);
  font-size: 0.76rem;
  font-weight: 750;
  letter-spacing: 0;
  text-transform: uppercase;
}

.brand-content h1 {
  margin: 0;
  color: #ffffff;
  font-size: 3.5rem;
  font-weight: 760;
  line-height: 1.16;
}

.brand-subtitle {
  margin: 8px 0 0;
  color: rgba(226, 232, 240, 0.72);
  font-size: 1.08rem;
  font-weight: 560;
  line-height: 1.75;
}

.system-id {
  position: absolute;
  left: 64px;
  bottom: 44px;
  z-index: 1;
  margin: 0;
  color: rgba(148, 163, 184, 0.9);
  font-family: "SFMono-Regular", Consolas, monospace;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0;
}

.login-right {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
  background:
    radial-gradient(circle at 82% 16%, rgba(37, 99, 235, 0.06), transparent 24%),
    #ffffff;
}

.login-panel {
  width: min(440px, 100%);
  display: grid;
  gap: 28px;
}

.login-heading {
  display: grid;
  gap: 10px;
}

.security-label {
  margin: 0;
  color: var(--login-primary);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0;
}

.login-heading h2 {
  margin: 0;
  color: var(--login-text-dark);
  font-size: 2.1rem;
  font-weight: 760;
  line-height: 1.1;
}

.login-heading p:not(.security-label) {
  margin: 0;
  color: var(--login-text-gray);
  font-size: 0.98rem;
  line-height: 1.7;
}

.login-form {
  display: grid;
  gap: 18px;
}

.form-field {
  display: grid;
  gap: 9px;
}

.form-field > span:first-child {
  color: #334155;
  font-size: 0.77rem;
  font-weight: 780;
  letter-spacing: 0;
}

.input-shell {
  display: flex;
  align-items: center;
  height: 48px;
  border: 1px solid var(--login-border);
  border-radius: 8px;
  background: #ffffff;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.input-shell:focus-within {
  border-color: var(--login-primary);
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.11);
}

.input-icon {
  width: 48px;
  color: var(--login-muted);
  font-size: 0.86rem;
  text-align: center;
}

.input-icon--dot {
  font-size: 0.72rem;
}

.input-shell input {
  min-width: 0;
  width: 100%;
  height: 100%;
  padding: 0 16px 0 0;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--login-text-dark);
  font-size: 0.97rem;
}

.input-shell input::placeholder {
  color: var(--login-muted);
}

.input-shell input:disabled {
  cursor: wait;
}

.captcha-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 128px;
  gap: 12px;
  align-items: center;
}

.captcha-input {
  min-width: 0;
}

.captcha-box {
  width: 128px;
  height: 48px;
  display: grid;
  place-items: center;
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--login-border);
  border-radius: 8px;
  background: #f8fafc;
  color: var(--login-text-gray);
  font-size: 0.8rem;
  font-weight: 760;
  cursor: pointer;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.captcha-box:hover:not(:disabled) {
  border-color: var(--login-primary);
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.1);
}

.captcha-box:disabled {
  cursor: wait;
}

.captcha-box img {
  width: 128px;
  height: 48px;
  display: block;
  object-fit: cover;
}

.remember-row {
  display: inline-flex;
  width: fit-content;
  align-items: center;
  gap: 9px;
  color: var(--login-text-gray);
  font-size: 0.9rem;
  font-weight: 620;
  user-select: none;
}

.remember-row input {
  width: 16px;
  height: 16px;
  accent-color: var(--login-primary);
}

.error-message {
  margin: 0;
  padding: 12px 14px;
  border: 1px solid #fecaca;
  border-radius: 8px;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 0.9rem;
  font-weight: 680;
}

.login-button {
  height: 52px;
  border-radius: 8px;
  background: var(--login-primary);
  color: #ffffff;
  font-size: 0.98rem;
  font-weight: 780;
  letter-spacing: 0;
  cursor: pointer;
  box-shadow: 0 14px 28px rgba(37, 99, 235, 0.24);
  transition: background-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.login-button:hover:not(:disabled) {
  background: #1d4ed8;
  box-shadow: 0 18px 34px rgba(37, 99, 235, 0.3);
  transform: translateY(-1px);
}

.login-button:disabled {
  opacity: 0.72;
  cursor: wait;
  box-shadow: none;
}

.account-hint {
  display: grid;
  gap: 10px;
  padding: 16px;
  border: 1px solid var(--login-border);
  border-radius: 8px;
  background: #f8fafc;
}

.account-hint p {
  margin: 0;
  color: #475569;
  font-size: 0.75rem;
  font-weight: 820;
  letter-spacing: 0;
  text-transform: uppercase;
}

.account-hint div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  color: var(--login-text-gray);
  font-size: 0.9rem;
}

.account-hint span {
  color: var(--login-text-dark);
  font-family: "SFMono-Regular", Consolas, monospace;
  font-weight: 760;
}

.account-hint strong {
  color: #475569;
  font-size: 0.88rem;
}

.security-footnote {
  margin: 2px 0 0;
  color: var(--login-muted);
  font-size: 0.82rem;
  line-height: 1.6;
}

@media (max-width: 980px) {
  .login-left {
    display: none;
  }

  .login-right {
    min-height: 100vh;
    padding: 36px 24px;
  }
}

@media (max-width: 560px) {
  .login-panel {
    gap: 22px;
  }

  .login-heading h2 {
    font-size: 1.82rem;
  }

  .account-hint div {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }

  .captcha-row {
    grid-template-columns: 1fr;
  }
}
</style>
