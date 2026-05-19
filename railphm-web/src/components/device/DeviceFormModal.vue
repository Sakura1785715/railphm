<template>
  <Teleport to="body">
    <div v-if="visible" class="device-form-modal" @click.self="handleClose">
      <section class="device-form-modal__panel" role="dialog" aria-modal="true" :aria-label="modalTitle">
        <header class="device-form-modal__header">
          <div>
            <p class="section-tag">设备台账</p>
            <h3>{{ modalTitle }}</h3>
            <p>{{ modalDescription }}</p>
          </div>
          <button
            class="device-form-modal__close"
            type="button"
            aria-label="关闭"
            :disabled="submitting"
            @click="handleClose"
          >
            ×
          </button>
        </header>

        <form class="device-form" @submit.prevent="handleSubmit">
          <label class="device-form__field">
            <span>设备编号</span>
            <input
              v-model.trim="form.deviceCode"
              type="text"
              placeholder="请输入设备编号，如 ATP001"
              :disabled="submitting"
              :aria-invalid="Boolean(fieldErrors.deviceCode)"
            />
            <small v-if="fieldErrors.deviceCode">{{ fieldErrors.deviceCode }}</small>
          </label>

          <label class="device-form__field">
            <span>设备名称</span>
            <input
              v-model.trim="form.deviceName"
              type="text"
              placeholder="请输入设备名称"
              :disabled="submitting"
              :aria-invalid="Boolean(fieldErrors.deviceName)"
            />
            <small v-if="fieldErrors.deviceName">{{ fieldErrors.deviceName }}</small>
          </label>

          <label class="device-form__field">
            <span>设备类型</span>
            <input
              v-model.trim="form.deviceType"
              type="text"
              placeholder="ATP"
              :disabled="submitting"
              :aria-invalid="Boolean(fieldErrors.deviceType)"
            />
            <small v-if="fieldErrors.deviceType">{{ fieldErrors.deviceType }}</small>
          </label>

          <label class="device-form__field">
            <span>车号</span>
            <input
              v-model.trim="form.carNo"
              type="text"
              placeholder="请输入车号"
              :disabled="submitting"
              :aria-invalid="Boolean(fieldErrors.carNo)"
            />
            <small v-if="fieldErrors.carNo">{{ fieldErrors.carNo }}</small>
          </label>

          <label class="device-form__field">
            <span>ATP 类型</span>
            <input
              v-model.trim="form.atpType"
              type="text"
              placeholder="请输入 ATP 类型"
              :disabled="submitting"
              :aria-invalid="Boolean(fieldErrors.atpType)"
            />
            <small v-if="fieldErrors.atpType">{{ fieldErrors.atpType }}</small>
          </label>

          <label class="device-form__field">
            <span>车组号</span>
            <input
              v-model.trim="form.trainNo"
              type="text"
              placeholder="请输入车组号，可为空"
              :disabled="submitting"
            />
          </label>

          <label class="device-form__field">
            <span>位置/配属铁路局</span>
            <input
              v-model.trim="form.attachBureau"
              type="text"
              placeholder="请输入配属铁路局"
              :disabled="submitting"
              :aria-invalid="Boolean(fieldErrors.attachBureau)"
            />
            <small v-if="fieldErrors.attachBureau">{{ fieldErrors.attachBureau }}</small>
          </label>

          <label class="device-form__field">
            <span>设备状态</span>
            <select
              v-model="form.deviceStatus"
              :disabled="submitting"
              :aria-invalid="Boolean(fieldErrors.deviceStatus)"
            >
              <option value="">请选择设备状态</option>
              <option value="1">正常</option>
              <option value="2">关注</option>
              <option value="3">预警</option>
              <option value="4">告警</option>
            </select>
            <small v-if="fieldErrors.deviceStatus">{{ fieldErrors.deviceStatus }}</small>
          </label>

          <p v-if="displayError" class="device-form__error">{{ displayError }}</p>

          <footer class="device-form__actions">
            <button class="secondary-button" type="button" :disabled="submitting" @click="handleClose">
              取消
            </button>
            <button class="primary-button" type="submit" :disabled="submitting">
              {{ submitting ? '提交中...' : '保存' }}
            </button>
          </footer>
        </form>
      </section>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  mode: {
    type: String,
    default: 'create'
  },
  initialDevice: {
    type: Object,
    default: null
  },
  submitting: {
    type: Boolean,
    default: false
  },
  errorMessage: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['submit', 'close'])

