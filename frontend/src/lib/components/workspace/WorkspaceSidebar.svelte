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
    { key: 'projects', label: '创作宇宙', icon: '01' },
    { key: 'episodes', label: '剧集编排', icon: '02' },
    { key: 'script', label: '脚本分镜', icon: '03' },
    { key: 'assets', label: '角色场景', icon: '04' },
    { key: 'video', label: '成片控制', icon: '05' },
    { key: 'account', label: '额度账户', icon: '06' }
  ];
</script>

<aside class="sidebar">
  <div class="brand">
    <div class="brand-mark">SP</div>
    <div>
      <div class="brand-title">ShortPlay Studio</div>
      <div class="brand-subtitle">短剧内容创作舱</div>
    </div>
  </div>

  <div class="studio-signal">
    <span></span><span></span><span></span><span></span>
  </div>

  <div class="project-switcher">
    <div class="switcher-head">
      <div>
        <div class="switcher-label">当前项目</div>
        <div class="switcher-caption">选择一个故事世界继续创作</div>
      </div>
      <button class="switcher-action switcher-action-primary" on:click={createProject}>+</button>
    </div>

    <div class="switcher-main">
      <div class="project-cover-mini"></div>
      <div class="switcher-name">
        <b>{currentProject?.short_name || '未选择项目'}</b>
        <span>{episodes.length} 集 · {currentProject ? getStatusLabel(currentProject.status) : '等待开始'}</span>
      </div>
      <button class="switcher-inline-toggle" aria-label="切换项目" on:click={() => (projectPickerOpen = !projectPickerOpen)}>
        <span class:open={projectPickerOpen} class="switcher-chevron">›</span>
      </button>
    </div>

    {#if projectPickerOpen}
      <div class="switcher-list">
        {#each projects as project}
          <button class:active={currentProject?.id === project.id} class="switcher-option" on:click={() => selectProject(project, false)}>
            <div class="switcher-option-name">{project.name}</div>
            <div class="switcher-option-meta">{project.episode_count} 集 · {getStatusLabel(project.status)}</div>
          </button>
        {:else}
          <div class="switcher-empty">还没有项目。先创建一个短剧世界。</div>
        {/each}
      </div>
    {/if}
  </div>

  <div class="nav">
    <div class="nav-section">制作动线</div>
    {#each navItems.slice(0, 5) as item}
      <button class:active={activePage === item.key} class="nav-item" on:click={() => setPage(item.key)}>
        <span class="nav-icon">{item.icon}</span>
        <span>{item.label}</span>
      </button>
    {/each}

    <div class="nav-section">账户</div>
    <button class:active={activePage === 'account'} class="nav-item" on:click={() => setPage('account')}>
      <span class="nav-icon">06</span>
      <span>额度账户</span>
    </button>
  </div>

  <div class="sidebar-footer">
    <div class="usage-card usage-card-user">
      <div class="usage-user-head">
        <div class="switcher-label">创作者</div>
        <button class="btn usage-user-exit" on:click={logout}>退出</button>
      </div>

      <div class="sidebar-user-row">
        <div class="sidebar-user-avatar">{currentUser.display_name.slice(0, 1)}</div>
        <div class="sidebar-user-copy">
          <b>{currentUser.display_name}</b>
          <span>@{currentUser.username}</span>
        </div>
        <div class="sidebar-user-points">{pointBalance}</div>
      </div>

      <div class="usage-divider"></div>
      <div class="title">本月剩余额度</div>
      <div class="usage-row"><span>视频生成</span><strong>{usage ? usage.video_total_seconds - usage.video_used_seconds : 0}s</strong></div>
      <div class="usage-row"><span>图片生成</span><strong>{usage ? usage.image_total - usage.image_used : 0} 张</strong></div>
      <div class="usage-row"><span>高清导出</span><strong>{usage ? usage.export_total - usage.export_used : 0} 条</strong></div>
    </div>
  </div>
</aside>
