import { t } from './i18n.js';

const byId = (identifier) => document.getElementById(identifier);

export class AdminConsole {
  constructor(connection, controls) {
    this.connection = connection;
    this.controls = controls;
    this.expanded = false;
    this.authorized = false;
    this.busy = false;
    this.player = null;
    byId('admin-button').onclick = () => this.toggle();
    byId('admin-close').onclick = () => this.toggle(false);
    byId('admin-form').onsubmit = (event) => { event.preventDefault(); this.submit(); };
    connection.addEventListener('status', ({ detail }) => {
      if (detail.phase !== 'connected') this.toggle(false, false);
    });
  }

  update(state) {
    if (this.player !== state?.you.id) {
      byId('admin-log').replaceChildren();
      byId('admin-input').value = '';
      this.player = state?.you.id ?? null;
    }
    this.authorized = Boolean(state?.you.is_admin);
    byId('admin-button').hidden = !this.authorized;
    if (!this.authorized) this.toggle(false, false);
  }

  toggle(open = !this.expanded, send = true) {
    if (open && (!this.authorized || !this.connection.ready)) return;
    if (this.expanded === open) return;
    this.expanded = open;
    byId('admin-console').hidden = !open;
    byId('admin-button').setAttribute('aria-expanded', String(open));
    if (open) this.controls.prepare();
    this.controls.stop();
    if (send && this.connection.ready) this.connection.send(open ? 'ui' : 'close', open ? { open: true } : {});
    if (open) byId('admin-input').focus({ preventScroll: true });
    else this.controls.focus();
  }

  append(text, error = false) {
    const line = document.createElement('div');
    line.className = error ? 'admin-error' : 'admin-output';
    line.textContent = text;
    const log = byId('admin-log');
    log.append(line);
    while (log.children.length > 80) log.firstChild.remove();
    log.scrollTop = log.scrollHeight;
  }

  async submit() {
    const input = byId('admin-input');
    const command = input.value.trim();
    if (!command || this.busy || !this.authorized || !this.connection.ready) return;
    this.busy = true;
    byId('admin-submit').disabled = true;
    this.append('> ' + command);
    input.value = '';
    try {
      const result = await this.connection.command('admin', { command });
      this.append(result.output);
    } catch (error) {
      this.append(error.message || (error.code === 'timeout' ? 'Command timed out. Check the connection before retrying.' : 'Command failed: connection unavailable.'), true);
    } finally {
      this.busy = false;
      byId('admin-submit').disabled = false;
      if (this.expanded) input.focus({ preventScroll: true });
    }
  }

  refreshLanguage() {
    byId('admin-button').title = t('admin.title');
  }
}
