<template>
  <div class="channels-page animate-slide-in">
    <!-- 搜索筛选区 -->
    <el-card shadow="never" class="filter-card" :body-style="{ padding: '16px' }">
      <el-form :model="filterForm" inline>
        <el-form-item label="关键词">
          <el-input
            v-model="filterForm.keyword"
            placeholder="搜索频道名称/URL"
            clearable
            style="width: 200px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="地区">
          <el-select
            v-model="filterForm.region"
            placeholder="选择地区"
            clearable
            style="width: 140px"
          >
            <el-option
              v-for="item in regionOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="运营商">
          <el-select
            v-model="filterForm.isp"
            placeholder="选择运营商"
            clearable
            style="width: 140px"
          >
            <el-option
              v-for="item in ispOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="分组">
          <el-select
            v-model="filterForm.group"
            placeholder="选择分组"
            clearable
            style="width: 140px"
          >
            <el-option
              v-for="item in groupOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="filterForm.status"
            placeholder="选择状态"
            clearable
            style="width: 120px"
          >
            <el-option label="全部" value="" />
            <el-option label="可用" value="valid" />
            <el-option label="不可用" value="invalid" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>搜索
          </el-btn>
          <el-button @click="handleReset" style="margin-left: 8px">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button type="primary" @click="handleAdd">
          <el-icon><Plus /></el-icon>新增频道
        </el-button>
        <el-button type="success" :disabled="!selectedRows.length" @click="handleBatchValid">
          <el-icon><CircleCheck /></el-icon>批量启用
        </el-button>
        <el-button type="warning" :disabled="!selectedRows.length" @click="handleBatchInvalid">
          <el-icon><CircleClose /></el-icon>批量禁用
        </el-button>
        <el-button type="danger" :disabled="!selectedRows.length" @click="handleBatchDelete">
          <el-icon><Delete /></el-icon>批量删除
          <span v-if="selectedRows.length" class="selected-count">({{ selectedRows.length }})</span>
        </el-button>
      </div>
      <div class="toolbar-right">
        <el-button @click="handleRefresh" :loading="loading">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
      </div>
    </div>

    <!-- 频道表格 -->
    <el-card shadow="never" class="table-card">
      <el-table
        :data="tableData"
        v-loading="loading"
        @selection-change="handleSelectionChange"
        stripe
        row-key="id"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column prop="name" label="频道名称" min-width="160">
          <template #default="{ row }">
            <div class="channel-name-cell">
              <span class="channel-name">{{ row.name }}</span>
              <el-tag v-if="row.hd" type="warning" size="small" class="hd-tag">HD</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="group" label="分组" width="120">
          <template #default="{ row }">
            <el-tag type="info" size="small">{{ row.group || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="region" label="地区" width="100">
          <template #default="{ row }">
            <span>{{ row.region || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="isp" label="运营商" width="100" />
        <el-table-column prop="sourceCount" label="源数量" width="90" align="center">
          <template #default="{ row }">
            <span class="source-count">{{ row.sourceCount || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="url" label="播放地址" min-width="280" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.statusVal"
              :active-value="true"
              :inactive-value="false"
              @change="val => handleStatusChange(row, val)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleEdit(row)">
              <el-icon><Edit /></el-icon>
            </el-button>
            <el-button type="primary" link size="small" @click="handleCopyUrl(row)">
              <el-icon><CopyDocument /></el-icon>
            </el-button>
            <el-popconfirm
              title="确定删除该频道吗？"
              @confirm="handleDelete(row)"
              width="200"
            >
              <template #reference>
                <el-button type="danger" link size="small">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-area">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handlePageChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑频道' : '新增频道'"
      width="560px"
      destroy-on-close
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="80px"
      >
        <el-form-item label="频道名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入频道名称" />
        </el-form-item>
        <el-form-item label="分组" prop="group">
          <el-input v-model="formData.group" placeholder="请输入分组名称" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="地区" prop="region">
              <el-input v-model="formData.region" placeholder="如：北京" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="运营商" prop="isp">
              <el-input v-model="formData.isp" placeholder="如：电信" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="播放地址" prop="url">
          <el-input
            v-model="formData.url"
            type="textarea"
            :rows="3"
            placeholder="请输入播放地址，支持 rtsp/http/rtp 等协议"
          />
        </el-form-item>
        <el-form-item label="台标" prop="logo">
          <el-input v-model="formData.logo" placeholder="台标图片URL（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitLoading">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { channelsApi } from '@/api/channels'

// 筛选表单
const filterForm = reactive({
  keyword: '',
  region: '',
  isp: '',
  group: '',
  status: '',
})

// 选项数据
const regionOptions = ref([
  { label: '北京', value: '北京' },
  { label: '上海', value: '上海' },
  { label: '广东', value: '广东' },
  { label: '浙江', value: '浙江' },
  { label: '江苏', value: '江苏' },
  { label: '四川', value: '四川' },
])

const ispOptions = ref([
  { label: '电信', value: '电信' },
  { label: '联通', value: '联通' },
  { label: '移动', value: '移动' },
  { label: '广电', value: '广电' },
])

const groupOptions = ref([
  { label: '央视频道', value: '央视频道' },
  { label: '卫视频道', value: '卫视频道' },
  { label: '地方频道', value: '地方频道' },
  { label: '体育频道', value: '体育频道' },
  { label: '影视频道', value: '影视频道' },
])

const search = () => console.log('search')

// 表格
const loading = ref(false)
const tableData = ref([])
const selectedRows = ref([])
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

// 弹窗
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitLoading = ref(false)
const formRef = ref(null)

const formData = reactive({
  id: null,
  name: '',
  group: '',
  region: '',
  isp: '',
  url: '',
  logo: '',
})

const formRules = {
  name: [{ required: true, message: '请输入频道名称', trigger: 'blur' }],
  url: [{ required: true, message: '请输入播放地址', trigger: 'blur' }],
}

// 获取频道列表
async function fetchChannels() {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      pageSize: pagination.pageSize,
      ...filterForm,
    }
    const res = await channelsApi.getList(params)
    const data = res.data || res
    tableData.value = (data.list || data.records || []).map(item => ({
      ...item,
      statusVal: item.status === 'valid' || item.enabled,
    }))
    pagination.total = data.total || tableData.value.length
  } catch (e) {
    // 演示数据
    tableData.value = [
      { id: 1, name: 'CCTV-1 综合', group: '央视频道', region: '北京', isp: '电信', sourceCount: 5, url: 'http://example.com/cctv1.m3u8', statusVal: true, hd: true },
      { id: 2, name: 'CCTV-2 财经', group: '央视频道', region: '北京', isp: '电信', sourceCount: 3, url: 'http://example.com/cctv2.m3u8', statusVal: true, hd: false },
      { id: 3, name: '湖南卫视', group: '卫视频道', region: '湖南', isp: '电信', sourceCount: 8, url: 'http://example.com/hunan.m3u8', statusVal: true, hd: true },
      { id: 4, name: '浙江卫视', group: '卫视频道', region: '浙江', isp: '联通', sourceCount: 6, url: 'http://example.com/zhejiang.m3u8', statusVal: true, hd: true },
      { id: 5, name: '东方卫视', group: '卫视频道', region: '上海', isp: '电信', sourceCount: 4, url: 'http://example.com/dongfang.m3u8', statusVal: false, hd: true },
      { id: 6, name: '广东卫视', group: '卫视频道', region: '广东', isp: '电信', sourceCount: 3, url: 'http://example.com/guangdong.m3u8', statusVal: true, hd: false },
      { id: 7, name: '深圳卫视', group: '卫视频道', region: '广东', isp: '移动', sourceCount: 5, url: 'http://example.com/shenzhen.m3u8', statusVal: true, hd: true },
      { id: 8, name: '江苏卫视', group: '卫视频道', region: '江苏', isp: '电信', sourceCount: 4, url: 'http://example.com/jiangsu.m3u8', statusVal: true, hd: true },
    ]
    pagination.total = 8
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  pagination.page = 1
  fetchChannels()
}

// 重置
const handleReset = () => {
  Object.assign(filterForm, { keyword: '', region: '', isp: '', group: '', status: '' })
  pagination.page = 1
  fetchChannels()
}

// 刷新
const handleRefresh = () => fetchChannels()

// 分页
const handlePageChange = () => fetchChannels()

// 多选
const handleSelectionChange = (rows) => {
  selectedRows.value = rows
}

// 新增
const handleAdd = () => {
  isEdit.value = false
  Object.assign(formData, { id: null, name: '', group: '', region: '', isp: '', url: '', logo: '' })
  dialogVisible.value = true
}

// 编辑
const handleEdit = (row) => {
  isEdit.value = true
  Object.assign(formData, { ...row })
  dialogVisible.value = true
}

// 提交
const handleSubmit = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitLoading.value = true
  try {
    if (isEdit.value) {
      await channelsApi.update(formData.id, formData)
      ElMessage.success('编辑成功')
    } else {
      await channelsApi.create(formData)
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    fetchChannels()
  } catch (e) {
    ElMessage.success(isEdit.value ? '编辑成功（演示）' : '新增成功（演示）')
    dialogVisible.value = false
  } finally {
    submitLoading.value = false
  }
}

// 删除
const handleDelete = async (row) => {
  try {
    await channelsApi.delete(row.id)
    ElMessage.success('删除成功')
    fetchChannels()
  } catch (e) {
    ElMessage.success('删除成功（演示）')
  }
}

// 状态切换
const handleStatusChange = async (row, val) => {
  try {
    await channelsApi.update(row.id, { status: val ? 'valid' : 'invalid' })
    ElMessage.success('状态已更新')
  } catch (e) {
    ElMessage.success('状态已更新（演示）')
  }
}

// 复制URL
const handleCopyUrl = (row) => {
  navigator.clipboard.writeText(row.url).then(() => {
    ElMessage.success('播放地址已复制到剪贴板')
  })
}

// 批量操作
const handleBatchValid = async () => {
  await channelsApi.batchUpdate({ ids: selectedRows.value.map(r => r.id), status: 'valid' })
  ElMessage.success('批量启用成功')
  fetchChannels()
}

const handleBatchInvalid = async () => {
  await channelsApi.batchUpdate({ ids: selectedRows.value.map(r => r.id), status: 'invalid' })
  ElMessage.success('批量禁用成功')
  fetchChannels()
}

const handleBatchDelete = async () => {
  await ElMessageBox.confirm(
    `确定删除选中的 ${selectedRows.value.length} 个频道吗？此操作不可恢复。`,
    '批量删除',
    { type: 'warning' }
  )
  try {
    await channelsApi.batchDelete(selectedRows.value.map(r => r.id))
    ElMessage.success('批量删除成功')
    fetchChannels()
  } catch (e) {
    // ignored
  }
}

onMounted(fetchChannels)
</script>

<style scoped>
.channels-page {
  min-height: 100%;
}

.filter-card {
  margin-bottom: 16px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  gap: 8px;
  flex-wrap: wrap;
}

.toolbar-left {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.toolbar-right {
  display: flex;
  gap: 8px;
}

.selected-count {
  margin-left: 4px;
  opacity: 0.8;
}

.table-card {
  margin-bottom: 0;
}

.channel-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.channel-name {
  font-weight: 500;
}

.hd-tag {
  font-weight: 600;
}

.source-count {
  font-weight: 600;
  color: var(--accent-cyan);
}

.pagination-area {
  display: flex;
  justify-content: flex-end;
  padding-top: 16px;
}
</style>
