<template>
  <div class="iptv-root">
    <!-- 顶栏 -->
    <header class="topbar">
      <div class="brand">
        <el-icon :size="24" color="#06b6d4"><Monitor /></el-icon>
        <span class="brand-text">IPTV 聚合器</span>
      </div>
      <div class="topbar-right">
        <el-tag :type="scheduleCfg.enabled ? 'success' : 'info'" size="small" class="sched-tag">
          <el-icon><Timer /></el-icon>
          {{ scheduleCfg.enabled ? `每天 ${String(scheduleCfg.hour).padStart(2,'0')}:${String(scheduleCfg.minute).padStart(2,'0')} 自动更新` : '定时未开启' }}
        </el-tag>
      </div>
    </header>

    <div class="main-layout">
      <!-- 左侧面板 -->
      <aside class="control-panel">
        <!-- IP 版本选择 -->
        <div class="panel-section">
          <h3><el-icon><Connection /></el-icon> IP 版本</h3>
          <el-radio-group v-model="ipVersion" size="small">
            <el-radio-button label="ipv4">IPv4</el-radio-button>
            <el-radio-button label="ipv6">IPv6</el-radio-button>
            <el-radio-button label="both">双栈</el-radio-button>
          </el-radio-group>
        </div>

        <!-- 搜索源 -->
        <div class="panel-section">
          <h3><el-icon><Search /></el-icon> 搜索源</h3>
          <el-select v-model="sourceType" size="small" style="width:100%;margin-bottom:8px">
            <el-option label="全部（组播+酒店）" value="all" />
            <el-option label="仅组播源" value="multicast" />
            <el-option label="仅酒店源" value="hotel" />
          </el-select>
          <el-input v-model="customUrls" type="textarea" :rows="3"
            placeholder="自定义 URL（可选）" size="small" />
        </div>

        <!-- 测速设置 -->
        <div class="panel-section">
          <h3><el-icon><Odometer /></el-icon> 测速设置</h3>
          <label>并发数</label>
          <el-slider v-model="concurrency" :min="5" :max="50" show-input size="small" />
          <label style="margin-top:6px">超时 {{ timeout }}s / 每频道保留 {{ maxKeep }} 条</label>
          <el-slider v-model="timeout" :min="2" :max="15" show-input size="small" />
          <el-slider v-model="maxKeep" :min="1" :max="20" show-input size="small" />
        </div>

        <!-- 执行按钮 -->
        <div class="panel-section">
          <el-button type="primary" class="full-btn" :loading="running" @click="runPipeline" size="default">
            <el-icon><VideoPlay /></el-icon> 搜索 → 测速 → 择优
          </el-button>
          <el-button type="success" class="full-btn" :disabled="!entries.length"
            @click="dlM3U" size="small" style="margin-top:6px">
            <el-icon><Download /></el-icon> 导出 M3U ({{ entries.length }})
          </el-button>
          <el-button type="success" class="full-btn" :disabled="!entries.length"
            @click="dlTXT" size="small" style="margin-top:4px">
            <el-icon><Download /></el-icon> 导出 TXT ({{ entries.length }})
          </el-button>
        </div>

        <!-- 进度 -->
        <div class="panel-section" v-if="running">
          <el-progress :percentage="progress.pct" :stroke-width="10" striped striped-flow />
          <div class="progress-text">{{ progress.text }}</div>
        </div>

        <!-- 频道表 -->
        <div class="panel-section">
          <h3><el-icon><List /></el-icon> 频道表 ({{ channels.length }})</h3>
          <el-button size="small" class="full-btn" @click="showChannelEditor = true">
            <el-icon><Edit /></el-icon> 编辑频道表
          </el-button>
          <el-button size="small" class="full-btn" @click="showScheduleDlg = true" style="margin-top:4px">
            <el-icon><Timer /></el-icon> 定时设置
          </el-button>
        </div>

        <!-- 统计 -->
        <div class="panel-section" v-if="stats.total">
          <h3><el-icon><DataAnalysis /></el-icon> 结果统计</h3>
          <div class="mini-stats">
            <span>总计 {{ stats.total }}</span>
            <span v-for="(n,g) in stats.groups" :key="g" class="mg">{{ g }}:{{ n }}</span>
          </div>
          <div class="mini-stats" style="margin-top:4px">
            <span v-for="(n,p) in stats.protocols" :key="p" class="mg">{{ p }}:{{ n }}</span>
          </div>
        </div>
      </aside>

      <!-- 右侧结果 -->
      <main class="result-panel">
        <!-- 结果表格 -->
        <el-table :data="entries" stripe size="small" height="calc(100vh - 100px)"
          empty-text="暂无数据。设置频道表后点击「搜索→测速→择优」">
          <el-table-column type="index" width="50" fixed />
          <el-table-column prop="group" label="分组" width="80" fixed />
          <el-table-column prop="name" label="频道名" min-width="140" fixed />
          <el-table-column label="播放地址" min-width="300">
            <template #default="{ row }">
              <span :style="{color: row.valid ? '#22c55e' : '#ef4444'}" class="url-text">
                {{ row.url.length > 55 ? row.url.substring(0,55) + '...' : row.url }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="protocol" label="协议" width="60">
            <template #default="{ row }">
              <el-tag size="small" :type="row.protocol === 'ipv6' ? 'warning' : 'info'">
                {{ row.protocol }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="response_time" label="响应" width="70">
            <template #default="{ row }">
              <span :style="{color: row.response_time < 500 ? '#22c55e' : row.response_time < 2000 ? '#f59e0b' : '#ef4444'}">
                {{ row.response_time }}ms
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="source_name" label="来源" width="100" show-overflow-tooltip />
        </el-table>
      </main>
    </div>

    <!-- 频道表编辑对话框 -->
    <el-dialog v-model="showChannelEditor" title="频道表管理" width="600px" destroy-on-close>
      <div class="channel-editor">
        <div class="ch-toolbar">
          <el-button size="small" type="primary" @click="addChannel">
            <el-icon><Plus /></el-icon> 添加
          </el-button>
          <el-button size="small" @click="importChannels">
            <el-icon><Upload /></el-icon> 批量导入
          </el-button>
          <el-button size="small" @click="resetChannels">
            <el-icon><RefreshLeft /></el-icon> 重置默认
          </el-button>
          <el-input v-model="chFilter" placeholder="筛选" size="small" style="width:120px;margin-left:auto" />
        </div>
        <el-table :data="filteredChannels" stripe size="small" height="400" class="ch-table">
          <el-table-column label="#" type="index" width="40" />
          <el-table-column label="频道名" min-width="120">
            <template #default="{ row, $index }">
              <el-input v-model="row.name" size="small" @change="saveChannelRow($index)" />
            </template>
          </el-table-column>
          <el-table-column label="分组" width="90">
            <template #default="{ row, $index }">
              <el-input v-model="row.group" size="small" @change="saveChannelRow($index)" />
            </template>
          </el-table-column>
          <el-table-column label="启用" width="50">
            <template #default="{ row, $index }">
              <el-switch v-model="row.enabled" size="small" @change="saveChannelRow($index)" />
            </template>
          </el-table-column>
          <el-table-column label="保留" width="60">
            <template #default="{ row, $index }">
              <el-input-number v-model="row.max_results" :min="1" :max="50" size="small"
                @change="saveChannelRow($index)" />
            </template>
          </el-table-column>
          <el-table-column width="40">
            <template #default="{ $index }">
              <el-button size="small" text type="danger" @click="delChannel($index)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <template #footer>
        <el-button @click="showChannelEditor = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 定时设置对话框 -->
    <el-dialog v-model="showScheduleDlg" title="定时更新设置" width="420px">
      <el-form :model="scheduleCfg" label-width="80px" size="small">
        <el-form-item label="启用">
          <el-switch v-model="scheduleCfg.enabled" />
        </el-form-item>
        <el-form-item label="时间">
          <el-input-number v-model="scheduleCfg.hour" :min="0" :max="23" /> :
          <el-input-number v-model="scheduleCfg.minute" :min="0" :max="59" />
        </el-form-item>
        <el-form-item label="IP 版本">
          <el-radio-group v-model="scheduleCfg.ip_version">
            <el-radio label="ipv4">IPv4</el-radio>
            <el-radio label="ipv6">IPv6</el-radio>
            <el-radio label="both">双栈</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="源类型">
          <el-select v-model="scheduleCfg.source_type" style="width:160px">
            <el-option label="全部" value="all" />
            <el-option label="组播" value="multicast" />
            <el-option label="酒店" value="hotel" />
          </el-select>
        </el-form-item>
        <el-form-item label="并发/超时">
          <el-input-number v-model="scheduleCfg.concurrency" :min="5" :max="50" /> /
          <el-input-number v-model="scheduleCfg.timeout" :min="2" :max="15" />s
        </el-form-item>
        <el-form-item label="每频道保留">
          <el-input-number v-model="scheduleCfg.max_keep" :min="1" :max="50" /> 条
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showScheduleDlg = false">取消</el-button>
        <el-button type="primary" @click="saveSchedule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/api/request'

// ============ 状态 ============
const ipVersion = ref('ipv4')
const sourceType = ref('all')
const customUrls = ref('')
const concurrency = ref(20)
const timeout = ref(5)
const maxKeep = ref(10)
const running = ref(false)
const progress = reactive({ pct: 0, text: '' })
const entries = ref([])
const channels = ref([])
const stats = reactive({ total: 0, groups: {}, protocols: {} })
const scheduleCfg = reactive({
  enabled: false, hour: 3, minute: 0,
  source_type: 'all', ip_version: 'ipv4',
  concurrency: 20, timeout: 5, max_keep: 10,
})

// 对话框
const showChannelEditor = ref(false)
const showScheduleDlg = ref(false)
const chFilter = ref('')
const filteredChannels = computed(() => {
  if (!chFilter.value) return channels.value
  const f = chFilter.value.toLowerCase()
  return channels.value.filter(ch => ch.name.toLowerCase().includes(f) || ch.group.toLowerCase().includes(f))
})

// ============ API ============
async function api(path, method = 'get', data = null) {
  try {
    const r = method === 'post' ? await request.post(path, data) : await request.get(path)
    return r && r.code === 0 ? (r.data || {}) : null
  } catch (e) { return null }
}

// ============ 加载数据 ============
async function loadChannels() {
  const data = await api('/channels', 'get')
  if (data) channels.value = data || []
}
async function loadStats() {
  const data = await api('/stats', 'get')
  if (data) {
    stats.total = data.total || 0
    stats.groups = data.groups || {}
    stats.protocols = data.protocols || {}
  }
}
async function loadSchedule() {
  const data = await api('/schedule', 'get')
  if (data) Object.assign(scheduleCfg, data)
}

onMounted(async () => {
  await loadChannels()
  await loadStats()
  await loadSchedule()
})

// ============ 执行流程 ============
async function runPipeline() {
  if (!channels.value.filter(ch => ch.enabled).length) {
    ElMessage.warning('频道表为空，请先添加频道')
    return
  }
  running.value = true
  progress.pct = 10
  progress.text = '正在搜索 IPTV 源...'
  try {
    const res = await request.post('/run', {
      source_type: sourceType.value,
      ip_version: ipVersion.value,
      concurrency: concurrency.value,
      timeout: timeout.value,
      max_keep: maxKeep.value,
      search_timeout: 15,
    })
    if (res && res.code === 0 && res.data) {
      entries.value = res.data.entries || []
      if (res.data.stats) {
        stats.total = res.data.stats.total_kept || 0
      }
      await loadStats()
      ElMessage.success(`完成！搜索 ${res.data.stats.total_searched} 条 → 匹配 ${res.data.stats.total_matched} → 有效 ${res.data.stats.total_tested} → 保留 ${res.data.stats.total_kept} 条`)
    } else {
      ElMessage.error(res?.message || '执行失败')
    }
  } catch (e) {
    ElMessage.error('网络错误: ' + (e.message || ''))
  } finally {
    running.value = false
  }
}

// ============ 导出 ============
function dlM3U() { window.open('/api/export/m3u', '_blank') }
function dlTXT() { window.open('/api/export/txt', '_blank') }

// ============ 频道表管理 ============
async function addChannel() {
  channels.value.push({ id: '', name: '新频道', group: '未分组', enabled: true, max_results: 10 })
}
async function delChannel(idx) {
  const realIdx = channels.value.indexOf(filteredChannels.value[idx])
  if (realIdx >= 0) {
    const ch = channels.value[realIdx]
    if (ch.id) {
      await api(`/channels/${ch.id}`, 'delete')
    }
    channels.value.splice(realIdx, 1)
  }
}
async function saveChannelRow(idx) {
  const ch = filteredChannels.value[idx]
  if (!ch) return
  if (ch.id) {
    await api(`/channels/${ch.id}`, 'put', { name: ch.name, group: ch.group, enabled: ch.enabled, max_results: ch.max_results })
  } else {
    const res = await api('/channels', 'post', { name: ch.name, group: ch.group, enabled: ch.enabled, max_results: ch.max_results })
    if (res && res.id) ch.id = res.id
  }
}
async function importChannels() {
  const input = prompt('批量导入频道（每行: 频道名,分组）:\n例:\nCCTV-1,央视\n湖南卫视,卫视')
  if (!input) return
  const lines = input.trim().split('\n').filter(l => l.trim())
  const items = lines.map(l => {
    const p = l.split(',')
    return { name: p[0].trim(), group: p[1]?.trim() || '未分组', enabled: true, max_results: 10 }
  })
  const res = await api('/channels/import', 'post', items)
  if (res) ElMessage.success(res.message || '导入成功')
  await loadChannels()
}
async function resetChannels() {
  if (!confirm('重置为默认频道表？')) return
  await api('/channels/reset', 'post')
  await loadChannels()
  ElMessage.success('已重置')
}

// ============ 定时设置 ============
async function saveSchedule() {
  await api('/schedule', 'post', {
    enabled: scheduleCfg.enabled,
    hour: scheduleCfg.hour,
    minute: scheduleCfg.minute,
    source_type: scheduleCfg.source_type,
    ip_version: scheduleCfg.ip_version,
    concurrency: scheduleCfg.concurrency,
    timeout: scheduleCfg.timeout,
    max_keep: scheduleCfg.max_keep,
  })
  showScheduleDlg.value = false
  ElMessage.success('定时设置已保存')
}
</script>

<style>
* { box-sizing: border-box; }
body { margin: 0; background: #0a0e1a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }

.iptv-root { height: 100vh; display: flex; flex-direction: column; overflow: hidden; }

/* 顶栏 */
.topbar { height: 48px; background: #0f172a; border-bottom: 1px solid #1e293b; display: flex; align-items: center; padding: 0 16px; gap: 10px; flex-shrink: 0; }
.brand { display: flex; align-items: center; gap: 8px; }
.brand-text { font-size: 15px; font-weight: 700; background: linear-gradient(135deg, #06b6d4, #3b82f6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.topbar-right { margin-left: auto; }
.sched-tag { background: #1e293b !important; border-color: #334155 !important; }

/* 主布局 */
.main-layout { flex: 1; display: flex; overflow: hidden; }

/* 左侧面板 */
.control-panel { width: 230px; background: #0f172a; border-right: 1px solid #1e293b; padding: 10px; overflow-y: auto; flex-shrink: 0; }
.panel-section { margin-bottom: 14px; padding-bottom: 10px; border-bottom: 1px solid #1e293b; }
.panel-section h3 { font-size: 12px; color: #06b6d4; margin: 0 0 6px; display: flex; align-items: center; gap: 4px; }
.panel-section label { font-size: 11px; color: #94a3b8; display: block; margin-bottom: 2px; }
.full-btn { width: 100%; }

/* 进度 */
.progress-text { font-size: 11px; color: #94a3b8; margin-top: 4px; text-align: center; }

/* 统计 */
.mini-stats { display: flex; flex-wrap: wrap; gap: 4px; font-size: 11px; color: #94a3b8; }
.mini-stats .mg { background: #1e293b; padding: 1px 4px; border-radius: 3px; }

/* 右侧 */
.result-panel { flex: 1; padding: 8px 12px; overflow: hidden; }
.url-text { font-size: 11px; word-break: break-all; }

/* 表格 */
.el-table { background: transparent; }
.el-table th.el-table__cell { background: #1e293b !important; color: #94a3b8 !important; border-color: #1e293b !important; }
.el-table tr { background: #0f172a !important; }
.el-table--striped .el-table__body tr.el-table__row--striped td { background: #1e293b !important; }
.el-table td.el-table__cell { border-color: #1e293b !important; color: #e2e8f0 !important; }
.el-table { --el-table-border-color: #1e293b; --el-table-header-bg-color: #1e293b; --el-table-row-hover-bg-color: #334155; }

/* 频道编辑器 */
.channel-editor .ch-toolbar { display: flex; gap: 6px; margin-bottom: 8px; align-items: center; }
.channel-editor .ch-table { background: transparent; }
</style>
