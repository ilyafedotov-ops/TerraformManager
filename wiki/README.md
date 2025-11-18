# Wiki Documentation

This directory contains all wiki pages for the TerraformManager project.

## Wiki Pages

- **Home.md** - Main wiki landing page with navigation
- **Getting-Started.md** - Installation and quick start guide
- **Architecture.md** - System architecture and component overview
- **CLI-Reference.md** - Complete CLI command documentation
- **API-Reference.md** - REST API endpoint reference
- **Configuration.md** - Environment variables and config files
- **Generators.md** - Terraform code generation guide
- **Authentication.md** - JWT authentication flow and security
- **Development.md** - Contributing and development setup
- **Deployment.md** - Production deployment guide
- **Troubleshooting.md** - Common issues and solutions
- **Knowledge-Base.md** - RAG knowledge system guide

## Uploading to GitHub

### Option 1: Automated Upload (Recommended)

```bash
cd wiki
./upload-wiki.sh
```

**First time setup**: The script will guide you to initialize the wiki by creating the Home page through the web interface.

### Option 2: Manual Upload

1. **Initialize Wiki** (first time only):
   - Visit: https://github.com/ilyafedotov-ops/TerraformManager/wiki
   - Click "Create the first page"
   - Title: `Home`
   - Paste content from `Home.md`
   - Click "Save Page"

2. **Clone Wiki Repository**:
   ```bash
   git clone https://github.com/ilyafedotov-ops/TerraformManager.wiki.git
   cd TerraformManager.wiki
   ```

3. **Copy Files**:
   ```bash
   cp /path/to/TerraformManager/wiki/*.md .
   ```

4. **Commit and Push**:
   ```bash
   git add *.md
   git commit -m "docs: add/update wiki pages"
   git push origin master
   ```

### Option 3: Web Interface

Upload each file individually through the GitHub wiki editor:

1. Visit: https://github.com/ilyafedotov-ops/TerraformManager/wiki
2. Click "New Page" or "Edit" for existing page
3. Copy content from corresponding `.md` file
4. Save

## Updating Wiki Pages

After making changes to any wiki file:

```bash
cd wiki
./upload-wiki.sh
```

The script will automatically detect changes and push updates.

## Wiki Structure

```
Home (Home.md)
├── Getting Started (Getting-Started.md)
├── Core Features
│   ├── CLI Reference (CLI-Reference.md)
│   ├── API Reference (API-Reference.md)
│   └── Generators Guide (Generators.md)
├── Configuration & Setup
│   ├── Configuration (Configuration.md)
│   ├── Authentication (Authentication.md)
│   └── Deployment (Deployment.md)
└── Reference
    ├── Architecture (Architecture.md)
    ├── Development (Development.md)
    ├── Knowledge Base (Knowledge-Base.md)
    └── Troubleshooting (Troubleshooting.md)
```

## Editing Guidelines

1. **Markdown Format**: All files use GitHub-flavored Markdown
2. **Internal Links**: Use format `[Page Title](Page-Name)`
3. **Code Blocks**: Specify language for syntax highlighting
4. **Images**: Store in repo and reference with relative paths
5. **Headers**: Use hierarchical structure (H1 → H2 → H3)

## Maintenance

- Keep wiki pages in sync with main codebase
- Update after major feature additions
- Review quarterly for accuracy
- Link to relevant wiki pages in code comments

## Viewing the Wiki

https://github.com/ilyafedotov-ops/TerraformManager/wiki
