<script lang="ts">
  import type { PointLedger, Usage, User } from '$lib/api';
  import { getUsagePercent } from '$lib/workspace/ui';

  export let currentUser: User;
  export let usage: Usage | null = null;
  export let pointBalance = 0;
  export let pointLedger: PointLedger[] = [];

  $: videoUsedPercent = usage ? getUsagePercent(usage.video_used_seconds, usage.video_total_seconds) : 0;
  $: imageUsedPercent = usage ? getUsagePercent(usage.image_used, usage.image_total) : 0;
  $: exportUsedPercent = usage ? getUsagePercent(usage.export_used, usage.export_total) : 0;
</script>

<div class="metrics">
  <div class="metric-card point-metric"><div class="metric-label">当前积分</div><div class="metric-value">{pointBalance}</div><div class="metric-note">账号：{currentUser.display_name}</div></div>
  <div class="metric-card"><div class="metric-label">视频生成额度</div><div class="metric-value">{usage ? usage.video_total_seconds - usage.video_used_seconds : 0}s</div><div class="metric-note">已用 {usage?.video_used_seconds || 0}s / {videoUsedPercent}%</div></div>
  <div class="metric-card"><div class="metric-label">图片生成额度</div><div class="metric-value">{usage ? usage.image_total - usage.image_used : 0}</div><div class="metric-note">已用 {usage?.image_used || 0} 张 / {imageUsedPercent}%</div></div>
  <div class="metric-card"><div class="metric-label">高清导出额度</div><div class="metric-value">{usage ? usage.export_total - usage.export_used : 0}</div><div class="metric-note">已用 {usage?.export_used || 0} 条 / {exportUsedPercent}%</div></div>
</div>

<div class="account-layout">
  <div class="panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">积分消耗规则</div>
        <div class="panel-subtitle">MVP 先使用固定规则，后续可改成后台可配置套餐。</div>
      </div>
    </div>

    <div class="panel-body rule-grid">
      <div class="rule-card"><b>生成/更新分镜</b><span>10 积分 / 次</span></div>
      <div class="rule-card"><b>生成视频</b><span>10 积分 / 秒</span></div>
      <div class="rule-card"><b>创建视觉素材</b><span>20 积分 / 个</span></div>
      <div class="rule-card"><b>合成成片</b><span>30 积分 / 次</span></div>
    </div>
  </div>

  <div class="panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">积分明细</div>
        <div class="panel-subtitle">展示当前账号最近 100 条积分增减记录。</div>
      </div>
    </div>

    <div class="panel-body table-wrap">
      <table class="table">
        <thead><tr><th>时间</th><th>场景</th><th>说明</th><th>变动</th><th>余额</th></tr></thead>
        <tbody>
          {#each pointLedger as row}
            <tr>
              <td>{row.created_at}</td>
              <td><div class="main-text">{row.scene}</div><div class="sub-text">{row.type}</div></td>
              <td>{row.description}</td>
              <td><span class={row.amount >= 0 ? 'amount plus' : 'amount minus'}>{row.amount >= 0 ? '+' : ''}{row.amount}</span></td>
              <td>{row.balance_after}</td>
            </tr>
          {:else}
            <tr><td colspan="5"><div class="sub-text">暂无积分记录。</div></td></tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>
</div>
