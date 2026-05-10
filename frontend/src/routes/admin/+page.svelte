<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { api, clearAuthToken, loadAuthToken, setAuthToken, type AdminSummary, type PointLedger, type User } from '$lib/api';

  type AdminTab = 'overview' | 'users' | 'points' | 'ledger';
  const PRIMARY_ADMIN_ID = 'user_admin';

  let currentUser: User | null = null;
  let activeTab: AdminTab = 'overview';
  let summary: AdminSummary | null = null;
  let users: User[] = [];
  let ledger: PointLedger[] = [];
  let selectedUserId = '';
  let amount = 1000;
  let reason = '运营充值';
  let loading = true;
  let error = '';
  let message = '';

  onMount(load);

  async function load() {
    loading = true;
    error = '';
    const token = loadAuthToken();
    if (!token) {
      goto('/');
      return;
    }
    setAuthToken(token);
    try {
      currentUser = await api.me();
      if (currentUser.role !== 'admin') {
        goto('/');
        return;
      }
      await refreshAdminData();
    } catch (err) {
      error = err instanceof Error ? err.message : '加载失败';
    } finally {
      loading = false;
    }
  }

  async function refreshAdminData() {
    summary = await api.adminSummary();
    users = await api.adminUsers();
    ledger = await api.adminLedger();
    if (!selectedUserId && users.length > 0) selectedUserId = users[0].id;
  }

  async function adjustPoints() {
    error = '';
    message = '';
    try {
      await api.adminAdjustPoints(selectedUserId, { amount: Number(amount), reason });
      await refreshAdminData();
      message = '积分调整成功';
    } catch (err) {
      error = err instanceof Error ? err.message : '调整失败';
    }
  }

  async function toggleUser(user: User) {
    error = '';
    if (cannotToggleStatus(user)) {
      error = isPrimaryAdmin(user) ? '不能禁用主管理员账号' : '不能禁用当前登录的管理员账号';
      return;
    }
    try {
      await api.adminUpdateUser(user.id, { status: user.status === 'active' ? 'disabled' : 'active' });
      await refreshAdminData();
    } catch (err) {
      error = err instanceof Error ? err.message : '操作失败';
    }
  }

  async function toggleUserRole(user: User) {
    error = '';
    message = '';
    if (cannotChangeRole(user)) {
      error = roleChangeBlockedReason(user);
      return;
    }
    const nextRole = user.role === 'admin' ? 'user' : 'admin';
    try {
      await api.adminUpdateUser(user.id, { role: nextRole });
      await refreshAdminData();
      message = nextRole === 'admin' ? '已添加子管理员' : '已取消子管理员权限';
    } catch (err) {
      error = err instanceof Error ? err.message : '操作失败';
    }
  }

  function isSelf(user: User) {
    return currentUser?.id === user.id;
  }

  function isPrimaryAdmin(user: User) {
    return user.id === PRIMARY_ADMIN_ID || user.username === 'admin';
  }

  function cannotToggleStatus(user: User) {
    return isSelf(user) || isPrimaryAdmin(user);
  }

  function cannotChangeRole(user: User) {
    return isSelf(user) || isPrimaryAdmin(user) || (user.role !== 'admin' && !isCurrentUserPrimaryAdmin());
  }

  function isCurrentUserPrimaryAdmin() {
    return !!currentUser && isPrimaryAdmin(currentUser);
  }

  function roleChangeBlockedReason(user: User) {
    if (isPrimaryAdmin(user)) return '不能修改主管理员角色';
    if (isSelf(user)) return '不能移除当前登录账号的管理员角色';
    return '只有主管理员可以添加子管理员';
  }

  function statusActionLabel(user: User) {
    if (isPrimaryAdmin(user)) return '主管理员';
    if (isSelf(user)) return '当前账号';
    return user.status === 'active' ? '禁用' : '启用';
  }

  function roleActionLabel(user: User) {
    if (isPrimaryAdmin(user)) return '主管理员';
    if (isSelf(user)) return '当前角色';
    if (user.role !== 'admin' && !isCurrentUserPrimaryAdmin()) return '仅主管理员';
    return user.role === 'admin' ? '设为用户' : '设为管理员';
  }

  function logout() {
    clearAuthToken();
    goto('/');
  }
</script>

