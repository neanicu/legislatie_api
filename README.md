# Legislatie.just.ro API Client & Interface

![Python CI](https://github.com/OWNER/REPO/actions/workflows/python-ci.yml/badge.svg)

*Replace OWNER/REPO with your GitHub repository.*

Acest proiect oferă acces la serviciul web SOAP `legislatie.just.ro` printr-un script Python și o interfață web modernă. Sistemul implementează o **strategie de fallback inteligentă** care trece automat de la API-ul SOAP defect la scraping HTML, asigurând acces continuu la date chiar și atunci când serverul oficial are probleme interne (Solr).

## Componente

1.  **`legislatie_client.py`**: Client SOAP robust cu cache persistente și fallback automat la scraping.
2.  **`legislatie_scraper.py`**: Motor de scraping HTML care extrage datele în același format ca API-ul SOAP.
3.  **`streamlit_app.py`**: Interfață Web modernă pentru explorare interactivă, cu export de date.
4.  **`config.py`**: Management configurare prin variabile de mediu.
5.  **`cache.py`**: Sistem de cache persistent (diskcache) sau în memorie.
6.  **`.env.example`**: Exemplu de variabile de mediu configurabile.

## Caracteristici Avansate

- **Fallback automat**: Dacă API-ul SOAP eșuează (eroare "Unable to connect to the remote server"), sistemul trece transparent la scraping HTML.
- **Cache inteligent**: Rezultatele sunt cache-uite local (TTL configurable) în memorie sau pe disc pentru performanță.
- **Configurare flexibilă**: Toate setările (URL-uri, timeout-uri, cache) se definesc prin variabile de mediu.
- **Monitoring sănătate**: Verificare automată a stării API-ului SOAP și a scraper-ului (`--health`).
- **Export date**: Interfața web permite exportul rezultatelor în formate CSV și JSON.
- **Logging comprehensiv**: Log-uri detaliate cu niveluri configurabile pentru depanare.
- **Paginație completă**: Suport pentru navigarea prin rezultate cu filtrare și sortare.

## Cerințe

- Python 3.7+
- Dependențe listate în `requirements.txt`

## Instalare

1. Clonează acest repository.
2. Instalează dependențele:

```bash
pip install -r requirements.txt
```

3. Configurare opțională: Copiază `.env.example` la `.env` și ajustează variabilele după nevoi.

4. (Opțional) Pentru development, instalează dependențele de development și configurează pre-commit hooks:

```bash
pip install -r requirements-dev.txt
pre-commit install
```

## CI/CD Pipeline

Acest proiect include un pipeline CI/CD configurat cu GitHub Actions care rulează automat la fiecare push sau pull request. Pipeline-ul include:

- **Teste** pe Python 3.8, 3.9, 3.10, 3.11, 3.12
- **Verificare formatare** cu Black
- **Linting** cu Flake8
- **Verificare tipuri** cu MyPy (basic și strict)
- **Construire Docker** și testare smoke pentru branch-ul main

Configurația se găsește în `.github/workflows/python-ci.yml`. Pentru a utiliza badge-ul de status în README, înlocuiți `OWNER/REPO` cu numele repository-ului dvs. GitHub.

## Utilizare

### 1. Interfața Web (Recomandat)

Pornește aplicația web pentru a căuta interactiv în legislație:

```bash
python -m streamlit run streamlit_app.py
```

Aplicația se va deschide automat în browserul tău default (de obicei la `http://localhost:8501`).

**Funcționalități UI:**
- **Filtre avansate**: Căutare după An, Număr, Text, Titlu, Tip Act, Publicație.
- **Sortare**: După dată (cele mai noi/vechi) sau titlu (A-Z/Z-A).
- **Paginație**: Navigare cu butoane "⬅️" și "➡️".
- **Export**: Descarcă rezultatele în CSV sau JSON cu un singur click.
- **Vizualizare text**: Afișare text curățat și generare automată de XML Akoma Ntoso.

### 2. Script CLI (Linia de comandă)

**Căutare simplă (comportament implicit):**

```bash
python legislatie_client.py
```

**Verificare sănătate sistem:**

```bash
python legislatie_client.py --health
```

**Statistici cache:**

```bash
python legislatie_client.py --cache-stats
```

### 3. Utilizare ca modul Python

```python
from legislatie_client import LegislatieClient

client = LegislatieClient()

# Căutare cu parametri
results = client.search(
    numar_pagina=0,
    rezultate_pagina=10,
    an="2023",
    numar="15",
    text="contract",
    titlu="LEGE"
)

# Verificare sănătate
health = client.check_health()
print(f"Status overall: {health['overall']}")
```

## Configurare

Variabilele de mediu (setate în `.env` sau sistem) controlează comportamentul aplicației:

| Variabilă | Descriere | Valoare implicită |
|-----------|-----------|-------------------|
| `LEGISLATIE_WSDL_URL` | URL WSDL API SOAP | `https://legislatie.just.ro/apiws/FreeWebService.svc?wsdl` |
| `LEGISLATIE_SOAP_ENDPOINT` | Endpoint SOAP | `https://legislatie.just.ro/apiws/FreeWebService.svc/SOAP` |
| `LEGISLATIE_BASE_URL` | URL site pentru scraping | `https://legislatie.just.ro` |
| `LEGISLATIE_REQUEST_DELAY` | Delay între request-uri scraping (secunde) | `1.0` |
| `LEGISLATIE_MAX_RETRIES` | Număr de reîncercări la erori | `3` |
| `LEGISLATIE_CACHE_TTL` | TTL cache (secunde) | `3600` |
| `LEGISLATIE_CACHE_PATH` | Director cache persistent | `./.legislatie_cache` |
| `LEGISLATIE_USE_PERSISTENT_CACHE` | Folosește cache pe disc | `false` |
| `LEGISLATIE_REQUEST_TIMEOUT` | Timeout request-uri (secunde) | `30` |
| `LEGISLATIE_SOAP_TIMEOUT` | Timeout SOAP (secunde) | `30` |
| `LEGISLATIE_LOG_LEVEL` | Nivel logging | `INFO` |
| `LEGISLATIE_LOG_FILE` | Fișier log (opțional) | `./legislatie.log` |

## Structura Proiectului

- `legislatie_client.py`: Clasa principală `LegislatieClient` cu:
  - **Autentificare automată** și reînnoire token.
  - **Fallback inteligent** la scraping la eroare SOAP.
  - **Cache integrat** cu TTL și persistare opțională.
  - **Verificare sănătate** (`check_health()`).
- `legislatie_scraper.py`: Clasa `LegislatieScraper` care:
  - Extrage datele din interfața HTML publică.
  - Parsează toate câmpurile relevante (Titlu, Numar, DataVigoare, Emitent, Publicatie, Text, TipAct).
  - Respectă politetea serverului (rate limiting, retry).
- `streamlit_app.py`: Aplicație Streamlit cu:
  - Interfață utilizator modernă și responsivă.
  - Filtrare și sortare avansată.
  - Export CSV/JSON.
  - Generare Akoma Ntoso XML.
- `config.py`: Încărcare configurare din `.env`.
- `cache.py`: Sistem de cache abstractizat (memorie/diskcache).
- `requirements.txt`: Dependențe Python.

## Depanare

### Eroare "Unable to connect to the remote server"

Aceasta este o problemă cunoscută a serverului `legislatie.just.ro` (conexiune internă Solr defectă). Sistemul nostru detectează automat această eroare și trece la scraping HTML, așa că aplicația va continua să funcționeze.

### Probleme de encoding (caractere românești)

Aplicația folosește UTF-8 peste tot. Dacă întâlniți probleme la afișarea caracterelor românești în consolă Windows, setați encoding-ul consolei la UTF-8 sau folosiți interfața web.

### Performanță scraping

Pentru a nu suprasolicita serverul, scraping-ul include:
- Delay între request-uri (configurabil)
- Retry la erori temporare
- Cache extensiv

### Monitorizare

Verificați fișierul de log (`legislatie.log`) sau rulați `python legislatie_client.py --health` pentru a vedea statusul componentelor.

## Contribuții

Contribuțiile sunt binevenite! Vă rugăm să deschideți issue-uri pentru bug-uri și să propuneți îmbunătățiri prin pull request-uri.

## Licență

Acest proiect este licențiat sub MIT License.