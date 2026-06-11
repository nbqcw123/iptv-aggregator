<template>
  <div class="iptv-root">
    <!-- 顶栏 -->
    <header class="topbar">
      <div class="brand">
        <el-icon :size="24" color="#06b6d4"><Monitor /></el-icon>
        <span class="brand-text">IPTV 聚合器</span>
      </div>
      <div class="topbar-tabs">
        <div class="tab" :class="{active: activeTab==='search'}" @click="activeTab='search'">
          <el-icon><Search /></el-icon> 搜索测速
        </div>
        <div class="tab" :class="{active: activeTab==='sources'}" @click="activeTab='sources'">
          <el-icon><Connection /></el-icon> 数据源管理
        </div>
        <div class="tab" :class="{active: activeTab==='channels'}" @click="activeTab='channels'">
          <el-icon><List /></el-icon> 频道表
        </div>
      </div>
      <div class="topbar-right">
        <el-tag :type="scheduleCfg.enabled ? 'success' : 'info'" size="small" class="sched-tag">
          <el-icon><Timer /></el-icon>
          {{ scheduleCfg.enabled ? `每天 ${String(scheduleCfg.hour).padStart(2,'0')}:${String(scheduleCfg.minute).padStart(2,'0')} 更新` : '定时未开启' }}
        </el-tag>
      </div>
    </header>

    <!-- ========== 搜索测速面板 ========== -->
    <div class="main-layout" v-show="activeTab==='search'">
      <aside class="control-panel">
        <div class="panel-section">
          <h3><el-icon><Connection /></el-icon> IP 版本</h3>
          <el-radio-group v-model="ipVersion" size="small">
            <el-radio-button label="ipv4">IPv4</el-radio-button>
            <el-radio-button label="ipv6">IPv6</el-radio-button>
            <el-radio-button label="both">双栈</el-radio-button>
          </el-radio-group>
        </div>
        <div class="panel-section">
          <h3><el-icon><Search /></el-icon> 搜索源</h3>
          <el-select v-model="sourceType" size="small" style="width:100%;margin-bottom:8px">
            <el-option label="全部（组播+酒店）" value="all" />
            <el-option label="仅组播源" value="multicast" />
            <el-option label="仅酒店源" value="hotel" />
          </el-select>
          <el-input v-model="customUrls" type="textarea" :rows="3" placeholder="自定义 URL（可选，每行一个）" size="small" />
        </div>
        <div class="panel-section">
          <h3><el-icon><Odometer /></el-icon> 测速设置</h3>
          <label>并发数</label>
          <el-slider v-model="concurrency" :min="5" :max="50" show-input size="small" />
          <label style="margin-top:6px">超时 {{ timeout }}s / 每频道保留 {{ maxKeep }} 条</label>
          <el-slider v-model="timeout" :min="2" :max="15" show-input size="small" />
          <el-slider v-model="maxKeep" :min="1" :max="20" show-input size="small" />
        </div>
        <div class="panel-section">
          <el-button type="primary" class="full-btn" :loading="running" @click="runPipeline" size="default">
            <el-icon><VideoPlay /></el-icon> 搜索 → 测速 → 择优
          </el-button>
          <el-button type="success" class="full-btn" :disabled="!entries.length" @click="dlM3U" size="small" style="margin-top:6px">
            <el-icon><Download /></el-icon> 导出 M3U ({{ entries.length }})
          </el-button>
          <el-button type="success" class="full-btn" :disabled="!entries.length" @click="dlTXT" size="small" style="margin-top:4px">
            <el-icon><Download /></el-icon> 导出 TXT ({{ entries.length }})
          </el-button>
        </div>
        <div class="panel-section" v-if="running">
          <el-progress :percentage="progress.pct" :stroke-width="10" striped striped-flow />
          <div class="progress-text">{{ progress.text }}</div>
        </div>
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
      <main class="result-panel">
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
              <el-tag size="small" :type="row.protocol === 'ipv6' ? 'warning' : 'info'">{{ row.protocol }}</el-tag>
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

    <!-- ========== 数据源管理面板 ========== -->
    <div class="sources-layout" v-show="activeTab==='sources'">
      <aside class="sources-sidebar">
        <!-- 搜索和筛选 -->
        <div class="filter-bar">
          <el-input v-model="srcFilter" placeholder="搜索数据源..." size="small" clearable>
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-select v-model="srcTypeFilter" placeholder="类型" size="small" clearable>
            <el-option label="全部类型" value="" />
            <el-option label="组播源" value="multicast" />
            <el-option label="酒店源" value="hotel" />
            <el-option label="自定义" value="custom" />
          </el-select>
          <el-select v-model="srcRegionFilter" placeholder="地区" size="small" clearable>
            <el-option label="全部地区" value="" />
            <el-option v-for="(label, val) in sourceStats.region_labels || {}" :key="val" :label="label" :value="val" />
          </el-select>
        </div>

        <!-- 操作按钮 -->
        <div class="action-bar">
          <el-button size="small" type="primary" @click="showAddSourceDlg = true">
            <el-icon><Plus /></el-icon> 添加
          </el-button>
          <el-button size="small" @click="searchOnline">
            <el-icon><Search /></el-icon> 搜全网
          </el-button>
          <el-button size="small" type="success" @click="checkAllSources" :loading="checking">
            <el-icon><Timer /></el-icon> 一键测速
          </el-button>
          <el-button size="small" @click="loadSources" :loading="srcLoading">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>

        <!-- 统计信息 -->
        <div class="src-stats" v-if="sourceStats.total">
          <span>共 {{ sourceStats.total }} 源</span>
          <span class="ok-dot">{{ sourceStats.by_status?.ok || 0 }} 正常</span>
          <span class="err-dot">{{ sourceStats.by_status?.error || 0 }} 异常</span>
        </div>

        <!-- 分类树 -->
        <div class="category-tree">
          <div class="cat-group" v-for="cat in sourceCategories" :key="cat.key">
            <div class="cat-header" @click="cat.expanded = !cat.expanded">
              <el-icon :class="{rotated: cat.expanded}"><ArrowRight /></el-icon>
              <span class="cat-label">{{ cat.label }}</span>
              <span class="cat-count">({{ cat.sources.length }})</span>
              <el-button size="small" text type="success" @click.stop="checkCategory(cat)" title="测速此分类">
                <el-icon><Timer /></el-icon>
              </el-button>
            </div>
            <div class="cat-sources" v-show="cat.expanded">
              <div class="src-item" v-for="s in cat.sources" :key="s.id"
                :class="{selected: selectedSource?.id === s.id, disabled: !s.enabled}"
                @click="selectSource(s)">
                <div class="src-status-dot" :class="s.last_status || 'unknown'" />
                <div class="src-info">
                  <div class="src-name" :title="s.name">{{ s.name }}</div>
                  <div class="src-url" :title="s.url">{{ s.url.length > 40 ? s.url.substring(0,40) + '...' : s.url }}</div>
                </div>
                <div class="src-badges">
                  <el-tag size="small" :type="s.last_status === 'ok' ? 'success' : s.last_status === 'error' ? 'danger' : 'info'" style="font-size:10px">
                    {{ s.last_response_ms ? s.last_response_ms + 'ms' : '?' }}
                  </el-tag>
                  <span class="src-entries" v-if="s.entry_count">{{ s.entry_count }}ch</span>
                </div>
              </div>
              <div class="cat-empty" v-if="!cat.sources.length">暂无数据源</div>
            </div>
          </div>
        </div>
      </aside>

      <!-- 详情/编辑区 -->
      <main class="sources-detail">
        <div v-if="!selectedSource" class="empty-detail">
          <el-empty description="选择一个数据源查看详情，或添加新数据源" />
        </div>
        <div v-else class="source-detail-content">
          <div class="detail-header">
            <h2>{{ selectedSource.name }}</h2>
            <div class="detail-actions">
              <el-button size="small" type="success" @click="checkOneSource(selectedSource)" :loading="checkingOne === selectedSource.id">
                <el-icon><Timer /></el-icon> 测速
              </el-button>
              <el-button size="small" @click="editSource(selectedSource)">
                <el-icon><Edit /></el-icon> 编辑
              </el-button>
              <el-button size="small" type="danger" @click="deleteSource(selectedSource)">
                <el-icon><Delete /></el-icon> 删除
              </el-button>
            </div>
          </div>

          <el-descriptions :column="2" size="small" border>
            <el-descriptions-item label="URL">
              <a :href="selectedSource.url" target="_blank" class="url-link">{{ selectedSource.url }}</a>
            </el-descriptions-item>
            <el-descriptions-item label="类型">
              <el-tag size="small">{{ TYPE_LABEL_MAP[selectedSource.type] || selectedSource.type }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="地区">
              <el-tag size="small" type="info">{{ REGION_LABEL_MAP[selectedSource.region] || selectedSource.region }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag size="small" :type="selectedSource.enabled ? 'success' : 'warning'">
                {{ selectedSource.enabled ? '启用' : '禁用' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="上次测速">
              {{ selectedSource.last_check ? new Date(selectedSource.last_check * 1000).toLocaleString() : '未测速' }}
            </el-descriptions-item>
            <el-descriptions-item label="响应时间">
              <span :style="{color: selectedSource.last_response_ms < 1000 ? '#22c55e' : selectedSource.last_response_ms < 3000 ? '#f59e0b' : '#ef4444'}">
                {{ selectedSource.last_response_ms ? selectedSource.last_response_ms + 'ms' : '-' }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="频道数">{{ selectedSource.entry_count || '-' }}</el-descriptions-item>
            <el-descriptions-item label="优先级">{{ selectedSource.priority }}</el-descriptions-item>
          </el-descriptions>

          <el-switch v-model="selectedSource.enabled" active-text="启用" inactive-text="禁用"
            @change="toggleSourceEnabled(selectedSource)" style="margin-top:12px" />

          <div v-if="selectedSource.note" class="source-note">
            <strong>备注：</strong>{{ selectedSource.note }}
          </div>
        </div>
      </main>
    </div>

    <!-- ========== 频道表面板 ========== -->
    <div class="channels-layout" v-show="activeTab==='channels'">
      <div class="channels-content">
        <div class="ch-header">
          <h3>频道表管理 ({{ channels.length }})</h3>
          <div class="ch-actions">
            <el-input v-model="chFilter" placeholder="筛选频道..." size="small" style="width:160px" clearable />
            <el-button size="small" type="primary" @click="addChannel"><el-icon><Plus /></el-icon> 添加</el-button>
            <el-button size="small" @click="importChannels"><el-icon><Upload /></el-icon> 批量导入</el-button>
            <el-button size="small" @click="resetChannels"><el-icon><RefreshLeft /></el-icon> 重置默认</el-button>
            <el-button size="small" @click="showScheduleDlg = true"><el-icon><Timer /></el-icon> 定时设置</el-button>
          </div>
        </div>
        <el-table :data="filteredChannels" stripe size="small" height="calc(100vh - 160px)">
          <el-table-column label="#" type="index" width="50" />
          <el-table-column label="频道名" min-width="140">
            <template #default="{ row }">
              <el-input v-model="row.name" size="small" @change="saveChannelRow(row)" />
            </template>
          </el-table-column>
          <el-table-column label="分组" width="100">
            <template #default="{ row }">
              <el-input v-model="row.group" size="small" @change="saveChannelRow(row)" />
            </template>
          </el-table-column>
          <el-table-column label="启用" width="60">
            <template #default="{ row }">
              <el-switch v-model="row.enabled" size="small" @change="saveChannelRow(row)" />
            </template>
          </el-table-column>
          <el-table-column label="保留条数" width="80">
            <template #default="{ row }">
              <el-input-number v-model="row.max_results" :min="1" :max="50" size="small" @change="saveChannelRow(row)" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="60">
            <template #default="{ row }">
              <el-button size="small" text type="danger" @click="delChannel(row)"><el-icon><Delete /></el-icon></el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- ===== 添加/编辑数据源对话框 ===== -->
    <el-dialog v-model="showAddSourceDlg" :title="editingSource ? '编辑数据源' : '添加数据源'" width="560px" destroy-on-close>
      <el-form :model="sourceForm" label-width="80px" size="small">
        <el-form-item label="名称" required>
          <el-input v-model="sourceForm.name" placeholder="显示名称" />
        </el-form-item>
        <el-form-item label="URL" required>
          <el-input v-model="sourceForm.url" placeholder="https://example.com/iptv.m3u" />
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="sourceForm.type">
            <el-radio label="multicast">组播源</el-radio>
            <el-radio label="hotel">酒店源</el-radio>
            <el-radio label="custom">自定义</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="地区">
          <el-select v-model="sourceForm.region" style="width:200px">
            <el-option v-for="(label, val) in REGION_LABEL_MAP" :key="val" :label="label" :value="val" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="sourceForm.priority" :min="0" :max="999" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="sourceForm.note" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddSourceDlg = false">取消</el-button>
        <el-button type="primary" @click="saveSource" :loading="savingSource">保存</el-button>
      </template>
    </el-dialog>

    <!-- ===== 全网搜索结果对话框 ===== -->
    <el-dialog v-model="showOnlineDlg" title="全网数据源搜索结果" width="700px" destroy-on-close>
      <div v-if="onlineLoading" class="loading-box">
        <el-skeleton :rows="6" animated />
      </div>
      <div v-else>
        <div class="online-info">搜索到 {{ onlineSources.length }} 个公开数据源</div>
        <el-table :data="onlineSources" stripe size="small" height="400" @selection-change="onlineSelection = $event">
          <el-table-column type="selection" width="40" />
          <el-table-column prop="name" label="名称" min-width="160" show-overflow-tooltip />
          <el-table-column prop="type" label="类型" width="70">
            <template #default="{ row }">
              <el-tag size="small">{{ TYPE_LABEL_MAP[row.type] || row.type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="region" label="地区" width="70">
            <template #default="{ row }">
              <el-tag size="small" type="info">{{ REGION_LABEL_MAP[row.region] || row.region }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="url" label="URL" min-width="200" show-overflow-tooltip />
        </el-table>
      </div>
      <template #footer>
        <el-button @click="showOnlineDlg = false">关闭</el-button>
        <el-button type="primary" @click="importOnlineSources" :disabled="!onlineSelection.length" :loading="importing">
          导入选中 ({{ onlineSelection.length }})
        </el-button>
      </template>
    </el-dialog>

    <!-- ===== 定时设置对话框 ===== -->
    <el-dialog v-model="showScheduleDlg" title="定时更新设置" width="420px">
      <el-form :model="scheduleCfg" label-width="80px" size="small">
        <el-form-item label="启用"><el-switch v-model="scheduleCfg.enabled" /></el-form-item>
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

// ============ 标签页 ============
const activeTab = ref('search')

// ============ 搜索测速 ============
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
const chFilter = ref('')
const showScheduleDlg = ref(false)

const filteredChannels = computed(() => {
  if (!chFilter.value) return channels.value
  const f = chFilter.value.toLowerCase()
  return channels.value.filter(ch => ch.name.toLowerCase().includes(f) || ch.group.toLowerCase().includes(f))
})

async function api(path, method = 'get', data = null) {
  try {
    const r = method === 'post' ? await request.post(path, data) : await request.get(path)
    return r && r.code === 0 ? (r.data || {}) : null
  } catch (e) { return null }
}

onMounted(async () => {
  await loadChannels()
  await loadStats()
  await loadSchedule()
  await loadSources()
})

async function loadChannels() {
  const data = await api('/channels')
  if (data) channels.value = data || []
}
async function loadStats() {
  const data = await api('/stats')
  if (data) { stats.total = data.total || 0; stats.groups = data.groups || {}; stats.protocols = data.protocols || {} }
}
async function loadSchedule() {
  const data = await api('/schedule')
  if (data) Object.assign(scheduleCfg, data)
}

async function runPipeline() {
  if (!channels.value.filter(ch => ch.enabled).length) { ElMessage.warning('频道表为空'); return }
  running.value = true
  progress.pct = 10; progress.text = '正在搜索 IPTV 源...'
  try {
    const res = await request.post('/run', {
      source_type: sourceType.value, ip_version: ipVersion.value,
      concurrency: concurrency.value, timeout: timeout.value, max_keep: maxKeep.value, search_timeout: 15,
    })
    if (res && res.code === 0 && res.data) {
      entries.value = res.data.entries || []
      if (res.data.stats) stats.total = res.data.stats.total_kept || 0
      await loadStats()
      ElMessage.success(`完成！搜索 ${res.data.stats.total_searched} → 匹配 ${res.data.stats.total_matched} → 有效 ${res.data.stats.total_tested} → 保留 ${res.data.stats.total_kept} 条`)
    } else {
      ElMessage.error(res?.message || '执行失败')
    }
  } catch (e) { ElMessage.error('网络错误: ' + (e.message || '')) }
  finally { running.value = false }
}

function dlM3U() { window.open('/api/export/m3u', '_blank') }
function dlTXT() { window.open('/api/export/txt', '_blank') }

async function addChannel() { channels.value.push({ id: '', name: '新频道', group: '未分组', enabled: true, max_results: 10 }) }
async function delChannel(row) {
  const idx = channels.value.indexOf(row)
  if (idx >= 0) { if (row.id) await api(`/channels/${row.id}`, 'delete'); channels.value.splice(idx, 1) }
}
async function saveChannelRow(row) {
  if (row.id) {
    await api(`/channels/${row.id}`, 'put', { name: row.name, group: row.group, enabled: row.enabled, max_results: row.max_results })
  } else {
    const res = await api('/channels', 'post', { name: row.name, group: row.group, enabled: row.enabled, max_results: row.max_results })
    if (res && res.id) row.id = res.id
  }
}
async function importChannels() {
  const input = prompt('批量导入频道（每行: 频道名,分组）:\n例:\nCCTV-1,央视\n湖南卫视,卫视')
  if (!input) return
  const lines = input.trim().split('\n').filter(l => l.trim())
  const items = lines.map(l => { const p = l.split(','); return { name: p[0].trim(), group: p[1]?.trim() || '未分组', enabled: true, max_results: 10 } })
  const res = await api('/channels/import', 'post', items)
  if (res) ElMessage.success(res.message || '导入成功')
  await loadChannels()
}
async function resetChannels() { if (!confirm('重置为默认频道表？')) return; await api('/channels/reset', 'post'); await loadChannels(); ElMessage.success('已重置') }
async function saveSchedule() {
  await api('/schedule', 'post', { enabled: scheduleCfg.enabled, hour: scheduleCfg.hour, minute: scheduleCfg.minute, source_type: scheduleCfg.source_type, ip_version: scheduleCfg.ip_version, concurrency: scheduleCfg.concurrency, timeout: scheduleCfg.timeout, max_keep: scheduleCfg.max_keep })
  showScheduleDlg.value = false; ElMessage.success('定时设置已保存')
}

// ============ 数据源管理 ============
const TYPE_LABEL_MAP = { multicast: '组播源', hotel: '酒店源', custom: '自定义' }
const REGION_LABEL_MAP = { cn: '中国大陆', hk: '中国香港', tw: '中国台湾', kr: '韩国', jp: '日本', sg: '新加坡', us: '美国', uk: '英国', overseas: '海外其他', unknown: '未知' }

const allSources = ref([])
const srcFilter = ref('')
const srcTypeFilter = ref('')
const srcRegionFilter = ref('')
const srcLoading = ref(false)
const checking = ref(false)
const checkingOne = ref(null)
const selectedSource = ref(null)
const showAddSourceDlg = ref(false)
const editingSource = ref(null)
const sourceForm = reactive({ name: '', url: '', type: 'multicast', region: 'cn', priority: 0, note: '', enabled: true })
const savingSource = ref(false)
const showOnlineDlg = ref(false)
const onlineSources = ref([])
const onlineLoading = ref(false)
const onlineSelection = ref([])
const importing = ref(false)
const sourceStats = reactive({ total: 0, by_status: {}, region_labels: {} })

// 分类数据
const sourceCategories = computed(() => {
  const sources = filteredSources.value
  const cats = []

  // 按类型分组
  const typeGroups = {}
  for (const s of sources) {
    const t = s.type || 'multicast'
    if (!typeGroups[t]) typeGroups[t] = []
    typeGroups[t].push(s)
  }
  for (const [type, items] of Object.entries(typeGroups)) {
    // 每个类型下按地区分组
    const regionGroups = {}
    for (const s of items) {
      const r = s.region || 'unknown'
      if (!regionGroups[r]) regionGroups[r] = []
      regionGroups[r].push(s)
    }
    for (const [region, rItems] of Object.entries(regionGroups)) {
      cats.push({
        key: `${type}-${region}`,
        label: `${TYPE_LABEL_MAP[type] || type} / ${REGION_LABEL_MAP[region] || region}`,
        sources: rItems.sort((a, b) => (a.priority || 0) - (b.priority || 0)),
        expanded: true,
      })
    }
  }
  return cats
})

const filteredSources = computed(() => {
  let result = allSources.value
  if (srcFilter.value) {
    const kw = srcFilter.value.toLowerCase()
    result = result.filter(s => s.name.toLowerCase().includes(kw) || s.url.toLowerCase().includes(kw))
  }
  if (srcTypeFilter.value) result = result.filter(s => s.type === srcTypeFilter.value)
  if (srcRegionFilter.value) result = result.filter(s => s.region === srcRegionFilter.value)
  return result
})

async function loadSources() {
  srcLoading.value = true
  try {
    const data = await api('/sources')
    if (data) {
      allSources.value = data.sources || []
      if (data.regions) Object.assign(REGION_LABEL_MAP, data.regions)
    }
    const sdata = await api('/sources/stats')
    if (sdata) Object.assign(sourceStats, sdata)
  } finally { srcLoading.value = false }
}

function selectSource(s) { selectedSource.value = s }

function editSource(s) {
  editingSource.value = s
  Object.assign(sourceForm, { name: s.name, url: s.url, type: s.type, region: s.region, priority: s.priority, note: s.note, enabled: s.enabled })
  showAddSourceDlg.value = true
}

async function saveSource() {
  if (!sourceForm.name || !sourceForm.url) { ElMessage.warning('名称和 URL 必填'); return }
  savingSource.value = true
  try {
    if (editingSource.value) {
      await api(`/sources/${editingSource.value.id}`, 'put', { ...sourceForm })
      ElMessage.success('更新成功')
    } else {
      const res = await api('/sources', 'post', { ...sourceForm })
      ElMessage.success('添加成功')
    }
    showAddSourceDlg.value = false
    editingSource.value = null
    Object.assign(sourceForm, { name: '', url: '', type: 'multicast', region: 'cn', priority: 0, note: '', enabled: true })
    await loadSources()
  } finally { savingSource.value = false }
}

async function deleteSource(s) {
  if (!confirm(`删除数据源「${s.name}」？`)) return
  await api(`/sources/${s.id}`, 'delete')
  ElMessage.success('已删除')
  if (selectedSource.value?.id === s.id) selectedSource.value = null
  await loadSources()
}

async function toggleSourceEnabled(s) {
  await api(`/sources/${s.id}`, 'put', { enabled: s.enabled })
  ElMessage.success(s.enabled ? '已启用' : '已禁用')
}

async function checkOneSource(s) {
  checkingOne.value = s.id
  try {
    const res = await api(`/sources/check/${s.id}`, 'post', null)
    if (res) {
      ElMessage.success(`测速完成: ${res.response_ms}ms, ${res.entry_count} 频道`)
      await loadSources()
    }
  } finally { checkingOne.value = null }
}

async function checkCategory(cat) {
  checking.value = true
  try {
    const ids = cat.sources.map(s => s.id)
    const res = await api('/sources/check', 'post', { ids, concurrency: 5, timeout: 10 })
    if (res) ElMessage.success(res.message || '测速完成')
    await loadSources()
  } finally { checking.value = false }
}

async function checkAllSources() {
  checking.value = true
  try {
    const res = await api('/sources/check', 'post', { concurrency: 5, timeout: 10 })
    if (res) ElMessage.success(res.message || '测速完成')
    await loadSources()
  } finally { checking.value = false }
}

async function searchOnline() {
  showOnlineDlg.value = true
  onlineLoading.value = true
  onlineSelection.value = []
  try {
    const res = await api('/sources/search-online')
    if (res) onlineSources.value = res || []
  } finally { onlineLoading.value = false }
}

async function importOnlineSources() {
  if (!onlineSelection.value.length) return
  importing.value = true
  try {
    const items = onlineSelection.value.map(s => ({ name: s.name, url: s.url, type: s.type || 'multicast', region: s.region || 'unknown' }))
    const res = await api('/sources/import', 'post', items)
    if (res) ElMessage.success(res.message || '导入成功')
    await loadSources()
  } finally { importing.value = false }
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

/* 顶栏标签页 */
.topbar-tabs { display: flex; gap: 4px; margin-left: 24px; }
.tab { padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 13px; color: #94a3b8; display: flex; align-items: center; gap: 4px; transition: all .2s; }
.tab:hover { background: #1e293b; color: #e2e8f0; }
.tab.active { background: #1e293b; color: #06b6d4; font-weight: 600; }

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
.progress-text { font-size: 11px; color: #94a3b8; margin-top: 4px; text-align: center; }
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

/* ===== 数据源管理布局 ===== */
.sources-layout { flex: 1; display: flex; overflow: hidden; }

/* 左侧边栏 */
.sources-sidebar { width: 340px; background: #0f172a; border-right: 1px solid #1e293b; display: flex; flex-direction: column; flex-shrink: 0; }
.filter-bar { padding: 8px; display: flex; flex-direction: column; gap: 6px; border-bottom: 1px solid #1e293b; }
.action-bar { padding: 8px; display: flex; gap: 6px; border-bottom: 1px solid #1e293b; flex-wrap: wrap; }
.src-stats { padding: 6px 10px; font-size: 11px; color: #94a3b8; display: flex; gap: 10px; border-bottom: 1px solid #1e293b; }
.ok-dot { color: #22c55e; }
.err-dot { color: #ef4444; }

/* 分类树 */
.category-tree { flex: 1; overflow-y: auto; padding: 4px 0; }
.cat-header { padding: 4px 10px; display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 12px; color: #94a3b8; }
.cat-header:hover { background: #1e293b; }
.cat-header .cat-label { flex: 1; font-weight: 600; color: #06b6d4; }
.cat-header .cat-count { font-size: 10px; color: #64748b; }
.cat-header .el-icon { transition: transform .2s; font-size: 12px; }
.cat-header .el-icon.rotated { transform: rotate(90deg); }

/* 数据源条目 */
.cat-sources { padding: 2px 0; }
.src-item { padding: 6px 14px; display: flex; align-items: center; gap: 8px; cursor: pointer; border-left: 3px solid transparent; transition: all .15s; }
.src-item:hover { background: #1e293b; }
.src-item.selected { background: #1e293b; border-left-color: #06b6d4; }
.src-item.disabled { opacity: 0.5; }
.src-status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.src-status-dot.ok { background: #22c55e; box-shadow: 0 0 4px #22c55e66; }
.src-status-dot.error { background: #ef4444; }
.src-status-dot.unknown { background: #64748b; }
.src-info { flex: 1; min-width: 0; }
.src-name { font-size: 12px; color: #e2e8f0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.src-url { font-size: 10px; color: #64748b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.src-badges { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; flex-shrink: 0; }
.src-entries { font-size: 10px; color: #64748b; }
.cat-empty { padding: 8px 20px; font-size: 11px; color: #475569; text-align: center; }

/* 详情区 */
.sources-detail { flex: 1; padding: 16px 20px; overflow-y: auto; }
.empty-detail { display: flex; align-items: center; justify-content: center; height: 100%; }
.source-detail-content h2 { font-size: 16px; color: #e2e8f0; margin: 0 0 12px; }
.detail-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.detail-actions { display: flex; gap: 8px; }
.url-link { color: #06b6d4; text-decoration: none; font-size: 12px; word-break: break-all; }
.url-link:hover { text-decoration: underline; }
.source-note { margin-top: 12px; padding: 8px 12px; background: #1e293b; border-radius: 6px; font-size: 12px; color: #94a3b8; }

/* 全网搜索 */
.loading-box { padding: 20px; }
.oneline-info { font-size: 12px; color: #94a3b8; margin-bottom: 8px; }

/* ===== 频道表布局 ===== */
.channels-layout { flex: 1; display: flex; overflow: hidden; }
.channels-content { flex: 1; padding: 12px 16px; display: flex; flex-direction: column; }
.ch-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.ch-header h3 { font-size: 14px; color: #e2e8f0; margin: 0; }
.ch-actions { display: flex; gap: 8px; align-items: center; }
</style>
