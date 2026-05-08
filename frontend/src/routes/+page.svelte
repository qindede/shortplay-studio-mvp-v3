<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { api, clearAuthToken, loadAuthToken, setAuthToken, type AdminSummary, type Asset, type Dashboard, type Episode, type PointLedger, type Project, type Shot, type Usage, type User, type VideoTask, type VideoVersion } from '$lib/api';

  type PageKey = 'projects' | 'episodes' | 'script' | 'assets' | 'video' | 'account';

  let activePage: PageKey = 'projects';
  let loading = true;
  let error = '';

  let currentUser: User | null = null;
  let authMode: 'login' | 'register' = 'login';
  let authUsername = 'demo';
  let authPassword = 'demo123';
  let authDisplayName = '';
  let pointLedger: PointLedger[] = [];
  let adminSummary: AdminSummary | null = null;
  let adminUsers: User[] = [];
  let adminLedger: PointLedger[] = [];
  let adminPointUserId = '';
  let adminPointAmount = 1000;
  let adminPointReason = '运营充值';

  let dashboard: Dashboard | null = null;
  let usage: Usage | null = null;
  let projects: Project[] = [];
  let currentProject: Project | null = null;
  let episodes: Episode[] = [];
  let selectedEpisode: Episode | null = null;
  let shots: Shot[] = [];
  let assets: Asset[] = [];
  let videoTasks: VideoTask[] = [];
  let versions: VideoVersion[] = [];
  let assetType = 'all';

  let episodeTitle = '';
  let episodeSummary = '';
  let episodeScript = '';
  let episodeDuration = 30;

  const pageMeta: Record<PageKey, [string, string, string]> = {
    projects: ['项目中心', '管理短剧项目、剧集、素材和视频版本', '新建项目'],
    episodes: ['剧集管理', '当前项目下的多集内容', '新建剧集'],
    script: ['剧情与分镜', '编辑剧情并逐镜头生成视频', '保存并生成'],
    assets: ['素材库', '项目素材可被所有剧集复用', '新建素材'],
    video: ['视频中心', '查看任务、片段和成片版本', '合成视频'],
    account: ['额度与导出', '团队额度与默认导出设置', '购买额度']
  };

  $: filteredAssets = assetType === 'all' ? assets : assets.filter((item) => item.type === assetType);
  $: completedShots = shots.filter((shot) => shot.status === 'completed').length;
  $: videoUsedPercent = usage ? Math.round((usage.video_used_seconds / usage.video_total_seconds) * 100) : 0;
  $: imageUsedPercent = usage ? Math.round((usage.image_used / usage.image_total) * 100) : 0;
  $: exportUsedPercent = usage ? Math.round((usage.export_used / usage.export_total) * 100) : 0;
  $: pointBalance = currentUser?.points || 0;

  onMount(async () => {
    const token = loadAuthToken();
    if (token) {
      setAuthToken(token);
      await loadMeAndBoot();
    } else {
      loading = false;
    }
  });

  async function safeRun(fn: () => Promise<void>) {
    error = '';
    try {
      await fn();
    } catch (err) {
      error = err instanceof Error ? err.message : '操作失败';
    }
  }

  async function submitAuth() {
    await safeRun(async () => {
      const payload =
        authMode === 'login'
          ? await api.login({ username: authUsername, password: authPassword })
          : await api.register({ username: authUsername, password: authPassword, display_name: authDisplayName });
      setAuthToken(payload.token);
      currentUser = payload.user;
      if (currentUser.role === 'admin') {
        goto('/admin');
        return;
      }
      await boot();
    });
  }

  function logout() {
    clearAuthToken();
    currentUser = null;
    dashboard = null;
    usage = null;
    projects = [];
    episodes = [];
    shots = [];
    assets = [];
    videoTasks = [];
    versions = [];
    pointLedger = [];
    activePage = 'projects';
    authMode = 'login';
  }

  async function loadMeAndBoot() {
    loading = true;
    await safeRun(async () => {
      currentUser = await api.me();
      if (currentUser.role === 'admin') {
        goto('/admin');
        return;
      }
      await bootData();
    });
    loading = false;
  }

  async function boot() {
    loading = true;
    await safeRun(async () => {
      if (!currentUser) currentUser = await api.me();
      await bootData();
    });
    loading = false;
  }

  async function bootData() {
    dashboard = await api.dashboard();
    usage = dashboard.usage;
    currentUser = dashboard.current_user || (await api.me());
    pointLedger = await api.myLedger();
    projects = await api.projects();
    if (projects.length > 0) {
      await selectProject(projects[0], false);
    }

  }

  async function refreshDashboard() {
    dashboard = await api.dashboard();
    usage = dashboard.usage;
    currentUser = dashboard.current_user || (await api.me());
    pointLedger = await api.myLedger();
    projects = await api.projects();
    if (currentProject) {
      currentProject = projects.find((project) => project.id === currentProject?.id) || currentProject;
    }

  }

  async function selectProject(project: Project, goEpisodes = true) {
    currentProject = project;
    episodes = await api.episodes(project.id);
    assets = await api.assets(project.id);
    versions = await api.versions(project.id);
    if (episodes.length > 0) {
      await selectEpisode(episodes[0], false);
    } else {
      selectedEpisode = null;
      shots = [];
      videoTasks = [];
    }
    if (goEpisodes) activePage = 'episodes';
  }

  async function selectEpisode(episode: Episode, goScript = false) {
    selectedEpisode = episode;
    episodeTitle = episode.title;
    episodeSummary = episode.summary;
    episodeScript = episode.script;
    episodeDuration = episode.duration_target;
    shots = await api.shots(episode.id);
    videoTasks = await api.videoTasks(episode.id);
    if (currentProject) versions = await api.versions(currentProject.id, episode.id);
    if (goScript) activePage = 'script';
  }

  async function reloadCurrentProject() {
    if (!currentProject) return;
    const freshProjects = await api.projects();
    projects = freshProjects;
    currentProject = freshProjects.find((project) => project.id === currentProject?.id) || currentProject;
    episodes = await api.episodes(currentProject.id);
    assets = await api.assets(currentProject.id);
    if (selectedEpisode) {
      const freshEpisode = episodes.find((episode) => episode.id === selectedEpisode?.id);
      if (freshEpisode) await selectEpisode(freshEpisode, false);
    }
    versions = await api.versions(currentProject.id, selectedEpisode?.id);
  }

  async function setPage(page: PageKey) {
    activePage = page;
  }

  async function loadAdmin() {
    if (currentUser?.role !== 'admin') return;
    adminSummary = await api.adminSummary();
    adminUsers = await api.adminUsers();
    adminLedger = await api.adminLedger();
    if (!adminPointUserId && adminUsers.length > 0) adminPointUserId = adminUsers[0].id;
  }

  async function adjustAdminPoints() {
    if (!adminPointUserId) return;
    await safeRun(async () => {
      await api.adminAdjustPoints(adminPointUserId, { amount: Number(adminPointAmount), reason: adminPointReason });
      await refreshDashboard();
    });
  }

  async function toggleUserStatus(user: User) {
    await safeRun(async () => {
      await api.adminUpdateUser(user.id, { status: user.status === 'active' ? 'disabled' : 'active' });
      await loadAdmin();
    });
  }

  function statusClass(status: string) {
    if (['active', 'completed', 'storyboard_ready', 'exported'].includes(status)) return 'green';
    if (['generating', 'review'].includes(status)) return 'blue';
    if (['draft', 'pending'].includes(status)) return 'amber';
    if (['needs_review'].includes(status)) return 'purple';
    return 'gray';
  }

  function statusLabel(status: string) {
    const map: Record<string, string> = {
      active: '制作中',
      review: '待审核',
      draft: '草稿',
      completed: '已完成',
      storyboard_ready: '已生成',
      generating: '生成中',
      pending: '待生成',
      needs_review: '待优化',
      exported: '已导出'
    };
    return map[status] || status;
  }

  async function handleTopAction() {
    if (activePage === 'projects') return createProject();
    if (activePage === 'episodes') return createEpisode();
    if (activePage === 'script') return saveAndGenerateStoryboard();
    if (activePage === 'assets') return createAsset();
    if (activePage === 'video') return composeVideo();
    return Promise.resolve();
  }

  async function createProject() {
    await safeRun(async () => {
      const name = prompt('项目名称', '新短剧项目');
      if (!name) return;
      const description = prompt('项目简介', '请输入项目简介') || '';
      const project = await api.createProject({ name, description, owner: currentUser?.display_name || '当前用户' });
      await refreshDashboard();
      const target = projects.find((item) => item.id === project.id) || project;
      await selectProject(target);
    });
  }

  async function createEpisode() {
    if (!currentProject) return;
    await safeRun(async () => {
      const title = prompt('剧集标题', `第${episodes.length + 1}集`);
      if (!title) return;
      const summary = prompt('剧情摘要', '请输入本集剧情摘要') || '';
      const episode = await api.createEpisode(currentProject!.id, {
        title,
        summary,
        script: summary,
        duration_target: 30
      });
      episodes = await api.episodes(currentProject!.id);
      await selectEpisode(episode, true);
      await refreshDashboard();
    });
  }

  async function saveEpisodeOnly() {
    if (!selectedEpisode) return;
    await safeRun(async () => {
      const episode = await api.updateEpisode(selectedEpisode!.id, {
        title: episodeTitle,
        summary: episodeSummary,
        script: episodeScript,
        duration_target: Number(episodeDuration)
      });
      await reloadCurrentProject();
      selectedEpisode = episode;
    });
  }

  async function saveAndGenerateStoryboard() {
    if (!selectedEpisode) return;
    await safeRun(async () => {
      await api.updateEpisode(selectedEpisode!.id, {
        title: episodeTitle,
        summary: episodeSummary,
        script: episodeScript,
        duration_target: Number(episodeDuration)
      });
      shots = await api.generateStoryboard(selectedEpisode!.id);
      await refreshDashboard();
      await reloadCurrentProject();
      activePage = 'script';
    });
  }

  async function batchGenerateVideos() {
    if (!selectedEpisode) return;
    await safeRun(async () => {
      videoTasks = await api.generateVideos(selectedEpisode!.id);
      shots = await api.shots(selectedEpisode!.id);
      await refreshDashboard();
      activePage = 'video';
    });
  }

  async function composeVideo() {
    if (!selectedEpisode || !currentProject) return;
    await safeRun(async () => {
      await api.compose(selectedEpisode!.id, {
        description: '合成生成 / 9:16 / 待审核',
        ratio: '9:16',
        duration: selectedEpisode!.duration_target
      });
      versions = await api.versions(currentProject!.id, selectedEpisode!.id);
      await refreshDashboard();
      activePage = 'video';
    });
  }

  async function createAsset() {
    if (!currentProject) return;
    await safeRun(async () => {
      const type = prompt('素材类型：character / scene / image / audio', 'character') || 'character';
      if (!['character', 'scene', 'image', 'audio'].includes(type)) {
        alert('素材类型只能是 character / scene / image / audio');
        return;
      }
      const name = prompt('素材名称', type === 'scene' ? '新场景' : '新角色');
      if (!name) return;
      const description = prompt('素材描述', '请输入素材描述') || '';
      await api.createAsset(currentProject!.id, { type, name, description, initial: name.slice(0, 1) });
      assets = await api.assets(currentProject!.id);
      await refreshDashboard();
    });
  }
