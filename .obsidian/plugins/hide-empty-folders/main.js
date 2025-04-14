const obsidian = require('obsidian');

class HideEmptyFoldersPlugin extends obsidian.Plugin {
    async onload() {
        console.log('Loading Hide Empty Folders plugin');

        // Folders to exclude from hiding
        this.excludedFolders = ['Assets', 'Templates'];

        // Cache for folder content checks to improve performance
        this.folderCache = new Map();

        // Run initially after a delay to ensure file explorer is loaded
        this.initialTimeout = setTimeout(() => this.updateFolderVisibility(), 2000);

        // Register events for file changes to keep visibility updated
        this.registerEvent(this.app.vault.on('create', () => this.clearCacheAndUpdate()));
        this.registerEvent(this.app.vault.on('delete', () => this.clearCacheAndUpdate()));
        this.registerEvent(this.app.vault.on('rename', () => this.clearCacheAndUpdate()));

        // Update when layout changes
        this.registerEvent(this.app.workspace.on('layout-change', () => {
            setTimeout(() => this.updateFolderVisibility(), 100);
        }));

        // Add click listener for folder expansions
        this.app.workspace.onLayoutReady(() => {
            const fileExplorer = this.getFileExplorer();
            if (fileExplorer && fileExplorer.containerEl) {
                fileExplorer.containerEl.addEventListener('click', (event) => {
                    // If a folder title was clicked, update visibility after a short delay
                    if (event.target.closest('.nav-folder-title')) {
                        setTimeout(() => this.updateFolderVisibility(), 50);
                    }
                });
            }
        });
    }

    onunload() {
        console.log('Unloading Hide Empty Folders plugin');
        if (this.initialTimeout) clearTimeout(this.initialTimeout);
        this.showAllFolders();
    }

    clearCacheAndUpdate() {
        this.folderCache.clear();
        setTimeout(() => this.updateFolderVisibility(), 100);
    }

    getFileExplorer() {
        const fileExplorer = this.app.workspace.getLeavesOfType('file-explorer')[0];
        return fileExplorer ? fileExplorer.view : null;
    }

    showAllFolders() {
        const fileExplorer = this.getFileExplorer();
        if (!fileExplorer) return;

        const folders = fileExplorer.containerEl.querySelectorAll('.nav-folder');
        folders.forEach(folder => {
            folder.style.display = '';
        });
    }

    /**
     * Check if a folder contains any markdown files recursively
     * @param {string} folderPath - Path to the folder to check
     * @returns {boolean} - True if this folder or any subfolder contains .md files
     */
    folderContainsMarkdown(folderPath) {
        // Check cache first for performance
        if (this.folderCache.has(folderPath)) {
            return this.folderCache.get(folderPath);
        }

        // Get the folder from the vault
        const folder = this.app.vault.getAbstractFileByPath(folderPath);
        if (!folder || !(folder instanceof obsidian.TFolder)) {
            this.folderCache.set(folderPath, false);
            return false;
        }

        // Check if any direct children are markdown files
        for (const child of folder.children) {
            if (child instanceof obsidian.TFile && child.extension === 'md') {
                this.folderCache.set(folderPath, true);
                return true;
            }
        }

        // Recursively check subfolders
        for (const child of folder.children) {
            if (child instanceof obsidian.TFolder) {
                const subfolderHasMarkdown = this.folderContainsMarkdown(child.path);
                if (subfolderHasMarkdown) {
                    this.folderCache.set(folderPath, true);
                    return true;
                }
            }
        }

        // No markdown files found
        this.folderCache.set(folderPath, false);
        return false;
    }

    /**
     * Update the visibility of all folders in the file explorer
     */
    async updateFolderVisibility() {
        const fileExplorer = this.getFileExplorer();
        if (!fileExplorer) return;

        // Get all folders (skip the root folder)
        const allFolders = Array.from(fileExplorer.containerEl.querySelectorAll('.nav-folder'))
            .filter(folder => !folder.classList.contains('nav-folder-root'));

        // Process each folder
        for (const folder of allFolders) {
            // Get the folder title element that has the path data
            const pathEl = folder.querySelector('.nav-folder-title');
            if (!pathEl) continue;

            // Get the folder path
            const folderPath = pathEl.getAttribute('data-path');
            if (!folderPath) continue;

            // Skip excluded folders
            if (this.excludedFolders.includes(folderPath)) {
                folder.style.display = '';
                continue;
            }

            // Check if this folder contains any markdown files (recursively)
            const hasMarkdownFiles = this.folderContainsMarkdown(folderPath);

            // Update visibility
            folder.style.display = hasMarkdownFiles ? '' : 'none';
        }
    }
}

module.exports = HideEmptyFoldersPlugin;