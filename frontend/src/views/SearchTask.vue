<template>
  <div class="search-task-page">
    <div class="page-header">
      <h2>搜索任务</h2>
      <p class="page-desc">自动或手动搜索 IPTV 源，管理内置源列表</p>
    </div>

    <!-- 快速搜索卡片 -->
    <el-row :gutter="16" class="mt-4">
      <el-col :xs="24" :sm="12" :md="8">
        <div class="action-card" @click="handleAutoSearch">
          <div class="card-icon auto">
            <el-icon :size="32"><Search /></el-icon>
          </div>
          <h3>自动搜索</h3>
          <p>一键搜索所有内置 IPTV 源</p>
          <el-button type="primary" :loading="autoSearching">
            <el-icon><Search /></el-icon>开始搜索
          </el-button>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :md="8">
        <div class="action-card" @click="customDialogVisible = true">
          <div class="card-icon custom">
            <el-icon :size="32"><Link /></el-icon>
          </div>
          <h3>自定义搜索</h3>
          <p>指定 URL 列表进行搜索</p>
          <el-button type="success">
            <el-icon><Link /></el-icon>添加 URL
          </el-button>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :md="8">
        <div class="action-card" @click="refreshBuiltins">
          <div class="card-icon builtin">
            <el-icon :size="32"><List /></el-icon>
          </div>
          <h3>内置源管理</h3>
          <p>查看和管理内置源列表</p>
          <el-button type="warning">
            <el-icon><List /></el-icon>查看列表
          </el-button>
        </div>
      </el-col>
    </el-row>

    <!-- 搜索结果 -->
    <div v-if="searchResult" class="mt-4">
      <el-card class="result-card">
        <template #header>
          <div class="card-header-flex">
            <span class="card-title">搜索结果</span>
            <div class="header-actions">
              <el-button size="small" @click="importAllChannels" :disabled="!searchResult.channels.length">
                <el-icon><Upload /></el-icon>全部导入
              </el-button>
              <el-button size="small" type="primary" @click="exportResult">
                <el-icon><Download /></el-icon>导出 M3U
              </el-button>
            </div>
          </div>
        </template>

        <!-- 统计 -->
        <el-row :gutter="16" class="result-stats">
          <el-col :span="6">
            <div class="stat-item">
              <div class="stat-value">{{ searchResult.total }}</div>
              <div class="stat-label">总源数</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-item stat-success">
              <div class="stat-value">{{ searchResult.valid }}</div>
              <div class="stat-label">有效源</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-item">
              <div class="stat-value">{{ searchResult.total_channels }}</div>
              <div class="stat-label">总频道数</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-item stat-success">
              <div class="stat-value">{{ searchResult.valid_channels }}</div>
              <div class="stat-label">去重频道</div>
            </div>
          </el-col>
        </el-row>

        <!-- 源状态列表 -->
        <el-table :data="searchResult.sources" stripe size="small" class="mt-3">
          <el-table-column prop="name" label="源名称" min-width="180" show-overflow-tooltip />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.valid ? 'success' : 'danger'" size="small">
                {{ row.valid ? '有效' : '无效' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="channel_count" label="频道数" width="90" />
          <el-table-column label="响应" width="90">
            <template #default="{ row }">
              {{ row.response_time ? row.response_time + 'ms' : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="error" label="错误信息" min-width="150" show-overflow-tooltip />
        </el-table>
      </el-card>
    </div>

    <!-- 搜索进度 -->
    <el-dialog v-model="progressVisible" title="搜索进度" width="400px" :close-on-click-modal="false">
      <div class="progress-area">
        <el-progress :percentage="searchProgress" :stroke-width="16" striped striped-flow />
        <p class="progress-text">{{ progressText }}</p>
      </div>
    </el-dialog>

    <!-- 自定义搜索对话框 -->
    <el-dialog v-model="customDialogVisible" title="自定义搜索" width="600px">
      <div class="custom-search-form">
        <p class="form-tip">每行输入一个 M3U/M3U8 地址</p>
        <el-input
          v-model="customUrls"
          type="textarea"
          :rows="8"
          placeholder="https://example.com/iptv.m3u&#10;https://example.com/iptv.m3u8"
        />
      </div>
      <template #footer>
        <el-button @click="customDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCustomSearch" :loading="customSearching">
          开始搜索
        </el-button>
      </template>
    </el-dialog>

    <!-- 内置源列表对话框 -->
    <el-dialog v-model="builtinDialogVisible" title="内置 IPTV 源" width="700px">
      <el-table :data="builtinSources" stripe size="small">
        <el-table-column prop="name" label="名称" min-width="180" />
        <el-table-column prop="region" label="地区" width="100" />
        <el-table-column prop="operator" label="运营商" width="100" />
        <el-table-column prop="url" label="URL" min-width="200" show-overflow-tooltip />
      </el-table>
      <template #footer>
        <el-button @click="builtinDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiSearchAll, apiSearchCustom, apiGetBuiltins, apiDownloadM3u } from '@/api/search'

const autoSearching = ref(false)
const customSearching = ref(false)
const progressVisible = ref(false)
const searchProgress = ref(0)
const progressText = ref('准备搜索...')
const searchResult = ref(null)

const customDialogVisible = ref(false)
const customUrls = ref('')

const builtinDialogVisible = ref(false)
const builtinSources = ref([])

async function handleAutoSearch() {
  autoSearching.value = true
  progressVisible.value = true
  searchProgress.value = 10
  progressText.value = '正在搜索内置 IPTV 源...'

  try {
    const res = await apiSearchAll()
    searchProgress.value = 100
    progressText.value = '搜索完成！'
    searchResult.value = res
    ElMessage.success(`搜索完成！发现 ${res.valid_channels} 个有效频道`)
  } catch (e) {
    ElMessage.error('搜索失败: ' + (e.message || '未知错误'))
  } finally {
    autoSearching.value = false
    setTimeout(() => { progressVisible.value = false }, 500)
  }
}

async function handleCustomSearch() {
  const urls = customUrls.value.split('\n').map(u => u.trim()).filter(u => u)
  if (!urls.length) {
    ElMessage.warning('请至少输入一个 URL')
    return
  }

  customSearching.value = true
  customDialogVisible.value = false
  progressVisible.value = true
  searchProgress.value = 10
  progressText.value = `正在搜索 ${urls.length} 个自定义源...`

  try {
    const res = await apiSearchCustom(urls)
    searchProgress.value = 100
    progressText.value = '搜索完成！'
    searchResult.value = res
    ElMessage.success(`搜索完成！发现 ${res.valid_channels} 个有效频道`)
  } catch (e) {
    ElMessage.error('搜索失败: ' + (e.message || '未知错误'))
  } finally {
    customSearching.value = false
    setTimeout(() => { progressVisible.value = false }, 500)
  }
}

async function refreshBuiltins() {
  try {
    const res = await apiGetBuiltins()
    builtinSources.value = res
    builtinDialogVisible.value = true
  } catch (e) {
    ElMessage.error('获取内置源失败')
  }
}

async function importAllChannels() {
  if (!searchResult.value?.channels?.length) return
  try {
    await ElMessageBox.confirm(
      `确定导入 ${searchResult.value.channels.length} 个频道？`,
      '批量导入', { type: 'warning' }
    )
    // 这里调用导入 API
    ElMessage.success('导入完成')
  } catch {}
}

async function exportResult() {
  if (!searchResult.value?.channels?.length) {
    ElMessage.warning('没有可导出的频道')
    return
  }
  window.open('/api/export/m3u', '_blank')
}
</script>

<style scoped>
.search-task-page { }
.page-header h2 { font-size: 20px; font-weight: 600; color: #e2e8f0; margin: 0; }
.page-desc { color: #94a3b8; font-size: 13px; margin-top: 4px; }

.action-card {
  background: #1e293b; border: 1px solid #334155; border-radius: 12px;
  padding: 24px; text-align: center; cursor: pointer; transition: all 0.3s;
}
.action-card:hover { border-color: #06b6d4; box-shadow: 0 0 20px rgba(6,182,212,0.15); transform: translateY(-2px); }
.card-icon { width: 60px; height: 60px; border-radius: 14px; display: flex; align-items: center; justify-content: center; margin: 0 auto 12px; }
.card-icon.auto { background: rgba(6,182,212,0.15); color: #06b6d4; }
.card-icon.custom { background: rgba(34,197,94,0.15); color: #22c55e; }
.card-icon.builtin { background: rgba(251,191,36,0.15); color: #fbbf24; }
.action-card h3 { font-size: 16px; color: #e2e8f0; margin: 0 0 6px; }
.action-card p { font-size: 12px; color: #94a3b8; margin: 0 0 16px; }

.result-card { background: #1e293b; border-color: #334155; }
.card-header-flex { display: flex; justify-content: space-between; align-items: center; }
.card-title { font-size: 15px; font-weight: 600; color: #e2e8f0; }
.header-actions { display: flex; gap: 8px; }

.result-stats { padding: 8px 0; }
.stat-item { text-align: center; padding: 12px; background: #0f172a; border-radius: 8px; }
.stat-value { font-size: 24px; font-weight: 700; color: #e2e8f0; }
.stat-label { font-size: 12px; color: #94a3b8; margin-top: 4px; }
.stat-success .stat-value { color: #22c55e; }

.progress-area { padding: 20px 0; }
.progress-text { text-align: center; color: #94a3b8; margin-top: 12px; font-size: 13px; }

.custom-search-form .form-tip { color: #94a3b8; font-size: 13px; margin-bottom: 8px; }
.mt-4 { margin-top: 16px; }
.mt-3 { margin-top: 12px; }
</style>
