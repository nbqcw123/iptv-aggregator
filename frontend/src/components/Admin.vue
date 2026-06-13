<template>
  <div class="admin-layout">
    <!-- 管理侧栏 -->
    <aside class="admin-sidebar">
      <div class="sidebar-header">
        <el-icon :size="20"><Setting /></el-icon>
        <span>后台管理</span>
      </div>
      <nav class="sidebar-nav">
        <div class="nav-item" :class="{active: adminTab==='channels'}" @click="adminTab='channels'">
          <el-icon><List /></el-icon> 频道管理
        </div>
        <div class="nav-item" :class="{active: adminTab==='results'}" @click="adminTab='results'">
          <el-icon><Search /></el-icon> 搜索结果
        </div>
        <div class="nav-item" :class="{active: adminTab==='output'}" @click="adminTab='output'">
          <el-icon><Document /></el-icon> 输出配置
        </div>
        <div class="nav-item" :class="{active: adminTab==='system'}" @click="adminTab='system'">
          <el-icon><Setting /></el-icon> 系统设置
        </div>
        <div class="nav-item" :class="{active: adminTab==='database'}" @click="adminTab='database'">
          <el-icon><Coin /></el-icon> 数据库
        </div>
      </nav>
    </aside>

    <!-- 管理主内容区 -->
    <main class="admin-content">

      <!-- ====== 频道管理 ====== -->
      <div v-show="adminTab==='channels'" class="admin-panel">
        <div class="panel-header">
          <h2><el-icon><List /></el-icon> 频道管理</h2>
          <div class="panel-actions">
            <el-input v-model="chSearch" placeholder="搜索频道..." size="small" style="width:180px" clearable />
            <el-select v-model="chGroupFilter" placeholder="分组" size="small" clearable style="width:120px">
              <el-option label="全部分组" value="" />
              <el-option v-for="g in allGroups" :key="g" :label="g" :value="g" />
            </el-select>
            <el-select v-model="chEnabledFilter" placeholder="状态" size="small" clearable style="width:100px">
              <el-option label="全部" value="" />
              <el-option label="启用" value="true" />
              <el-option label="禁用" value="false" />
            </el-select>
            <el-button size="small" type="primary" @click="showAddChDlg=true"><el-icon><Plus /></el-icon> 添加</el-button>
            <el-button size="small" @click="showImportChDlg=true"><el-icon><Upload /></el-icon> 批量导入</el-button>
            <el-button size="small" @click="exportChannels"><el-icon><Download /></el-icon> 导出</el-button>
          </div>
        </div>

        <!-- 批量操作栏 -->
        <div class="batch-bar" v-if="selectedChannels.length">
          <span>已选 {{ selectedChannels.length }} 个</span>
          <el-button size="small" type="success" @click="batchEnable(true)">批量启用</el-button>
          <el-button size="small" type="warning" @click="batchEnable(false)">批量禁用</el-button>
          <el-select v-model="batchGroup" placeholder="移动到分组" size="small" style="width:140px">
            <el-option v-for="g in allGroups" :key="g" :label="g" :value="g" />
          </el-select>
          <el-button size="small" @click="batchChangeGroup">移动</el-button>
          <el-button size="small" type="danger" @click="batchDelete">批量删除</el-button>
        </div>

        <el-table :data="filteredChannels" stripe size="small" height="calc(100vh - 220px)"
          @selection-change="selectedChannels=$element" v-loading="chLoading">
          <el-table-column type="selection" width="40" />
          <el-table-column prop="name" label="频道名" min-width="160">
            <template #default="{row}">
              <el-input v-model="row.name" size="small" @change="saveChannelInline(row)" />
            </template>
          </el-table-column>
          <el-table-column prop="group" label="分组" width="140">
            <template #default="{row}">
              <el-select v-model="row.group" size="small" @change="saveChannelInline(row)">
                <el-option v-for="g in allGroups" :key="g" :label="g" :value="g" />
                <el-option label="📺央视频道" value="📺央视频道" />
                <el-option label="📡卫视频道" value="📡卫视频道" />
                <el-option label="🆕4K频道" value="🆕4K频道" />
                <el-option label="☘️地方频道" value="☘️地方频道" />
                <el-option label="💰财经频道" value="💰财经频道" />
                <el-option label="✉新闻频道" value="✉新闻频道" />
                <el-option label="🌊港台·海外" value="🌊港台·海外" />
                <el-option label="🎬电影频道" value="🎬电影频道" />
                <el-option label="🏀体育频道" value="🏀体育频道" />
                <el-option label="🎮游戏频道" value="🎮游戏频道" />
                <el-option label="🎵音乐频道" value="🎵音乐频道" />
                <el-option label="🧒动画频道" value="🧒动画频道" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="70">
            <template #default="{row}">
              <el-switch v-model="row.enabled" size="small" @change="saveChannelInline(row)" />
            </template>
          </el-table-column>
          <el-table-column label="保留条数" width="90">
            <template #default="{row}">
              <el-input-number v-model="row.max_results" :min="1" :max="50" size="small" @change="saveChannelInline(row)" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80">
            <template #default="{row}">
              <el-button size="small" text type="danger" @click="deleteChannel(row)"><el-icon><Delete /></el-icon></el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pagination-bar">
          <el-pagination layout="total, prev, pager, next" :total="chTotal" :page-size="chPageSize"
            :current-page="chPage" @current-change="chPage=$event; loadChannels()" />
        </div>
      </div>

      <!-- ====== 搜索结果管理 ====== -->
      <div v-show="adminTab==='results'" class="admin-panel">
        <div class="panel-header">
          <h2><el-icon><Search /></el-icon> 搜索结果管理 ({{ resTotal }})</h2>
          <div class="panel-actions">
            <el-input v-model="resSearch" placeholder="搜索..." size="small" style="width:160px" clearable />
            <el-select v-model="resGroupFilter" placeholder="分组" size="small" clearable style="width:120px">
              <el-option label="全部分组" value="" />
              <el-option v-for="g in resGroups" :key="g" :label="g" :value="g" />
            </el-select>
            <el-select v-model="resSortBy" size="small" style="width:100px">
              <el-option label="按名称" value="name" />
              <el-option label="按响应" value="response_time" />
              <el-option label="按分组" value="group" />
            </el-select>
            <el-button size="small" @click="resSortOrder=resSortOrder==='asc'?'desc':'asc'">
              {{ resSortOrder==='asc' ? '↑升序' : '↓降序' }}
            </el-button>
            <el-button size="small" type="primary" @click="showAddResDlg=true"><el-icon><Plus /></el-icon> 手动添加</el-button>
            <el-button size="small" type="danger" @click="clearAllResults" :disabled="!resTotal">清空全部</el-button>
          </div>
        </div>
        <el-table :data="filteredResults" stripe size="small" height="calc(100vh - 180px)" v-loading="resLoading">
          <el-table-column type="index" width="50" />
          <el-table-column label="频道名" min-width="160">
            <template #default="{row}">
              <el-input v-model="row.name" size="small" @blur="saveResultInline(row)" />
            </template>
          </el-table-column>
          <el-table-column label="URL" min-width="280">
            <template #default="{row}">
              <el-input v-model="row.url" size="small" @blur="saveResultInline(row)" />
            </template>
          </el-table-column>
          <el-table-column label="分组" width="120">
            <template #default="{row}">
              <el-input v-model="row.group" size="small" @blur="saveResultInline(row)" />
            </template>
          </el-table-column>
          <el-table-column label="来源" width="100" show-overflow-tooltip>
            <template #default="{row}">
              <el-tag size="small">{{ row.source_name || '-' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="协议" width="70">
            <template #default="{row}">{{ row.protocol || 'ipv4' }}</template>
          </el-table-column>
          <el-table-column label="响应" width="80">
            <template #default="{row}">
              <span :style="{color: row.response_time < 500 ? '#22c55e' : row.response_time < 2000 ? '#f59e0b' : '#ef4444'}">
                {{ row.response_time ? row.response_time + 'ms' : '-' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="70">
            <template #default="{row}">
              <el-button size="small" text type="danger" @click="deleteResult(row)"><el-icon><Delete /></el-icon></el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pagination-bar">
          <el-pagination layout="total, prev, pager, next" :total="resTotal" :page-size="resPageSize"
            :current-page="resPage" @current-change="resPage=$event; loadResults()" />
        </div>
      </div>

      <!-- ====== 输出配置 ====== -->
      <div v-show="adminTab==='output'" class="admin-panel">
        <div class="panel-header">
          <h2><el-icon><Document /></el-icon> 输出配置</h2>
          <el-button size="small" type="primary" @click="saveOutputConfig" :loading="outputSaving">保存配置</el-button>
        </div>
        <el-form :model="outputConfig" label-width="140px" size="default">
          <el-divider content-position="left">M3U 设置</el-divider>
          <el-form-item label="M3U 头部">
            <el-input v-model="outputConfig.m3u_header" placeholder="#EXTM3U" />
          </el-form-item>
          <el-form-item label="包含频道图标">
            <el-switch v-model="outputConfig.include_logo" />
            <span class="form-hint">自动匹配 fanmingming/live 仓库的频道 logo</span>
          </el-form-item>
          <el-form-item label="包含 EPG">
            <el-switch v-model="outputConfig.include_epg" />
            <span class="form-hint">添加 x-tvg-url 标签</span>
          </el-form-item>
          <el-form-item label="包含分组">
            <el-switch v-model="outputConfig.include_group" />
          </el-form-item>
          <el-form-item label="分组 emoji">
            <el-switch v-model="outputConfig.group_emoji" />
            <span class="form-hint">📺央视频道 / 📡卫视频道 等 emoji 前缀</span>
          </el-form-item>

          <el-divider content-position="left">TXT 设置</el-divider>
          <el-form-item label="分隔符">
            <el-select v-model="outputConfig.txt_separator" style="width:120px">
              <el-option label="逗号 ," value="," />
              <el-option label="竖线 |" value="|" />
              <el-option label="制表符" value="&#9;" />
            </el-select>
          </el-form-item>

          <el-divider content-position="left">排序与过滤</el-divider>
          <el-form-item label="排序方式">
            <el-radio-group v-model="outputConfig.sort_by">
              <el-radio label="name">按名称</el-radio>
              <el-radio label="response_time">按响应时间</el-radio>
              <el-radio label="group">按分组</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="排序方向">
            <el-radio-group v-model="outputConfig.sort_order">
              <el-radio label="asc">升序</el-radio>
              <el-radio label="desc">降序</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="协议过滤">
            <el-radio-group v-model="outputConfig.filter_protocol">
              <el-radio label="all">全部</el-radio>
              <el-radio label="ipv4">仅 IPv4</el-radio>
              <el-radio label="ipv6">仅 IPv6</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="最大响应时间">
            <el-input-number v-model="outputConfig.filter_max_response" :min="0" :max="30000" :step="500" />
            <span class="form-hint">ms (0=不限)</span>
          </el-form-item>
        </el-form>

        <el-divider content-position="left">预览</el-divider>
        <div class="preview-btns">
          <el-button size="small" @click="previewM3U">预览 M3U</el-button>
          <el-button size="small" @click="previewTXT">预览 TXT</el-button>
          <el-button size="small" type="success" @click="dlM3U">下载 M3U</el-button>
          <el-button size="small" type="success" @click="dlTXT">下载 TXT</el-button>
        </div>
      </div>

      <!-- ====== 系统设置 ====== -->
      <div v-show="adminTab==='system'" class="admin-panel">
        <div class="panel-header">
          <h2><el-icon><Setting /></el-icon> 系统设置</h2>
        </div>
        <el-tabs v-model="systemTab">
          <el-tab-pane label="定时任务" name="schedule">
            <el-form :model="systemSettings.schedule" label-width="120px" size="default">
              <el-form-item label="启用定时">
                <el-switch v-model="systemSettings.schedule.enabled" />
              </el-form-item>
              <el-form-item label="执行时间">
                <el-input-number v-model="systemSettings.schedule.hour" :min="0" :max="23" /> :
                <el-input-number v-model="systemSettings.schedule.minute" :min="0" :max="59" />
              </el-form-item>
              <el-form-item label="源类型">
                <el-select v-model="systemSettings.schedule.source_type" style="width:160px">
                  <el-option label="全部" value="all" />
                  <el-option label="组播" value="multicast" />
                  <el-option label="酒店" value="hotel" />
                </el-select>
              </el-form-item>
              <el-form-item label="IP 版本">
                <el-radio-group v-model="systemSettings.schedule.ip_version">
                  <el-radio label="ipv4">IPv4</el-radio>
                  <el-radio label="ipv6">IPv6</el-radio>
                  <el-radio label="both">双栈</el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item label="并发数">
                <el-slider v-model="systemSettings.schedule.concurrency" :min="5" :max="100" show-input />
              </el-form-item>
              <el-form-item label="超时(秒)">
                <el-slider v-model="systemSettings.schedule.timeout" :min="2" :max="30" show-input />
              </el-form-item>
              <el-form-item label="每频道保留">
                <el-slider v-model="systemSettings.schedule.max_keep" :min="1" :max="50" show-input />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="saveSchedule">保存定时设置</el-button>
              </el-form-item>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="采集参数" name="collect">
            <el-form :model="systemSettings.settings" label-width="140px" size="default">
              <el-form-item label="默认并发数">
                <el-input-number v-model="systemSettings.settings.default_concurrency" :min="5" :max="100" />
              </el-form-item>
              <el-form-item label="默认超时(秒)">
                <el-input-number v-model="systemSettings.settings.default_timeout" :min="2" :max="30" />
              </el-form-item>
              <el-form-item label="默认保留条数">
                <el-input-number v-model="systemSettings.settings.default_max_keep" :min="1" :max="50" />
              </el-form-item>
              <el-form-item label="自动清理(天)">
                <el-input-number v-model="systemSettings.settings.auto_cleanup_days" :min="1" :max="30" />
              </el-form-item>
              <el-form-item label="最大日志数">
                <el-input-number v-model="systemSettings.settings.max_log_entries" :min="10" :max="1000" />
              </el-form-item>
              <el-form-item label="API 超时(秒)">
                <el-input-number v-model="systemSettings.settings.api_timeout" :min="10" :max="120" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="saveSystemSettings">保存系统设置</el-button>
              </el-form-item>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="关于" name="about">
            <div class="about-info">
              <h3>IPTV 聚合器 v4</h3>
              <p>功能：多源聚合、智能测速、自动择优</p>
              <p>数据来源：组播源 + 酒店源 + 订阅源 + 自定义源</p>
              <p>API 文档：<a href="/docs" target="_blank">/docs</a></p>
              <el-divider />
              <h4>支持的数据源类型</h4>
              <ul>
                <li>📡 组播源 — api.cqshushu.com/multicast.php</li>
                <li>🏨 酒店源 — api.cqshushu.com/hotel.php</li>
                <li>📋 订阅源 — M3U/TXT URL</li>
                <li>✏️ 自定义源 — 手动添加</li>
              </ul>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>

      <!-- ====== 数据库管理 ====== -->
      <div v-show="adminTab==='database'" class="admin-panel">
        <div class="panel-header">
          <h2><el-icon><Coin /></el-icon> 数据库维护</h2>
        </div>

        <el-row :gutter="16" class="db-stats">
          <el-col :span="6"><el-statistic title="活跃 IP" :value="dbStats.active_ips" /></el-col>
          <el-col :span="6"><el-statistic title="暂时失效" :value="dbStats.temp_failed_ips" /></el-col>
          <el-col :span="6"><el-statistic title="总计 IP" :value="dbStats.total_ips" /></el-col>
          <el-col :span="6"><el-statistic title="数据库大小" :value="dbStats.db_size_mb" suffix="MB" /></el-col>
        </el-row>

        <el-divider />

        <div class="db-actions">
          <h4>清理操作</h4>
          <el-button type="warning" size="small" @click="cleanupDb('failed')">清除失效 IP</el-button>
          <el-button type="warning" size="small" @click="cleanupDb('logs')">清除采集日志</el-button>
          <el-button type="warning" size="small" @click="cleanupDb('cache')">清除测速缓存</el-button>
          <el-button type="danger" size="small" @click="resetDb">⚠️ 重置所有数据</el-button>
        </div>

        <el-divider />

        <div class="db-logs">
          <h4>采集日志</h4>
          <el-table :data="dbLogs" stripe size="small" height="300">
            <el-table-column prop="created_at" label="时间" width="160" />
            <el-table-column prop="source_type" label="类型" width="100" />
            <el-table-column prop="found_count" label="发现" width="80" />
            <el-table-column prop="valid_count" label="有效" width="80" />
            <el-table-column prop="fail_count" label="失效" width="80" />
          </el-table>
        </div>
      </div>
    </main>

    <!-- ===== 对话框 ===== -->

    <!-- 添加频道 -->
    <el-dialog v-model="showAddChDlg" title="添加频道" width="480px">
      <el-form :model="newChannel" label-width="80px" size="small">
        <el-form-item label="名称" required>
          <el-input v-model="newChannel.name" placeholder="CCTV-1" />
        </el-form-item>
        <el-form-item label="分组">
          <el-select v-model="newChannel.group" allow-create filterable style="width:100%">
            <el-option v-for="g in allGroups" :key="g" :label="g" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item label="保留条数">
          <el-input-number v-model="newChannel.max_results" :min="1" :max="50" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddChDlg=false">取消</el-button>
        <el-button type="primary" @click="addChannel">添加</el-button>
      </template>
    </el-dialog>

    <!-- 批量导入频道 -->
    <el-dialog v-model="showImportChDlg" title="批量导入频道" width="560px">
      <div style="margin-bottom:12px;color:#666;font-size:13px">
        每行一个频道，格式：频道名,分组<br>
        示例：CCTV-1,央视 或 湖南卫视,卫视
      </div>
      <el-input v-model="importText" type="textarea" :rows="12" placeholder="CCTV-1,央视&#10;CCTV-2,央视&#10;湖南卫视,卫视" />
      <template #footer>
        <el-button @click="showImportChDlg=false">取消</el-button>
        <el-button type="primary" @click="importChannels">导入</el-button>
      </template>
    </el-dialog>

    <!-- 添加搜索结果 -->
    <el-dialog v-model="showAddResDlg" title="手动添加搜索结果" width="480px">
      <el-form :model="newResult" label-width="80px" size="small">
        <el-form-item label="频道名" required>
          <el-input v-model="newResult.name" placeholder="CCTV-1" />
        </el-form-item>
        <el-form-item label="URL" required>
          <el-input v-model="newResult.url" placeholder="http://..." />
        </el-form-item>
        <el-form-item label="分组">
          <el-input v-model="newResult.group" placeholder="未分组" />
        </el-form-item>
        <el-form-item label="来源">
          <el-input v-model="newResult.source_name" placeholder="手动添加" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddResDlg=false">取消</el-button>
        <el-button type="primary" @click="addResult">添加</el-button>
      </template>
    </el-dialog>

    <!-- 预览对话框 -->
    <el-dialog v-model="showPreviewDlg" title="输出预览" width="700px" top="5vh">
      <el-input v-model="previewContent" type="textarea" :rows="20" readonly />
      <template #footer>
        <el-button @click="showPreviewDlg=false">关闭</el-button>
        <el-button type="primary" @click="copyPreview">复制</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search, List, Connection, Setting, Document, Coin,
  Plus, Upload, Download, Delete, Timer, Refresh, Right, ArrowRight,
  VideoPlay, Odometer, DataAnalysis, Edit, RefreshLeft, Monitor
} from '@element-plus/icons-vue'
import request from '@/api/request'

// ============ 当前 Tab ============
const adminTab = ref('channels')

// ============ 频道管理 ============
const channels = ref([])
const chTotal = ref(0)
const chPage = ref(1)
const chPageSize = ref(50)
const chSearch = ref('')
const chGroupFilter = ref('')
const chEnabledFilter = ref('')
const chLoading = ref(false)
const selectedChannels = ref([])
const allGroups = ref([])
const batchGroup = ref('')
const showAddChDlg = ref(false)
const showImportChDlg = ref(false)
const importText = ref('')
const newChannel = reactive({ name: '', group: '未分组', enabled: true, max_results: 10 })

const filteredChannels = computed(() => {
  let data = channels.value
  if (chGroupFilter.value) data = data.filter(c => c.group === chGroupFilter.value)
  if (chEnabledFilter.value === 'true') data = data.filter(c => c.enabled)
  if (chEnabledFilter.value === 'false') data = data.filter(c => !c.enabled)
  if (chSearch.value) {
    const kw = chSearch.value.toLowerCase()
    data = data.filter(c => c.name.toLowerCase().includes(kw) || c.group.toLowerCase().includes(kw))
  }
  return data
})

async function loadChannels() {
  chLoading.value = true
  try {
    const res = await request.get('/admin/channels', {
      params: { page: chPage.value, page_size: chPageSize.value,
        group_filter: chGroupFilter.value, enabled_filter: chEnabledFilter.value, keyword: chSearch.value }
    })
    if (res?.code === 0) {
      channels.value = res.data.channels
      chTotal.value = res.data.total
      allGroups.value = res.data.groups
    }
  } finally { chLoading.value = false }
}

async function saveChannelInline(row) {
  if (row.id) {
    await request.put(`/admin/channels/${row.id}`, { name: row.name, group: row.group, enabled: row.enabled, max_results: row.max_results })
  }
}

async function deleteChannel(row) {
  await ElMessageBox.confirm(`确定删除频道「${row.name}」？`, '确认删除', { type: 'warning' })
  await request.delete(`/admin/channels/${row.id}`)
  ElMessage.success('已删除')
  loadChannels()
}

async function addChannel() {
  if (!newChannel.name.trim()) { ElMessage.warning('请输入频道名'); return }
  await request.post('/admin/channels', { ...newChannel })
  ElMessage.success('添加成功')
  showAddChDlg.value = false
  newChannel.name = ''
  loadChannels()
}

async function importChannels() {
  if (!importText.value.trim()) return
  const lines = importText.value.trim().split('\n').filter(l => l.trim())
  const items = lines.map(l => {
    const p = l.split(',')
    return { name: p[0].trim(), group: p[1]?.trim() || '未分组', enabled: true, max_results: 10 }
  })
  const res = await request.post('/admin/channels/batch', items)
  if (res?.code === 0) ElMessage.success(res.message)
  showImportChDlg.value = false
  importText.value = ''
  loadChannels()
}

async function batchEnable(enabled) {
  const ids = selectedChannels.value.map(c => c.id)
  await request.post('/admin/channels/batch?action=' + (enabled ? 'enable' : 'disable'), ids)
  ElMessage.success(`已${enabled ? '启用' : '禁用'} ${ids.length} 个频道`)
  loadChannels()
}

async function batchChangeGroup() {
  if (!batchGroup.value) { ElMessage.warning('请选择目标分组'); return }
  const ids = selectedChannels.value.map(c => c.id)
  await request.post(`/admin/channels/batch?action=change_group&group=${batchGroup.value}`, ids)
  ElMessage.success(`已移动 ${ids.length} 个频道`)
  loadChannels()
}

async function batchDelete() {
  await ElMessageBox.confirm(`确定删除 ${selectedChannels.value.length} 个频道？`, '批量删除', { type: 'warning' })
  const ids = selectedChannels.value.map(c => c.id)
  await request.post('/admin/channels/batch?action=delete', ids)
  ElMessage.success(`已删除`)
  loadChannels()
}

function exportChannels() {
  window.open('/api/admin/channels/export?format=json', '_blank')
}

// ============ 搜索结果管理 ============
const results = ref([])
const resTotal = ref(0)
const resPage = ref(1)
const resPageSize = ref(50)
const resSearch = ref('')
const resGroupFilter = ref('')
const resSortBy = ref('name')
const resSortOrder = ref('asc')
const resLoading = ref(false)
const resGroups = ref([])
const showAddResDlg = ref(false)
const newResult = reactive({ name: '', url: '', group: '未分组', source_name: '手动添加' })

const filteredResults = computed(() => {
  let data = [...results.value]
  if (resGroupFilter.value) data = data.filter(r => r.group === resGroupFilter.value)
  if (resSearch.value) {
    const kw = resSearch.value.toLowerCase()
    data = data.filter(r => r.name?.toLowerCase().includes(kw) || r.url?.toLowerCase().includes(kw))
  }
  const reverse = resSortOrder.value === 'desc'
  data.sort((a, b) => {
    let va = resSortBy.value === 'response_time' ? (a.response_time || 0) : (a[resSortBy.value] || '')
    let vb = resSortBy.value === 'response_time' ? (b.response_time || 0) : (b[resSortBy.value] || '')
    if (va < vb) return reverse ? 1 : -1
    if (va > vb) return reverse ? -1 : 1
    return 0
  })
  return data
})

async function loadResults() {
  resLoading.value = true
  try {
    const res = await request.get('/admin/results', {
      params: { page: resPage.value, page_size: resPageSize.value,
        keyword: resSearch.value, group_filter: resGroupFilter.value,
        sort_by: resSortBy.value, sort_order: resSortOrder.value }
    })
    if (res?.code === 0) {
      results.value = res.data.results
      resTotal.value = res.data.total
      resGroups.value = res.data.groups
    }
  } finally { resLoading.value = false }
}

async function saveResultInline(row) {
  const idx = results.value.indexOf(row)
  if (idx >= 0) {
    await request.put(`/admin/results/${idx}`, { name: row.name, url: row.url, group: row.group, source_name: row.source_name })
  }
}

async function deleteResult(row) {
  const idx = results.value.indexOf(row)
  if (idx >= 0) {
    await request.delete(`/admin/results/${idx}`)
    ElMessage.success('已删除')
    loadResults()
  }
}

async function addResult() {
  if (!newResult.name.trim() || !newResult.url.trim()) { ElMessage.warning('名称和 URL 不能为空'); return }
  await request.post('/admin/results', { ...newResult })
  ElMessage.success('添加成功')
  showAddResDlg.value = false
  newResult.name = ''; newResult.url = ''
  loadResults()
}

async function clearAllResults() {
  await ElMessageBox.confirm('确定清空所有搜索结果？', '确认', { type: 'warning' })
  await request.delete('/admin/results')
  ElMessage.success('已清空')
  loadResults()
}

// ============ 输出配置 ============
const outputConfig = reactive({
  m3u_header: '#EXTM3U', txt_separator: ',',
  include_group: true, include_logo: true, include_epg: true,
  sort_by: 'name', sort_order: 'asc',
  filter_protocol: 'all', filter_max_response: 0, group_emoji: true,
})
const outputSaving = ref(false)
const showPreviewDlg = ref(false)
const previewContent = ref('')

async function loadOutputConfig() {
  const res = await request.get('/admin/output-config')
  if (res?.code === 0) Object.assign(outputConfig, res.data)
}

async function saveOutputConfig() {
  outputSaving.value = true
  await request.post('/admin/output-config', { ...outputConfig })
  outputSaving.value = false
  ElMessage.success('保存成功')
}

async function previewM3U() {
  const res = await request.get('/admin/preview/m3u')
  previewContent.value = typeof res === 'string' ? res : JSON.stringify(res, null, 2)
  showPreviewDlg.value = true
}

async function previewTXT() {
  const res = await request.get('/admin/preview/txt')
  previewContent.value = typeof res === 'string' ? res : JSON.stringify(res, null, 2)
  showPreviewDlg.value = true
}

function dlM3U() { window.open('/api/export/m3u', '_blank') }
function dlTXT() { window.open('/api/export/txt', '_blank') }
function copyPreview() {
  navigator.clipboard.writeText(previewContent.value)
  ElMessage.success('已复制')
}

// ============ 系统设置 ============
const systemTab = ref('schedule')
const systemSettings = reactive({
  settings: { auto_cleanup_days: 7, max_log_entries: 100, default_concurrency: 20, default_timeout: 5, default_max_keep: 10, api_timeout: 30 },
  schedule: { enabled: false, hour: 3, minute: 0, source_type: 'all', ip_version: 'ipv4', concurrency: 20, timeout: 5, max_keep: 10 },
})

async function loadSystemSettings() {
  const res = await request.get('/admin/settings')
  if (res?.code === 0) {
    if (res.data.settings) Object.assign(systemSettings.settings, res.data.settings)
    if (res.data.schedule) Object.assign(systemSettings.schedule, res.data.schedule)
  }
}

async function saveSchedule() {
  await request.post('/admin/schedule', { ...systemSettings.schedule })
  ElMessage.success('定时设置已保存')
}

async function saveSystemSettings() {
  await request.post('/admin/settings', { ...systemSettings.settings })
  ElMessage.success('系统设置已保存')
}

// ============ 数据库 ============
const dbStats = ref({ active_ips: 0, temp_failed_ips: 0, total_ips: 0, db_size_mb: 0 })
const dbLogs = ref([])

async function loadDbStats() {
  const res = await request.get('/admin/db/stats')
  if (res?.code === 0) dbStats.value = res.data
}

async function loadDbLogs() {
  const res = await request.get('/admin/db/logs', { params: { limit: 20 } })
  if (res?.code === 0) dbLogs.value = res.data
}

async function cleanupDb(type) {
  const params = new URLSearchParams()
  if (type === 'failed') params.set('clear_failed', 'true')
  if (type === 'logs') params.set('clear_logs', 'true')
  if (type === 'cache') params.set('clear_speed_cache', 'true')
  await request.post(`/admin/db/cleanup?${params}`)
  ElMessage.success('清理完成')
  loadDbStats()
  loadDbLogs()
}

async function resetDb() {
  await ElMessageBox.confirm('确定重置所有数据？此操作不可恢复！', '⚠️ 危险操作', { type: 'error' })
  await request.post('/admin/db/reset')
  ElMessage.success('已重置')
  loadDbStats()
  loadDbLogs()
}

// ============ 初始化 ============
onMounted(() => {
  loadChannels()
  loadResults()
  loadOutputConfig()
  loadSystemSettings()
  loadDbStats()
  loadDbLogs()
})

watch(adminTab, (tab) => {
  if (tab === 'channels') loadChannels()
  if (tab === 'results') loadResults()
  if (tab === 'output') loadOutputConfig()
  if (tab === 'system') loadSystemSettings()
  if (tab === 'database') { loadDbStats(); loadDbLogs() }
})
</script>

<style scoped>
.admin-layout { display: flex; height: calc(100vh - 52px); }
.admin-sidebar { width: 180px; background: #1e293b; color: #94a3b8; flex-shrink: 0; }
.sidebar-header { padding: 16px; font-size: 15px; font-weight: 600; color: #e2e8f0; display: flex; align-items: center; gap: 8px; border-bottom: 1px solid #334155; }
.sidebar-nav { padding: 8px 0; }
.nav-item { padding: 10px 16px; cursor: pointer; display: flex; align-items: center; gap: 8px; font-size: 13px; transition: all .2s; }
.nav-item:hover { background: #334155; color: #e2e8f0; }
.nav-item.active { background: #0f172a; color: #38bdf8; border-right: 3px solid #38bdf8; }
.admin-content { flex: 1; overflow: auto; padding: 16px; background: #f8fafc; }
.admin-panel { background: #fff; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.08); min-height: calc(100vh - 84px); }
.panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #e2e8f0; }
.panel-header h2 { font-size: 16px; display: flex; align-items: center; gap: 8px; margin: 0; }
.panel-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.batch-bar { background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 8px 12px; margin-bottom: 12px; display: flex; align-items: center; gap: 10px; font-size: 13px; }
.batch-bar span { color: #1d4ed8; font-weight: 600; }
.pagination-bar { display: flex; justify-content: flex-end; padding-top: 12px; }
.form-hint { color: #94a3b8; font-size: 12px; margin-left: 8px; }
.preview-btns { display: flex; gap: 8px; margin-top: 12px; }
.db-stats { margin-bottom: 16px; }
.db-actions { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.db-actions h4 { margin: 0 8px 0 0; font-size: 14px; }
.db-logs { margin-top: 16px; }
.db-logs h4 { margin: 0 0 8px 0; font-size: 14px; }
.about-info { padding: 16px; }
.about-info h3 { margin: 0 0 8px; }
.about-info p { color: #64748b; margin: 4px 0; }
.about-info ul { padding-left: 20px; }
.about-info li { margin: 4px 0; }
</style>
