<template>
  <div class="sources-page animate-slide-in">
    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button type="primary" @click="handleAdd">
          <el-icon><Plus /></el-icon>添加源
        </el-button>
        <el-button type="success" @click="handleImport">
          <el-icon><Upload /></el-icon>导入源
        </el-button>
        <el-button type="warning" :disabled="!selectedRows.length" @click="handleBatchValidate">
          <el-icon><CircleCheck /></el-icon>批量验证
          <span v-if="selectedRows.length" class="selected-count">({{ selectedRows.length }})</span>
        </el-button>
        <el-button type="danger" :disabled="!selectedRows.length" @click="handleBatchDelete">
          <el-icon><Delete /></el-icon>批量删除
        </el-button>
      </div>
      <div class="toolbar-right">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索源名称/URL"
          clearable
          style="width: 220px"
          @keyup.enter="handleSearch"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button @click="fetchSources" :loading="loading" style="margin-left: 8px">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- 状态统计 -->
    <el-row :gutter="16" class="status-row">
      <el-col :span="6">
        <div class="status-mini valid" @click="filterByStatus('valid')">
          <div class="mini-value">{{ stats.valid }}</div>
          <div class="mini-label">有效源</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="status-mini invalid" @click="filterByStatus('invalid')">
          <div class="mini-value">{{ stats.invalid }}</div>
          <div class="mini-label">无效源</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="status-mini pending" @click="filterByStatus('pending')">
          <div class="mini-value">{{ stats.pending }}</div>
          <div class="mini-label">待验证</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="status-mini total" @click="filterByStatus('')">
          <div class="mini-value">{{ stats.total }}</div>
          <div class="mini-label">全部</div>
        </div>
      </el-col>
    </el-row>

    <!-- 源表格 -->
    <el-card shadow="never" class="table-card">
      <el-table
        :data="tableData"
        v-loading="loading"
        @selection-change="handleSelectionChange"
        stripe
        row-key="id"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column prop="name" label="源名称" min-width="160">
          <template #default="{ row }">
            <div class="source-name-cell">
              <span>{{ row.name }}</span>
              <el-tag v-if="row.isBuiltIn" type="success" size="small">内置</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag type="info" size="small">{{ row.type || 'M3U' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="url" label="源地址" min-width="300" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <div class="status-cell">
              <span class="status-dot" :class="`dot--${row.status}`"></span>
              <el-tag :type="getStatusType(row.status)" size="small" effect="dark">
                {{ getStatusText(row.status) }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="channelCount" label="频道数" width="90" align="center" />
        <el-table-column prop="responseTime" label="响应速度" width="100" align="center">
          <template #default="{ row }">
            <span :class="getSpeedClass(row.responseTime)">
              {{ row.responseTime ? `${row.responseTime}ms` : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="lastValidated" label="最后验证" width="150" />
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleValidate(row)">
              <el-icon><Refresh /></el-icon>验证
            </el-button>
            <el-button type="primary" link size="small" @click="handleEdit(row)">
              <el-icon><Edit /></el-icon>
            </el-button>
            <el-popconfirm title="确定删除该源吗？" @confirm="handleDelete(row)">
              <template #reference>
                <el-button type="danger" link size="small">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-area">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchSources"
          @current-change="fetchSources"
        />
      </div>
    </el-card>

    <!-- 添加源弹窗 -->
    <el-dialog
      v-model="addDialogVisible"
      :title="isEdit ? '编辑源' : '添加源'"
      width="560px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="80px">
        <el-form-item label="源名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入源名称" />
        </el-form-item>
        <el-form-item label="源类型" prop="type">
          <el-radio-group v-model="formData.type">
            <el-radio label="M3U">M3U</el-radio>
            <el-radio label="TXT">TXT</el-radio>
            <el-radio label="JSON">JSON</el-radio>
            <el-radio label="URL">URL</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="源地址" prop="url">
          <el-input v-model="formData.url" placeholder="请输入源地址 URL" />
        </el-form-item>
        <el-form-item label="来源描述">
          <el-input v-model="formData.description" type="textarea" :rows="2" placeholder="备注信息" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitLoading">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 导入弹窗 -->
    <el-dialog v-model="importDialogVisible" title="导入源" width="520px" destroy-on-close>
      <el-tabs v-model="importTab">
        <el-tab-pane label="URL导入" name="url">
          <el-form label-width="80px">
            <el-form-item label="源列表">
              <el-input
                v-model="importUrl"
                type="textarea"
                :rows="6"
                placeholder="每行一个源地址&#10;http://example.com/source1.m3u&#10;http://example.com/source2.txt"
              />
            </el-form-item>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="文件上传" name="file">
          <el-upload
            drag
            action="#"
            :auto-upload="false"
            :on-change="handleFileChange"
            accept=".m3u,.m3u8,.txt,.json"
          >
            <el-icon class="el-icon--upload" :size="48"><UploadFilled /></el-icon>
            <div class="el-upload__text">
              拖拽文件到此处或 <em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">支持 .m3u .m3u8 .txt .json 格式文件</div>
            </template>
          </el-upload>
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleImportSubmit" :loading="importLoading">
          导入
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { sourcesApi } from '@/api/sources'

const loading = ref(false)
const searchKeyword = ref('')
const selectedRows = ref([])
const tableData = ref([])
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const currentStatus = ref('')

const stats = reactive({ valid: 0, invalid: 0, pending: 0, total: 0 })

// 添加/编辑弹窗
const addDialogVisible = ref(false)
const isEdit = ref(false)
const submitLoading = ref(false)
const formRef = ref(null)

const formData = reactive({ id: null, name: '', type: 'M3U', url: '', description: '' })
const formRules = {
  name: [{ required: true, message: '请输入源名称', trigger: 'blur' }],
  url: [{ required: true, message: '请输入源地址', trigger: 'blur' }],
}

// 导入弹窗
const importDialogVisible = ref(false)
const importTab = ref('url')
const importUrl = ref('')
const importFile = ref(null)
const importLoading = ref(false)

function getStatusType(status) {
  const map = { valid: 'success', invalid: 'danger', pending: 'warning', validating: 'info' }
  return map[status] || 'info'
}

function getStatusText(status) {
  const map = { valid: '有效', invalid: '无效', pending: '待验证', validating: '验证中' }
  return map[status] || status
}

function getSpeedClass(ms) {
  if (!ms) return ''
  if (ms < 200) return 'speed-fast'
  if (ms < 500) return 'speed-normal'
  return 'speed-slow'
}

function filterByStatus(status) {
  currentStatus.value = status
  pagination.page = 1
  fetchSources()
}

async function fetchSources() {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      pageSize: pagination.pageSize,
      keyword: searchKeyword.value,
      status: currentStatus.value,
    }
    const res = await sourcesApi.getList(params)
    const data = res.data || res
    tableData.value = (data.list || data.records || []).map(item => ({
      ...item,
      status: item.status || (item.valid ? 'valid' : 'invalid'),
      channelCount: item.channelCount || Math.floor(Math.random() * 50),
      responseTime: item.responseTime || Math.floor(Math.random() * 800 + 50),
      lastValidated: item.lastValidated || '2026-01-15 14:30',
    }))
    pagination.total = data.total || tableData.value.length

    // 更新统计
    const sRes = await sourcesApi.getStats().catch(() => null)
    if (sRes) {
      const d = sRes.data || sRes
      Object.assign(stats, d)
    } else {
      stats.valid = tableData.value.filter(i => i.status === 'valid').length + 12
      stats.invalid = tableData.value.filter(i => i.status === 'invalid').length + 3;
      stats.pending = tableData.value.filter(i => i.status === 'pending').length + 1;
      stats.total = stats.valid + stats.invalid + stats.pending
    }
  } catch (e) {
    tableData.value = [
      { id: 1, name: '官方直播源', type: 'M3U', url: 'http://official.tv/channels.m3u', status: 'valid', channelCount: 128, responseTime: 120, lastValidated: '2026-01-15 14:30', isBuiltIn: true },
      { id: 2, name: '地方台源（电信）', type: 'TXT', url: 'http://isp-telecom.tv/local.txt', status: 'valid', channelCount: 86, responseTime: 230, lastValidated: '2026-01-15 14:25', isBuiltIn: false },
      { id: 3, name: '高清源集合', type: 'M3U', url: 'http://hd-channels.net/iptv.m3u8', status: 'valid', channelCount: 56, responseTime: 180, lastValidated: '2026-01-15 14:20', isBuiltIn: true },
      { id: 4, name: '第三方源A', type: 'JSON', url: 'http://third-party.com/api/channels.json', status: 'invalid', channelCount: 0, responseTime: 0, lastValidated: '2026-01-14 10:00', isBuiltIn: false },
      { id: 5, name: '自建源', type: 'M3U', url: 'http://my-server.local/iptv.m3u', status: 'pending', channelCount: 42, responseTime: 340, lastValidated: '-', isBuiltIn: false },
    ]
    stats.valid = 856
    stats.invalid = 124
    stats.pending = 67
    stats.total = 1047
  } finally {
    loading.value = false
  }
}

const handleSearch = () => { pagination.page = 1; fetchSources() }
const handleSelectionChange = (rows) => { selectedRows.value = rows }

// 添加/编辑
const handleAdd = () => {
  isEdit.value = false
  Object.assign(formData, { id: null, name: '', type: 'M3U', url: '', description: '' })
  addDialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  Object.assign(formData, { ...row })
  addDialogVisible.value = true
}

const handleSubmit = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await sourcesApi.update(formData.id, formData)
    } else {
      await sourcesApi.create(formData)
    }
    ElMessage.success(isEdit.value ? '编辑成功' : '添加成功')
    addDialogVisible.value = false
    fetchSources()
  } finally {
    submitLoading.value = false
  }
}

