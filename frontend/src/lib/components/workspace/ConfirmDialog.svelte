<script lang="ts">
  export let title = '确认操作';
  export let message = '';
  export let detail = '';
  export let confirmText = '确认';
  export let cancelText = '取消';
  export let confirmDisabled = false;
  export let onConfirm: () => void | Promise<void>;
  export let onCancel: () => void;

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape' && !confirmDisabled) {
      onCancel();
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

<div
  class="modal-backdrop"
  role="presentation"
  on:click|self={() => {
    if (!confirmDisabled) onCancel();
  }}
>
  <div class="modal-panel confirm-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-dialog-title" aria-describedby="confirm-dialog-message">
    <div class="confirm-body">
      <div class="confirm-copy">
        <div class="modal-title-accent confirm-title" id="confirm-dialog-title">{title}</div>
        <div class="confirm-message" id="confirm-dialog-message">{message}</div>
        {#if detail}
          <div class="confirm-detail">{detail}</div>
        {/if}
      </div>
    </div>

    <div class="modal-actions confirm-actions">
      <button class="btn btn-secondary" disabled={confirmDisabled} on:click={onCancel}>{cancelText}</button>
      <button class="btn btn-danger confirm-delete-button" disabled={confirmDisabled} on:click={onConfirm}>{confirmText}</button>
    </div>
  </div>
</div>

<style>
  .confirm-modal {
    width: min(460px, 100%);
  }

  .confirm-body {
    display: flex;
    gap: 14px;
    padding: 18px;
  }

  .confirm-copy {
    min-width: 0;
  }

  .confirm-title {
    color: var(--red);
    font-size: 20px;
  }

  .confirm-message {
    margin-top: 8px;
    color: var(--text);
    line-height: 1.65;
  }

  .confirm-detail {
    margin-top: 10px;
    color: var(--muted);
    font-size: 12px;
    line-height: 1.55;
  }

  .confirm-actions {
    justify-content: flex-end;
  }

  .confirm-delete-button {
    min-width: 96px;
  }

  @media (max-width: 520px) {
    .confirm-body {
      flex-direction: column;
    }

    .confirm-actions .btn {
      width: 100%;
    }
  }
</style>
