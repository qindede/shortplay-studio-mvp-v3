<script lang="ts">
  import type { AuthMode } from '$lib/workspace/ui';

  export let authMode: AuthMode = 'login';
  export let authUsername = '';
  export let authPassword = '';
  export let error = '';
  export let loading = false;
  export let submitAuth: () => void | Promise<void>;

  function switchToLogin() {
    authMode = 'login';
    authUsername = '';
    authPassword = '';
  }

  function switchToRegister() {
    authMode = 'register';
    authUsername = '';
    authPassword = '';
  }
</script>

<div class="auth-shell">
  <div class="auth-stage">
    <div class="auth-poster">
      <div class="poster-frame frame-a"></div>
      <div class="poster-frame frame-b"></div>
      <div class="poster-frame frame-c"></div>
      <div class="auth-headline">
        <span>AI Short Drama Lab</span>
        <h1>让每个创意，燃成一幕好戏</h1>
      </div>
    </div>

    <div class="auth-card">
      <div class="auth-brand">
        <div class="brand-mark">SP</div>
        <div>
          <div class="brand-title">shortplay-studio</div>
          <div class="brand-subtitle">短剧内容创作舱</div>
        </div>
      </div>

      <h2>{authMode === 'login' ? '进入工作室' : '创建创作者账号'}</h2>
      <p>注册后获得 1000 初始积分。分镜、视频、素材和成片合成会按规则消耗积分。</p>

      {#if error}<div class="error">{error}</div>{/if}
      {#if loading}<div class="loading compact">正在验证登录状态...</div>{/if}

      <div class="auth-tabs">
        <button class:active={authMode === 'login'} on:click={switchToLogin}>登录</button>
        <button class:active={authMode === 'register'} on:click={switchToRegister}>注册</button>
      </div>

      <div class="field">
        <label for="auth-username">用户名</label>
        <input id="auth-username" bind:value={authUsername} placeholder="请输入用户名" />
      </div>

      <div class="field">
        <label for="auth-password">密码</label>
        <input id="auth-password" type="password" bind:value={authPassword} placeholder="至少 6 位" on:keydown={(event) => event.key === 'Enter' && submitAuth()} />
      </div>

      <button class="btn btn-primary auth-submit" on:click={submitAuth}>
        {authMode === 'login' ? '登录工作室' : '注册并进入'}
      </button>
    </div>
  </div>
</div>