const form = reactive({
  deviceCode: '',
  deviceName: '',
  deviceType: 'ATP',
  carNo: '',
  atpType: '',
  trainNo: '',
  attachBureau: '',
  deviceStatus: '1'
})
const validationError = ref('')
const fieldErrors = reactive({
  deviceCode: '',
  deviceName: '',
  deviceType: '',
  carNo: '',
  atpType: '',
  attachBureau: '',
  deviceStatus: ''
})

const modalTitle = computed(() => (props.mode === 'edit' ? '编辑设备' : '新增设备'))
const modalDescription = computed(() =>
  props.mode === 'edit' ? '调整设备基础档案字段，保存后自动刷新台账列表。' : '录入设备基础档案，设备 ID 由后端生成。'
)
const displayError = computed(() => validationError.value || props.errorMessage)

watch(
  () => [props.visible, props.mode, props.initialDevice],
  () => {
    if (props.visible) {
      syncForm()
    }
  },
  { immediate: true }
)

function syncForm() {
  resetErrors()

  if (props.mode === 'edit' && props.initialDevice) {
    form.deviceCode = props.initialDevice.device_code ? String(props.initialDevice.device_code) : ''
    form.deviceName = props.initialDevice.device_name ? String(props.initialDevice.device_name) : ''
    form.deviceType = props.initialDevice.device_type ? String(props.initialDevice.device_type) : 'ATP'
    form.carNo = props.initialDevice.car_no ? String(props.initialDevice.car_no) : ''
    form.atpType = props.initialDevice.atp_type ? String(props.initialDevice.atp_type) : ''
    form.trainNo = props.initialDevice.train_no ? String(props.initialDevice.train_no) : ''
    form.attachBureau = props.initialDevice.attach_bureau ? String(props.initialDevice.attach_bureau) : ''
    form.deviceStatus = normalizeDeviceStatus(props.initialDevice.device_status)
    return
  }

  form.deviceCode = ''
  form.deviceName = ''
  form.deviceType = 'ATP'
  form.carNo = ''
  form.atpType = ''
  form.trainNo = ''
  form.attachBureau = ''
  form.deviceStatus = '1'
}

function handleSubmit() {
  resetErrors()

  if (!validateForm()) {
    validationError.value = '请修正表单中的必填项后再提交'
    return
  }

  emit('submit', {
    device_code: form.deviceCode.trim(),
    device_name: form.deviceName.trim(),
    device_type: form.deviceType.trim() || 'ATP',
    car_no: form.carNo.trim(),
    atp_type: form.atpType.trim(),
    train_no: form.trainNo.trim() || null,
    attach_bureau: form.attachBureau.trim(),
    device_status: Number(form.deviceStatus)
  })
}

function validateForm() {
  if (!form.deviceCode.trim()) {
    fieldErrors.deviceCode = '请输入设备编号'
  }

  if (!form.deviceName.trim()) {
    fieldErrors.deviceName = '请输入设备名称'
  }

  if (!form.deviceType.trim()) {
    fieldErrors.deviceType = '请输入设备类型'
  }

  if (!form.carNo.trim()) {
    fieldErrors.carNo = '请输入车号'
  }

  if (!form.atpType.trim()) {
    fieldErrors.atpType = '请输入 ATP 类型'
  }

  if (!form.attachBureau.trim()) {
    fieldErrors.attachBureau = '请输入配属铁路局'
  }

  if (form.deviceStatus === '') {
    fieldErrors.deviceStatus = '请选择设备状态'
  } else if (!['1', '2', '3', '4'].includes(String(form.deviceStatus))) {
    fieldErrors.deviceStatus = '设备状态只能为 1、2、3 或 4'
  }

  return !fieldErrors.deviceCode && !fieldErrors.deviceName && !fieldErrors.deviceType && !fieldErrors.carNo && !fieldErrors.atpType && !fieldErrors.attachBureau && !fieldErrors.deviceStatus
}

