<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    api,
    clearAuthToken,
    loadAuthToken,
    setAuthToken,
    type Asset,
    type Dashboard,
    type Episode,
    type PointLedger,
    type Project,
    type ProjectOutlineEpisode,
    type Shot,
    type ShotPayload,
    type ShotUpdate,
    type Usage,
    type User,
    type VideoTask,
    type VideoVersion
  } from '$lib/api';
  import AuthScreen from '$lib/components/workspace/AuthScreen.svelte';
  import WorkspaceSidebar from '$lib/components/workspace/WorkspaceSidebar.svelte';
  import WorkspaceTopbar from '$lib/components/workspace/WorkspaceTopbar.svelte';
  import AccountPage from '$lib/components/workspace/pages/AccountPage.svelte';
  import AssetsPage from '$lib/components/workspace/pages/AssetsPage.svelte';
  import EpisodesPage from '$lib/components/workspace/pages/EpisodesPage.svelte';
  import ProjectsPage from '$lib/components/workspace/pages/ProjectsPage.svelte';
  import ScriptPage from '$lib/components/workspace/pages/ScriptPage.svelte';
  import VideoPage from '$lib/components/workspace/pages/VideoPage.svelte';
  import { type AuthMode, type PageKey } from '$lib/workspace/ui';

  type AssetFilter = 'all' | Asset['type'];

  let activePage: PageKey = 'projects';
  let loading = true;
  let error = '';

  let currentUser: User | null = null;
  let authMode: AuthMode = 'login';
  let authUsername = 'demo';
  let authPassword = 'demo123';
  let authDisplayName = '';
  let pointLedger: PointLedger[] = [];

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
  let assetType: AssetFilter = 'all';
  let projectPickerOpen = false;

  let episodeTitle = '';
  let episodeSummary = '';
  let episodeScript = '';
  let episodeDuration = 30;
  let episodeDialogOpen = false;
  let episodeSubmitting = false;
  let episodeFormError = '';
  let newEpisodeTitle = '';
  let newEpisodeSummary = '';
  let newEpisodeScript = '';
  let newEpisodeDuration = 30;
  let projectDialogOpen = false;
  let projectName = '';
  let projectDescription = '';
  let outlineCost = 20;
  let storyboardCost = 20;
  let outlineEpisodes: ProjectOutlineEpisode[] = [];
  let outlineLoading = false;
  let projectSubmitting = false;
  let projectFormError = '';

  const assetTypes: Asset['type'][] = ['character', 'scene', 'image', 'audio'];

  $: pointBalance = currentUser?.points || 0;

  onMount(() => {
    void restoreSession();
  });

  function resetEpisodeForm() {
    episodeTitle = '';
    episodeSummary = '';
    episodeScript = '';
    episodeDuration = 30;
  }

  function resetNewEpisodeForm() {
    newEpisodeTitle = `第${episodes.length + 1}集`;
    newEpisodeSummary = '';
    newEpisodeScript = '';
    newEpisodeDuration = 30;
    episodeSubmitting = false;
    episodeFormError = '';
  }

  function openEpisodeDialog() {
    resetNewEpisodeForm();
    episodeDialogOpen = true;
  }

  function closeEpisodeDialog() {
    if (episodeSubmitting) return;
    episodeDialogOpen = false;
    resetNewEpisodeForm();
  }

  function resetProjectForm() {
    projectName = '';
    projectDescription = '';
    outlineEpisodes = [];
    outlineLoading = false;
    projectSubmitting = false;
    projectFormError = '';
  }

  function openProjectDialog() {
    resetProjectForm();
    projectDialogOpen = true;
  }

  function closeProjectDialog() {
    if (outlineLoading || projectSubmitting) return;
    projectDialogOpen = false;
    resetProjectForm();
  }

  function updateOutlineEpisode(index: number, key: keyof ProjectOutlineEpisode, value: string | number) {
    outlineEpisodes = outlineEpisodes.map((episode, currentIndex) =>
      currentIndex === index
        ? { ...episode, [key]: value, script: key === 'summary' ? String(value) : episode.script }
        : episode
    );
  }

  function fillEpisodeForm(episode: Episode) {
    episodeTitle = episode.title;
    episodeSummary = episode.summary;
    episodeScript = episode.script;
    episodeDuration = episode.duration_target;
  }

  function resetWorkspaceState() {
    dashboard = null;
    usage = null;
    projects = [];
    currentProject = null;
    episodes = [];
    selectedEpisode = null;
    shots = [];
    assets = [];
    videoTasks = [];
    versions = [];
    pointLedger = [];
    assetType = 'all';
    projectPickerOpen = false;
    activePage = 'projects';
    projectDialogOpen = false;
    episodeDialogOpen = false;
    resetProjectForm();
    resetNewEpisodeForm();
    resetEpisodeForm();
  }

  function buildEpisodePayload() {
    return {
      title: episodeTitle,
      summary: episodeSummary,
      script: episodeScript,
      duration_target: Number(episodeDuration)
    };
  }

  async function restoreSession() {
    const token = loadAuthToken();
    if (!token) {
      loading = false;
      return;
    }

    setAuthToken(token);
    await loadMeAndBoot();
  }

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
    error = '';
    authMode = 'login';
    authUsername = 'demo';
    authPassword = 'demo123';
    authDisplayName = '';
    resetWorkspaceState();
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

    if (projects.length === 0) {
      currentProject = null;
      episodes = [];
      selectedEpisode = null;
      shots = [];
      assets = [];
      videoTasks = [];
      versions = [];
      resetEpisodeForm();
      return;
    }

    await selectProject(projects[0], false);
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
    projectPickerOpen = false;
    episodes = await api.episodes(project.id);
    assets = await api.assets(project.id);
    versions = await api.versions(project.id);

    if (episodes.length === 0) {
      selectedEpisode = null;
      shots = [];
      videoTasks = [];
      resetEpisodeForm();
    } else {
      await selectEpisode(episodes[0], false);
    }

    if (goEpisodes) activePage = 'episodes';
  }

  async function selectEpisode(episode: Episode, goScript = false) {
    selectedEpisode = episode;
    fillEpisodeForm(episode);
    shots = await api.shots(episode.id);
    videoTasks = await api.videoTasks(episode.id);

    if (currentProject) {
      versions = await api.versions(currentProject.id, episode.id);
    }

    if (goScript) activePage = 'script';
  }

  async function reloadCurrentProject() {
    if (!currentProject) return;

    const freshProjects = await api.projects();
    projects = freshProjects;
    currentProject = freshProjects.find((project) => project.id === currentProject?.id) || currentProject;
    episodes = await api.episodes(currentProject.id);
    assets = await api.assets(currentProject.id);

    if (!selectedEpisode) {
      versions = await api.versions(currentProject.id);
      return;
    }

    const freshEpisode = episodes.find((episode) => episode.id === selectedEpisode?.id);
    if (!freshEpisode) {
      selectedEpisode = null;
      shots = [];
      videoTasks = [];
      versions = await api.versions(currentProject.id);
      resetEpisodeForm();
      return;
    }

    await selectEpisode(freshEpisode, false);
  }

  function setPage(page: PageKey) {
    activePage = page;
  }

  async function handleTopAction() {
    if (activePage === 'projects') return createProject();
    if (activePage === 'episodes') return createEpisode();
    if (activePage === 'script') return saveAndGenerateStoryboard();
    if (activePage === 'assets') return createAsset();
    if (activePage === 'video') return composeVideo();
  }

  function createProject() {
    openProjectDialog();
  }

  async function generateProjectOutline() {
    const name = projectName.trim();
    const description = projectDescription.trim();
    projectFormError = '';
    error = '';

    if (!name || !description) {
      projectFormError = '请先填写短剧名称和简介，再生成短剧大纲。';
      return;
    }

    outlineLoading = true;
    try {
      const outline = await api.generateProjectOutline({
        name,
        description
      });
      outlineCost = outline.cost;
      outlineEpisodes = outline.episodes;
      await refreshDashboard();
    } catch (err) {
      projectFormError = err instanceof Error ? err.message : '生成短剧大纲失败';
    } finally {
      outlineLoading = false;
    }
  }

  async function submitProject() {
    const name = projectName.trim();
    const description = projectDescription.trim();
    projectFormError = '';
    error = '';

    if (!name || !description) {
      projectFormError = '请填写短剧名称和简介。';
      return;
    }

    projectSubmitting = true;
    try {
      const project = await api.createProject({
        name,
        description,
        owner: currentUser?.display_name || '当前用户',
        episodes: outlineEpisodes
      });
      projectDialogOpen = false;
      resetProjectForm();
      await refreshDashboard();
      const target = projects.find((item) => item.id === project.id) || project;
      await selectProject(target);
    } catch (err) {
      projectFormError = err instanceof Error ? err.message : '创建项目失败';
    } finally {
      projectSubmitting = false;
    }
  }

  async function createEpisode() {
    openEpisodeDialog();
  }

  async function submitEpisode(generateStoryboard = false) {
    const project = currentProject;
    if (!project || episodeSubmitting) return;

    const title = newEpisodeTitle.trim();
    const summary = newEpisodeSummary.trim();
    episodeFormError = '';
    error = '';

    if (!title || !summary) {
      episodeFormError = '请填写剧情标题和剧情摘要。';
      return;
    }

    episodeSubmitting = true;
    try {
      const episode = await api.createEpisode(project.id, {
        title,
        summary,
        script: newEpisodeScript.trim() || summary,
        duration_target: Math.max(1, Number(newEpisodeDuration) || 30)
      });

      episodes = await api.episodes(project.id);
      await selectEpisode(episode, true);

      if (generateStoryboard) {
        shots = await api.generateStoryboard(episode.id);
      }

      await refreshDashboard();
      await reloadCurrentProject();
      episodeDialogOpen = false;
      resetNewEpisodeForm();
      activePage = 'script';
    } catch (err) {
      episodeFormError = err instanceof Error ? err.message : generateStoryboard ? '创建剧情并生成分镜失败' : '创建剧情失败';
    } finally {
      episodeSubmitting = false;
    }
  }

  async function deleteEpisode(episode: Episode) {
    const project = currentProject;
    if (!project) return;

    const confirmed = confirm(
      `确定删除第 ${String(episode.no).padStart(2, '0')} 集「${episode.title}」吗？相关分镜、视频任务和成片版本也会一并删除。`
    );
    if (!confirmed) return;

    await safeRun(async () => {
      const wasSelected = selectedEpisode?.id === episode.id;
      await api.deleteEpisode(episode.id);
      await refreshDashboard();

      episodes = await api.episodes(project.id);

      if (episodes.length === 0) {
        selectedEpisode = null;
        shots = [];
        videoTasks = [];
        versions = await api.versions(project.id);
        resetEpisodeForm();
        activePage = 'episodes';
        return;
      }

      if (wasSelected) {
        const nextEpisode = episodes.find((item) => item.no > episode.no) || episodes[episodes.length - 1];
        await selectEpisode(nextEpisode, false);
        activePage = 'episodes';
        return;
      }

      const freshSelected = episodes.find((item) => item.id === selectedEpisode?.id);
      if (freshSelected) {
        await selectEpisode(freshSelected, false);
      }
    });
  }

  async function saveEpisodeOnly() {
    const episodeToSave = selectedEpisode;
    if (!episodeToSave) return;

    await safeRun(async () => {
      const episode = await api.updateEpisode(episodeToSave.id, buildEpisodePayload());
      await reloadCurrentProject();
      selectedEpisode = episode;
      fillEpisodeForm(episode);
    });
  }

  async function saveAndGenerateStoryboard() {
    const episodeToUpdate = selectedEpisode;
    if (!episodeToUpdate) return;

    await safeRun(async () => {
      await api.updateEpisode(episodeToUpdate.id, buildEpisodePayload());
      shots = await api.generateStoryboard(episodeToUpdate.id);
      await refreshDashboard();
      await reloadCurrentProject();
      activePage = 'script';
    });
  }

  async function runEpisodeVideoGeneration(episode: Episode) {
    selectedEpisode = episode;
    fillEpisodeForm(episode);
    videoTasks = await api.generateVideos(episode.id);
    shots = await api.shots(episode.id);
    await refreshDashboard();
    await reloadCurrentProject();
    activePage = 'video';
  }

  async function batchGenerateVideos() {
    const episodeToRender = selectedEpisode;
    if (!episodeToRender) return;

    await safeRun(async () => {
      await runEpisodeVideoGeneration(episodeToRender);
    });
  }

  async function generateVideosForEpisode(episode: Episode) {
    await safeRun(async () => {
      await runEpisodeVideoGeneration(episode);
    });
  }

  async function generateVideoForShot(shot: Shot) {
    const episode = selectedEpisode;
    if (!episode) return;

    await safeRun(async () => {
      await api.generateShotVideo(shot.id);
      shots = await api.shots(episode.id);
      videoTasks = await api.videoTasks(episode.id);

      if (currentProject) {
        episodes = await api.episodes(currentProject.id);
        selectedEpisode = episodes.find((item) => item.id === episode.id) || episode;
        versions = await api.versions(currentProject.id, episode.id);
      }

      await refreshDashboard();
      activePage = 'video';
    });
  }

  async function updateShot(shotId: string, payload: ShotUpdate) {
    error = '';
    try {
      const updatedShot = await api.updateShot(shotId, payload);
      shots = shots.map((shot) => (shot.id === shotId ? updatedShot : shot));
    } catch (err) {
      error = err instanceof Error ? err.message : '操作失败';
      throw err;
    }
  }

  async function createShot(payload: ShotPayload) {
    const episode = selectedEpisode;
    if (!episode) return;

    error = '';
    try {
      const createdShot = await api.createShot(episode.id, payload);
      shots = [...shots, createdShot].sort((a, b) => a.no - b.no);
      if (currentProject) {
        episodes = await api.episodes(currentProject.id);
        selectedEpisode = episodes.find((item) => item.id === episode.id) || selectedEpisode;
      }
    } catch (err) {
      error = err instanceof Error ? err.message : '操作失败';
      throw err;
    }
  }

  async function deleteShot(shot: Shot) {
    if (!confirm(`确定删除镜头 #${String(shot.no).padStart(2, '0')}「${shot.title}」吗？相关视频任务也会一并删除。`)) {
      return;
    }

    await safeRun(async () => {
      await api.deleteShot(shot.id);
      if (selectedEpisode) {
        shots = await api.shots(selectedEpisode.id);
        if (currentProject) {
          episodes = await api.episodes(currentProject.id);
          selectedEpisode = episodes.find((item) => item.id === selectedEpisode?.id) || selectedEpisode;
        }
      } else {
        shots = shots.filter((item) => item.id !== shot.id);
      }
    });
  }

  async function composeVideo() {
    const episodeToCompose = selectedEpisode;
    const project = currentProject;
    if (!episodeToCompose || !project) return;

    await safeRun(async () => {
      await api.compose(episodeToCompose.id, {
        description: '合成生成 / 9:16 / 待审核',
        ratio: '9:16',
        duration: episodeToCompose.duration_target
      });
      versions = await api.versions(project.id, episodeToCompose.id);
      await refreshDashboard();
      activePage = 'video';
    });
  }

  async function createAsset() {
    const project = currentProject;
    if (!project) return;

    await safeRun(async () => {
      const input = prompt('素材类型：character / scene / image / audio', 'character') || 'character';
      if (!assetTypes.includes(input as Asset['type'])) {
        alert('素材类型只能是 character / scene / image / audio');
        return;
      }

      const type = input as Asset['type'];
      const name = prompt('素材名称', type === 'scene' ? '新场景' : '新角色');
      if (!name) return;

      const description = prompt('素材描述', '请输入素材描述') || '';
      await api.createAsset(project.id, { type, name, description, initial: name.slice(0, 1) });
      assets = await api.assets(project.id);
      await refreshDashboard();
    });
  }
