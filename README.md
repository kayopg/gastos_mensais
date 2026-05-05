# Gastos Mensais - Cartão de Crédito

Dashboard interativo em **Python + Streamlit** para análise de gastos mensais de cartão de crédito, com integração ao **Google Drive** (faturas em CSV/Excel/OFX) e classificação manual de despesas.

> Repositório alvo: [`kayopg/gastos_mensais`](https://github.com/kayopg/gastos_mensais)
> Hospedagem: **Streamlit Community Cloud**

---

## Stack Tecnológica

| Camada | Tecnologia | Por quê |
|---|---|---|
| App / UI | Streamlit | Construção rápida de dashboards reativos em puro Python |
| Dados | pandas | Tratamento, agregação e filtragem em memória |
| Gráficos | Plotly | Pizza, barras empilhadas e séries históricas interativas |
| Integração | Google Drive API (Service Account) | Lê automaticamente as faturas da pasta compartilhada |
| Parsing | pandas (CSV/XLSX) + ofxparse (OFX) | Suporte aos três formatos planejados |
| Hospedagem | Streamlit Community Cloud | Deploy contínuo via GitHub |

---

## Estrutura de Pastas

```
gastos_mensais/
├── app.py                      # Entrada do Streamlit (layout + filtros + gráficos)
├── requirements.txt
├── README.md
├── .gitignore
├── LICENSE
├── .streamlit/
│   ├── config.toml             # Tema e configuração visual
│   └── secrets.toml.example    # Template para credenciais do Google
├── src/
│   ├── __init__.py
│   ├── config.py               # Constantes (categorias, colunas, paleta)
│   ├── drive_loader.py         # Autenticação + listagem + download da pasta do Drive
│   ├── parsers.py              # Leitura de CSV/XLSX/OFX em DataFrame normalizado
│   ├── classifier.py           # Regras automáticas + dicionário manual
│   └── charts.py               # Componentes Plotly reutilizáveis
├── data/
│   ├── categories.json         # Mapeamento manual: estabelecimento -> categoria
│   └── .gitkeep
└── tests/
    └── .gitkeep
```

---

## Modelo de Dados (3 dimensões)

Cada lançamento é classificado por **três eixos independentes**:

### 1. Categoria — *o que é a despesa*

```
Alimentação · Combustível · Farmácia · Manutenção Predial · Manutenção Veículo
Hospedagem · Vestuário · Agropecuária · Educação · Terceiros · Outros
```

**Terceiros** = compras feitas para familiares (não é despesa direta sua).

### 2. Subcategoria — *para que / para quem / onde* (opcional)

```
Lanches · Trabalho · Rotina · Água · Energia · Eletrônicos · Obras · Viagens
Sítio · Praia · Bananal           ← lugares
Kayo · Carme · Ita · Valter       ← pessoas (uso típico com Categoria=Terceiros)
```

### 3. Tipo — *recorrência da despesa*

| Tipo | Quando aplica |
|---|---|
| **Fixo** | Override manual (assinaturas, mensalidades) |
| **Variável** | Default — qualquer compra à vista |
| **Parcelado** | Auto: campo `Parcela` ≠ `-` |

A coluna `Parcela` continua presente para mostrar a posição (`1 de 6`, etc.).

### Coluna Cartão

Suporte a múltiplos emissores. Detecta automaticamente pelo subdiretório:

```
data/raw/Fatura2026-01-10.csv          → cartão "XP" (default)
data/raw/Sicoob/Fatura2026-01-10.csv   → cartão "Sicoob"
data/raw/Itaú/Fatura2026-01-10.csv     → cartão "Itaú"
```

Mesma convenção vale para o Google Drive — basta criar subpastas com o nome do cartão.

### Persistência da classificação manual

`data/categories.json` mapeia estabelecimento → override:

```json
{
  "BOOKING.COM HOTEL": {
    "categoria": "Hospedagem",
    "subcategoria": "Viagens",
    "tipo": null
  },
  "CLAUDE.AI SUBSCRIPTION": {
    "categoria": "Educação",
    "subcategoria": "Trabalho",
    "tipo": "Fixo"
  }
}
```

Cada campo é independente — você pode marcar só categoria, só tipo, ou os três. O override sempre vence as regras automáticas. Formato antigo (`{"X": "Categoria"}`) continua sendo aceito para compatibilidade.

### Mês de Referência (importante)

O cartão fecha em um dia X — então compras de novembro/dezembro entram na fatura de **janeiro**. O dashboard considera o mês da **fatura**, não o da compra: o `mes_ref` é extraído do **nome do arquivo** (padrão `FaturaYYYY-MM-DD.csv`, ex: `Fatura2026-01-10.csv` → `2026-01`).

- **Filtro "Mês de Referência"** → agrupa por mês da fatura (`mes_ref`).
- **Filtro "Período"** e a tabela de detalhamento → continuam usando a **data real da compra** para permitir buscas livres.
- Se um arquivo não seguir esse padrão, usa-se o mês da própria compra como fallback.

---

## Filtros e Reatividade

Os filtros ficam na **sidebar** e são aplicados em cascata sobre o mesmo DataFrame em memória — toda vez que o usuário mexe em qualquer widget, o Streamlit re-executa o script (de cima para baixo) e os gráficos/tabela refletem instantaneamente o subconjunto filtrado.

| Filtro | Widget | Como funciona |
|---|---|---|
| Mês de Referência | `st.selectbox` | Lista todos os meses presentes nas faturas; usado para os cards e gráfico de pizza |
| Período (intervalo) | `st.date_input` (range) | Limita a tabela e gráficos a um intervalo de **datas de compra** |
| Cartão | `st.multiselect` | Filtra por emissor (XP, Sicoob, Itaú, ...) |
| Estabelecimento | `st.multiselect` com busca | Permite escolher um ou vários estabelecimentos |
| Categoria | `st.multiselect` | Filtra por uma das 11 categorias |
| Subcategoria | `st.multiselect` | Filtra por subcategoria (Lanches, Trabalho, Sítio, Kayo, etc.) |
| Tipo | `st.multiselect` | Fixo / Variável / Parcelado |

Pseudocódigo do laço reativo:

```python
df = load_invoices()                 # @st.cache_data — só recarrega se as faturas no Drive mudarem
df = apply_filters(df, sidebar)      # filtra por mês, data, estabelecimento, categoria
render_summary_cards(df)             # totais
render_pie(df_mes_atual)             # pizza por categoria
render_evolution(df_ult_6_meses)     # barras empilhadas dos últimos 6 meses
render_table(df)                     # tabela detalhada (responde aos filtros)
```

---

## Setup Local

```bash
# 1. Clonar
git clone https://github.com/kayopg/gastos_mensais.git
cd gastos_mensais

# 2. Ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Dependências
pip install -r requirements.txt

# 4. Credenciais (ver seção abaixo)
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# preencher secrets.toml com a Service Account JSON

# 5. Rodar
streamlit run app.py
```

---

## Configurando o Google Drive (Service Account)

1. Acesse [console.cloud.google.com](https://console.cloud.google.com), crie um projeto (ex: `gastos-mensais`).
2. **APIs e Serviços → Biblioteca** → habilite **Google Drive API**.
3. **Credenciais → Criar credencial → Conta de serviço**. Baixe o JSON da chave.
4. Compartilhe a [pasta do Drive](https://drive.google.com/drive/folders/19i_VwMuXWDGCkmFxkFftCP7ZPdcSsRum) com o e-mail da service account (acesso de Leitor).
5. Cole o conteúdo do JSON em `.streamlit/secrets.toml`:

```toml
[gdrive]
folder_id = "19i_VwMuXWDGCkmFxkFftCP7ZPdcSsRum"

[gdrive.service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "...@....iam.gserviceaccount.com"
client_id = "..."
# (demais campos do JSON)
```

---

## Deploy no Streamlit Community Cloud

1. Faça push do projeto para `kayopg/gastos_mensais`.
2. Acesse [share.streamlit.io](https://share.streamlit.io), conecte sua conta GitHub e selecione o repositório.
3. Defina o branch (`main`) e o arquivo de entrada (`app.py`).
4. Em **Settings → Secrets**, cole o mesmo conteúdo do `secrets.toml` local.
5. Pronto — cada `git push` re-implanta automaticamente.

---

## Roadmap

- [x] Estrutura inicial e definição da stack
- [x] Parser CSV / XLSX / OFX
- [x] Loader híbrido (Google Drive em produção / pasta local em dev)
- [x] Mês de referência baseado no nome do arquivo da fatura
- [x] Modelo de 3 dimensões: **Categoria + Subcategoria + Tipo**
- [x] Coluna **Cartão** com detecção automática por subdiretório
- [x] Página de classificação manual com 3 colunas editáveis
- [x] Cards de resumo + pizza + evolução 6 meses + tabela
- [x] Filtros: Mês, Período, Cartão, Estabelecimento, Categoria, Subcategoria, Tipo
- [x] Suite de testes (`pytest tests/`)
- [ ] Push para `kayopg/gastos_mensais` no GitHub
- [ ] Configurar Service Account do Drive
- [ ] Deploy no Streamlit Community Cloud
- [ ] Persistência das classificações de volta no Drive (opcional)

---

## Licença

MIT
