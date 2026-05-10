<script lang="ts">
  import { api } from '$lib/api';

  let currentPassword = '';
  let newPassword = '';
  let confirmPassword = '';
  let passwordSaving = false;
  let passwordError = '';
  let passwordMessage = '';

  async function changePassword() {
    passwordError = '';
    passwordMessage = '';
    if (!currentPassword || !newPassword) {
      passwordError = '请输入当前密码和新密码';
      return;
    }
    if (newPassword.length < 6) {
      passwordError = '新密码至少 6 位';
      return;
    }
    if (newPassword !== confirmPassword) {
      passwordError = '两次输入的新密码不一致';
      return;
    }

    passwordSaving = true;
    try {
      await api.changePassword({ current_password: currentPassword, new_password: newPassword });
      currentPassword = '';
      newPassword = '';
      confirmPassword = '';
      passwordMessage = '密码已更新';
    } catch (err) {
      passwordError = err instanceof Error ? err.message : '修改失败';
    } finally {
      passwordSaving = false;
    }
  }
</script>

<div class="panel password-panel">
  <div class="panel-head">
    <div>
      <div class="panel-title">密码安全</div>
      <div class="panel-subtitle">更新当前登录账号的密码。</div>
    </div>
  </div>

  <div class="panel-body">
    <form class="password-form" on:submit|preventDefault={changePassword}>
      {#if passwordError}<div class="error">{passwordError}</div>{/if}
      {#if passwordMessage}<div class="success">{passwordMessage}</div>{/if}

      <div class="field password-field">
        <label for="password-current">当前密码</label>
        <input id="password-current" type="password" bind:value={currentPassword} autocomplete="current-password" />
      </div>

      <div class="field password-field">
        <label for="password-new">新密码</label>
        <input id="password-new" type="password" bind:value={newPassword} autocomplete="new-password" />
      </div>
      <div class="field password-field">
        <label for="password-confirm">确认新密码</label>
        <input id="password-confirm" type="password" bind:value={confirmPassword} autocomplete="new-password" />
      </div>

      <div class="panel-actions password-actions">
        <button class="btn btn-primary" disabled={passwordSaving} type="submit">
          {passwordSaving ? '正在保存...' : '修改密码'}
        </button>
      </div>
    </form>
  </div>
</div>