function handleClose() {
  if (props.submitting) {
    return
  }

  emit('close')
}

function normalizeDeviceStatus(status) {
  const normalized = String(status)
  return ['1', '2', '3', '4'].includes(normalized) ? normalized : ''
}

function resetErrors() {
  validationError.value = ''
  fieldErrors.deviceCode = ''
  fieldErrors.deviceName = ''
  fieldErrors.deviceType = ''
  fieldErrors.carNo = ''
  fieldErrors.atpType = ''
  fieldErrors.attachBureau = ''
  fieldErrors.deviceStatus = ''
}
</script>

<style scoped>
.device-form-modal {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 22px;
  background: rgba(15, 23, 42, 0.36);
}

.device-form-modal__panel {
  width: min(560px, 100%);
  display: grid;
  gap: 18px;
  padding: 24px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: 0 28px 70px rgba(15, 23, 42, 0.22);
}

.device-form-modal__header,
.device-form__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.section-tag {
  margin: 0;
  color: var(--color-primary);
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.device-form-modal__header h3 {
  margin: 8px 0 0;
  color: var(--color-text-primary);
}

.device-form-modal__header p:not(.section-tag) {
  margin: 8px 0 0;
  color: var(--color-text-secondary);
  line-height: 1.6;
}

.device-form-modal__close {
  width: 36px;
  height: 36px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-lg);
  background: var(--color-bg-soft);
  color: var(--color-text-secondary);
  font-size: 1.4rem;
  line-height: 1;
  cursor: pointer;
}

.device-form-modal__close:disabled {
  opacity: 0.58;
  cursor: not-allowed;
}

.device-form {
  display: grid;
  gap: 14px;
}

.device-form__field {
  display: grid;
  gap: 8px;
}

.device-form__field span {
  color: var(--color-text-secondary);
  font-size: 0.92rem;
  font-weight: 650;
}

.device-form__field small {
  color: var(--color-danger);
  line-height: 1.5;
}

.device-form__field input,
.device-form__field select {
  width: 100%;
  min-height: 46px;
  padding: 0 14px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-lg);
  background: var(--color-bg-panel);
  color: var(--color-text-primary);
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
}

.device-form__field input[aria-invalid="true"],
.device-form__field select[aria-invalid="true"] {
  border-color: var(--color-danger-border);
  background: var(--color-danger-soft);
}

.device-form__field input:focus,
.device-form__field select:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 4px rgba(29, 79, 145, 0.12);
  background: var(--color-bg-panel);
}

.device-form__field input:disabled,
.device-form__field select:disabled {
  opacity: 0.72;
  cursor: wait;
}

.device-form__error {
  margin: 0;
  padding: 12px 14px;
  color: var(--color-danger);
  background: var(--color-danger-soft);
  border: 1px solid var(--color-danger-border);
  border-radius: var(--radius-lg);
  font-size: 0.92rem;
  font-weight: 650;
}

.device-form__actions {
  justify-content: flex-end;
  padding-top: 4px;
}

@media (max-width: 640px) {
  .device-form-modal {
    padding: 14px;
  }

  .device-form-modal__panel {
    padding: 20px;
  }

  .device-form-modal__header,
  .device-form__actions {
    align-items: flex-start;
    flex-direction: column;
  }

  .device-form__actions,
  .device-form__actions button {
    width: 100%;
  }
}
</style>