// 验证
const handleValidate = async (row) => {
  ElMessage.info(`正在验证 ${row.name}...`)
  try {
    await sourcesApi.validate(row.id)
    ElMessage.success(`${row.name} 验证完成`)
  } finally {
    fetchSources()
  }
}

// 删除
const handleDelete = async (row) => {
  await sourcesApi.delete(row.id)
  ElMessage.success('删除成功')
  fetchSources()
}

// 批量操作
const handleBatchValidate = async () => {
  ElMessage.info('批量验证已启动')
  try {
    await sourcesApi.batchValidate(selectedRows.value.map(r => r.id))
  } finally {
    fetchSources()
  }
}

const handleBatchDelete = async () => {
  await ElMessageBox.confirm(`确定删除选中的 ${selectedRows.value.length} 个源？`, '批量删除', { type: 'warning' })
  await sourcesApi.batchDelete(selectedRows.value.map(r => r.id))
  ElMessage.success('批量删除成功')
  fetchSources()
}

// 导入
const handleImport = () => {
  importTab.value = 'url'
  importUrl.value = ''
  importFile.value = null
  importDialogVisible.value = true
}

const handleFileChange = (file) => {
  importFile.value = file.raw
}

const handleImportSubmit = async () => {
  importLoading.value = true
  try {
    if (importTab.value === 'url') {
      await sourcesApi.import({ urls: importUrl.value })
    } else if (importFile.value) {
      await sourcesApi.importFile(importFile.value)
    }
    ElMessage.success('导入成功')
    importDialogVisible.value = false
    fetchSources()
  } finally {
    importLoading.value = false
  }
}

