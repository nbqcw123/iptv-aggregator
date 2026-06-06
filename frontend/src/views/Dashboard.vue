<template>
  <div class="dashboard animate-slide-in">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-cards">
      <el-col :xs="24" :sm="12" :md="6" v-for="card in statCards" :key="card.key">
        <div class="stat-card" :class="`stat-card--${card.color}`">
          <div class="stat-icon">
            <el-icon :size="24"><component :is="card.icon" /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ card.value }}</div>
            <div class="stat-label">{{ card.label }}</div>
          </div>
          <div class="stat-trend" v-if="card.trend !== undefined">
            <el-icon :size="14" :class="card.trend >= 0 ? 'trend-up' : 'trend-down'">
              <Top v-if="card.trend >= 0" /><Bottom v-else />
            </el-icon>
            <span :class="card.trend >= 0 ? 'trend-up' : 'trend-down'">
              {{ Math.abs(card.trend) }}%
            </span>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :span="16">
        <el-card class="chart-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span>频道趋势</span>
              <el-radio-group v-model="trendPeriod" size="small">
                <el-radio-button label="7d">近7天</el-radio-button>
                <el-radio-button label="30d">近30天</el-radio-button>
                <el-radio-button label="90d">近90天</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div ref="trendChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="chart-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span>源状态分布</span>
            </div>
          </template>
          <div ref="pieChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 最近活动 & 热门频道 -->
    <el-row :gutter="16" class="bottom-row">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>最近搜索结果</span>
              <el-button text type="primary" size="small" @click="$router.push('/search')">
                查看全部
              </el-button>
            </div>
          </template>
          <el-table :data="recentTasks" stripe size="small">
            <el-table-column prop="keyword" label="关键词" min-width="120" />
            <el-table-column prop="results" label="结果数" width="80" align="center" />
            <el-table-column prop="status" label="状态" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">
                  {{ getStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="time" label="时间" width="140" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>源验证状态</span>
              <el-button text type="primary" size="small" @click="$router.push('/sources')">
                管理源
              </el-button>
            </div>
          </template>
          <div class="source-status-list">
            <div class="source-status-item" v-for="item in sourceStatusList" :key="item.name">
              <div class="source-status-info">
                <span class="status-dot" :class="`dot--${item.status}`"></span>
                <span class="source-name">{{ item.name }}</span>
              </div>
              <el-progress
                :percentage="item.percentage"
                :color="getProgressColor(item.percentage)"
                :stroke-width="6"
                :show-text="false"
              />
              <span class="status-text">{{ item.count }} / {{ item.total }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as echarts from 'echarts'
import { channelsApi, sourcesApi, searchApi } from '@/api/channels'
import '@/api/sources'
import '@/api/search'

const trendPeriod = ref('7d')
const trendChartRef = ref(null)
const pieChartRef = ref(null)
const recentTasks = ref([])
const sourceStatusList = ref([])

const statCards = ref([
  { key: 'channels', label: '频道总数', value: 0, icon: 'Monitor', color: 'blue', trend: 12 },
  { key: 'sources', label: '源总数', value: 0, icon: 'Connection', color: 'cyan', trend: 5 },
  { key: 'valid', label: '有效源', value: 0, icon: 'CircleCheck', color: 'green', trend: 8 },
  { key: 'today', label: '今日新增', value: 0, icon: 'Plus', color: 'purple', trend: -3 },
])

let trendChart = null
let pieChart = null

const getStatusType = (status) => {
  const map = { completed: 'success', running: 'warning', failed: 'danger', pending: 'info' }
  return map[status] || 'info'
}

const getStatusText = (status) => {
  const map = { completed: '已完成', running: '运行中', failed: '失败', pending: '等待中' }
  return map[status] || status
}

const getProgressColor = (pct) => {
  if (pct >= 80) return '#10b981'
  if (pct >= 50) return '#f59e0b'
  return '#ef4444'
}

function initTrendChart() {
  if (!trendChartRef.value) return
  trendChart = echarts.init(trendChartRef.value, 'dark')
  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1a2235',
      borderColor: '#2a3a5c',
      textStyle: { color: '#e5e7eb' },
    },
    legend: {
      data: ['频道数', '有效源'],
      textStyle: { color: '#9ca3af' },
      top: 0,
    },
    grid: { top: 40, right: 20, bottom: 30, left: 50 },
    xAxis: {
      type: 'category',
      data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
      axisLine: { lineStyle: { color: '#2a3a5c' } },
      axisLabel: { color: '#9ca3af' },
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#2a3a5c' } },
      axisLabel: { color: '#9ca3af' },
      splitLine: { lineStyle: { color: '#1a2235' } },
    },
    series: [
      {
        name: '频道数',
        type: 'line',
        smooth: true,
        data: [820, 932, 901, 934, 1290, 1330, 1320],
        lineStyle: { color: '#3b82f6', width: 2 },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
              { offset: 1, color: 'rgba(59, 130, 246, 0)' },
            ],
          },
        },
        itemStyle: { color: '#3b82f6' },
      },
      {
        name: '有效源',
        type: 'line',
        smooth: true,
        data: [220, 332, 401, 434, 590, 630, 720],
        lineStyle: { color: '#06b6d4', width: 2 },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(6, 182, 212, 0.3)' },
              { offset: 1, color: 'rgba(6, 182, 212, 0)' },
            ],
          },
        },
        itemStyle: { color: '#06b6d4' },
      },
    ],
  }
  trendChart.setOption(option)
}

