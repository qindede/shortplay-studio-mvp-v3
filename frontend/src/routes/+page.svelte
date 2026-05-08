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
    type Shot,
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
    const project = currentProject;
    if (!project) return;

    await safeRun(async () => {
      const title = prompt('剧集标题', `第${episodes.length + 1}集`);
      if (!title) return;

      const summary = prompt('剧情摘要', '请输入本集剧情摘要') || '';
      const episode = await api.createEpisode(project.id, {
        title,
        summary,
        script: summary,
        duration_target: 30
      });

      episodes = await api.episodes(project.id);
      await selectEpisode(episode, true);
      await refreshDashboard();
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

  async function batchGenerateVideos() {
    const episodeToRender = selectedEpisode;
    if (!episodeToRender) return;

    await safeRun(async () => {
      videoTasks = await api.generateVideos(episodeToRender.id);
      shots = await api.shots(episodeToRender.id);
      await refreshDashboard();
      activePage = 'video';
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
            <EpisodesPage {episodes} {selectedEpisode} {selectEpisode} {createEpisode} />
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
              {setPage}
              {saveEpisodeOnly}
              {saveAndGenerateStoryboard}
              {batchGenerateVideos}
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
{/if}
