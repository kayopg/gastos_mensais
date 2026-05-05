"""Configurações globais e constantes do projeto."""
from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
CATEGORIES_FILE = DATA_DIR / "categories.json"

# ---------------------------------------------------------------------------
# Categorias (eixo principal — "o que é a despesa")
# ---------------------------------------------------------------------------
CATEGORIES = [
    "Alimentação",
    "Combustível",
    "Farmácia",
    "Manutenção Predial",
    "Manutenção Veículo",
    "Hospedagem",
    "Vestuário",
    "Agropecuária",
    "Educação",
    "Terceiros",        # compras feitas para familiares (não é despesa direta sua)
    "Outros",
]

# ---------------------------------------------------------------------------
# Subcategorias (eixo secundário — "para quem / pra que / onde")
# Aceita também string vazia (sem subcategoria definida).
# ---------------------------------------------------------------------------
SUBCATEGORIES = [
    "",                 # sem subcategoria
    # Propósito / contexto
    "Lanches",
    "Trabalho",
    "Rotina",
    "Água",
    "Energia",
    "Eletrônicos",
    "Obras",
    "Viagens",
    # Lugares
    "Sítio",
    "Praia",
    "Bananal",
    # Pessoas (uso típico com Categoria=Terceiros)
    "Kayo",
    "Carme",
    "Ita",
    "Valter",
]

# ---------------------------------------------------------------------------
# Tipo (recorrência da despesa)
# ---------------------------------------------------------------------------
TIPOS = ["Fixo", "Variável", "Parcelado"]
TIPO_DEFAULT = "Variável"  # quando não há parcela e não há override manual

# Cor por tipo (usada em alguns gráficos secundários)
TIPO_COLORS = {
    "Fixo":      "#5778A4",
    "Variável":  "#E49444",
    "Parcelado": "#85B6B2",
}

# ---------------------------------------------------------------------------
# Paleta consistente entre os gráficos (categorias)
# ---------------------------------------------------------------------------
CATEGORY_COLORS = {
    "Alimentação":         "#E45756",
    "Combustível":         "#F58518",
    "Farmácia":            "#54A24B",
    "Manutenção Predial":  "#4C78A8",
    "Manutenção Veículo":  "#72B7B2",
    "Hospedagem":          "#17BECF",
    "Vestuário":           "#B279A2",
    "Agropecuária":        "#7C9D44",
    "Educação":            "#EECA3B",
    "Terceiros":           "#FF9DA6",
    "Outros":              "#9D755D",
}

# ---------------------------------------------------------------------------
# Cartões — suporte a múltiplos emissores (XP, Sicoob, Itaú, ...)
# Convenção: arquivos em `data/raw/<NOME_CARTAO>/...` herdam o nome do cartão.
# Arquivos soltos em `data/raw/` usam DEFAULT_CARTAO.
# ---------------------------------------------------------------------------
DEFAULT_CARTAO = "XP"
KNOWN_CARTOES = ["XP", "Sicoob", "Itaú"]

# ---------------------------------------------------------------------------
# Pagamentos de fatura — não são despesas, devem ser filtrados do dataset
# (são apenas a quitação da fatura anterior, vindo da conta corrente).
# ---------------------------------------------------------------------------
PAGAMENTO_FATURA_RE = (
    r"Pagamento de fatura"               # XP CSV
    r"|PAGAMENTO\s*DEBITO\s*EM\s*CONTA"  # Sicoob OFX
    r"|Pagamentos Validos Normais"       # XP — variante
)

# ---------------------------------------------------------------------------
# Schema do DataFrame normalizado (após o parse das faturas)
# ---------------------------------------------------------------------------
COLUMNS = [
    "data",            # datetime64[ns]
    "estabelecimento", # str
    "portador",        # str
    "cartao",          # str  (XP, Sicoob, Itaú, ...)
    "valor",           # float (positivo = compra, negativo = pagamento)
    "parcela",         # str  (ex: "1 de 6", "-")
    "is_parcelado",    # bool
    "categoria",       # str  (uma das CATEGORIES)
    "subcategoria",    # str  (uma das SUBCATEGORIES, ou "")
    "tipo",            # str  ("Fixo" | "Variável" | "Parcelado")
    "mes_ref",         # str  ("YYYY-MM")  vem do nome do arquivo da fatura
    "fonte",           # str  (nome do arquivo de origem)
]