function initPieChart() {
  if (!pieChartRef.value) return
  pieChart = echarts.init(pieChartRef.value, 'dark')
  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: '#1a2235',
      borderColor: '#2a3a5c',
      textStyle: { color: '#e5e7eb' },
      formatter: '{b}: {c} ({d}%)',
    },
    legend: {
      orient: 'vertical',
      right: '5%',
      top: 'center',
      textStyle: { color: '#9ca3af' },
    },
    series: [
      {
        type: 'pie',
        radius: ['45%', '70%'],
        center: ['35%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 8,
          borderColor: '#1a2235',
          borderWidth: 2,
        },
        label: { show: false },
        data: [
          { value: 856, name: '有效源', itemStyle: { color: '#10b981' } },
          { value: 124, name: '无效源', itemStyle: { color: '#ef4444' } },
          { value: 67, name: '待验证', itemStyle: { color: '#f59e0b' } },
        ],
      },
    ],
  }
  pieChart.setOption(option)
}

async function fetchDashboardData() {
  try {
    const [channelsRes, sourcesRes, tasksRes] = await Promise.allSettled([
      channelsApi.getStats(),
      sourcesApi.getStats(),
      searchApi.getTasks({ page: 1, pageSize: 5 }),
    ])

    if (channelsRes.status === 'fulfilled') {
      const d = channelsRes.value.data || channelsRes.value
      statCards.value[0].value = d.total || d.channelCount || 0
      statCards.value[3].value = d.todayAdded || d.today || 0
    }

    if (sourcesRes.status === 'fulfilled') {
      const d = sourcesRes.value.data || sourcesRes.value
      statCards.value[1].value = d.total || d.sourceCount || 0
      statCards.value[2].value = d.valid || d.validCount || 0
    }

    if (tasksRes.status === 'fulfilled') {
      const d = tasksRes.value.data || tasksRes.value
      const list = (d.list || d.records || []).map(t => ({
        keyword: t.keyword || t.name || '-',
        results: t.results || t.resultCount || 0,
        status: t.status || 'completed',
        time: t.createdAt || t.time || '-',
      }))
      recentTasks.value = list
    } else {
      recentTasks.value = [
        { keyword: 'CCTV1', results: 8, status: 'completed', time: '2026-01-15 14:30' },
        { keyword: '湖南卫视', results: 5, status: 'completed', time: '2026-01-15 14:25' },
        { keyword: '浙江卫视', results: 6, status: 'running', time: '2026-01-15 14:20' },
      ]
    }

    sourceStatusList.value = [
      { name: '官方源', status: 'valid', percentage: 95, count: 95, total: 100 },
      { name: '第三方源A', status: 'valid', percentage: 78, count: 78, total: 100 },
      { name: '第三方源B', status: 'warning', percentage: 56, count: 56, total: 100 },
      { name: '自建源', status: 'invalid', percentage: 23, count: 23, total: 100 },
    ]
  } catch (e) {
    console.error('fetchDashboardData error:', e)
  }
}

function handleResize() {
  trendChart?.resize()
  pieChart?.resize()
}

onMounted(() => {
  initTrendChart()
  initPieChart()
  fetchDashboardData()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  pieChart?.dispose()
})

watch(trendPeriod, () => {
  fetchDashboardData()
})
</script>

<style scoped>
.dashboard {
  min-height: 100%;
}

.stat-cards {
  margin-bottom: 16px;
}

.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 14px;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.stat-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
}

.stat-card--blue::before { background: linear-gradient(90deg, #3b82f6, #2563eb); }
.stat-card--cyan::before { background: linear-gradient(90deg, #06b6d4, #0891b2); }
.stat-card--green::before { background: linear-gradient(90deg, #10b981, #059669); }
.stat-card--purple::before { background: linear-gradient(90deg, #8b5cf6, #7c3aed); }

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
}

.stat-icon {
  width: 50px;
  height: 50px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-card--blue .stat-icon { background: rgba(59, 130, 246, 0.15); color: #3b82f6; }
.stat-card--cyan .stat-icon { background: rgba(6, 182, 212, 0.15); color: #06b6d4; }
.stat-card--green .stat-icon { background: rgba(16, 185, 129, 0.15); color: #10b981; }
.stat-card--purple .stat-icon { background: rgba(139, 92, 246, 0.15); color: #8b5cf6; }

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 4px;
}

.stat-trend {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 600;
}

.trend-up { color: #10b981; }
.trend-down { color: #ef4444; }

.chart-row,
.bottom-row {
  margin-bottom: 16px;
}

.chart-card {
  height: 340px;
}

.chart-container {
  height: 280px;
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header span {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.source-status-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 8px 0;
}

.source-status-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.source-status-info {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 110px;
  flex-shrink: 0;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot--valid { background: #10b981; box-shadow: 0 0 6px rgba(16, 185, 129, 0.5); }
.dot--warning { background: #f59e0b; box-shadow: 0 0 6px rgba(245, 158, 11, 0.5); }
.dot--invalid { background: #ef4444; box-shadow: 0 0 6px rgba(239, 68, 68, 0.5); }

.source-name {
  font-size: 13px;
  color: var(--text-secondary);
}

.source-status-item :deep(.el-progress) {
  flex: 1;
  margin: 0;
}

.status-text {
  font-size: 12px;
  color: var(--text-muted);
  width: 70px;
  text-align: right;
  flex-shrink: 0;
}
</style>