</script>

{#if !currentUser}
  <div class="auth-shell">
    <div class="auth-card">
      <div class="auth-brand">
        <div class="brand-mark">SP</div>
        <div>
          <div class="brand-title">ShortPlay Studio</div>
          <div class="brand-subtitle">短剧内容生产工作台</div>
        </div>
      </div>

      <h1>{authMode === 'login' ? '登录工作台' : '注册账号'}</h1>
      <p>注册后获得 1000 初始积分。生成分镜、视频、素材和合成成片会按规则扣减积分。</p>

      {#if error}<div class="error">{error}</div>{/if}
      {#if loading}<div class="loading compact">正在验证登录状态...</div>{/if}

      <div class="auth-tabs">
        <button class:active={authMode === 'login'} on:click={() => { authMode = 'login'; authUsername = 'demo'; authPassword = 'demo123'; }}>登录</button>
        <button class:active={authMode === 'register'} on:click={() => { authMode = 'register'; authUsername = ''; authPassword = ''; }}>注册</button>
      </div>

      <div class="field">
        <label>用户名</label>
        <input bind:value={authUsername} placeholder="请输入用户名" />
      </div>
      {#if authMode === 'register'}
        <div class="field">
          <label>显示名称</label>
          <input bind:value={authDisplayName} placeholder="用于项目协作中的展示名称" />
        </div>
      {/if}
      <div class="field">
        <label>密码</label>
        <input type="password" bind:value={authPassword} placeholder="至少 6 位" on:keydown={(e) => e.key === 'Enter' && submitAuth()} />
      </div>

      <button class="btn btn-primary auth-submit" on:click={submitAuth}>{authMode === 'login' ? '登录' : '注册并进入'}</button>

      <div class="auth-hint">
        <b>演示账号：</b> demo / demo123<br />
        <b>管理员：</b> admin / admin123
      </div>
    </div>
  </div>
{:else}
<div class="app">
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-mark">SP</div>
      <div>
        <div class="brand-title">ShortPlay Studio</div>
        <div class="brand-subtitle">短剧内容生产工作台</div>
      </div>
    </div>

    <div class="project-switcher">
      <div class="switcher-label">当前项目</div>
      <div class="switcher-main">
        <div class="project-cover-mini"></div>
        <div class="switcher-name">
          <b>{currentProject?.short_name || '未选择项目'}</b>
          <span>{episodes.length}集 · {currentProject ? statusLabel(currentProject.status) : '-'}</span>
        </div>
      </div>
    </div>

    <div class="nav">
      <div class="nav-section">创作流程</div>
      <button class:active={activePage === 'projects'} class="nav-item" on:click={() => setPage('projects')}><span class="nav-icon">项</span><span>项目中心</span></button>
      <button class:active={activePage === 'episodes'} class="nav-item" on:click={() => setPage('episodes')}><span class="nav-icon">集</span><span>剧集管理</span></button>
      <button class:active={activePage === 'script'} class="nav-item" on:click={() => setPage('script')}><span class="nav-icon">镜</span><span>剧情与分镜</span></button>
      <button class:active={activePage === 'assets'} class="nav-item" on:click={() => setPage('assets')}><span class="nav-icon">素</span><span>素材库</span></button>
      <button class:active={activePage === 'video'} class="nav-item" on:click={() => setPage('video')}><span class="nav-icon">片</span><span>视频中心</span></button>
      <div class="nav-section">账户</div>
      <button class:active={activePage === 'account'} class="nav-item" on:click={() => setPage('account')}><span class="nav-icon">额</span><span>额度与导出</span></button>
    </div>

    <div class="usage-card">
      <div class="title">本月额度</div>
      <div class="usage-row"><span>视频生成</span><strong>{usage ? usage.video_total_seconds - usage.video_used_seconds : 0}s</strong></div>
      <div class="usage-row"><span>图片生成</span><strong>{usage ? usage.image_total - usage.image_used : 0}张</strong></div>
      <div class="usage-row"><span>高清导出</span><strong>{usage ? usage.export_total - usage.export_used : 0}条</strong></div>
    </div>
  </aside>

  <main class="main">
    <div class="topbar">
      <div>
        <div class="crumbs"><span>工作台</span><span>/</span><strong>{pageMeta[activePage][0]}</strong></div>
        <div class="sub-context">{pageMeta[activePage][1]}</div>
      </div>
      <div class="top-actions">
        <div class="search">搜索项目、剧集、素材</div>
        <div class="user-pill">
          <span>{currentUser.display_name}</span>
          <b>{pointBalance} 积分</b>
        </div>
        <button class="btn btn-secondary" on:click={boot}>刷新</button>
        <button class="btn btn-secondary" on:click={logout}>退出</button>
        <button class="btn btn-primary" on:click={handleTopAction}>{pageMeta[activePage][2]}</button>
      </div>
    </div>

    <div class="content">
      {#if loading}
        <div class="loading">正在加载工作台...</div>
      {:else}
        {#if error}<div class="error">{error}</div>{/if}

        {#if activePage === 'projects'}
          <div class="page-head">
            <div>
              <h1 class="page-title">项目中心</h1>
              <p class="page-desc">以项目为单位组织短剧内容。每个项目下包含剧集、角色、场景、分镜、视频任务和成片版本。</p>
            </div>
            <div><button class="btn btn-blue" on:click={createProject}>新建项目</button></div>
          </div>

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
                <div class="insight-desc">当前项目包含 {episodes.length} 集、{currentProject?.asset_count || 0} 个素材、{currentProject?.version_count || 0} 个成片版本。</div>
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
            <div class="panel-head"><div><div class="panel-title">短剧项目</div><div class="panel-subtitle">选择项目后，可进入该项目的剧集、素材和视频工作区。</div></div></div>
            <div class="panel-body">
              <div class="project-grid">
                {#each projects as project}
                  <button class="project-card" on:click={() => selectProject(project)}>
                    <div class={'project-cover ' + project.cover}></div>
                    <div class="project-card-body">
                      <div class="project-name">{project.name}</div>
                      <div class="project-desc">{project.description}</div>
                      <div class="project-meta"><span>{project.episode_count}集</span><span>{project.asset_count}素材</span><span class={'status ' + statusClass(project.status)}>{statusLabel(project.status)}</span></div>
                    </div>
                  </button>
                {/each}
                <button class="empty-card" on:click={createProject}><div><b>新建短剧项目</b><span>从剧情梗概、已有脚本或项目模板开始。</span></div></button>
              </div>
            </div>
          </div>
        {/if}

        {#if activePage === 'episodes'}
          <div class="page-head">
            <div><h1 class="page-title">剧集管理</h1><p class="page-desc">当前项目：{currentProject?.short_name}。剧集与项目绑定，每一集可独立维护剧情、分镜、视频任务和成片版本。</p></div>
            <div><button class="btn btn-blue" on:click={createEpisode}>新建剧集</button></div>
          </div>

          <div class="episode-board">
            <div class="panel">
              <div class="panel-head"><div><div class="panel-title">剧集目录</div><div class="panel-subtitle">共 {episodes.length} 集</div></div></div>
              <div class="panel-body"><div class="episode-list">
                {#each episodes as episode}
                  <button class:active={selectedEpisode?.id === episode.id} class="episode-item" on:click={() => selectEpisode(episode, true)}>
                    <div class="episode-no">{String(episode.no).padStart(2, '0')}</div>
                    <div class="episode-text"><div class="episode-title">{episode.title}</div><div class="episode-sub">{episode.shot_count}镜头 · {episode.version_count}版本 · {statusLabel(episode.status)}</div></div>
                  </button>
                {/each}
                <button class="empty-card" style="min-height: 86px;" on:click={createEpisode}><div><b>新增剧集</b><span>继续扩展当前短剧项目。</span></div></button>
              </div></div>
            </div>

            <div class="panel">
              <div class="panel-head"><div><div class="panel-title">剧集列表</div><div class="panel-subtitle">查看每集制作状态与下一步动作。</div></div></div>
              <div class="panel-body table-wrap"><table class="table"><thead><tr><th>剧集</th><th>剧情摘要</th><th>分镜</th><th>视频版本</th><th>时长</th><th>状态</th><th>操作</th></tr></thead><tbody>
                {#each episodes as episode}
                  <tr>
                    <td><div class="main-text">第{String(episode.no).padStart(2, '0')}集 · {episode.title}</div></td>
                    <td><div class="sub-text">{episode.summary}</div></td>
                    <td>{episode.shot_count}镜头</td><td>{episode.version_count}个</td><td>{episode.duration_target}s</td>
                    <td><span class={'status ' + statusClass(episode.status)}>{statusLabel(episode.status)}</span></td>
                    <td><button class="btn btn-text" on:click={() => selectEpisode(episode, true)}>编辑</button></td>
                  </tr>
                {/each}
              </tbody></table></div>
            </div>
          </div>
        {/if}

        {#if activePage === 'script'}
          <div class="page-head">
            <div><h1 class="page-title">剧情与分镜</h1><p class="page-desc">当前剧集：第{String(selectedEpisode?.no || 0).padStart(2, '0')}集《{selectedEpisode?.title || '-'}》。维护本集剧情，并逐镜头生成视频。</p></div>
            <div><button class="btn btn-secondary" on:click={() => setPage('episodes')}>返回剧集</button><button class="btn btn-blue" on:click={saveAndGenerateStoryboard}>保存并生成</button></div>
          </div>

          {#if selectedEpisode}
            <div class="workspace-layout">
              <div>
                <div class="panel">
                  <div class="panel-head"><div><div class="panel-title">本集剧情</div><div class="panel-subtitle">修改剧情后可重新拆分镜，也可只保存草稿。</div></div><button class="btn btn-secondary" on:click={saveEpisodeOnly}>保存草稿</button></div>
                  <div class="panel-body">
                    <div class="field-grid">
                      <div class="field"><label>剧集标题</label><input bind:value={episodeTitle} /></div>
                      <div class="field"><label>目标时长</label><input type="number" bind:value={episodeDuration} /></div>
                    </div>
                    <div class="field"><label>剧情摘要</label><input bind:value={episodeSummary} /></div>
                    <div class="field"><label>剧情内容</label><textarea bind:value={episodeScript}></textarea><div class="tag-list"><span class="tag">身份反转</span><span class="tag">订婚现场</span><span class="tag">当众打脸</span><span class="tag">强情绪冲突</span></div></div>
                  </div>
                </div>

                <div class="panel">
                  <div class="panel-head"><div><div class="panel-title">本集分镜</div><div class="panel-subtitle">每个镜头可单独生成、替换、重生成。</div></div><div><button class="btn btn-secondary" on:click={saveAndGenerateStoryboard}>生成/更新分镜</button><button class="btn btn-primary" on:click={batchGenerateVideos}>批量生成视频</button></div></div>
                  <div class="panel-body table-wrap"><table class="table"><thead><tr><th>镜头</th><th>画面描述</th><th>台词/旁白</th><th>角色/场景</th><th>时长</th><th>状态</th></tr></thead><tbody>
                    {#each shots as shot}
                      <tr>
                        <td>#{String(shot.no).padStart(2, '0')}</td>
                        <td><div class="main-text">{shot.title}</div><div class="sub-text">{shot.visual}</div></td>
                        <td>{shot.dialogue || '无台词'}</td>
                        <td>{shot.characters.join('、')} / {shot.scene}</td>
                        <td>{shot.duration}s</td>
                        <td><span class={'status ' + statusClass(shot.status)}>{statusLabel(shot.status)}</span></td>
                      </tr>
                    {:else}
                      <tr><td colspan="6"><div class="sub-text">暂无分镜，点击「生成/更新分镜」。</div></td></tr>
                    {/each}
                  </tbody></table></div>
                </div>
              </div>

              <div>
                <div class="export-card">
                  <div class="title">本集概览</div>
                  <div class="export-row"><span>所属项目</span><b>{currentProject?.short_name}</b></div>
                  <div class="export-row"><span>当前剧集</span><b>第{String(selectedEpisode.no).padStart(2, '0')}集</b></div>
                  <div class="export-row"><span>分镜数量</span><b>{shots.length}镜头</b></div>
                  <div class="export-row"><span>成片版本</span><b>{versions.length}个</b></div>
                  <div class="export-row"><span>预计时长</span><b>{episodeDuration}s</b></div>
                </div>
                <div class="panel" style="margin-top:16px;"><div class="panel-head"><div><div class="panel-title">本集素材</div><div class="panel-subtitle">从项目素材库选择。</div></div></div><div class="panel-body">
                  <div class="info-card"><div class="label">角色</div><div class="value">{assets.filter((a) => a.type === 'character').slice(0, 3).map((a) => a.name.replace(/.*：/, '')).join('、') || '未配置'}</div></div>
                  <div class="info-card"><div class="label">场景</div><div class="value">{assets.find((a) => a.type === 'scene')?.name || '未配置'}</div></div>
                  <button class="btn btn-secondary" style="width:100%;" on:click={() => setPage('assets')}>管理素材</button>
                </div></div>
              </div>
            </div>
          {/if}
        {/if}

        {#if activePage === 'assets'}
          <div class="page-head"><div><h1 class="page-title">素材库</h1><p class="page-desc">素材绑定到当前项目，可被项目下所有剧集复用，用于保持角色、场景和视觉风格一致。</p></div><div><button class="btn btn-blue" on:click={createAsset}>新建素材</button></div></div>
          <div class="panel">
            <div class="panel-head"><div><div class="panel-title">项目素材</div><div class="panel-subtitle">当前项目：{currentProject?.short_name}</div></div><div class="segment"><button class:active={assetType==='all'} on:click={() => assetType='all'}>全部</button><button class:active={assetType==='character'} on:click={() => assetType='character'}>角色</button><button class:active={assetType==='scene'} on:click={() => assetType='scene'}>场景</button><button class:active={assetType==='image'} on:click={() => assetType='image'}>图片</button><button class:active={assetType==='audio'} on:click={() => assetType='audio'}>音频</button></div></div>
            <div class="panel-body"><div class="asset-grid">
              {#each filteredAssets as asset}
                <div class="asset-card">
                  <div class={'asset-preview ' + (asset.type === 'scene' ? 'scene' : 'person')}>{#if asset.type !== 'scene'}<div class="portrait">{asset.initial}</div>{/if}</div>
                  <div class="asset-body"><div class="asset-name">{asset.name}</div><div class="asset-desc">{asset.description}</div><div class="asset-foot"><span>{asset.ref_count}张参考</span><button class="btn btn-text">查看</button></div></div>
                </div>
              {/each}
              <button class="empty-card" on:click={createAsset}><div><b>新增素材</b><span>上传参考图或根据剧情创建素材。</span></div></button>
            </div></div>
          </div>
        {/if}

        {#if activePage === 'video'}
          <div class="page-head"><div><h1 class="page-title">视频中心</h1><p class="page-desc">按项目和剧集查看视频任务、镜头片段和成片版本。</p></div><div><button class="btn btn-secondary" on:click={batchGenerateVideos}>批量生成</button><button class="btn btn-blue" on:click={composeVideo}>合成视频</button></div></div>
          <div class="video-layout">
            <div>
              <div class="panel"><div class="panel-head"><div><div class="panel-title">第{String(selectedEpisode?.no || 0).padStart(2, '0')}集视频任务</div><div class="panel-subtitle">分镜视频片段生成状态。</div></div></div>
                <div class="panel-body table-wrap"><table class="table"><thead><tr><th>任务</th><th>镜头</th><th>时长</th><th>进度</th><th>状态</th><th>更新时间</th></tr></thead><tbody>
                  {#each videoTasks as task}
                    <tr><td><div class="main-text">{task.title}</div><div class="sub-text">角色参考 + 场景参考</div></td><td>{task.shot_id}</td><td>{task.duration}s</td><td><div class="progress"><span style={`width: ${task.progress}%`}></span></div></td><td><span class={'status ' + statusClass(task.status)}>{statusLabel(task.status)}</span></td><td>{task.updated_at}</td></tr>
                  {:else}
                    <tr><td colspan="6"><div class="sub-text">暂无视频任务，请先在「剧情与分镜」生成分镜并批量生成视频。</div></td></tr>
                  {/each}
                </tbody></table></div>
              </div>

              <div class="panel"><div class="panel-head"><div><div class="panel-title">成片版本</div><div class="panel-subtitle">同一剧集可保留多个开头和节奏版本。</div></div></div><div class="panel-body"><div class="video-grid">
                {#each versions as version}
                  <div class="video-card"><div class={'video-thumb ' + version.theme}><div class="play"></div></div><div class="video-body"><div class="video-name">{version.name}</div><div class="video-desc">{version.description} / {version.ratio}</div></div></div>
                {/each}
              </div></div></div>
            </div>
            <div><div class="export-card"><div class="title">本集导出</div><div class="export-row"><span>当前剧集</span><b>第{String(selectedEpisode?.no || 0).padStart(2, '0')}集</b></div><div class="export-row"><span>视频比例</span><b>9:16</b></div><div class="export-row"><span>清晰度</span><b>1080P</b></div><div class="export-row"><span>字幕样式</span><b>白字黑边</b></div><div class="export-row"><span>镜头状态</span><b>{completedShots}/{shots.length}完成</b></div><button class="btn btn-blue" style="width:100%; margin-top:14px;" on:click={composeVideo}>合成本集视频</button></div></div>
          </div>
        {/if}

        {#if activePage === 'account'}
          <div class="page-head">
            <div><h1 class="page-title">额度与导出</h1><p class="page-desc">查看当前账号积分、团队生成额度、高清导出额度和最近积分明细。</p></div>
            <div><button class="btn btn-secondary" on:click={refreshDashboard}>刷新积分</button></div>
          </div>

          <div class="metrics">
            <div class="metric-card point-metric"><div class="metric-label">当前积分</div><div class="metric-value">{pointBalance}</div><div class="metric-note">账号：{currentUser.display_name}</div></div>
            <div class="metric-card"><div class="metric-label">视频生成额度</div><div class="metric-value">{usage ? usage.video_total_seconds - usage.video_used_seconds : 0}s</div><div class="metric-note">已用 {usage?.video_used_seconds || 0}s / {videoUsedPercent}%</div></div>
            <div class="metric-card"><div class="metric-label">图片生成额度</div><div class="metric-value">{usage ? usage.image_total - usage.image_used : 0}</div><div class="metric-note">已用 {usage?.image_used || 0} 张 / {imageUsedPercent}%</div></div>
            <div class="metric-card"><div class="metric-label">高清导出额度</div><div class="metric-value">{usage ? usage.export_total - usage.export_used : 0}</div><div class="metric-note">已用 {usage?.export_used || 0} 条 / {exportUsedPercent}%</div></div>
          </div>

          <div class="account-layout">
            <div class="panel">
              <div class="panel-head"><div><div class="panel-title">积分消耗规则</div><div class="panel-subtitle">MVP 先使用固定规则，后续可改成后台可配置套餐。</div></div></div>
              <div class="panel-body rule-grid">
                <div class="rule-card"><b>生成/更新分镜</b><span>10 积分 / 次</span></div>
                <div class="rule-card"><b>生成视频</b><span>10 积分 / 秒</span></div>
                <div class="rule-card"><b>创建视觉素材</b><span>20 积分 / 个</span></div>
                <div class="rule-card"><b>合成成片</b><span>30 积分 / 次</span></div>
              </div>
            </div>

            <div class="panel">
              <div class="panel-head"><div><div class="panel-title">积分明细</div><div class="panel-subtitle">展示当前账号最近 100 条积分增减记录。</div></div></div>
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
        {/if}


      {/if}
    </div>
  </main>
</div>
{/if}
