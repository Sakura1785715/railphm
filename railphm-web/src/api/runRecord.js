import http from './http'

const RUN_RECORD_INFER_TIMEOUT_MS = 180000

export const DEFAULT_RUN_RECORD_INFER_PAYLOAD = {
  mc_samples: 20,
  persist: true,
  generate_alert: false,
  inference_stride_seconds: 1
}

export function getRunRecords(params = {}) {
  return http.get('/v1/run-records', { params })
}

export function getRunRecordDetail(runRecordId) {
  return http.get(`/v1/run-records/${runRecordId}`)
}

export function getRunRecordMonitor(runRecordId) {
  return http.get(`/v1/run-records/${runRecordId}/monitor`)
}

export function getRandomRunRecord(params = {}) {
  return http.get('/v1/run-records/random', { params })
}

export function inferRunRecord(runRecordId, payload = {}) {
  return http.post(
    `/v1/run-records/${runRecordId}/infer`,
    {
      ...DEFAULT_RUN_RECORD_INFER_PAYLOAD,
      ...payload,
      inference_stride_seconds: 1
    },
    {
      timeout: RUN_RECORD_INFER_TIMEOUT_MS
    }
  )
}

export function generateRunRecordAlert(runRecordId, payload = {}) {
  return http.post(`/v1/run-records/${runRecordId}/alert`, payload || {})
}