</script>

{#if !currentUser}
  <AuthScreen
    bind:authMode
    bind:authUsername
    bind:authPassword
    bind:authDisplayName
    {error}
    {loading}
    {submitAuth}
  />
{:else}
  <div class="app">
    <WorkspaceSidebar
      {activePage}
      {currentProject}
      {episodes}
      {projects}
      bind:projectPickerOpen
      {currentUser}
      {pointBalance}
      {usage}
      {setPage}
      {selectProject}
      {createProject}
      {logout}
    />

    <main class="main">
      <WorkspaceTopbar {activePage} {setPage} {batchGenerateVideos} {refreshDashboard} {handleTopAction} />

      <div class="content">
        {#if loading}
          <div class="loading">正在加载工作台...</div>
        {:else}
          {#if error}<div class="error">{error}</div>{/if}

          {#if activePage === 'projects'}
            <ProjectsPage {dashboard} {currentProject} {episodes} {projects} {setPage} {selectProject} {createProject} />
          {/if}

          {#if activePage === 'episodes'}
            <EpisodesPage {episodes} {selectEpisode} {generateVideosForEpisode} {deleteEpisode} />
          {/if}

          {#if activePage === 'script'}
            <ScriptPage
              {selectedEpisode}
              {currentProject}
              {shots}
              {versions}
              {assets}
              bind:episodeTitle
              bind:episodeSummary
              bind:episodeScript
              bind:episodeDuration
              {saveEpisodeOnly}
              {saveAndGenerateStoryboard}
              {generateVideoForShot}
              {createShot}
              {updateShot}
              {deleteShot}
            />
          {/if}

          {#if activePage === 'assets'}
            <AssetsPage {currentProject} {assets} bind:assetType {createAsset} />
          {/if}

          {#if activePage === 'video'}
            <VideoPage {selectedEpisode} {shots} {videoTasks} {versions} {composeVideo} />
          {/if}

          {#if activePage === 'account'}
            <AccountPage {currentUser} {usage} {pointBalance} {pointLedger} />
          {/if}
        {/if}
      </div>
    </main>
  </div>

  {#if episodeDialogOpen}
    <div class="modal-backdrop" role="presentation">
      <div class="modal-panel episode-create-modal" role="dialog" aria-modal="true" aria-labelledby="episode-create-title">
        <div class="modal-head">
          <div>
            <div class="modal-title-accent" id="episode-create-title">新建剧情</div>
            <div class="panel-subtitle">填写剧情描述，确认后可直接智能生成分镜。</div>
          </div>
          <button class="modal-close" aria-label="关闭" on:click={closeEpisodeDialog}>×</button>
        </div>

        <div class="modal-body">
          {#if episodeFormError}<div class="error compact-alert">{episodeFormError}</div>{/if}

          <div class="field-grid">
            <div class="field">
              <label for="new-episode-title">剧情标题</label>
              <input id="new-episode-title" bind:value={newEpisodeTitle} placeholder={`第${episodes.length + 1}集`} />
            </div>
            <div class="field">
              <label for="new-episode-duration">目标时长（秒）</label>
              <input id="new-episode-duration" type="number" min="1" bind:value={newEpisodeDuration} />
            </div>
          </div>

          <div class="field">
            <label for="new-episode-summary">剧情摘要</label>
            <input id="new-episode-summary" bind:value={newEpisodeSummary} placeholder="一句话说明本集冲突、转折和结尾钩子" />
          </div>

          <div class="field episode-description-field">
            <label for="new-episode-script">文本描述</label>
            <textarea
              id="new-episode-script"
              bind:value={newEpisodeScript}
              placeholder="写下本集剧情正文、关键对白、反转节奏或结尾悬念"
            ></textarea>
          </div>

          {#if pointBalance < storyboardCost}
            <div class="inline-hint warn">当前积分 {pointBalance}，不足以生成分镜。</div>
          {/if}
        </div>

        <div class="modal-actions modal-actions-split">
          <button
            class="btn btn-outline-generate"
            disabled={episodeSubmitting || pointBalance < storyboardCost}
            on:click={() => submitEpisode(true)}
          >
            {episodeSubmitting ? '处理中...' : `✨ 创建并智能生成分镜（ ${storyboardCost} 积分 ）`}
          </button>

          <div class="modal-action-right">
            <button class="btn btn-secondary" disabled={episodeSubmitting} on:click={closeEpisodeDialog}>取消</button>
            <button class="btn btn-primary" disabled={episodeSubmitting} on:click={() => submitEpisode(false)}>
              {episodeSubmitting ? '创建中...' : '确认创建剧情'}
            </button>
          </div>
        </div>
      </div>
    </div>
  {/if}

  {#if projectDialogOpen}
    <div class="modal-backdrop" role="presentation">
      <div class="modal-panel project-create-modal" role="dialog" aria-modal="true" aria-labelledby="project-create-title">
        <div class="modal-head">
          <div>
            <div class="modal-title-accent" id="project-create-title">新建短剧项目</div>
            <div class="panel-subtitle">填写短剧名称和简介，可先生成剧集大纲，确认后再创建项目。</div>
          </div>
          <button class="modal-close" aria-label="关闭" on:click={closeProjectDialog}>×</button>
        </div>

        <div class="modal-body">
          {#if projectFormError}<div class="error compact-alert">{projectFormError}</div>{/if}

          <div class="field">
            <label for="project-name">短剧名称</label>
            <input id="project-name" bind:value={projectName} placeholder="例如：错爱重生：她从婚礼现场逆袭" />
          </div>

          <div class="field">
            <label for="project-description">短剧简介</label>
            <textarea
              id="project-description"
              class="project-description-input"
              bind:value={projectDescription}
              placeholder="写清主角、核心冲突、爽点或反转。"
            ></textarea>
          </div>

          {#if pointBalance < outlineCost}
            <div class="inline-hint warn">当前积分 {pointBalance}，不足以生成短剧大纲。</div>
          {/if}

          {#if outlineEpisodes.length > 0}
            <div class="outline-preview">
              <div class="outline-preview-head">
                <div>
                  <div class="panel-title">剧集目录预览</div>
                  <div class="panel-subtitle">可在确认创建前微调每集标题和简介。</div>
                </div>
                <span class="status blue">{outlineEpisodes.length} 集</span>
              </div>

              <div class="outline-list">
                {#each outlineEpisodes as episode, index}
                  <div class="outline-item">
                    <div class="episode-no">{String(index + 1).padStart(2, '0')}</div>
                    <div class="outline-item-body">
                      <input
                        aria-label={`第${index + 1}集标题`}
                        value={episode.title}
                        on:input={(event) => updateOutlineEpisode(index, 'title', event.currentTarget.value)}
                      />
                      <textarea
                        aria-label={`第${index + 1}集简介`}
                        value={episode.summary}
                        on:input={(event) => updateOutlineEpisode(index, 'summary', event.currentTarget.value)}
                      ></textarea>
                    </div>
                  </div>
                {/each}
              </div>
            </div>
          {/if}
        </div>

        <div class="modal-actions modal-actions-split">
          <button
            class="btn btn-outline-generate"
            disabled={outlineLoading || projectSubmitting || pointBalance < outlineCost}
            on:click={generateProjectOutline}
          >
            {outlineLoading ? '生成中...' : `✨智能生成大纲（ ${outlineCost} 积分 ）`}
          </button>

          <div class="modal-action-right">
            <button class="btn btn-secondary" disabled={outlineLoading || projectSubmitting} on:click={closeProjectDialog}>取消</button>
            <button class="btn btn-primary" disabled={outlineLoading || projectSubmitting} on:click={submitProject}>
              {projectSubmitting ? '创建中...' : outlineEpisodes.length > 0 ? `确认创建项目和 ${outlineEpisodes.length} 集` : '确认创建项目'}
            </button>
          </div>
        </div>
      </div>
    </div>
  {/if}
{/if}
