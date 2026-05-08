<script lang="ts">
  import type { Episode, Project, Usage, User } from '$lib/api';
  import { getStatusLabel, type PageKey } from '$lib/workspace/ui';

  export let activePage: PageKey;
  export let currentProject: Project | null = null;
  export let episodes: Episode[] = [];
  export let projects: Project[] = [];
  export let projectPickerOpen = false;
  export let currentUser: User;
  export let pointBalance = 0;
  export let usage: Usage | null = null;
  export let setPage: (page: PageKey) => void | Promise<void>;
  export let selectProject: (project: Project, goEpisodes?: boolean) => void | Promise<void>;
  export let createProject: () => void | Promise<void>;
  export let logout: () => void;

  const navItems: Array<{ key: PageKey; label: string; icon: string }> = [
    { key: 'projects', label: '项目中心', icon: '项' },
    { key: 'episodes', label: '剧集管理', icon: '集' },
    { key: 'script', label: '剧情与分镜', icon: '镜' },
    { key: 'assets', label: '素材库', icon: '素' },
    { key: 'video', label: '视频中心', icon: '片' },
    { key: 'account', label: '额度与导出', icon: '额' }
  ];
</script>

<aside class="sidebar">
  <div class="brand">
    <div class="brand-mark">SP</div>
    <div>
      <div class="brand-title">ShortPlay Studio</div>
      <div class="brand-subtitle">短剧内容生产工作台</div>
    </div>
  </div>

  <div class="project-switcher">
    <div class="switcher-head">
      <div class="switcher-label">当前项目</div>
      <div class="switcher-actions">
        <button class="switcher-action switcher-action-primary" on:click={createProject}>新增</button>
      </div>
    </div>

    <div class="switcher-main">
      <div class="project-cover-mini"></div>
      <div class="switcher-name">
        <b>{currentProject?.short_name || '未选择项目'}</b>
        <span>{episodes.length}集 · {currentProject ? getStatusLabel(currentProject.status) : '-'}</span>
      </div>
      <button class="switcher-inline-toggle" aria-label="切换项目" on:click={() => (projectPickerOpen = !projectPickerOpen)}>
        <span class:open={projectPickerOpen} class="switcher-chevron">></span>
      </button>
    </div>

    {#if projectPickerOpen}
      <div class="switcher-list">
        {#each projects as project}
          <button class:active={currentProject?.id === project.id} class="switcher-option" on:click={() => selectProject(project, false)}>
            <div class="switcher-option-name">{project.name}</div>
            <div class="switcher-option-meta">{project.episode_count}集 · {getStatusLabel(project.status)}</div>
          </button>
        {:else}
          <div class="switcher-empty">暂无项目，先新建一个。</div>
        {/each}
      </div>
    {/if}
  </div>

  <div class="nav">
    <div class="nav-section">创作流程</div>
    {#each navItems.slice(0, 5) as item}
      <button class:active={activePage === item.key} class="nav-item" on:click={() => setPage(item.key)}>
        <span class="nav-icon">{item.icon}</span>
        <span>{item.label}</span>
      </button>
    {/each}

    <div class="nav-section">账户</div>
    <button class:active={activePage === 'account'} class="nav-item" on:click={() => setPage('account')}>
      <span class="nav-icon">额</span>
      <span>额度与导出</span>
    </button>
  </div>

  <div class="sidebar-footer">
    <div class="usage-card usage-card-user">
      <div class="usage-user-head">
        <div class="switcher-label">当前登录</div>
        <button class="btn usage-user-exit" on:click={logout}>退出</button>
      </div>

      <div class="sidebar-user-row">
        <div class="sidebar-user-avatar">{currentUser.display_name.slice(0, 1)}</div>
        <div class="sidebar-user-copy">
          <b>{currentUser.display_name}</b>
          <span>@{currentUser.username}</span>
        </div>
        <div class="sidebar-user-points">{pointBalance} 积分</div>
      </div>

      <div class="usage-divider"></div>
      <div class="title">本月额度</div>
      <div class="usage-row"><span>视频生成</span><strong>{usage ? usage.video_total_seconds - usage.video_used_seconds : 0}s</strong></div>
      <div class="usage-row"><span>图片生成</span><strong>{usage ? usage.image_total - usage.image_used : 0}张</strong></div>
      <div class="usage-row"><span>高清导出</span><strong>{usage ? usage.export_total - usage.export_used : 0}条</strong></div>
    </div>
  </div>
</aside>