<div class="admin-shell-v2">
  <aside class="admin-side-v2">
    <div class="brand admin-brand-v2">
      <div class="brand-mark">OP</div>
      <div>
        <div class="brand-title">运营后台</div>
        <div class="brand-subtitle">Platform Console</div>
      </div>
    </div>

    <div class="nav">
      <div class="nav-section">平台运营</div>
      <button class:active={activeTab === 'overview'} class="nav-item" on:click={() => activeTab = 'overview'}><span class="nav-icon">览</span><span>运营概览</span></button>
      <button class:active={activeTab === 'users'} class="nav-item" on:click={() => activeTab = 'users'}><span class="nav-icon">用</span><span>用户管理</span></button>
      <button class:active={activeTab === 'points'} class="nav-item" on:click={() => activeTab = 'points'}><span class="nav-icon">积</span><span>积分调整</span></button>
      <button class:active={activeTab === 'ledger'} class="nav-item" on:click={() => activeTab = 'ledger'}><span class="nav-icon">流</span><span>积分流水</span></button>
    </div>

    <div class="admin-side-footer">
      <div class="sidebar-user-card sidebar-user-card-dark">
        <div class="switcher-label">当前登录</div>
        <div class="sidebar-user-row">
          <div class="sidebar-user-avatar">{(currentUser?.display_name || '管理员').slice(0, 1)}</div>
          <div class="sidebar-user-copy">
            <b>{currentUser?.display_name || '管理员'}</b>
            <span>@{currentUser?.username || 'admin'}</span>
          </div>
          <button class="sidebar-user-points" on:click={logout}>退出</button>
        </div>
      </div>

    </div>
  </aside>

  <main class="main">
    <div class="topbar">
      <div>
        <div class="crumbs"><span>管理员后台</span><span>/</span><strong>{activeTab === 'overview' ? '运营概览' : activeTab === 'users' ? '用户管理' : activeTab === 'points' ? '积分调整' : '积分流水'}</strong></div>
        <div class="sub-context">平台运营、用户与积分管理</div>
      </div>
    </div>

    <div class="content">
      {#if loading}
        <div class="loading">正在加载管理员后台...</div>
      {:else}
        {#if error}<div class="error">{error}</div>{/if}
        {#if message}<div class="success">{message}</div>{/if}

        {#if activeTab === 'overview'}
          <div class="metrics">
            <div class="metric-card"><div class="metric-label">用户总数</div><div class="metric-value">{summary?.user_count || 0}</div><div class="metric-note">启用 {summary?.active_user_count || 0} 人</div></div>
            <div class="metric-card"><div class="metric-label">平台积分余额</div><div class="metric-value">{summary?.total_balance || 0}</div><div class="metric-note">所有用户余额合计</div></div>
            <div class="metric-card"><div class="metric-label">累计消耗</div><div class="metric-value">{summary?.consumed_points || 0}</div><div class="metric-note">内容生成和导出</div></div>
            <div class="metric-card"><div class="metric-label">累计赠送/充值</div><div class="metric-value">{summary?.granted_points || 0}</div><div class="metric-note">注册赠送和后台调整</div></div>
          </div>
        {/if}

        {#if activeTab === 'users'}
          <div class="panel"><div class="panel-head"><div><div class="panel-title">用户列表</div><div class="panel-subtitle">共 {users.length} 个账号</div></div></div><div class="panel-body table-wrap"><table class="table"><thead><tr><th>用户</th><th>角色</th><th>状态</th><th>积分</th><th>注册时间</th><th>最近登录</th><th>操作</th></tr></thead><tbody>{#each users as user}<tr><td><div class="main-text">{user.display_name}</div><div class="sub-text">@{user.username}</div></td><td><span class="status blue">{isPrimaryAdmin(user) ? '主管理员' : user.role === 'admin' ? '子管理员' : '普通用户'}</span></td><td><span class={'status ' + (user.status === 'active' ? 'green' : 'red')}>{user.status === 'active' ? '启用' : '禁用'}</span></td><td>{user.points}</td><td>{user.created_at}</td><td>{user.last_login || '-'}</td><td><button class="btn btn-text" disabled={cannotChangeRole(user)} on:click={() => toggleUserRole(user)}>{roleActionLabel(user)}</button><button class="btn btn-text" disabled={cannotToggleStatus(user)} on:click={() => toggleUser(user)}>{statusActionLabel(user)}</button></td></tr>{/each}</tbody></table></div></div>
        {/if}

        {#if activeTab === 'points'}
          <div class="admin-layout">
            <div class="panel"><div class="panel-head"><div><div class="panel-title">调整积分</div><div class="panel-subtitle">正数为充值，负数为扣减。</div></div></div><div class="panel-body"><div class="field"><label for="admin-selected-user">选择用户</label><select id="admin-selected-user" bind:value={selectedUserId}>{#each users as user}<option value={user.id}>{user.display_name} / @{user.username} / {user.points}积分</option>{/each}</select></div><div class="field"><label for="admin-amount">调整积分</label><input id="admin-amount" type="number" bind:value={amount} /></div><div class="field"><label for="admin-reason">操作原因</label><input id="admin-reason" bind:value={reason} /></div><button class="btn btn-primary" style="width:100%;" on:click={adjustPoints}>提交调整</button></div></div>
            <div class="panel"><div class="panel-head"><div><div class="panel-title">积分规则</div><div class="panel-subtitle">MVP 固定规则，后续可做平台配置。</div></div></div><div class="panel-body rule-grid"><div class="rule-card"><b>注册赠送</b><span>1000 积分</span></div><div class="rule-card"><b>智能生成短剧大纲</b><span>20 积分 / 次</span></div><div class="rule-card"><b>生成分镜</b><span>10 积分 / 次</span></div><div class="rule-card"><b>生成视频</b><span>10 积分 / 秒</span></div><div class="rule-card"><b>合成成片</b><span>30 积分 / 次</span></div></div></div>
          </div>
        {/if}

        {#if activeTab === 'ledger'}
          <div class="panel"><div class="panel-head"><div><div class="panel-title">流水记录</div><div class="panel-subtitle">最近 {ledger.length} 条记录</div></div></div><div class="panel-body table-wrap"><table class="table"><thead><tr><th>时间</th><th>用户</th><th>场景</th><th>说明</th><th>类型</th><th>变动</th><th>余额</th></tr></thead><tbody>{#each ledger as row}<tr><td>{row.created_at}</td><td><div class="main-text">{row.display_name}</div><div class="sub-text">@{row.username}</div></td><td>{row.scene}</td><td>{row.description}</td><td>{row.type}</td><td><span class={row.amount >= 0 ? 'amount plus' : 'amount minus'}>{row.amount >= 0 ? '+' : ''}{row.amount}</span></td><td>{row.balance_after}</td></tr>{/each}</tbody></table></div></div>
        {/if}
      {/if}
    </div>
  </main>
</div>
