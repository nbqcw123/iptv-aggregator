<template>
  <div class="iptv-root">
    <!-- 顶栏 -->
    <header class="topbar">
      <div class="brand">
        <el-icon :size="24" color="#06b6d4"><Monitor /></el-icon>
        <span class="brand-text">IPTV 聚合器</span>
      </div>
    </header>

    <div class="main-layout">
      <!-- 左侧面板 -->
      <aside class="control-panel">
        <!-- 搜索 -->
        <div class="panel-section">
          <h3><el-icon><Search /></el-icon> 1. 搜索源</h3>
          <label>源类型</label>
          <el-select v-model="searchForm.source_type" size="small" style="width:100%;margin-bottom:8px">
            <el-option label="全部（组播+酒店）" value="all" />
            <el-option label="组播源" value="multicast" />
            <el-option label="酒店源" value="hotel" />
          </el-select>
          <label>自定义 URL（可选，每行一个）</label>
          <el-input v-model="customUrlsInput" type="textarea" :rows="3"
            placeholder="留空则使用内置源" size="small" style="margin-bottom:8px" />
          <el-button type="primary" class="full-btn" :loading="searching" @click="doSearch" size="small">
            <el-icon><Search /></el-icon> 搜索
          </el-button>
        </div>

        <!-- 验证 -->
        <div class="panel-section">
          <h3><el-icon><CircleCheck /></el-icon> 2. 验证可用性</h3>
          <div style="display:flex;gap:8px;margin-bottom:8px">
            <div style="flex:1">
              <label>并发</label>
              <el-input-number v-model="validateForm.concurrency" :min="5" :max="50" size="small" style="width:100%" />
            </div>
            <div style="flex:1">
              <label>超时(秒)</label>
              <el-input-number v-model="validateForm.timeout" :min="2" :max="15" size="small" style="width:100%" />
            </div>
          </div>
          <el-button type="warning" class="full-btn" :loading="validating"
            :disabled="!searchResult.length" @click="doValidate" size="small">
            <el-icon><CircleCheck /></el-icon> 验证全部 ({{ searchResult.length }})
          </el-button>
        </div>

        <!-- 导出 -->
        <div class="panel-section">
          <h3><el-icon><Download /></el-icon> 3. 导出文件</h3>
          <el-button type="success" class="full-btn" :disabled="!validResult.length"
            @click="downloadExport('m3u')" size="small" style="margin-bottom:6px">
            <el-icon><Download /></el-icon> 导出 M3U ({{ validResult.length }})
          </el-button>
          <el-button type="success" class="full-btn" :disabled="!validResult.length"
            @click="downloadExport('txt')" size="small" style="margin-bottom:6px">
            <el-icon><Download /></el-icon> 导出 TXT ({{ validResult.length }})
          </el-button>
          <el-divider style="margin:8px 0" />
          <el-button class="full-btn" @click="downloadFull('m3u')" size="small" style="margin-bottom:4px">
            <el-icon><Promotion /></el-icon> 一键搜索→验证→M3U
          </el-button>
          <el-button class="full-btn" @click="downloadFull('txt')" size="small">
            <el-icon><Promotion /></el-icon> 一键搜索→验证→TXT
          </el-button>
        </div>

        <!-- 内置源 -->
        <div class="panel-section">
          <el-button @click="showBuiltinSources" class="full-btn" size="small">
            <el-icon><Link /></el-icon> 查看内置源 ({{ builtinCount }})
          </el-button>
        </div>
      </aside>

      <!-- 右侧结果 -->
      <main class="result-panel">
        <!-- 统计 -->
        <div class="stats-row">
          <div class="stat-card">
            <div class="stat-num">{{ stats.searched }}</div>
            <div class="stat-label">搜索到地址</div>
          </div>
          <div class="stat-card stat-ok">
            <div class="stat-num">{{ stats.valid }}</div>
            <div class="stat-label">验证有效</div>
          </div>
          <div class="stat-card stat-fail">
            <div class="stat-num">{{ stats.invalid }}</div>
            <div class="stat-label">已剔除</div>
          </div>
          <div class="stat-card" v-if="stats.searched > 0">
            <div class="stat-num">{{ validRate }}%</div>
            <div class="stat-label">有效率</div>
          </div>
        </div>

        <!-- 进度 -->
        <div v-if="searching || validating" class="progress-area">
          <el-progress :percentage="progress_pct" :stroke-width="12" striped striped-flow />
          <div class="progress-text">{{ progress_text }}</div>
        </div>

        <!-- 结果表格 -->
        <el-tabs v-model="activeTab" class="result-tabs">
          <el-tab-pane :label="`全部 (${searchResult.length})`" name="all">
            <el-table :data="pagedAll" stripe size="small" height="calc(100vh - 320px)"
              empty-text="暂无数据，请先搜索">
              <el-table-column label="#" type="index" width="50" />
              <el-table-column prop="name" label="频道名" min-width="150" show-overflow-tooltip />
              <el-table-column prop="group" label="分组" width="90" />
              <el-table-column prop="source_type" label="类型" width="70">
                <template #default="{ row }">
                  <el-tag size="small" :type="row.source_type === 'hotel' ? 'warning' : 'info'">
                    {{ row.source_type === 'hotel' ? '酒店' : '组播' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="source_name" label="来源" width="120" show-overflow-tooltip />
              <el-table-column label="播放地址" min-width="250">
                <template #default="{ row }">
                  <span style="font-size:12px;word-break:break-all">{{ row.url.length > 45 ? row.url.substring(0, 45) + '...' : row.url }}</span>
                </template>
              </el-table-column>
              <el-table-column label="可用" width="70">
                <template #default="{ row }">
                  <span v-if="row.validated === undefined" style="color:#94a3b8">—</span>
                  <el-tag v-else-if="row.validated" type="success" size="small">✓</el-tag>
                  <el-tag v-else type="danger" size="small">✗</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="60" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" text @click="testSingle(row)">测</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-pagination v-model:current-page="pageAll" :page-size="page_size" :total="searchResult.length"
              layout="prev, pager, next, jumper, total" small style="margin-top:8px;justify-content:flex-end" />
          </el-tab-pane>

          <el-tab-pane :label="`已验证有效 (${validResult.length})`" name="valid">
            <el-table :data="pagedValid" stripe size="small" height="calc(100vh - 320px)" empty-text="暂无">
              <el-table-column label="#" type="index" width="50" />
              <el-table-column prop="name" label="频道名" min-width="150" />
              <el-table-column prop="group" label="分组" width="90" />
              <el-table-column prop="source_type" label="类型" width="70">
                <template #default="{ row }">
                  <el-tag size="small" :type="row.source_type === 'hotel' ? 'warning' : 'info'">
                    {{ row.source_type === 'hotel' ? '酒店' : '组播' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="播放地址" min-width="300">
                <template #default="{ row }">
                  <span style="font-size:12px;word-break:break-all;color:#22c55e">{{ row.url.length > 50 ? row.url.substring(0, 50) + '...' : row.url }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="response_time" label="响应" width="60" />
            </el-table>
            <el-pagination v-model:current-page="pageValid" :page-size="page_size" :total="validResult.length"
              layout="prev, pager, next, jumper, total" small style="margin-top:8px;justify-content:flex-end" />
          </el-tab-pane>

          <el-tab-pane :label="`已剔除 (${invalidResult.length})`" name="invalid">
            <el-table :data="pagedInvalid" stripe size="small" height="calc(100vh - 320px)" empty-text="暂无">
              <el-table-column label="#" type="index" width="50" />
              <el-table-column prop="name" label="频道名" min-width="150" />
              <el-table-column prop="group" label="分组" width="90" />
              <el-table-column label="播放地址" min-width="300">
                <template #default="{ row }">
                  <span style="font-size:12px;color:#64748b">{{ row.url.length > 50 ? row.url.substring(0, 50) + '...' : row.url }}</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="60">
                <template #default="{ row }">
                  <el-button size="small" text @click="testSingle(row)">重测</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-pagination v-model:current-page="pageInvalid" :page-size="page_size" :total="invalidResult.length"
              layout="prev, pager, next, jumper, total" small style="margin-top:8px;justify-content:flex-end" />
          </el-tab-pane>
        </el-tabs>
      </main>
    </div>

    <!-- 内置源对话框 -->
    <el-dialog v-model="builtinVisible" title="内置搜索源" width="750px">
      <el-tabs>
        <el-tab-pane label="组播源">
          <el-table :data="builtinSources.multicast" stripe size="small" max-height="400">
            <el-table-column prop="name" label="名称" min-width="150" />
            <el-table-column label="类型" width="80">
              <template #default><el-tag size="small" type="info">组播</el-tag></template>
            </el-table-column>
            <el-table-column prop="url" label="URL" min-width="350" show-overflow-tooltip />
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="酒店源">
          <el-table :data="builtinSources.hotel" stripe size="small" max-height="400">
            <el-table-column prop="name" label="名称" min-width="150" />
            <el-table-column label="类型" width="80">
              <template #default><el-tag size="small" type="warning">酒店</el-tag></template>
            </el-table-column>
            <el-table-column prop="url" label="URL" min-width="350" show-overflow-tooltip />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

    <!-- 单地址测试对话框 -->
    <el-dialog v-model="singleTestVisible" title="测试播放地址" width="450px">
      <div v-if="singleTestResult">
        <p><strong>地址：</strong>{{ singleTestResult.url }}</p>
        <p><strong>状态：</strong>
          <el-tag :type="singleTestResult.valid ? 'success' : 'danger'">
            {{ singleTestResult.valid ? '✓ 可用' : '✗ 不可用' }}
          </el-tag>
        </p>
        <p><strong>HTTP 状态码：</strong>{{ singleTestResult.status_code || 'N/A' }}</p>
        <p><strong>响应时间：</strong>{{ singleTestResult.response_time }}ms</p>
        <p v-if="singleTestResult.error"><strong>错误：</strong>{{ singleTestResult.error }}</p>
      </div>
      <div v-else style="text-align:center;padding:20px;color:#94a3b8">
        <el-icon :size="32" class="is-loading"><Loading /></el-icon>
        <p>测试中...</p>
      </div>
      <template #footer>
        <el-button @click="singleTestVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { apiSearch, apiValidate, apiValidateSingle, apiExportM3u, apiExportTxt, apiExportFull } from '@/api/search'
import { apiGetBuiltins } from '@/api/search'

const page_size = 50
const pageAll = ref(1)
const pageValid = ref(1)
const pageInvalid = ref(1)
const activeTab = ref('all')

const searchForm = reactive({ source_type: 'all', concurrency: 5, timeout: 15 })
const validateForm = reactive({ concurrency: 20, timeout: 5 })
const customUrlsInput = ref('')

const searching = ref(false)
const validating = ref(false)
const progress_pct = ref(0)
const progress_text = ref('')
const searchResult = ref([])
const validResult = ref([])
const singleTestVisible = ref(false)
const singleTestResult = ref(null)
const builtinVisible = ref(false)
const builtinSources = ref({ multicast: [], hotel: [] })
const builtinCount = computed(() => (builtinSources.value.multicast?.length || 0) + (builtinSources.value.hotel?.length || 0))

const stats = reactive({ searched: 0, valid: 0, invalid: 0 })

const validRate = computed(() => {
  if (!stats.searched) return 0
  return Math.round((stats.valid / stats.searched) * 100)
})

const invalidResult = computed(() => searchResult.value.filter(r => r.validated === false))
const pagedAll = computed(() => {
  const s = (pageAll.value - 1) * page_size
  return searchResult.value.slice(s, s + page_size)
})
const pagedValid = computed(() => {
  const s = (pageValid.value - 1) * page_size
  return validResult.value.slice(s, s + page_size)
})
const pagedInvalid = computed(() => {
  const s = (pageInvalid.value - 1) * page_size
  return invalidResult.value.slice(s, s + page_size)
})

// ============ 搜索 ============
async function doSearch() {
  searching.value = true
  progress_pct.value = 10
  progress_text.value = '正在从网上搜索 IPTV 源...'
  try {
    const urls = customUrlsInput.value.split('\n').map(u => u.trim()).filter(u => u)
    const res = await apiSearch({
      source_type: searchForm.source_type,
      custom_urls: urls,
      timeout: searchForm.timeout,
      concurrency: searchForm.concurrency,
    })
    if (res.code === 0 && res.data) {
      searchResult.value = (res.data.entries || []).map(e => ({ ...e, validated: undefined }))
      stats.searched = res.data.total || searchResult.value.length
      stats.valid = 0
      stats.invalid = 0
      validResult.value = []
      activeTab.value = 'all'
      ElMessage.success(`搜索完成！发现 ${stats.searched} 个地址（去重后）`)
    }
  } catch (e) {
    ElMessage.error('搜索失败: ' + (e.message || '网络错误'))
  } finally {
    searching.value = false
  }
}

// ============ 验证 ============
async function doValidate() {
  if (!searchResult.value.length) return
  validating.value = true
  progress_pct.value = 5
  progress_text.value = `正在验证 ${searchResult.value.length} 个地址可用性...`

  try {
    const res = await apiValidate({
      concurrency: validateForm.concurrency,
      timeout: validateForm.timeout,
    })
    if (res.code === 0 && res.data) {
      // 标记有效
      const validSet = new Set()
      for (const e of (res.data.entries || [])) {
        validSet.add(e.url)
      }
      for (const e of searchResult.value) {
        if (validSet.has(e.url)) {
          e.validated = true
        } else {
          e.validated = false
        }
      }
      validResult.value = searchResult.value.filter(e => e.validated)
      stats.valid = validResult.value.length
      stats.invalid = searchResult.value.length - stats.valid
      activeTab.value = 'valid'
      ElMessage.success(`验证完成！${stats.valid}/${stats.searched} 个有效，剔除 ${stats.invalid} 个`)
    }
  } catch (e) {
    ElMessage.error('验证失败: ' + (e.message || '网络错误'))
  } finally {
    validating.value = false
  }
}

// ============ 单地址测试 ============
async function testSingle(row) {
  singleTestVisible.value = true
  singleTestResult.value = null
  try {
    const res = await apiValidateSingle(row.url)
    if (res.code === 0) {
      singleTestResult.value = res.data
      row.validated = res.data.valid
      row.response_time = res.data.response_time
    }
  } catch (e) {
    ElMessage.error('测试失败')
  }
}

// ============ 导出 ============
function downloadExport(format) {
  window.open(`/api/export/${format}`, '_blank')
}

function downloadFull(format) {
  const url = `/api/export/${format}/full?source_type=${searchForm.source_type}&timeout=${validateForm.timeout}&concurrency=${validateForm.concurrency}`
  window.open(url, '_blank')
  ElMessage.info('一键流程已开始：搜索→验证→导出，文件准备好后自动下载')
}

// ============ 内置源列表 ============
async function showBuiltinSources() {
  try {
    const res = await apiGetBuiltins()
    if (res.code === 0 && res.data) {
      builtinSources.value = res.data
      builtinVisible.value = true
    }
  } catch (e) {
    ElMessage.error('获取内置源列表失败')
  }
}
</script>

<style>
/* ============ 全局深色科技风 ============ */
* { box-sizing: border-box; }
body { margin: 0; background: #0a0e1a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
::-webkit-scrollbar-track { background: transparent; }

.iptv-root { height: 100vh; display: flex; flex-direction: column; overflow: hidden; }

/* 顶栏 */
.topbar { height: 48px; background: #0f172a; border-bottom: 1px solid #1e293b; display: flex; align-items: center; padding: 0 16px; gap: 10px; flex-shrink: 0; }
.brand { display: flex; align-items: center; gap: 8px; }
.brand-text { font-size: 15px; font-weight: 700; background: linear-gradient(135deg, #06b6d4, #3b82f6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }

/* 主布局 */
.main-layout { flex: 1; display: flex; overflow: hidden; }

/* 左侧面板 */
.control-panel { width: 240px; background: #0f172a; border-right: 1px solid #1e293b; padding: 12px; overflow-y: auto; flex-shrink: 0; }
.panel-section { margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #1e293b; }
.panel-section h3 { font-size: 13px; color: #06b6d4; margin: 0 0 8px; display: flex; align-items: center; gap: 4px; }
.panel-section label { font-size: 11px; color: #94a3b8; display: block; margin-bottom: 3px; }
.full-btn { width: 100%; }
.el-divider { border-color: #1e293b !important; }

/* 右侧面板 */
.result-panel { flex: 1; padding: 12px 16px; overflow: hidden; display: flex; flex-direction: column; }

/* 统计 */
.stats-row { display: flex; gap: 12px; margin-bottom: 12px; flex-shrink: 0; }
.stat-card { flex: 1; background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px; text-align: center; }
.stat-num { font-size: 22px; font-weight: 700; color: #e2e8f0; }
.stat-label { font-size: 11px; color: #94a3b8; margin-top: 2px; }
.stat-ok .stat-num { color: #22c55e; }
.stat-fail .stat-num { color: #ef4444; }

/* 进度 */
.progress-area { margin-bottom: 12px; flex-shrink: 0; }
.progress-text { font-size: 12px; color: #94a3b8; margin-top: 6px; text-align: center; }

/* 表格 */
.result-tabs { flex: 1; overflow: hidden; display: flex; flex-direction: column; }
.result-tabs :deep(.el-tabs__content) { flex: 1; overflow: hidden; }
.result-tabs :deep(.el-tab-pane) { height: 100%; }
.el-table { background: transparent; }
.el-table th.el-table__cell { background: #1e293b !important; color: #94a3b8 ! important; }
.el-table tr { background: #0f172a !important; }
.el-table--striped .el-table__body tr.el-table__row--striped td { background: #1e293b !important; }
.el-table td.el-table__cell { border-color: #1e293b !important; color: #e2e8f0 !important; }
.el-table th.el-table__cell { border-color: #1e293b !important; }
.el-table--border .el-table__cell { border-color: #1e293b !important; }
.el-table { --el-table-border-color: #1e293b; --el-table-header-bg-color: #1e293b; --el-table-row-hover-bg-color: #334155; }

/* 标签页 */
.result-tabs :deep(.el-tabs__item) { color: #94a3b8; }
.result-tabs :deep(.el-tabs__item.is-active) { color: #06b6d4; }
.result-tabs :deep(.el-tabs__active-bar) { background: #06b6d4; }
.result-tabs :deep(.el-tabs__nav-wrap::after) { background: #1e293b; }

/* 分页 */
.el-pagination { --el-pagination-bg-color: transparent; --el-pagination-text-color: #94a3b8; --el-pagination-button-bg-color: #1e293b; }

/* 对话框 */
.el-dialog { --el-dialog-bg-color: #1e293b; }
.el-dialog__title { color: #e2e8f0 !important; }
.el-dialog__body { color: #94a3b8 !important; }
</style>
