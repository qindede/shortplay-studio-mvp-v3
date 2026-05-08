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
</script>

<div class="hero-board">
  <div class="hero-card">
    <div class="hero-copy">
      <div class="hero-kicker">当前项目</div>
      <h2>{currentProject?.name}</h2>
      <p>{currentProject?.description}</p>
      <button class="btn btn-primary" on:click={() => setPage('episodes')}>进入剧集管理</button>
      <button class="btn btn-secondary" on:click={() => setPage('assets')}>查看素材库</button>
    </div>
    <div class="poster-stack"><div class="poster one"></div><div class="poster two"></div></div>
  </div>

  <div class="side-insights">
    <div class="insight-card">
      <div class="insight-title">制作进度</div>
      <div class="insight-desc">
        当前项目包含 {episodes.length} 集、{currentProject?.asset_count || 0} 个素材、{currentProject?.version_count || 0} 个成片版本。
      </div>
      <div class="mini-progress"><span style={`width: ${Math.min(100, episodes.length * 8)}%;`}></span></div>
    </div>

    <div class="insight-card">
      <div class="insight-title">下一步建议</div>
      <div class="insight-desc">选择一集进入「剧情与分镜」，生成镜头后即可批量生成视频任务。</div>
    </div>
  </div>
</div>

<div class="metrics">
  <div class="metric-card"><div class="metric-label">项目总数</div><div class="metric-value">{dashboard?.project_count || 0}</div><div class="metric-note">团队短剧项目</div></div>
  <div class="metric-card"><div class="metric-label">剧集总数</div><div class="metric-value">{dashboard?.episode_count || 0}</div><div class="metric-note">项目下绑定剧集</div></div>
  <div class="metric-card"><div class="metric-label">成片版本</div><div class="metric-value">{dashboard?.version_count || 0}</div><div class="metric-note">含待审核与已导出</div></div>
  <div class="metric-card"><div class="metric-label">项目素材</div><div class="metric-value">{dashboard?.asset_count || 0}</div><div class="metric-note">角色 / 场景 / 图片 / 音频</div></div>
</div>

<div class="panel">
  <div class="panel-head">
    <div>
      <div class="panel-title">短剧项目</div>
      <div class="panel-subtitle">选择项目后，可进入该项目的剧集、素材和视频工作区。</div>
    </div>
  </div>

  <div class="panel-body">
    <div class="project-grid">
      {#each projects as project}
        <button class="project-card" on:click={() => selectProject(project)}>
          <div class={'project-cover ' + project.cover}></div>
          <div class="project-card-body">
            <div class="project-name">{project.name}</div>
            <div class="project-desc">{project.description}</div>
            <div class="project-meta">
              <span>{project.episode_count}集</span>
              <span>{project.asset_count}素材</span>
              <span class={'status ' + getStatusClass(project.status)}>{getStatusLabel(project.status)}</span>
            </div>
          </div>
        </button>
      {/each}

      <button class="empty-card" on:click={createProject}>
        <div><b>新建短剧项目</b><span>从剧情梗概、已有脚本或项目模板开始。</span></div>
      </button>
    </div>
  </div>
</div>
