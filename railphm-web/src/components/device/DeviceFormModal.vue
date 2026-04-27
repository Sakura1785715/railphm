<template>
  <Teleport to="body">
    <div v-if="visible" class="device-form-modal" @click.self="handleClose">
      <section class="device-form-modal__panel" role="dialog" aria-modal="true" :aria-label="modalTitle">
        <header class="device-form-modal__header">
          <div>
            <p class="section-tag">设备台账</p>
            <h3>{{ modalTitle }}</h3>
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
            <span>车号</span>
            <input
              v-model.trim="form.carNo"
              type="text"
              placeholder="请输入车号"
              :disabled="submitting"
            />
          </label>

          <label class="device-form__field">
            <span>ATP 类型</span>
            <input
              v-model.trim="form.atpType"
              type="text"
              placeholder="请输入 ATP 类型"
              :disabled="submitting"
            />
          </label>

          <label class="device-form__field">
            <span>配属铁路局</span>
            <input
              v-model.trim="form.attachBureau"
              type="text"
              placeholder="请输入配属铁路局"
              :disabled="submitting"
            />
          </label>

          <label class="device-form__field">
            <span>设备状态</span>
            <select v-model="form.deviceStatus" :disabled="submitting">
              <option value="">请选择设备状态</option>
              <option value="1">在册运行</option>
              <option value="0">停用观察</option>
            </select>
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
  carNo: '',
  atpType: '',
  attachBureau: '',
  deviceStatus: '1'
})
const validationError = ref('')

const modalTitle = computed(() => (props.mode === 'edit' ? '编辑设备' : '新增设备'))
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
  validationError.value = ''

  if (props.mode === 'edit' && props.initialDevice) {
    form.carNo = props.initialDevice.car_no ? String(props.initialDevice.car_no) : ''
    form.atpType = props.initialDevice.atp_type ? String(props.initialDevice.atp_type) : ''
    form.attachBureau = props.initialDevice.attach_bureau ? String(props.initialDevice.attach_bureau) : ''
    form.deviceStatus = normalizeDeviceStatus(props.initialDevice.device_status)
    return
  }

  form.carNo = ''
  form.atpType = ''
  form.attachBureau = ''
  form.deviceStatus = '1'
}

function handleSubmit() {
  validationError.value = ''

  const error = validateForm()
  if (error) {
    validationError.value = error
    return
  }

  emit('submit', {
    car_no: form.carNo.trim(),
    atp_type: form.atpType.trim(),
    attach_bureau: form.attachBureau.trim(),
    device_status: Number(form.deviceStatus)
  })
}

function validateForm() {
  if (!form.carNo.trim()) {
    return '请输入车号'
  }

  if (!form.atpType.trim()) {
    return '请输入 ATP 类型'
  }

  if (!form.attachBureau.trim()) {
    return '请输入配属铁路局'
  }

  if (form.deviceStatus === '') {
    return '请选择设备状态'
  }

  if (!['0', '1'].includes(String(form.deviceStatus))) {
    return '请选择设备状态'
  }

  return ''
}

function handleClose() {
  if (props.submitting) {
    return
  }

  emit('close')
}

function normalizeDeviceStatus(status) {
  const normalized = String(status)
  return normalized === '0' || normalized === '1' ? normalized : ''
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
  background: #ffffff;
  border: 1px solid #d7e1ee;
  border-radius: 22px;
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
  color: #0f6c85;
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.device-form-modal__header h3 {
  margin: 8px 0 0;
  color: #0f172a;
}

.device-form-modal__close {
  width: 36px;
  height: 36px;
  border: 1px solid #cfe0eb;
  border-radius: 12px;
  background: #f8fbfd;
  color: #45617f;
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
  color: #45617f;
  font-size: 0.92rem;
  font-weight: 650;
}

.device-form__field input,
.device-form__field select {
  width: 100%;
  min-height: 46px;
  padding: 0 14px;
  border: 1px solid #cfe0eb;
  border-radius: 12px;
  background: #f8fbfd;
  color: #17253a;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
}

.device-form__field input:focus,
.device-form__field select:focus {
  border-color: #0f6c85;
  box-shadow: 0 0 0 4px rgba(15, 108, 133, 0.12);
  background: #ffffff;
}

.device-form__field input:disabled,
.device-form__field select:disabled {
  opacity: 0.72;
  cursor: wait;
}

.device-form__error {
  margin: 0;
  padding: 12px 14px;
  color: #b42318;
  background: #fef3f2;
  border: 1px solid #fecdca;
  border-radius: 12px;
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
}
</style>
