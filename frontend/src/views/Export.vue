<template>
  <div class="export-page">
    <div class="page-header">
      <h2>导出管理</h2>
      <p class="page-desc">导出 M3U / TXT / JSON 格式的播放列表</p>
    </div>

    <!-- 筛选 -->
    <el-card class="export-card mt-4">
      <template #header>
        <span class="card-title">筛选条件</span>
      </template>
      <el-form :inline="true" size="default">
        <el-form-item label="地区">
          <el-select v-model="filter.region" placeholder="全部" clearable style="width: 140px">
            <el-option v-for="r in regions" :key="r" :label="r" :value="r" />
          </el-select>
        </el-form-item>
        <el-form-item label="运营商">
          <el-select v-model="filter.operator" placeholder="全部" clearable style="width: 140px">
            <el-option v-for="o in operators" :key="o" :label="o" :value="o" />
          </el-select>
        </el-form-item>
        <el-form-item label="分组">
          <el-select v-model="filter.group" placeholder="全部" clearable style="width: 160px">
            <el-option v-for="g in groups" :key="g" :label="g" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="queryPreview">
            <el-icon><Search /></el-icon>查询
          </el-button>
          <el-button @click="resetFilter">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 导出操作 -->
    <el-row :gutter="16" class="mt-4">
      <el-col :xs="24" :sm="8">
        <div class="export-action-card m3u-card" @click="downloadExport('m3u')">
          <div class="ea-icon"><el-icon :size="36"><Document /></el-icon></div>
          <h3>导出 M3U</h3>
          <p>标准 M3U 格式，兼容大多数播放器</p>
          <div class="ea-count">预览: 约 {{ channelCount }} 频道</div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="8">
        <div class="export-action-card txt-card" @click="downloadExport('txt')">
          <div class="ea-icon"><el-icon :size="36"><List /></el-icon></div>
          <h3>导出 TXT</h3>
          <p>简洁 TXT 格式，频道名,URL</p>
          <div class="ea-count">预览: 约 {{ channelCount }} 频道</div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="8">
        <div class="export-action-card json-card" @click="downloadExport('json')">
          <div class="ea-icon"><el-icon :size="36"><DataAnalysis /></el-icon></div>
          <h3>导出 JSON</h3>
          <p>JSON 格式，适合程序处理</p>
          <div class="ea-count">预览: 约 {{ channelCount }} 频道</div>
        </div>
      </el-col>
    </el-row>

    <!-- 导出全部（自动搜索） -->
    <el-card class="export-card mt-4">
      <template #header>
        <span class="card-title">自动搜索并导出</span>
      </template>
      <div class="auto-export-area">
        <div>
          <p>自动搜索所有内置 IPTV 源，验证后导出有效频道</p>
          <p class="hint">此操作将搜索 ~{{ builtinSourceCount }} 个源，可能需要几分钟</p>
        </div>
        <el-button type="success" @click="autoSearchAndExport" :loading="autoExporting">
          <el-icon><Search /></el-icon>搜索并导出 M3U
        </el-button>
      </div>
    </el-card>

    <!-- 频道预览 -->
    <el-card class="export-card mt-4">
      <template #header>
        <span class="card-title">频道预览 <span style="color:#94a3b8;font-size:13px">(前 50 条)</span></span>
      </template>
      <el-table :data="previewChannels" stripe size="small" height="400">
        <el-table-column type="index" width="60" />
        <el-table-column prop="name" label="频道名" min-width="150" />
        <el-table-column prop="group_title" label="分组" width="120" />
        <el-table-column prop="region" label="地区" width="100" />
        <el-table-column prop="operator" label="运营商" width="100" />
        <el-table-column label="播放地址" min-width="200">
          <template #default="{ row }">
            <el-link type="info" :href="row.url" target="_blank" :underline="false" style="font-size:12px">
              {{ row.url?.substring(0, 60) }}...
            </el-link>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { apiGetChannels, apiGetExportM3u, apiGetExportTxt, apiGetExportJson } from '@/api/export'
import { apiGetBuiltins } from '@/api/search'

const filter = reactive({ region: '', operator: '', group: '' })
const regions = ref([])
const operators = ref([])
const groups = ref([])
const channelCount = ref(0)
const builtinSourceCount = ref(0)
const autoExporting = ref(false)
const previewChannels = ref([])

onMounted(async () => {
  try {
    const chRes = await apiGetChannels({ page: 1, page_size: 1 })
    channelCount.value = chRes?.total || 0

    // 获取内置源数量
    const builtins = await apiGetBuiltins()
    builtinSourceCount.value = builtins?.length || 0
  } catch {}
})

async function queryPreview() {
  try {
    const res = await apiGetChannels({
      page: 1, page_size: 50,
      region: filter.region || undefined,
      operator: filter.operator || undefined,
      group: filter.group || undefined,
    })
    previewChannels.value = res?.list || []
    channelCount.value = res?.total || 0
  } catch (e) {
    ElMessage.error('查询失败')
  }
}

function resetFilter() {
  filter.region = ''
  filter.operator = ''
  filter.group = ''
  queryPreview()
}

function downloadExport(format) {
  const params = new URLSearchParams()
  if (filter.region) params.set('region', filter.region)
  if (filter.operator) params.set('operator', filter.operator)
  if (filter.group) params.set('group', filter.group)

  const url = `/api/export/${format}?${params.toString()}`
  window.open(url, '_blank')
}

async function autoSearchAndExport() {
  autoExporting.value = true
  try {
    window.open('/api/export/m3u/auto', '_blank')
    ElMessage.success('自动搜索已开始，完成后自动下载')
  } finally {
    autoExporting.value = false
  }
}
</script>

<style scoped>
.export-page { }
.page-header h2 { font-size: 20px; font-weight: 600; color: #e2e8f0; margin: 0; }
.page-desc { color: #94a3b8; font-size: 13px; margin-top: 4px; }

.export-card { background: #1e293b; border-color: #334155; }
.card-title { font-size: 15px; font-weight: 600; color: #e2e8f0; }

.export-action-card {
  background: #0f172a; border: 1px solid #334155; border-radius: 12px;
  padding: 24px; text-align: center; cursor: pointer; transition: all 0.3s;
  height: 100%;
}
.export-action-card:hover { transform: translateY(-2px); }
.m3u-card:hover { border-color: #06b6d4; box-shadow: 0 0 20px rgba(6,182,212,0.15); }
.txt-card:hover { border-color: #22c55e; box-shadow: 0 0 20px rgba(34,197,94,0.15); }
.json-card:hover { border-color: #a855f7; box-shadow: 0 0 20px rgba(168,85,247,0.15); }

.ea-icon { width: 64px; height: 64px; border-radius: 14px; display: flex; align-items: center; justify-content: center; margin: 0 auto 12px; }
.m3u-card .ea-icon { background: rgba(6,182,212,0.15); color: #06b6d4; }
.txt-card .ea-icon { background: rgba(34,197,94,0.15); color: #22c55e; }
.json-card .ea-icon { background: rgba(168,85,247,0.15); color: #a855f7; }

.export-action-card h3 { font-size: 18px; color: #e2e8f0; margin: 0 0 6px; }
.export-action-card p { font-size: 12px; color: #94a3b8; margin: 0 0 12px; }
.ea-count { font-size: 13px; color: #06b6d4; }

.auto-export-area { display: flex; justify-content: space-between; align-items: center; }
.auto-export-area p { color: #94a3b8; font-size: 13px; margin: 0 0 4px; }
.auto-export-area .hint { color: #64748b; font-size: 12px; }

.mt-4 { margin-top: 16px; }
</style>
