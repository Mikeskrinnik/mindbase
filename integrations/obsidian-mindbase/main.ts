import { Plugin, PluginSettingTab, Setting, App } from 'obsidian';

interface MindbaseSettings {
  apiUrl: string;
  apiKey: string;
  autoSync: boolean;
}

const DEFAULT_SETTINGS: MindbaseSettings = {
  apiUrl: 'http://localhost:8080',
  apiKey: '',
  autoSync: true,
};

export default class MindbasePlugin extends Plugin {
  settings: MindbaseSettings;

  async onload() {
    await this.loadSettings();
    this.addSettingTab(new MindbaseSettingTab(this.app, this));

    if (this.settings.autoSync) {
      this.registerEvent(
        this.app.vault.on('modify', (file) => {
          if (file.extension === 'md') {
            this.syncFile(file);
          }
        })
      );
      this.registerEvent(
        this.app.vault.on('create', (file) => {
          if (file.extension === 'md') {
            this.syncFile(file);
          }
        })
      );
    }

    this.addCommand({
      id: 'mindbase-sync-current',
      name: 'Sync current note to Mindbase',
      callback: () => {
        const file = this.app.workspace.getActiveFile();
        if (file) this.syncFile(file);
      },
    });
  }

  async syncFile(file: import('obsidian').TFile) {
    if (!this.settings.apiKey) return;

    const content = await this.app.vault.read(file);
    const payload = {
      content,
      source: 'obsidian',
      external_id: `obsidian:${file.path}`,
      content_type: 'text/markdown',
      metadata: {
        obsidian_path: file.path,
        title: file.basename,
      },
    };

    try {
      const resp = await fetch(`${this.settings.apiUrl}/v1/ingest`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': this.settings.apiKey,
        },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        console.error('Mindbase sync failed:', await resp.text());
      }
    } catch (e) {
      console.error('Mindbase sync error:', e);
    }
  }

  async loadSettings() {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
  }

  async saveSettings() {
    await this.saveData(this.settings);
  }
}

class MindbaseSettingTab extends PluginSettingTab {
  plugin: MindbasePlugin;

  constructor(app: App, plugin: MindbasePlugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();
    containerEl.createEl('h2', { text: 'Mindbase Sync' });

    new Setting(containerEl)
      .setName('API URL')
      .setDesc('Mindbase API endpoint')
      .addText((text) =>
        text.setValue(this.plugin.settings.apiUrl).onChange(async (value) => {
          this.plugin.settings.apiUrl = value;
          await this.plugin.saveSettings();
        })
      );

    new Setting(containerEl)
      .setName('API Key')
      .setDesc('X-API-Key from your .env')
      .addText((text) =>
        text.setValue(this.plugin.settings.apiKey).onChange(async (value) => {
          this.plugin.settings.apiKey = value;
          await this.plugin.saveSettings();
        })
      );

    new Setting(containerEl)
      .setName('Auto-sync on save')
      .setDesc('Automatically push notes when created or modified')
      .addToggle((toggle) =>
        toggle.setValue(this.plugin.settings.autoSync).onChange(async (value) => {
          this.plugin.settings.autoSync = value;
          await this.plugin.saveSettings();
        })
      );
  }
}
