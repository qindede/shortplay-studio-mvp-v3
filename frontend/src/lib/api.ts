const API_BASE = import.meta.env.VITE_API_BASE || '';

let authToken = '';

export function loadAuthToken() {
  if (typeof localStorage === 'undefined') return '';
  authToken = localStorage.getItem('shortplay_token') || '';
  return authToken;
}

export function setAuthToken(token: string) {
  authToken = token;
  if (typeof localStorage !== 'undefined') localStorage.setItem('shortplay_token', token);
}

export function clearAuthToken() {
  authToken = '';
  if (typeof localStorage !== 'undefined') localStorage.removeItem('shortplay_token');
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(authToken ? { 'X-User-Token': authToken } : {}),
      ...(options.headers || {})
    },
    ...options
  });

  if (!response.ok) {
    let message = `Request failed: ${response.status}`;
    try {
      const text = await response.text();
      try {
        const body = JSON.parse(text);
        if (Array.isArray(body.detail)) {
          message = body.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join('; ');
        } else if (typeof body.detail === 'string') {
          message = body.detail;
        }
      } catch {
        message = text || message;
      }
    } catch {
      // body unreadable, keep default message
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export type Status = 'active' | 'review' | 'draft' | 'completed' | 'storyboard_ready' | 'generating' | 'pending' | 'needs_review' | 'exported' | 'failed';
export type UserRole = 'user' | 'admin';
export type UserStatus = 'active' | 'disabled';

export interface User {
  id: string;
  username: string;
  display_name: string;
  role: UserRole;
  status: UserStatus;
  points: number;
  created_at: string;
  last_login: string;
}

export interface AuthResponse {
  user: User;
  token: string;
}

export interface PointLedger {
  id: string;
  user_id: string;
  username: string;
  display_name: string;
  amount: number;
  type: string;
  scene: string;
  description: string;
  balance_after: number;
  created_at: string;
}

export interface PointLedgerResponse {
  items: PointLedger[];
  total: number;
}

export interface AdminSummary {
  user_count: number;
  active_user_count: number;
  total_balance: number;
  consumed_points: number;
  granted_points: number;
  ledger_count: number;
}

export interface Dashboard {
  project_count: number;
  episode_count: number;
  version_count: number;
  asset_count: number;
  usage: Usage;
  current_user?: User;
}

export interface WorkspaceBootstrap {
  dashboard: Dashboard;
  point_ledger: PointLedgerResponse;
  projects: Project[];
  current_project: Project | null;
  episodes: Episode[];
  selected_episode: Episode | null;
  shots: Shot[];
  assets: Asset[];
  video_jobs: VideoJob[];
  versions: VideoVersion[];
}

export interface EpisodeWorkspace {
  shots: Shot[];
  video_jobs: VideoJob[];
  versions: VideoVersion[];
}

export interface Usage {
  video_total_seconds: number;
  video_used_seconds: number;
  image_total: number;
  image_used: number;
  export_total: number;
  export_used: number;
  team_members: number;
}

export interface Project {
  id: string;
  name: string;
  short_name: string;
  description: string;
  status: Status;
  status_label: string;
  owner: string;
  owner_user_id: string;
  cover: string;
  cover_image?: string;
  created_at: string;
  updated_at: string;
  episode_count: number;
  asset_count: number;
  version_count: number;
}

export interface Episode {
  id: string;
  project_id: string;
  no: number;
  title: string;
  summary: string;
  script: string;
  duration_target: number;
  status: Status;
  status_label: string;
  updated_at: string;
  shot_count: number;
  version_count: number;
}

export interface ProjectOutlineEpisode {
  title: string;
  summary: string;
  script: string;
  duration_target: number;
}

export interface ProjectOutline {
  cost: number;
  episodes: ProjectOutlineEpisode[];
}

export interface Shot {
  id: string;
  episode_id: string;
  no: number;
  title: string;
  visual: string;
  dialogue: string;
  characters: string[];
  scene: string;
  duration: number;
  status: Status;
  updated_at: string;
}

export type ShotPayload = Pick<Shot, 'title' | 'visual' | 'dialogue' | 'characters' | 'scene' | 'duration'>;
export type ShotUpdate = Partial<ShotPayload>;

export interface Asset {
  id: string;
  project_id: string;
  type: 'character' | 'scene' | 'image' | 'audio';
  name: string;
  description: string;
  ref_count: number;
  initial: string;
  image?: string;
  voice?: string;
  voice_url?: string;
  voice_status?: Status | 'uploaded';
  speaker_id?: string;
  references?: AssetReference[];
  updated_at: string;
}

export interface AssetReference {
  id: string;
  type: 'image' | 'audio' | 'video' | 'text';
  name: string;
  url?: string;
  note?: string;
}

export interface StoryboardAssetCandidate {
  type: 'character' | 'scene';
  name: string;
  description: string;
  prompt: string;
}

export interface StoryboardPrepareResponse {
  cost: number;
  asset_cost: number;
  missing_assets: StoryboardAssetCandidate[];
}

export interface VideoJob {
  id: string;
  episode_id: string;
  shot_id: string;
  title: string;
  duration: number;
  progress: number;
  status: Status;
  updated_at: string;
  preview_url?: string;
  video_url?: string;
  error?: string;
  provider?: string;
  provider_task_id?: string;
}

export interface VideoVersion {
  id: string;
  project_id: string;
  episode_id: string;
  name: string;
  description: string;
  duration: number;
  ratio: string;
  status: Status;
  theme: string;
  created_at: string;
  preview_url?: string;
  video_url?: string;
}

export interface AiJob {
  id: string;
  user_id: string;
  project_id?: string;
  episode_id?: string;
  shot_id?: string;
  asset_id?: string;
  type: string;
  provider: string;
  provider_task_id?: string;
  status: string;
  progress: number;
  error?: string;
  cost_points: number;
  created_at: string;
  updated_at: string;
}

export const api = {
  register: (body: { username: string; password: string; display_name?: string }) =>
    request<AuthResponse>('/api/auth/register', { method: 'POST', body: JSON.stringify(body) }),
  login: (body: { username: string; password: string }) =>
    request<AuthResponse>('/api/auth/login', { method: 'POST', body: JSON.stringify(body) }),
  me: () => request<User>('/api/me'),
  changePassword: (body: { current_password: string; new_password: string }) =>
    request<{ ok: boolean }>('/api/me/password', { method: 'PATCH', body: JSON.stringify(body) }),
  myLedger: (page = 1, pageSize = 10) => request<PointLedgerResponse>(`/api/me/point-ledger?page=${page}&page_size=${pageSize}`),

  workspaceBootstrap: () => request<WorkspaceBootstrap>('/api/workspace/bootstrap'),
  dashboard: () => request<Dashboard>('/api/dashboard'),
  projects: () => request<Project[]>('/api/projects'),
  createProject: (body: { name: string; description: string; owner?: string; episodes?: ProjectOutlineEpisode[] }) =>
    request<Project>('/api/projects', { method: 'POST', body: JSON.stringify(body) }),
  updateProject: (projectId: string, body: { name?: string; description?: string; status?: Status }) =>
    request<Project>(`/api/projects/${projectId}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteProject: (projectId: string) =>
    request<{ ok: boolean }>(`/api/projects/${projectId}`, { method: 'DELETE' }),
  generateProjectOutline: (body: { name: string; description: string; episode_count?: number }) =>
    request<ProjectOutline>('/api/projects/generate-outline', { method: 'POST', body: JSON.stringify(body) }),
  episodes: (projectId: string) => request<Episode[]>(`/api/projects/${projectId}/episodes`),
  createEpisode: (projectId: string, body: { title: string; summary: string; script: string; duration_target: number }) =>
    request<Episode>(`/api/projects/${projectId}/episodes`, { method: 'POST', body: JSON.stringify(body) }),
  updateEpisode: (episodeId: string, body: Partial<Episode>) =>
    request<Episode>(`/api/episodes/${episodeId}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteEpisode: (episodeId: string) =>
    request<{ ok: boolean }>(`/api/episodes/${episodeId}`, { method: 'DELETE' }),
  episodeWorkspace: (episodeId: string) => request<EpisodeWorkspace>(`/api/episodes/${episodeId}/workspace`),
  shots: (episodeId: string) => request<Shot[]>(`/api/episodes/${episodeId}/shots`),
  createShot: (episodeId: string, body: ShotPayload) =>
    request<Shot>(`/api/episodes/${episodeId}/shots`, { method: 'POST', body: JSON.stringify(body) }),
  updateShot: (shotId: string, body: ShotUpdate) =>
    request<Shot>(`/api/shots/${shotId}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteShot: (shotId: string) =>
    request<{ ok: boolean }>(`/api/shots/${shotId}`, { method: 'DELETE' }),
  prepareStoryboard: (episodeId: string) =>
    request<StoryboardPrepareResponse>(`/api/episodes/${episodeId}/prepare-storyboard`, { method: 'POST' }),
  generateStoryboard: (episodeId: string, body: { confirmed_assets?: StoryboardAssetCandidate[] } = {}) =>
    request<Shot[]>(`/api/episodes/${episodeId}/generate-storyboard`, { method: 'POST', body: JSON.stringify(body) }),
  generateShotVideo: (shotId: string) => request<VideoJob>(`/api/shots/${shotId}/generate-video`, { method: 'POST' }),
  generateVideos: (episodeId: string) => request<VideoJob[]>(`/api/episodes/${episodeId}/generate-videos`, { method: 'POST' }),
  videoJobs: (episodeId: string) => request<VideoJob[]>(`/api/episodes/${episodeId}/video-jobs`),
  assets: (projectId: string, type?: string) => request<Asset[]>(`/api/projects/${projectId}/assets${type ? `?type=${type}` : ''}`),
  createAsset: (projectId: string, body: { type: string; name: string; description: string; initial: string; image?: string; voice?: string; voice_url?: string; references?: { type: string; name: string; url?: string; note?: string }[] }) =>
    request<Asset>(`/api/projects/${projectId}/assets`, { method: 'POST', body: JSON.stringify(body) }),
  generateAsset: (projectId: string, body: { type: string; name: string; description: string; prompt: string }) =>
    request<Asset>(`/api/projects/${projectId}/assets/generate`, { method: 'POST', body: JSON.stringify(body) }),
  deleteAsset: (assetId: string) =>
    request<{ ok: boolean }>(`/api/assets/${assetId}`, { method: 'DELETE' }),
  updateAsset: (assetId: string, body: { name?: string; description?: string; initial?: string; image?: string; voice?: string; voice_url?: string; references?: { id?: string; type: string; name: string; url?: string; note?: string }[] }) =>
    request<Asset>(`/api/assets/${assetId}`, { method: 'PUT', body: JSON.stringify(body) }),
  startVoiceClone: (assetId: string, body: { voice_url?: string; consent: boolean }) =>
    request<Asset>(`/api/assets/${assetId}/voice-clone`, { method: 'POST', body: JSON.stringify(body) }),
  voiceCloneStatus: (assetId: string) => request<Asset>(`/api/assets/${assetId}/voice-clone`),
  optimizePrompt: (body: { prompt: string; context: string; projectName?: string }) =>
    request<{ optimized: string }>('/api/optimize-prompt', { method: 'POST', body: JSON.stringify(body) }),
  upload: async (file: File): Promise<{ url: string }> => {
    const form = new FormData();
    form.append('file', file);
    const response = await fetch(`${API_BASE}/api/upload`, {
      method: 'POST',
      headers: { ...(authToken ? { 'X-User-Token': authToken } : {}) },
      body: form
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `Upload failed: ${response.status}`);
    }
    return response.json();
  },
  versions: (projectId: string, episodeId?: string) =>
    request<VideoVersion[]>(`/api/projects/${projectId}/video-versions${episodeId ? `?episode_id=${episodeId}` : ''}`),
  deleteVersion: (versionId: string) =>
    request<{ ok: boolean }>(`/api/video-versions/${versionId}`, { method: 'DELETE' }),
  compose: (episodeId: string, body: { name?: string; description?: string; ratio?: string; duration?: number }) =>
    request<VideoVersion>(`/api/episodes/${episodeId}/compose`, { method: 'POST', body: JSON.stringify(body) }),
  usage: () => request<Usage>('/api/usage'),
  aiJob: (jobId: string) => request<AiJob>(`/api/ai-jobs/${jobId}`),
  projectAiJobs: (projectId: string) => request<AiJob[]>(`/api/projects/${projectId}/ai-jobs`),

  adminSummary: () => request<AdminSummary>('/api/admin/summary'),
  adminUsers: () => request<User[]>('/api/admin/users'),
  adminLedger: (userId?: string) => request<PointLedger[]>(`/api/admin/point-ledger${userId ? `?user_id=${userId}` : ''}`),
  adminAdjustPoints: (userId: string, body: { amount: number; reason: string }) =>
    request<{ entry: PointLedger; user: User }>(`/api/admin/users/${userId}/points`, { method: 'POST', body: JSON.stringify(body) }),
  adminUpdateUser: (userId: string, body: { role?: UserRole; status?: UserStatus }) =>
    request<User>(`/api/admin/users/${userId}`, { method: 'PATCH', body: JSON.stringify(body) }),
  adminResetPassword: (userId: string, body: { password: string }) =>
    request<{ user: User }>(`/api/admin/users/${userId}/password`, { method: 'PATCH', body: JSON.stringify(body) })
};
