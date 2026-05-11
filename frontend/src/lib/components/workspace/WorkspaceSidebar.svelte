<script lang="ts">
  import type { Episode, Project, User } from '$lib/api';
  import { getStatusLabel, type PageKey } from '$lib/workspace/ui';
  import Clapperboard from 'lucide-svelte/icons/clapperboard';
  import FolderKanban from 'lucide-svelte/icons/folder-kanban';
  import Images from 'lucide-svelte/icons/images';
  import KeyRound from 'lucide-svelte/icons/key-round';
  import LibraryBig from 'lucide-svelte/icons/library-big';
  import UserIcon from 'lucide-svelte/icons/user';
  import WalletCards from 'lucide-svelte/icons/wallet-cards';

  export let activePage: PageKey;
  export let currentProject: Project | null = null;
  export let episodes: Episode[] = [];
  export let projects: Project[] = [];
  export let projectPickerOpen = false;
  export let currentUser: User;
  export let pointBalance = 0;
  export let setPage: (page: PageKey) => void | Promise<void>;
  export let selectProject: (project: Project, goEpisodes?: boolean) => void | Promise<void>;
  export let createProject: () => void | Promise<void>;
  export let logout: () => void;

  const productionNavItems = [
    { key: 'projects' as PageKey, label: '项目中心', icon: FolderKanban },
    { key: 'episodes' as PageKey, label: '剧集编排', icon: LibraryBig },
    { key: 'assets' as PageKey, label: '资产中心', icon: Images },
    { key: 'video' as PageKey, label: '视频中心', icon: Clapperboard }
  ];

  const accountNavItems = [
    { key: 'account' as PageKey, label: '额度账户', icon: WalletCards },
    { key: 'password' as PageKey, label: '密码安全', icon: KeyRound }
  ];
</script>

<aside class="sidebar">
  <div class="brand">
    <div class="brand-mark">SP</div>
    <div>
      <div class="brand-title">shortplay-studio</div>
      <div class="brand-subtitle">短剧内容创作舱</div>
    </div>
  </div>

  <div class="project-switcher">
    <div class="switcher-head">
      <div>
        <div class="switcher-label">当前项目</div>
        <div class="switcher-caption">选择一个项目继续创作</div>
      </div>
      <button class="switcher-action switcher-action-primary" on:click={createProject}>+</button>
    </div>

    <div class="switcher-main">
      <div class="project-cover-mini">
        {#if currentProject?.cover_image}
          <img class="project-cover-mini-img" src={currentProject.cover_image} alt={currentProject.short_name} />
        {/if}
      </div>
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
    {#each productionNavItems as item}
      {@const Icon = item.icon}
      <button class:active={activePage === item.key} class="nav-item" on:click={() => setPage(item.key)}>
        <span class="nav-icon">
          <Icon size={15} strokeWidth={2.3} />
        </span>
        <span>{item.label}</span>
      </button>
    {/each}

    <div class="nav-section">账户</div>
    {#each accountNavItems as item}
      {@const Icon = item.icon}
      <button class:active={activePage === item.key} class="nav-item" on:click={() => setPage(item.key)}>
        <span class="nav-icon">
          <Icon size={15} strokeWidth={2.3} />
        </span>
        <span>{item.label}</span>
      </button>
    {/each}
  </div>

  <div class="sidebar-footer">
    <div class="usage-card usage-card-user">
      <div class="usage-user-head">
        <div class="switcher-label">创作者</div>
        <button class="usage-user-exit" on:click={logout}>退出</button>
      </div>

      <div class="sidebar-user-row">
        <div class="sidebar-user-avatar"><UserIcon size={18} strokeWidth={2} /></div>
        <div class="sidebar-user-copy">
          <b>{currentUser.display_name}</b>
          <span>@{currentUser.username}</span>
        </div>
        <div class="sidebar-user-points">{pointBalance}</div>
      </div>
    </div>
  </div>
</aside>