# ---------------------------------------------------------------------------
# Heurísticas de classificação automática — CATEGORIA
# Iteradas em ordem; primeira a casar vence.
# ---------------------------------------------------------------------------
KEYWORD_RULES = {
    "Combustível": [
        "POSTO", "ABASTEC", "SHELL", "IPIRANGA", "BR MANIA", "PETROBRAS",
        "AUTO POSTO", "ABASTECE", "SHELLBOX", "FSR COMBUSTIVEIS",
    ],
    "Farmácia": [
        "FARMACIA", "FARMÁCIA", "DROGA", "RAIA", "PACHECO", "PANVEL",
        "ESSENZA", "ANTONELLI", "TATIFARM", "MAIS FARMA", "SAO JOAO",
        "RADIOLOGIA", "CONSULTORIO", "CLINICA",
    ],
    "Hospedagem": [
        "BOOKING", "AIRBNB", "HOTEL", "POUSADA", "RESORT", "HOSTEL",
        "INN ", " INN", "HOTELLAWRENCE", "OK INN",
    ],
    "Educação": [
        "OPEN ENGLISH", "WIZARD", "CCAA", "CULTURAINGLESA", "CULTURA INGLESA",
        "CURSO", "ESCOLA", "FACULDADE", "UNIVERSIDADE", "TREINAMENTO",
        "A3TREINAMENTO", "UDEMY", "ALURA", "CLAUDE.AI",
    ],
    "Agropecuária": [
        "AGROPECUARIA", "AGROPECUÁRIA", "ALIANCA AGROPECUARIA",
        "RACAO", "RAÇÃO", "VETERINARIA", "VETERINÁRIA", "PETSHOP", "PET SHOP",
    ],
    "Vestuário": [
        "RIACHUELO", "RENNER", "C&A", "ZARA", "SHEIN", "PITTOLCALCADOS",
        "PITTOL", "ESKIMOLOJADE", "VESTUARIO", "VESTUÁRIO", "MODA",
        "CALCADOS", "CALÇADOS",
    ],
    "Manutenção Veículo": [
        "BORRACHARIA", "OFICINA", "OFFICINA", "CENTER CAR", "MECANIC",
        "AUTO ELETRIC", "PNEUS", "LAVA RAPIDO", "LAVA-RAPIDO",
        "VIPERODAS", "JIM.COM AUTO FIX",
    ],
    "Manutenção Predial": [
        "DELLA VECHIA", "AMILTON", "CONSTRUC", "CONSTRUÇ",
        "MATERIAL DE CONST", "FERRAGEM", "FERRAGENS",
        "CARLESS", "CARLESSI", "MORANGASOLUCOES", "ELETRICA", "HIDRAULICA",
    ],
    "Alimentação": [
        "SUPERMERCA", "MERCADO", "RESTAURANTE", "LANCHONETE", "PIZZA",
        "CHURRASCARIA", "BAR", "CAFE", "CAFÉ", "PADARIA", "ACOUGUE",
        "AÇOUGUE", "SUSHI", "BURGER", "GIRAFFAS", "GRILL", "FOOD", "FOODS",
        "GELATIER", "COMBO ATACAD", "ATACADISTA", "ATACADAO", "ATACADÃO",
        "GIASSI", "X DO GORDO", "ANGELONI", "OUTBACK", "KFC",
        "BOB'S", "DELIVERY", "PASTEL", "DOCE", "GULA", "STEAK",
    ],
}

# ---------------------------------------------------------------------------
# Heurísticas opcionais para SUBCATEGORIA (palavras-chave -> subcategoria)
# Serve de "primeiro chute" quando não há override manual.
# ---------------------------------------------------------------------------
SUBCATEGORY_RULES = {
    "Lanches": [
        "LANCHE", "LANCHES", "X DO GORDO", "BOB'S", "BURGER", "PASTEL",
        "HOT DOG", "ZICO HOT", "GIRAFFAS", "KFC",
    ],
    "Eletrônicos": [
        "SMART BLACK CELL", "INFORMATICA", "INFORMÁTICA", "TECN", "ELETRONIC",
    ],
    "Trabalho": [
        "CLAUDE.AI", "GITHUB", "OPENAI", "AWS", "GOOGLE WORKSPACE",
    ],
    "Viagens": [
        "BOOKING", "AIRBNB", "HOTEL", "POUSADA", "RESORT", "TURISMO",
        "LOUMAR", "DECOLAR", "LATAM", "GOL ", "AZUL ",
        "URBIA CATARATAS", "CATARATAS",
    ],
}
