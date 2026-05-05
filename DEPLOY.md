# Guia de Deploy — Gastos Mensais

Sequência completa para colocar o dashboard em produção:

1. **[Service Account do Google Drive](#1-service-account-do-google-drive)** — para o app ler suas faturas automaticamente.
2. **[Repositório no GitHub](#2-repositório-no-github)** — `kayopg/gastos_mensais`.
3. **[Deploy no Streamlit Community Cloud](#3-deploy-no-streamlit-community-cloud)** — URL pública 24/7.

> **Tempo estimado:** 30 a 45 minutos · **Custo:** R$ 0 (todos os passos usam camadas grátis).

---

## 1. Service Account do Google Drive

### 1.1 Criar projeto no Google Cloud

1. Acesse [console.cloud.google.com](https://console.cloud.google.com).
2. No topo, clique no seletor de projeto → **Novo Projeto**.
3. Nome: `gastos-mensais` (ou outro de sua escolha). **Criar**.
4. Confirme que esse projeto está selecionado no topo da tela.

### 1.2 Habilitar a Google Drive API

1. Menu (☰) → **APIs e Serviços → Biblioteca**.
2. Busque por **Google Drive API**. Clique no resultado.
3. Botão **Ativar**. Aguarde 5-10 segundos.

### 1.3 Criar a Service Account

1. Menu → **APIs e Serviços → Credenciais**.
2. **+ Criar Credencial** → **Conta de serviço**.
3. Preencha:
   - Nome: `drive-reader`
   - ID: pode aceitar o sugerido
   - Descrição: "Leitor das faturas no Drive"
4. **Criar e continuar** → na tela de papéis, **Continuar** (sem papel) → **Concluir**.

### 1.4 Gerar a chave JSON

1. Na lista de Service Accounts, clique no e-mail recém-criado (`drive-reader@...iam.gserviceaccount.com`).
2. Aba **Chaves** → **Adicionar chave** → **Criar nova chave** → **JSON** → **Criar**.
3. Um arquivo `.json` é baixado automaticamente. **Guarde** — vamos usar adiante.

> ⚠️ Esse JSON contém a `private_key`. Trate como senha. **Nunca** commite no GitHub. O `.gitignore` do projeto já bloqueia `.streamlit/secrets.toml`.

### 1.5 Compartilhar a pasta do Drive com a Service Account

1. Abra a [pasta do Drive das faturas](https://drive.google.com/drive/folders/19i_VwMuXWDGCkmFxkFftCP7ZPdcSsRum).
2. Botão **Compartilhar** (canto superior direito).
3. Cole o e-mail da Service Account (algo como `drive-reader@gastos-mensais.iam.gserviceaccount.com`).
4. Permissão: **Leitor**. **Enviar** (pode desmarcar a opção de notificar por e-mail).

### 1.6 (Opcional) Estrutura por cartão no Drive

Se você for usar Sicoob/Itaú depois, crie subpastas dentro da pasta principal:

```
Gastos Mensais (pasta raiz compartilhada)
├── XP/                    ← faturas XP
├── Sicoob/                ← faturas Sicoob
└── Itaú/                  ← faturas Itaú
```

O loader detecta automaticamente o nome do cartão pelo subdiretório. Faturas soltas na raiz continuam sendo lidas como `XP` (default).

### 1.7 Criar o `secrets.toml` local

1. Na pasta do projeto, copie o template:
   ```powershell
   Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml
   ```
2. Abra o `secrets.toml` em um editor.
3. Cole o conteúdo do JSON baixado no passo 1.4 dentro da seção `[gdrive.service_account]` — uma chave por linha. Exemplo do formato final:

   ```toml
   [gdrive]
   folder_id = "19i_VwMuXWDGCkmFxkFftCP7ZPdcSsRum"

   [gdrive.service_account]
   type = "service_account"
   project_id = "gastos-mensais"
   private_key_id = "abc123..."
   private_key = "-----BEGIN PRIVATE KEY-----\nMIIE...\n-----END PRIVATE KEY-----\n"
   client_email = "drive-reader@gastos-mensais.iam.gserviceaccount.com"
   client_id = "1234567890..."
   auth_uri = "https://accounts.google.com/o/oauth2/auth"
   token_uri = "https://oauth2.googleapis.com/token"
   auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
   client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/drive-reader%40gastos-mensais.iam.gserviceaccount.com"
   universe_domain = "googleapis.com"
   ```

   > Atenção à `private_key`: o JSON original tem `\n` literais; mantenha-os exatamente como vieram (sim, `\n` mesmo, não quebra de linha real).

4. Teste localmente:
   ```powershell
   .\run.bat
   ```
   No app, a sidebar deve mostrar **"Fonte: Google Drive"**. Clique em **🔄 Recarregar** para puxar as faturas do Drive.

---

## 2. Repositório no GitHub

### 2.1 Criar o repositório

1. Vá em [github.com/new](https://github.com/new).
2. Owner: **kayopg**. Repository name: **gastos_mensais**.
3. Visibilidade: **Public** (necessário para o tier grátis do Streamlit Cloud) ou **Private** (Streamlit Cloud também aceita private mediante autorização).
4. **NÃO** marque "Add a README" / "Add .gitignore" / "Add license" — já temos esses arquivos.
5. **Create repository**.

### 2.2 Inicializar o git local e fazer o primeiro commit

Abra o PowerShell na pasta do projeto e rode na ordem:

```powershell
cd D:\claude_ia\gastos_mensais_cartao

# Inicializa o repositório
git init -b main

# Confere se o secrets.toml NÃO está sendo trackeado
git status                    # secrets.toml NÃO deve aparecer

# Identifica você como autor (ajuste para seu e-mail/nome do GitHub)
git config user.email "seu-email@example.com"
git config user.name "Seu Nome"

# Adiciona tudo (o .gitignore protege secrets, faturas e venv)
git add .
git status                    # revisa antes de commitar

# Primeiro commit
git commit -m "feat: dashboard executivo de gastos mensais

- Streamlit + Plotly + pandas
- 11 categorias × 15 subcategorias × 3 tipos
- Suporte multi-cartão (XP/Sicoob/Itaú) por subpasta
- Loader híbrido Google Drive/local com cache
- Página de classificação manual
- Tema dark executivo com cores vivas"

# Conecta com o GitHub
git remote add origin https://github.com/kayopg/gastos_mensais.git

# Sobe pro main
git push -u origin main
```

> Se o `git push` pedir autenticação:
> - **HTTPS**: use um Personal Access Token em vez de senha. Crie em [github.com/settings/tokens](https://github.com/settings/tokens) (escopo `repo` basta).
> - **SSH**: configure em [docs.github.com/en/authentication/connecting-to-github-with-ssh](https://docs.github.com/en/authentication/connecting-to-github-with-ssh) e troque o remote por `git@github.com:kayopg/gastos_mensais.git`.

### 2.3 Verificar

Acesse `https://github.com/kayopg/gastos_mensais` — você deve ver `app.py`, `views/`, `src/`, `README.md`, `DEPLOY.md`. **Confirme** que NÃO está visível: `.streamlit/secrets.toml`, `data/raw/*.csv`.

---

## 3. Deploy no Streamlit Community Cloud

### 3.1 Conectar com o GitHub

1. Acesse [share.streamlit.io](https://share.streamlit.io).
2. **Sign in with GitHub** (use a mesma conta `kayopg`).
3. Autorize o Streamlit a ler seus repositórios.

### 3.2 Criar o app

1. Botão **Create app** → **Yup, I have an app** (ou "Deploy from existing repo").
2. Preencha:
   - **Repository**: `kayopg/gastos_mensais`
   - **Branch**: `main`
   - **Main file path**: `app.py`
   - **App URL** (opcional): customize para algo como `gastos-kayopg`.
3. Avançado (clique em **Advanced settings**):
   - **Python version**: 3.11
4. **Deploy**. Aguarde 2-5 minutos enquanto o Streamlit instala dependências e sobe o serviço.

### 3.3 Configurar os secrets

Enquanto o app está subindo:

1. No painel do Streamlit Cloud, abra seu app → **⋮** → **Settings** → **Secrets**.
2. Cole **exatamente** o conteúdo do seu `.streamlit/secrets.toml` local (TOML inteiro).
3. **Save**. O app reinicia automaticamente.

### 3.4 Verificar produção

1. Acesse a URL do app (algo como `https://gastos-kayopg.streamlit.app`).
2. Sidebar deve indicar **"Fonte: Google Drive"**.
3. As 5 faturas devem aparecer nos cards e gráficos.
4. Adicione uma nova fatura na pasta do Drive → clique **🔄 Recarregar** → o app puxa o novo arquivo (cache de 5 min).

### 3.5 Hot deploy contínuo

A partir daí, todo `git push origin main` re-deploy o app automaticamente. Para testar uma alteração:

```powershell
# (após mudar algum arquivo)
git add .
git commit -m "chore: <descrição>"
git push origin main
```

O Streamlit Cloud detecta o push, faz `pip install -r requirements.txt` se mudou e recarrega o app.

---

## Troubleshooting

| Sintoma | Causa provável | Solução |
|---|---|---|
| App mostra "Fonte: Pasta local" em produção | Secrets não configurados / mal formatados | Verifique **Settings → Secrets**; deve ter `[gdrive]` e `[gdrive.service_account]` |
| `403 Forbidden` ao listar pasta | Pasta não compartilhada com a SA | Compartilhe novamente com `client_email` da SA, papel **Leitor** |
| `private_key` não funciona | `\n` foi substituído por quebra de linha real | Mantenha o `\n` literal no TOML |
| `ModuleNotFoundError: No module named 'src'` | Streamlit rodando do diretório errado | Confirme que `app.py` está na raiz e o **Main file path** = `app.py` |
| Gráfico vazio no início | Faturas ainda não classificadas | Vá na aba **🏷️ Classificação** e atribua categoria/subcat |

## Referências

- [Streamlit Secrets Management](https://docs.streamlit.io/develop/concepts/connections/secrets-management)
- [Google Service Accounts](https://cloud.google.com/iam/docs/service-account-overview)
- [GitHub Personal Access Tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