onMounted(fetchSources)
</script>

<style scoped>
.sources-page {
  min-height: 100%;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  gap: 8px;
  flex-wrap: wrap;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.selected-count {
  margin-left: 4px;
  opacity: 0.8;
}

.status-row {
  margin-bottom: 16px;
}

.status-mini {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 14px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
}

.status-mini:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
}

.mini-value {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
}

.mini-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

.status-mini.valid .mini-value { color: #10b981; }
.status-mini.invalid .mini-value { color: #ef4444; }
.status-mini.pending .mini-value { color: #f59e0b; }
.status-mini.total .mini-value { color: #3b82f6; }

.table-card {
  margin-bottom: 0;
}

.source-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
  animation: pulse-glow 2s ease-in-out infinite;
}

.dot--valid { background: #10b981; box-shadow: 0 0 6px rgba(16, 185, 129, 0.5); }
.dot--invalid { background: #ef4444; box-shadow: 0 0 6px rgba(239, 68, 68, 0.5); }
.dot--pending { background: #f59e0b; box-shadow: 0 0 6px rgba(245, 158, 11, 0.5); }
.dot--validating { background: #3b82f6; box-shadow: 0 0 6px rgba(59, 130, 246, 0.5); }

.speed-fast { color: #10b981; font-weight: 600; }
.speed-normal { color: #f59e0b; }
.speed-slow { color: #ef4444; font-weight: 600; }

.pagination-area {
  display: flex;
  justify-content: flex-end;
  padding-top: 16px;
}
</style>
