import http from './http'

const RUN_RECORD_INFER_TIMEOUT_MS = 180000

// 执行运行记录预测时默认传给后端的参数
export const DEFAULT_RUN_RECORD_INFER_PAYLOAD = {
  mc_samples: 20, // MC Dropout推理次数
  persist: true, // 是否把预测结果保存到数据库
  generate_alert: false, // 执行预测时默认不生成告警
  inference_stride_seconds: 1 // 每 1 秒生成一个预测点
}

// 查询运行记录列表
export function getRunRecords(params = {}) {
  // 查询参数
  return http.get('/v1/run-records', { params })
}

// 查询单条运行记录详情
export function getRunRecordDetail(runRecordId) {
  return http.get(`/v1/run-records/${runRecordId}`)
}

// 查询运行记录对应的监测数据
export function getRunRecordMonitor(runRecordId) {
  return http.get(`/v1/run-records/${runRecordId}/monitor`)
}

// 随机选择一条运行记录
export function getRandomRunRecord(params = {}) {
  return http.get('/v1/run-records/random', { params })
}


// 执行运行记录预测
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

// 生成运行记录告警
export function generateRunRecordAlert(runRecordId, payload = {}) {
  return http.post(`/v1/run-records/${runRecordId}/alert`, payload || {})
}
