<script lang="ts">
  import type { PointLedgerResponse, Usage, User } from '$lib/api';
  import { api } from '$lib/api';
  import { getUsagePercent } from '$lib/workspace/ui';

  export let currentUser: User;
  export let usage: Usage | null = null;
  export let pointBalance = 0;
  export let pointLedger: PointLedgerResponse = { items: [], total: 0 };

  const PAGE_SIZE = 10;
  let currentPage = 1;
  let loading = false;

  $: totalPages = Math.max(1, Math.ceil(pointLedger.total / PAGE_SIZE));

  $: videoUsedPercent = usage ? getUsagePercent(usage.video_used_seconds, usage.video_total_seconds) : 0;
  $: imageUsedPercent = usage ? getUsagePercent(usage.image_used, usage.image_total) : 0;
  $: exportUsedPercent = usage ? getUsagePercent(usage.export_used, usage.export_total) : 0;

  async function goToPage(page: number) {
    if (page < 1 || page > totalPages || loading) return;
    loading = true;
    currentPage = page;
    try {
      pointLedger = await api.myLedger(page, PAGE_SIZE);
    } finally {
      loading = false;
    }
  }
</script>

<div class="metrics">
  <div class="metric-card point-metric"><div class="metric-label">当前积分</div><div class="metric-value">{pointBalance}</div><div class="metric-note">账号：{currentUser.display_name}</div></div>
  <div class="metric-card"><div class="metric-label">视频生成</div><div class="metric-value">{usage ? usage.video_total_seconds - usage.video_used_seconds : 0}s</div><div class="metric-note">已用 {usage?.video_used_seconds || 0}s / {videoUsedPercent}%</div></div>
  <div class="metric-card"><div class="metric-label">图片生成</div><div class="metric-value">{usage ? usage.image_total - usage.image_used : 0}</div><div class="metric-note">已用 {usage?.image_used || 0} 张 / {imageUsedPercent}%</div></div>
  <div class="metric-card"><div class="metric-label">高清导出</div><div class="metric-value">{usage ? usage.export_total - usage.export_used : 0}</div><div class="metric-note">已用 {usage?.export_used || 0} 条 / {exportUsedPercent}%</div></div>
</div>

<div class="account-layout">
  <div class="panel" style="align-self: start">
    <div class="panel-head">
      <div>
        <div class="panel-title">积分规则</div>
        <div class="panel-subtitle">MVP 阶段使用固定规则，后续可扩展成后台可配置套餐。</div>
      </div>
    </div>

    <div class="panel-body rule-grid">
      <div class="rule-card"><b>生成 / 更新分镜</b><span>10 积分 / 次</span></div>
      <div class="rule-card"><b>智能生成短剧大纲</b><span>20 积分 / 次</span></div>
      <div class="rule-card"><b>生成视频</b><span>10 积分 / 秒</span></div>
      <div class="rule-card"><b>创建视觉素材</b><span>20 积分 / 个</span></div>
      <div class="rule-card"><b>合成成片</b><span>30 积分 / 次</span></div>
    </div>
  </div>

  <div class="panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">积分流水</div>
        <div class="panel-subtitle">共 {pointLedger.total} 条记录，每页 {PAGE_SIZE} 条。</div>
      </div>
    </div>

    <div class="panel-body table-wrap">
      <table class="table">
        <thead><tr><th>时间</th><th>场景</th><th>说明</th><th>变动</th><th>余额</th></tr></thead>
        <tbody>
          {#each pointLedger.items as row}
            <tr>
              <td>{row.created_at}</td>
              <td>{row.scene}</td>
              <td>{row.description}</td>
              <td><span class={row.amount >= 0 ? 'amount plus' : 'amount minus'}>{row.amount >= 0 ? '+' : ''}{row.amount}</span></td>
              <td>{row.balance_after}</td>
            </tr>
          {:else}
            <tr><td colspan="5"><div class="sub-text">{loading ? '加载中...' : '暂无积分记录。'}</div></td></tr>
          {/each}
        </tbody>
      </table>

      {#if totalPages > 1}
        <div class="pagination">
          <button class="page-btn" disabled={currentPage <= 1 || loading} on:click={() => goToPage(currentPage - 1)}>上一页</button>
          <span class="page-info">{currentPage} / {totalPages}</span>
          <button class="page-btn" disabled={currentPage >= totalPages || loading} on:click={() => goToPage(currentPage + 1)}>下一页</button>
        </div>
      {/if}
    </div>
  </div>
</div>
