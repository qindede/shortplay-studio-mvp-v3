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
    type PointLedgerResponse,
    type Project,
    type ProjectOutlineEpisode,
    type Shot,
    type ShotPayload,
    type ShotUpdate,
    type StoryboardAssetCandidate,
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
  import PasswordPage from '$lib/components/workspace/pages/PasswordPage.svelte';
  import ProjectsPage from '$lib/components/workspace/pages/ProjectsPage.svelte';
  import ScriptPage from '$lib/components/workspace/pages/ScriptPage.svelte';
  import VideoPage from '$lib/components/workspace/pages/VideoPage.svelte';
  import { type AuthMode, type PageKey } from '$lib/workspace/ui';
  import ConfirmDialog from '$lib/components/workspace/ConfirmDialog.svelte';
  import CreateAssetModal from '$lib/components/workspace/pages/CreateAssetModal.svelte';
  import PromptOptimizeButton from '$lib/components/workspace/PromptOptimizeButton.svelte';

  type AssetFilter = 'all' | Asset['type'];
  type DeleteConfirmState = {
    title: string;
    message: string;
    detail?: string;
    confirmText: string;
    resolve: (confirmed: boolean) => void;
  };
  type StoryboardAssetConfirmState = {
    assets: StoryboardAssetCandidate[];
    cost: number;
    assetCost: number;
    selected: Record<string, boolean>;
    phase: 'confirming' | 'generating' | 'failed';
    error: string;
    episodeId: string;
    resolve: (completed: boolean) => void;
  };

  let activePage: PageKey = 'projects';
  let loading = true;
  let error = '';

  let currentUser: User | null = null;
  let authMode: AuthMode = 'login';
  let authUsername = '';
  let authPassword = '';
  let pointLedger: PointLedgerResponse = { items: [], total: 0 };

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
  let editingProject: Project | null = null;
  let projectName = '';
  let projectDescription = '';
  let outlineCost = 20;
  let storyboardCost = 20;
  let episodeCount = 12;
  let outlineEpisodes: ProjectOutlineEpisode[] = [];
  let outlineLoading = false;
  let projectSubmitting = false;
  let projectFormError = '';
  let deleteConfirm: DeleteConfirmState | null = null;
  let storyboardAssetConfirm: StoryboardAssetConfirmState | null = null;
  let showCreateAssetModal = false;

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
    editingProject = null;
    projectName = '';
    projectDescription = '';
    episodeCount = 12;
    outlineEpisodes = [];
    outlineLoading = false;
    projectSubmitting = false;
    projectFormError = '';
  }

  function openProjectDialog() {
    resetProjectForm();
    projectDialogOpen = true;
  }

  function openProjectEditDialog(project: Project) {
    resetProjectForm();
    editingProject = project;
    projectName = project.name;
    projectDescription = project.description;
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
    pointLedger = { items: [], total: 0 };
    assetType = 'all';
    projectPickerOpen = false;
    activePage = 'projects';
    projectDialogOpen = false;
    episodeDialogOpen = false;
    cancelDeleteConfirm();
    resetProjectForm();
    resetNewEpisodeForm();
    resetEpisodeForm();
  }

  function requestDeleteConfirmation(options: Omit<DeleteConfirmState, 'resolve'>) {
    return new Promise<boolean>((resolve) => {
      deleteConfirm = { ...options, resolve };
    });
  }

  function cancelDeleteConfirm() {
    if (!deleteConfirm) return;
    deleteConfirm.resolve(false);
    deleteConfirm = null;
  }

  function confirmDeleteDialog() {
    if (!deleteConfirm) return;
    deleteConfirm.resolve(true);
    deleteConfirm = null;
  }

  function assetCandidateKey(asset: StoryboardAssetCandidate) {
    return `${asset.type}:${asset.name}`;
  }

  function requestStoryboardAssetConfirmation(episodeId: string, assetsToCreate: StoryboardAssetCandidate[], cost: number, assetCost: number) {
    return new Promise<boolean>((resolve) => {
      storyboardAssetConfirm = {
        assets: assetsToCreate,
        cost,
        assetCost,
        selected: Object.fromEntries(assetsToCreate.map((asset) => [assetCandidateKey(asset), true])),
        phase: 'confirming',
        error: '',
        episodeId,
        resolve
      };
    });
  }

  function cancelStoryboardAssetConfirm() {
    if (!storyboardAssetConfirm || storyboardAssetConfirm.phase === 'generating') return;
    storyboardAssetConfirm.resolve(false);
    storyboardAssetConfirm = null;
  }

  async function confirmStoryboardAssetDialog() {
    if (!storyboardAssetConfirm || storyboardAssetConfirm.phase === 'generating') return;
    const currentConfirm = storyboardAssetConfirm;
    const selectedAssets = currentConfirm.assets.filter((asset) => currentConfirm.selected[assetCandidateKey(asset)]);
    storyboardAssetConfirm = { ...currentConfirm, phase: 'generating', error: '' };

    try {
      await runStoryboardGeneration(currentConfirm.episodeId, selectedAssets);
      currentConfirm.resolve(true);
      storyboardAssetConfirm = null;
    } catch (err) {
      storyboardAssetConfirm = {
        ...currentConfirm,
        phase: 'failed',
        error: err instanceof Error ? err.message : '素材或分镜生成失败'
      };
    }
  }

  function toggleStoryboardAsset(asset: StoryboardAssetCandidate) {
    if (!storyboardAssetConfirm || storyboardAssetConfirm.phase !== 'confirming') return;
    const key = assetCandidateKey(asset);
    storyboardAssetConfirm = {
      ...storyboardAssetConfirm,
      selected: {
        ...storyboardAssetConfirm.selected,
        [key]: !storyboardAssetConfirm.selected[key]
      }
    };
  }

  $: storyboardSelectedCount = storyboardAssetConfirm
    ? storyboardAssetConfirm.assets.filter((asset) => storyboardAssetConfirm?.selected[assetCandidateKey(asset)]).length
    : 0;
  $: storyboardConfirmCost = storyboardAssetConfirm
    ? storyboardAssetConfirm.cost + storyboardSelectedCount * storyboardAssetConfirm.assetCost
    : 0;

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
          : await api.register({ username: authUsername, password: authPassword, display_name: authUsername });

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
    authUsername = '';
    authPassword = '';
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
    const bootstrap = await api.workspaceBootstrap();

    dashboard = bootstrap.dashboard;
    usage = dashboard.usage;
    currentUser = dashboard.current_user || (await api.me());
    if (currentUser.role === 'admin') {
      goto('/admin');
      return;
    }
    pointLedger = bootstrap.point_ledger;
    projects = bootstrap.projects;

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

    currentProject = bootstrap.current_project;
    episodes = bootstrap.episodes;
    assets = bootstrap.assets;
    selectedEpisode = bootstrap.selected_episode;
    shots = bootstrap.shots;
    videoTasks = bootstrap.video_tasks;
    versions = bootstrap.versions;
    if (selectedEpisode) {
      fillEpisodeForm(selectedEpisode);
    } else {
      resetEpisodeForm();
    }
  }

  async function refreshDashboard() {
    const [dashboardData, ledgerData, projectData] = await Promise.all([
      api.dashboard(),
      api.myLedger(),
      api.projects()
    ]);

    dashboard = dashboardData;
    usage = dashboard.usage;
    currentUser = dashboard.current_user || (await api.me());
    pointLedger = ledgerData;
    projects = projectData;

    if (currentProject) {
      currentProject = projects.find((project) => project.id === currentProject?.id) || currentProject;
    }
  }

  async function selectProject(project: Project, goEpisodes = true) {
    currentProject = project;
    projectPickerOpen = false;
    const [episodeData, assetData] = await Promise.all([
      api.episodes(project.id),
      api.assets(project.id)
    ]);
    episodes = episodeData;
    assets = assetData;

    if (episodes.length === 0) {
      selectedEpisode = null;
      shots = [];
      videoTasks = [];
      versions = await api.versions(project.id);
      resetEpisodeForm();
    } else {
      await selectEpisode(episodes[0], false);
    }

    if (goEpisodes) activePage = 'episodes';
  }

  async function selectEpisode(episode: Episode, goScript = false) {
    selectedEpisode = episode;
    fillEpisodeForm(episode);
    if (goScript) activePage = 'script';
    const workspace = await api.episodeWorkspace(episode.id);
    shots = workspace.shots;
    videoTasks = workspace.video_tasks;
    versions = workspace.versions;
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

  function editProject(project: Project) {
    openProjectEditDialog(project);
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
        description,
        episode_count: episodeCount
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
    const projectToEdit = editingProject;
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
      if (projectToEdit) {
        const project = await api.updateProject(projectToEdit.id, {
          name,
          description
        });
        projectDialogOpen = false;
        resetProjectForm();
        await refreshDashboard();
        currentProject = projects.find((item) => item.id === project.id) || project;
        if (currentProject.id === project.id) {
          await selectProject(currentProject, false);
        }
        activePage = 'projects';
        return;
      }

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

  async function deleteProject(projectToDelete: Project) {
    if (!projectToDelete || projectSubmitting) return;

    const confirmed = await requestDeleteConfirmation({
      title: '删除项目',
      message: `确定删除项目「${projectToDelete.name}」吗？`,
      detail: '项目下的剧集、分镜、素材、视频任务和成片版本都会一并删除，此操作不可恢复。',
      confirmText: '确认删除'
    });
    if (!confirmed) return;

    projectSubmitting = true;
    projectFormError = '';
    error = '';
    try {
      await api.deleteProject(projectToDelete.id);
      projectDialogOpen = false;
      resetProjectForm();
      await refreshDashboard();

      if (projects.length === 0) {
        currentProject = null;
        episodes = [];
        selectedEpisode = null;
        shots = [];
        assets = [];
        videoTasks = [];
        versions = [];
        resetEpisodeForm();
        activePage = 'projects';
        return;
      }

      await selectProject(projects[0], false);
      activePage = 'projects';
    } catch (err) {
      error = err instanceof Error ? err.message : '删除项目失败';
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
        episodeDialogOpen = false;
        await generateStoryboardWithAssetCheck(episode.id);
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

    const confirmed = await requestDeleteConfirmation({
      title: '删除剧集',
      message: `确定删除第 ${String(episode.no).padStart(2, '0')} 集「${episode.title}」吗？`,
      detail: '相关分镜、视频任务和成片版本也会一并删除，此操作不可恢复。',
      confirmText: '确认删除'
    });
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
      await generateStoryboardWithAssetCheck(episodeToUpdate.id);
      await refreshDashboard();
      await reloadCurrentProject();
      activePage = 'script';
    });
  }

  async function generateStoryboardWithAssetCheck(episodeId: string) {
    const preparation = await api.prepareStoryboard(episodeId);

    if (preparation.missing_assets.length > 0) {
      const completed = await requestStoryboardAssetConfirmation(
        episodeId,
        preparation.missing_assets,
        preparation.cost,
        preparation.asset_cost
      );
      if (!completed) return;
      return;
    }

    await runStoryboardGeneration(episodeId, []);
  }

  async function runStoryboardGeneration(episodeId: string, confirmedAssets: StoryboardAssetCandidate[]) {
    shots = await api.generateStoryboard(episodeId, { confirmed_assets: confirmedAssets });
    if (currentProject) {
      assets = await api.assets(currentProject.id);
    }
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

  async function regenerateVideo(shotId: string) {
    const episode = selectedEpisode;
    if (!episode) return;

    await safeRun(async () => {
      await api.generateShotVideo(shotId);
      videoTasks = await api.videoTasks(episode.id);
      shots = await api.shots(episode.id);
      await refreshDashboard();
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
        const updatedEpisode = {
          ...episode,
          status: 'storyboard_ready' as const,
          status_label: '分镜就绪',
          shot_count: shots.length,
          updated_at: createdShot.updated_at
        };
        episodes = episodes.map((item) => (item.id === episode.id ? updatedEpisode : item));
        selectedEpisode = updatedEpisode;
      }
    } catch (err) {
      error = err instanceof Error ? err.message : '操作失败';
      throw err;
    }
  }

  async function deleteShot(shot: Shot) {
    const confirmed = await requestDeleteConfirmation({
      title: '删除镜头',
      message: `确定删除镜头 #${String(shot.no).padStart(2, '0')}「${shot.title}」吗？`,
      detail: '相关视频任务也会一并删除，此操作不可恢复。',
      confirmText: '确认删除'
    });
    if (!confirmed) {
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
    if (!currentProject) return;
    showCreateAssetModal = true;
  }

  function handleAssetCreated(asset: Asset) {
    assets = [asset, ...assets];
    showCreateAssetModal = false;
    refreshDashboard();
  }

  async function deleteAsset(asset: Asset) {
    const confirmed = await requestDeleteConfirmation({
      title: '删除素材',
      message: `确定删除「${asset.name}」吗？`,
      detail: '此操作不可恢复。',
      confirmText: '确认删除'
    });
    if (!confirmed) return;

    await safeRun(async () => {
      await api.deleteAsset(asset.id);
      assets = assets.filter((a) => a.id !== asset.id);
    });
  }

  function handleAssetUpdated(asset: Asset) {
    assets = assets.map((a) => (a.id === asset.id ? asset : a));
  }

  async function deleteVersion(version: VideoVersion) {
    const confirmed = await requestDeleteConfirmation({
      title: '删除版本',
      message: `确定删除「${version.name}」吗？`,
      detail: '此操作不可恢复。',
      confirmText: '确认删除'
    });
    if (!confirmed) return;

    await safeRun(async () => {
      await api.deleteVersion(version.id);
      versions = versions.filter((v) => v.id !== version.id);
    });
  }
</script>

{#if !currentUser}
  <AuthScreen
    bind:authMode
    bind:authUsername
    bind:authPassword
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
      {setPage}
      {selectProject}
      {createProject}
      {logout}
    />

    <main class="main">
      <WorkspaceTopbar {activePage} {setPage} {refreshDashboard} {handleTopAction} />

      <div class="content">
        {#if loading}
          <div class="loading">正在加载工作台...</div>
        {:else}
          {#if error}<div class="error">{error}</div>{/if}

          {#if activePage === 'projects'}
            <ProjectsPage {dashboard} {currentProject} {episodes} {projects} {setPage} {selectProject} {createProject} {editProject} {deleteProject} />
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
              {storyboardCost}
              {saveEpisodeOnly}
              {saveAndGenerateStoryboard}
              {generateVideoForShot}
              {createShot}
              {updateShot}
              {deleteShot}
            />
          {/if}

          {#if activePage === 'assets'}
            <AssetsPage {currentProject} {assets} bind:assetType {createAsset} on:deleteAsset={(e) => deleteAsset(e.detail)} on:assetUpdated={(e) => handleAssetUpdated(e.detail)} />
          {/if}

          {#if activePage === 'video'}
            <VideoPage {selectedEpisode} {shots} {videoTasks} {versions} {composeVideo} {regenerateVideo} on:deleteVersion={(e) => deleteVersion(e.detail)} />
          {/if}

          {#if activePage === 'account'}
            <AccountPage {currentUser} {usage} {pointBalance} {pointLedger} />
          {/if}

          {#if activePage === 'password'}
            <PasswordPage />
          {/if}
        {/if}
      </div>
    </main>
  </div>

  {#if deleteConfirm}
    <ConfirmDialog
      title={deleteConfirm.title}
      message={deleteConfirm.message}
      detail={deleteConfirm.detail || ''}
      confirmText={deleteConfirm.confirmText}
      cancelText="取消"
      onConfirm={confirmDeleteDialog}
      onCancel={cancelDeleteConfirm}
    />
  {/if}

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
            <div class="prompt-field">
              <textarea
                id="new-episode-script"
                bind:value={newEpisodeScript}
                placeholder="写下本集剧情正文、关键对白、反转节奏或结尾悬念"
              ></textarea>
              <PromptOptimizeButton
                value={newEpisodeScript}
                context="episode_script"
                {projectName}
                onOptimized={(v) => (newEpisodeScript = v)}
              />
            </div>
          </div>

          {#if pointBalance < storyboardCost}
            <div class="inline-hint warn">当前积分 {pointBalance}，不足以生成分镜。</div>
          {/if}
        </div>

        <div class="modal-actions modal-actions-split" class:modal-actions-right-only={editingProject}>
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
            <div class="modal-title-accent" id="project-create-title">{editingProject ? '编辑短剧项目' : '新建短剧项目'}</div>
            <div class="panel-subtitle">{editingProject ? '更新短剧名称和简介，保存后会同步到项目中心。' : '填写短剧名称和简介，可先生成剧集大纲，确认后再创建项目。'}</div>
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
            <div class="prompt-field">
              <textarea
                id="project-description"
                class="project-description-input"
                bind:value={projectDescription}
                placeholder="写清主角、核心冲突、爽点或反转。"
              ></textarea>
              {#if !editingProject}
                <PromptOptimizeButton
                  value={projectDescription}
                  context="project_description"
                  {projectName}
                  onOptimized={(v) => (projectDescription = v)}
                />
              {/if}
            </div>
          </div>

          {#if !editingProject && pointBalance < outlineCost}
            <div class="inline-hint warn">当前积分 {pointBalance}，不足以生成短剧大纲。</div>
          {/if}

          {#if !editingProject && outlineEpisodes.length > 0}
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

        <div class="modal-actions" class:modal-actions-split={!editingProject} class:modal-actions-right-only={editingProject}>
          {#if !editingProject}
            <div class="outline-generate-row">
              <input class="episode-count-input" type="number" min="3" max="24" bind:value={episodeCount} disabled={outlineLoading || projectSubmitting} />
              <button
                class="btn btn-outline-generate"
                disabled={outlineLoading || projectSubmitting || pointBalance < outlineCost}
                on:click={generateProjectOutline}
              >
                {outlineLoading ? '生成中...' : `✨智能生成大纲（ ${outlineCost} 积分 ）`}
              </button>
            </div>
          {/if}

          <div class="modal-action-right">
            <button class="btn btn-secondary" disabled={outlineLoading || projectSubmitting} on:click={closeProjectDialog}>取消</button>
            <button class="btn btn-primary" disabled={outlineLoading || projectSubmitting} on:click={submitProject}>
              {projectSubmitting ? (editingProject ? '保存中...' : '创建中...') : editingProject ? '保存修改' : outlineEpisodes.length > 0 ? `确认创建项目和 ${outlineEpisodes.length} 集` : '确认创建项目'}
            </button>
          </div>
        </div>
      </div>
    </div>
  {/if}

  {#if storyboardAssetConfirm}
    <div class="modal-backdrop" role="presentation">
      <div class="modal-panel storyboard-asset-modal" role="dialog" aria-modal="true" aria-labelledby="storyboard-asset-title">
        <div class="modal-head">
          <div>
            <div class="modal-title-accent" id="storyboard-asset-title">
              {storyboardAssetConfirm.phase === 'generating' ? '正在生成素材和分镜' : storyboardAssetConfirm.phase === 'failed' ? '生成失败' : '生成分镜前需要补充素材'}
            </div>
            <div class="panel-subtitle">
              {storyboardAssetConfirm.phase === 'generating'
                ? '系统正在生成选中的素材，并继续生成本集镜头表。完成后会自动更新分镜。'
                : storyboardAssetConfirm.phase === 'failed'
                  ? '素材或分镜没有完成生成，请查看错误后重试。'
                  : '系统检测到本集包含项目中尚未创建的角色或场景。确认后将自动生成选中的素材，并用于后续分镜。'}
            </div>
          </div>
          <button class="modal-close" aria-label="关闭" disabled={storyboardAssetConfirm.phase === 'generating'} on:click={cancelStoryboardAssetConfirm}>×</button>
        </div>

        <div class="modal-body">
          {#if storyboardAssetConfirm.phase === 'generating'}
            <div class="storyboard-progress-card">
              <div class="loading-dot"></div>
              <div>
                <b>生成任务进行中</b>
                <span>已确认 {storyboardSelectedCount} 个新素材，正在依次生成素材图片和分镜内容。</span>
              </div>
            </div>
          {/if}

          {#if storyboardAssetConfirm.phase === 'failed'}
            <div class="error compact-alert">{storyboardAssetConfirm.error}</div>
          {/if}

          <div class="storyboard-asset-summary">
            <div>
              <span>分镜生成</span>
              <b>{storyboardAssetConfirm.cost} 积分</b>
            </div>
            <div>
              <span>新增素材</span>
              <b>{storyboardSelectedCount} × {storyboardAssetConfirm.assetCost} 积分</b>
            </div>
            <div>
              <span>本次预计</span>
              <b>{storyboardConfirmCost} 积分</b>
            </div>
          </div>

          {#if pointBalance < storyboardConfirmCost}
            <div class="inline-hint warn">当前积分 {pointBalance}，不足以完成所选素材和分镜生成。</div>
          {/if}

          <div class="storyboard-asset-list">
            {#each storyboardAssetConfirm.assets as asset}
              {@const key = assetCandidateKey(asset)}
              <button
                class="storyboard-asset-item"
                class:selected={storyboardAssetConfirm.selected[key]}
                disabled={storyboardAssetConfirm.phase === 'generating'}
                type="button"
                on:click={() => toggleStoryboardAsset(asset)}
              >
                <span class="status {asset.type === 'character' ? 'purple' : 'blue'}">{asset.type === 'character' ? '角色' : '场景'}</span>
                <span class="storyboard-asset-copy">
                  <b>{asset.name}</b>
                  <span>{asset.description}</span>
                </span>
                <span class="storyboard-asset-check">{storyboardAssetConfirm.selected[key] ? '生成' : '跳过'}</span>
              </button>
            {/each}
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn btn-secondary" disabled={storyboardAssetConfirm.phase === 'generating'} on:click={cancelStoryboardAssetConfirm}>
            {storyboardAssetConfirm.phase === 'failed' ? '关闭' : '取消'}
          </button>
          <button
            class="btn btn-primary"
            disabled={pointBalance < storyboardConfirmCost || storyboardAssetConfirm.phase === 'generating'}
            on:click={confirmStoryboardAssetDialog}
          >
            {storyboardAssetConfirm.phase === 'generating'
              ? '生成中...'
              : storyboardAssetConfirm.phase === 'failed'
                ? '重试生成'
                : '确认并生成素材与分镜'}
          </button>
        </div>
      </div>
    </div>
  {/if}

  {#if currentProject}
    <CreateAssetModal
      show={showCreateAssetModal}
      projectId={currentProject.id}
      projectName={currentProject?.short_name || ''}
      {pointBalance}
      onCreate={handleAssetCreated}
      onClose={() => (showCreateAssetModal = false)}
    />
  {/if}
{/if}
