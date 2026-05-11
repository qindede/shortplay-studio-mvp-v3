<script lang="ts">
  import type { Dashboard, Episode, Project } from '$lib/api';
  import { getStatusClass, getStatusLabel, type PageKey } from '$lib/workspace/ui';

  export let dashboard: Dashboard | null = null;
  export let currentProject: Project | null = null;
  export let episodes: Episode[] = [];
  export let projects: Project[] = [];
  export let setPage: (page: PageKey) => void | Promise<void>;
  export let selectProject: (project: Project, goEpisodes?: boolean) => void | Promise<void>;
  export let createProject: () => void | Promise<void>;
  export let editProject: (project: Project) => void | Promise<void>;
  export let deleteProject: (project: Project) => void | Promise<void>;
</script>

<div class="hero-board">
  <div class="hero-card">
    <div class="hero-copy">
      <div class="hero-kicker">Now In Production</div>
      <h2>{currentProject?.name || '开启你的第一部短剧'}</h2>
      <p>{currentProject?.description || '创建项目后，可以在这里组织剧集、角色、场景、分镜和成片版本。'}</p>
      <div class="hero-actions">
        <button class="btn btn-primary" on:click={() => setPage('episodes')}>进入剧集编排</button>
        <button class="btn btn-secondary" on:click={() => setPage('assets')}>查看资产中心</button>
      </div>
    </div>
    <div class="poster-stack">
      <div class="poster one"></div>
      <div class="poster two"></div>
      <div class="poster three"></div>
    </div>
  </div>

  <div class="side-insights">
    <div class="insight-card spotlight">
      <div class="insight-title">制作进度</div>
      <div class="insight-desc">
        当前项目包含 {episodes.length} 集、{currentProject?.asset_count || 0} 个素材、{currentProject?.version_count || 0} 个成片版本。
      </div>
      <div class="mini-progress"><span style={`width: ${Math.min(100, episodes.length * 12)}%;`}></span></div>
    </div>

    <div class="insight-card">
      <div class="insight-title">下一步</div>
      <div class="insight-desc">选择一集进入脚本与分镜，生成镜头后即可批量产出视频片段。</div>
    </div>
  </div>
</div>

<div class="metrics">
  <div class="metric-card"><div class="metric-label">项目</div><div class="metric-value">{dashboard?.project_count || 0}</div><div class="metric-note">正在构建的短剧宇宙</div></div>
  <div class="metric-card"><div class="metric-label">剧集</div><div class="metric-value">{dashboard?.episode_count || 0}</div><div class="metric-note">已纳入制作计划</div></div>
  <div class="metric-card"><div class="metric-label">成片</div><div class="metric-value">{dashboard?.version_count || 0}</div><div class="metric-note">可复盘的版本资产</div></div>
  <div class="metric-card"><div class="metric-label">素材</div><div class="metric-value">{dashboard?.asset_count || 0}</div><div class="metric-note">角色 / 场景 / 声音</div></div>
</div>

<div class="panel">
  <div class="panel-head">
    <div>
      <div class="panel-title">项目画廊</div>
      <div class="panel-subtitle">选择一个项目后，进入对应的剧集、素材和成片工作区。</div>
    </div>
  </div>

  <div class="panel-body">
    <div class="project-grid">
      {#each projects as project}
        <div class="project-card">
          <button class="project-card-select" on:click={() => selectProject(project)}>
          <div class={'project-cover ' + project.cover}>
            {#if project.cover_image}
              <img class="project-cover-img" src={project.cover_image} alt={project.short_name} />
            {/if}
            <span>{project.short_name}</span>
          </div>
          <div class="project-card-body">
            <div class="project-name">{project.name}</div>
            <div class="project-desc">{project.description}</div>
            <div class="project-meta">
              <span>{project.episode_count} 集</span>
              <span>{project.asset_count} 素材</span>
              <span class={'status ' + getStatusClass(project.status)}>{getStatusLabel(project.status)}</span>
            </div>
          </div>
          </button>
          <div class="project-card-actions">
            <button class="project-action-btn" aria-label={`编辑 ${project.name}`} on:click={() => editProject(project)}>编辑</button>
            <button class="project-action-btn project-action-danger" aria-label={`删除 ${project.name}`} on:click={() => deleteProject(project)}>删除</button>
          </div>
        </div>
      {/each}

      <button class="empty-card" on:click={createProject}>
        <div><b>新建短剧项目</b><span>从故事梗概、现有脚本或项目模板开始。</span></div>
      </button>
    </div>
  </div>
</div>
