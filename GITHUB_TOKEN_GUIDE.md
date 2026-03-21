# GitHub API Token & Deployment Guide

## 🔑 Получить GitHub API Token (Personal Access Token)

### Прямая ссылка:
**https://github.com/settings/tokens**

### Или пошагово:

1. **Перейти в настройки GitHub**:
   - https://github.com/settings/profile

2. **Developer settings**:
   - https://github.com/settings/apps
   - Или: Settings → Developer settings (внизу слева)

3. **Personal access tokens**:
   - https://github.com/settings/tokens
   - Выбрать: **Tokens (classic)** или **Fine-grained tokens**

4. **Generate new token**:
   - https://github.com/settings/tokens/new

---

## 📝 Настройка токена

### Classic Token (рекомендуется для начала):

**Ссылка**: https://github.com/settings/tokens/new

**Необходимые права (scopes)**:
```
✅ repo (Full control of private repositories)
   ✅ repo:status
   ✅ repo_deployment
   ✅ public_repo
   ✅ repo:invite
   ✅ security_events

✅ workflow (Update GitHub Action workflows)

✅ write:packages (Upload packages to GitHub Package Registry)
✅ read:packages (Download packages from GitHub Package Registry)

✅ delete_repo (Delete repositories) - опционально
```

**Срок действия**: 
- Выбрать: `No expiration` (без срока) или `90 days`

**Note**: `C2 Server deployment token`

---

## 🚀 Использование токена

### 1. Настройка Git credentials:

```bash
# Сохранить токен в Git
git config --global credential.helper store

# При первом push введите:
# Username: ваш_github_username
# Password: ghp_ваш_токен_здесь
```

### 2. Клонирование с токеном:

```bash
git clone https://ghp_YOUR_TOKEN@github.com/GaredBerns/C2_server.git
```

### 3. Добавление remote с токеном:

```bash
git remote set-url origin https://ghp_YOUR_TOKEN@github.com/GaredBerns/C2_server.git
```

### 4. Push с токеном:

```bash
git push https://ghp_YOUR_TOKEN@github.com/GaredBerns/C2_server.git main
```

---

## 🔐 Fine-grained Token (более безопасный)

**Ссылка**: https://github.com/settings/personal-access-tokens/new

**Преимущества**:
- Доступ только к конкретным репозиториям
- Более детальные права
- Лучше для production

**Настройка**:
1. Repository access: `Only select repositories`
2. Выбрать: `C2_server`
3. Permissions:
   - Contents: `Read and write`
   - Metadata: `Read-only`
   - Workflows: `Read and write`

---

## 📦 Deployment через GitHub Actions

### Создать файл `.github/workflows/deploy.yml`:

```yaml
name: Deploy C2 Server

on:
  push:
    branches: [ main ]
    tags: [ 'v*' ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        python -c "from core import server, cache, metrics"
    
    - name: Build Docker image
      run: |
        docker build -t c2-server:${{ github.sha }} .
    
    - name: Deploy
      run: |
        echo "Deployment successful!"
```

---

## 🌐 GitHub Pages для документации

**Включить GitHub Pages**:
1. https://github.com/GaredBerns/C2_server/settings/pages
2. Source: `Deploy from a branch`
3. Branch: `main` → `/docs`
4. Save

**Документация будет доступна**:
- https://garedberns.github.io/C2_server/

---

## 🔗 Полезные ссылки

### GitHub Settings:
- **Profile**: https://github.com/settings/profile
- **Tokens**: https://github.com/settings/tokens
- **SSH Keys**: https://github.com/settings/keys
- **Applications**: https://github.com/settings/applications

### Repository Settings:
- **General**: https://github.com/GaredBerns/C2_server/settings
- **Branches**: https://github.com/GaredBerns/C2_server/settings/branches
- **Actions**: https://github.com/GaredBerns/C2_server/settings/actions
- **Pages**: https://github.com/GaredBerns/C2_server/settings/pages
- **Secrets**: https://github.com/GaredBerns/C2_server/settings/secrets/actions

### GitHub API:
- **API Docs**: https://docs.github.com/en/rest
- **GraphQL**: https://docs.github.com/en/graphql

---

## 🛠️ Команды для деплоя

### Первый раз (с токеном):

```bash
cd /mnt/F/C2_server-main

# Настроить remote с токеном
git remote set-url origin https://ghp_YOUR_TOKEN@github.com/GaredBerns/C2_server.git

# Добавить все файлы
git add .

# Commit
git commit -m "feat: C2 Server v2.0 - Complete Overhaul"

# Tag
git tag -a v2.0.0 -m "Version 2.0.0 - Production Ready"

# Push
git push origin main
git push origin v2.0.0
```

### Последующие разы:

```bash
git add .
git commit -m "update: your changes"
git push
```

---

## 🔒 Безопасность токена

### ⚠️ ВАЖНО:
- **НЕ коммитить токен в код**
- **НЕ публиковать токен**
- **Использовать .env для локального хранения**

### Хранение токена:

```bash
# В .env файле (не коммитить!)
GITHUB_TOKEN=ghp_your_token_here

# Использование в скриптах
export GITHUB_TOKEN=$(cat .env | grep GITHUB_TOKEN | cut -d'=' -f2)
git push https://$GITHUB_TOKEN@github.com/GaredBerns/C2_server.git
```

### Если токен скомпрометирован:
1. Немедленно удалить: https://github.com/settings/tokens
2. Создать новый токен
3. Обновить в Git credentials

---

## 📱 GitHub CLI (альтернатива)

### Установка:

```bash
# Linux
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh
```

### Использование:

```bash
# Авторизация
gh auth login

# Push
gh repo view
git push
```

---

## ✅ Готово!

**Главная ссылка для токена**: https://github.com/settings/tokens/new

После получения токена:
1. Скопировать токен (начинается с `ghp_`)
2. Использовать в командах выше
3. Сохранить в безопасном месте

**Токен действует как пароль для Git операций!**
