import streamlit as st
import pandas as pd
import json
import re
import html
import datetime
from legislatie_client import LegislatieClient


# Helper pentru a curata textul legislativ
def clean_legislatie_text(text):
    if not text:
        return "Nu există text disponibil."

    lines = text.splitlines()
    cleaned_lines = []

    for line in lines:
        # Normalizare whitespace
        line = line.replace("\xa0", " ").replace("\t", " ")

        # Eliminăm liniile care conțin doar separatori (+ sau ...)
        # Regex: start, spatii optionale, unul sau mai multe + sau ., spatii optionale, end
        if re.match(r"^\s*[\+\.]+\s*$", line):
            continue

        # Eliminăm markerii " ... " din interiorul liniilor
        line = line.replace(" ... ", " ")

        # Eliminăm spațiile multiple
        line = re.sub(r"\s+", " ", line).strip()

        if line:
            cleaned_lines.append(line)

    return "\n\n".join(cleaned_lines)


@st.cache_resource
def init_client():
    return LegislatieClient()


def generate_akoma_ntoso(item, clean_text):
    """
    Genereaza o structura XML Akoma Ntoso 3.0 simplificata din textul legislativ.
    Include o etapa de pre-segmentare pentru a sparge blocurile mari de text.
    """
    try:
        # Pregatire metadate
        titlu = html.escape(item.get("Titlu") or "Act")
        data_act = item.get("Data") or datetime.date.today().isoformat()
        numar = html.escape(item.get("Numar") or "")
        emitent = html.escape(item.get("Emitent") or "Autoritate")
        publicatie = html.escape(item.get("Publicatie") or "")

        # Header XML standard
        xml = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0">',
            '  <act name="act">',
            "    <meta>",
            '      <identification source="#source">',
            f"        <FRBRWork>",
            f'          <FRBRthis value="/ro/act/{data_act}/{numar}/main"/>',
            f'          <FRBRuri value="/ro/act/{data_act}/{numar}"/>',
            f'          <FRBRdate date="{data_act}" name="Generation"/>',
            f'          <FRBRauthor href="#{emitent}" as="#author"/>',
            f'          <FRBRcountry value="ro"/>',
            f"        </FRBRWork>",
            f"        <FRBRExpression>",
            f'          <FRBRthis value="/ro/act/{data_act}/{numar}/ron@/main"/>',
            f'          <FRBRuri value="/ro/act/{data_act}/{numar}/ron@"/>',
            f'          <FRBRdate date="{data_act}" name="Generation"/>',
            f'          <FRBRauthor href="#source" as="#editor"/>',
            f'          <FRBRlanguage language="ron"/>',
            f"        </FRBRExpression>",
            f"        <FRBRManifestation>",
            f'          <FRBRthis value="/ro/act/{data_act}/{numar}/ron@/main.xml"/>',
            f'          <FRBRuri value="/ro/act/{data_act}/{numar}/ron@.akn"/>',
            f'          <FRBRdate date="{datetime.date.today().isoformat()}" name="Generation"/>',
            f'          <FRBRauthor href="#source" as="#editor"/>',
            f"        </FRBRManifestation>",
            "      </identification>",
            "      <publication "
            + (f'date="{data_act}" name="{publicatie}"' if publicatie else "")
            + ' showAs="Monitorul Oficial"/>',
            "    </meta>",
            "    <body>",
        ]

        # --- ETAPA 1: Pre-segmentare text ---
        # Scop: Sa ne asiguram ca fiecare element structural (Articol, Alineat) incepe pe o linie noua
        # chiar daca in sursa e "Articolul 1 ... + Articolul 2" pe aceeasi linie.

        # Normalizam textul, eliminam + si ... care incurca
        text_to_process = clean_text.replace("\r", "\n")

        # Regex-uri pentru structura
        # Articol: (Articolul X | Art. X) - inceput de linie sau precedat de spatiu/newline
        re_art = re.compile(
            r"(?:\n|^|\s+)(Articolul\s+[IVX0-9]+|Art\.\s*\d+)", re.IGNORECASE
        )
        # Alineat: (1), (2) ...
        re_alin = re.compile(r"(?:\n|^|\s+)(\(\d+\))")
        # Litera: a), b) ...
        re_lit = re.compile(r"(?:\n|^|\s+)([a-z]\^?\d?\))")

        # Inseram NEWLINE inaintea structurilor detectate
        processed_text = re_art.sub(r"\n\1", text_to_process)
        processed_text = re_alin.sub(r"\n\1", processed_text)
        processed_text = re_lit.sub(r"\n\1", processed_text)

        lines = [line.strip() for line in processed_text.splitlines() if line.strip()]

        # --- ETAPA 2: Parsing structurat ---

        current_article = None
        current_para = None  # Alineat

        for line in lines:
            # 1. Detectie Articol
            art_match = re.match(
                r"^(Articolul\s+[IVX0-9]+|Art\.\s*\d+)(.*)", line, re.IGNORECASE
            )
            if art_match:
                # Inchidem structurile anterioare
                if current_para:
                    xml.append("          </paragraph>")
                    current_para = None
                if current_article:
                    xml.append("        </article>")

                # Deschidem articol nou
                full_marker = art_match.group(1)  # ex: Articolul 1
                rest_content = art_match.group(2).strip()

                # Extragem numarul (doar cifre sau romane) pentru eId
                art_num_clean = re.sub(r"[^a-zA-Z0-9]", "", full_marker).lower()

                current_article = art_num_clean
                xml.append(f'        <article eId="{current_article}">')
                xml.append(f"          <num>{full_marker}</num>")

                if rest_content:
                    # Daca restul liniei e scurt, poate e titlu marginal. Daca e lung, e text introductiv.
                    # Simplificam: il punem intr-un div introductiv
                    xml.append(
                        f"          <content><p>{html.escape(rest_content)}</p></content>"
                    )
                continue

            # 2. Detectie Alineat numerotat: (1)
            para_match = re.match(r"^(\(\d+\))(.*)", line)
            if para_match:
                if current_para:
                    xml.append("          </paragraph>")

                # Daca gasim alineat dar nu suntem in articol, cream unul dummy sau il punem in body direct
                # Dar standardul zice ca paragraph sta in article/section.
                # Daca nu avem articol deschis, deschidem unul generic sau continuam in body (nu e 100% valid akn fara container)
                if not current_article:
                    current_article = "art_preambul"
                    xml.append(f'        <article eId="{current_article}">')
                    xml.append(f"          <num>Preambul</num>")

                para_marker = para_match.group(1)  # (1)
                para_num = para_marker.replace("(", "").replace(")", "")
                rest_content = para_match.group(2).strip()

                current_para = f"{current_article}_para_{para_num}"
                xml.append(f'          <paragraph eId="{current_para}">')
                xml.append(f"            <num>{para_marker}</num>")
                if rest_content:
                    xml.append(
                        f"            <content><p>{html.escape(rest_content)}</p></content>"
                    )
                # Nu inchidem paragraph inca, poate urmeaza litere
                continue

            # 3. Detectie Litera: a) sau a^1)
            lit_match = re.match(r"^([a-z]\^?\d?\))(.*)", line)
            if lit_match:
                lit_marker = lit_match.group(1)
                rest_content = lit_match.group(2).strip()

                # Literele stau de obicei intr-o lista, dar simplificat le punem ca wrapUp sau content in paragraph curent
                # Daca nu avem paragraph deschis, e ciudat, dar tratam ca text
                if current_para:
                    xml.append(
                        f'            <list eId="{current_para}_list">'
                    )  # Simplificare: nu urmarim listele perfect
                    xml.append(
                        f'              <item eId="{current_para}_list_{lit_marker}">'
                    )
                    xml.append(f"                <num>{lit_marker}</num>")
                    xml.append(f"                <p>{html.escape(rest_content)}</p>")
                    xml.append(f"              </item>")
                    xml.append(f"            </list>")
                else:
                    # Fallback daca nu suntem in alineat
                    if current_article:
                        xml.append(
                            f"          <content><p>{lit_marker} {html.escape(rest_content)}</p></content>"
                        )
                    else:
                        xml.append(
                            f"          <p>{lit_marker} {html.escape(rest_content)}</p>"
                        )
                continue

            # 4. Text simplu (continuare sau nerecunoscut)
            # Daca avem un paragraph deschis, continuam in el
            if current_para:
                xml.append(f"            <content><p>{html.escape(line)}</p></content>")
            elif current_article:
                xml.append(f"          <content><p>{html.escape(line)}</p></content>")
            else:
                # Text la nivel de root (preambul, titlu lege repetat etc)
                xml.append(f"          <p>{html.escape(line)}</p>")

        # Inchidere finala
        if current_para:
            xml.append("          </paragraph>")
        if current_article:
            xml.append("        </article>")

        xml.append("    </body>")
        xml.append("  </act>")
        xml.append("</akomaNtoso>")

        return "\n".join(xml)

    except Exception as e:
        return f"<!-- Eroare la generarea XML: {str(e)} -->"


# Helper pentru a extrage datele din obiectele Zeep
def unpack_results(results):
    data = []

    def clean_str(val):
        """Curata spatiile invizibile (non-breaking spaces) si whitespace-ul"""
        if not val:
            return None
        # Convertim la string si inlocuim \xa0 cu spatiu normal
        s = str(val).replace("\xa0", " ")
        # Eliminam spatiile multiple (ex: "  ")
        s = re.sub(r"\s+", " ", s)
        return s.strip()

    for item in results:
        # Verificam daca e dict sau obiect Zeep
        def get_val(obj, key):
            val = obj[key] if isinstance(obj, dict) else getattr(obj, key, None)
            return clean_str(val)  # Curatam automat toate campurile

        data.append(
            {
                "Data": get_val(item, "DataVigoare"),
                "Numar": get_val(item, "Numar"),
                "Emitent": get_val(item, "Emitent"),
                "Titlu": get_val(item, "Titlu"),
                "Text": get_val(
                    item, "Text"
                ),  # Textul e curatat suplimentar la afisare, dar e bine sa fie curat si aici
                "Link": get_val(item, "LinkHtml"),
                "TipAct": get_val(item, "TipAct"),
                "Publicatie": get_val(item, "Publicatie"),
            }
        )
    return data


@st.dialog("Document Complet", width="large")
def show_full_text_dialog(item):
    titlu = item["Titlu"]
    text = item["Text"]
    st.markdown(f"### {titlu}")

    tab_curat, tab_brut, tab_akn = st.tabs(
        ["Text Formatat", "Text Brut (API)", "Akoma Ntoso (XML)"]
    )

    # Procesare comună
    clean_text = clean_legislatie_text(text)

    with tab_curat:
        st.info(
            "ℹ️ Notă: Textul afișat este furnizat de API-ul legislatie.just.ro în forma sa de bază sau republicată. Pentru forma consolidată la zi, vă rugăm să consultați Linkul Oficial."
        )
        with st.container(height=600):
            st.code(clean_text, language=None, wrap_lines=True)

    with tab_brut:
        st.warning("⚠️ Acest tab afișează textul exact așa cum este primit de la API.")
        with st.container(height=600):
            st.code(text if text else "Nu există text.", language=None, wrap_lines=True)

    with tab_akn:
        st.info("ℹ️ Generare automată (best-effort) în format XML Akoma Ntoso 3.0.")

        # Buton de generare "la cerere" pentru a nu încărca procesorul inutil
        if st.button("Generează XML Akoma Ntoso", key="btn_gen_akn"):
            with st.spinner("Se generează structura XML..."):
                akn_xml = generate_akoma_ntoso(item, clean_text)

            with st.container(height=600):
                st.code(akn_xml, language="xml", wrap_lines=True)

            # Buton de download
            st.download_button(
                label="Descarcă XML",
                data=akn_xml,
                file_name=f"legislatie_{item['Numar']}.xml",
                mime="application/xml",
            )


def main():
    st.set_page_config(page_title="Legislatie RO Explorer", layout="wide")

    st.title("🇷🇴 Explorer Legislatie.Just.ro")
    st.markdown(
        "Interfata simpla pentru cautarea actelor normative folosind serviciul web oficial."
    )

    # Sidebar cu filtre
    st.sidebar.header("Filtre Cautare")

    search_an = st.sidebar.text_input(
        "An (Vigoare/Publicare)",
        value="",
        help="Introduceți anul publicării în Monitorul Oficial (poate diferi de anul emiterii din titlu).",
    )
    search_numar = st.sidebar.text_input("Numar Act", value="")
    search_text = st.sidebar.text_input("Text (Continut)", value="")
    search_titlu = st.sidebar.text_input("Titlu", value="")

    # Filtru client-side
    filter_tip = st.sidebar.text_input("Filtru Tip Act (ex: LEGE, ORDIN)", value="")
    filter_publicatie = st.sidebar.text_input(
        "Filtru Publicație (ex: Monitorul)", value=""
    )

    # Optiune Sortare
    sort_option = st.sidebar.selectbox(
        "Ordonare rezultate (pagina curentă)",
        [
            "Implicită (API)",
            "Dată (Cele mai noi)",
            "Dată (Cele mai vechi)",
            "Titlu (A-Z)",
            "Titlu (Z-A)",
        ],
    )

    if filter_tip or filter_publicatie:
        st.sidebar.info("Nota: Filtrarea se aplica doar rezultatelor incarcate.")

    # Selectare numar rezultate pe pagina (UI)
    results_per_page = st.sidebar.selectbox(
        "Rezultate pe pagina", options=[10, 20, 30, 50, 100], index=0
    )

    # Paginare
    if "page" not in st.session_state:
        st.session_state.page = 0

    col1, col2, col3 = st.sidebar.columns([1, 2, 1])
    if col1.button("⬅️"):
        if st.session_state.page > 0:
            st.session_state.page -= 1
    col3.write(f"Pagina {st.session_state.page + 1}")  # Display 1-based index
    if col2.button("➡️"):
        st.session_state.page += 1

    # Buton Cautare
    search_clicked = st.sidebar.button("🔍 Cauta", type="primary")
    
    if search_clicked:
        st.session_state.page = 0

    # Branding Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        <div style='text-align: center; color: #666; font-size: 0.8em;'>
            Dezvoltat de <b>LOGIQO SRL</b><br>
            <a href='mailto:contact@logiqo.ro' style='color: #666; text-decoration: none;'>contact@logiqo.ro</a>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Functie callback pentru notificari non-blocante
    def status_notifier(msg):
        st.toast(msg, icon="🔄")

    # Initializare client (cache resource pentru performanta la incarcare WSDL)
    # Folosim st.cache_resource doar pentru initializarea grea, dar instanta trebuie sa fie in session_state pentru a pastra tokenul
    if "client" not in st.session_state:
        st.session_state.client = init_client()

    try:
        client = st.session_state.client
        client.status_callback = status_notifier

        with st.spinner(f"Se incarca {results_per_page} rezultate..."):
            # Calculam paginile de server necesare
            SERVER_PAGE_SIZE = 10

            start_index = st.session_state.page * results_per_page
            end_index = (st.session_state.page + 1) * results_per_page

            first_server_page = start_index // SERVER_PAGE_SIZE
            last_server_page = (end_index - 1) // SERVER_PAGE_SIZE

            all_results = []

            # Parametrii de cautare
            p_an = search_an.strip() if search_an else None
            p_numar = search_numar.strip() if search_numar else None
            p_text = search_text.strip() if search_text else None
            p_titlu = search_titlu.strip() if search_titlu else None

            # --- SMART SEARCH LOGIC ---
            # Dacă utilizatorul a introdus text liber care pare a fi o referință la o lege (ex: "Legea 223/2015"),
            # încercăm să extragem Numărul și Anul pentru a îmbunătăți precizia căutării.

            # Combinăm textul din titlu și text pentru analiză, dacă nu sunt setați an/număr
            text_to_analyze = (p_titlu or "") + " " + (p_text or "")

            if not p_numar and not p_an and text_to_analyze.strip():
                # Pattern 1: "223/2015" sau "223 / 2015"
                match_slash = re.search(r"(\d+)\s*/\s*(\d{4})", text_to_analyze)

                # Pattern 2: "nr. 223 din 2015" sau "legea 223 ... 2015"
                # Căutăm un număr urmat eventual de text și apoi un an
                match_verbose = re.search(
                    r"(?:nr\.?|legea)?\s*(\d+)\b.*?(\d{4})\b",
                    text_to_analyze,
                    re.IGNORECASE,
                )

                extracted_numar = None
                extracted_an = None

                if match_slash:
                    extracted_numar = match_slash.group(1)
                    extracted_an = match_slash.group(2)
                elif match_verbose:
                    extracted_numar = match_verbose.group(1)
                    extracted_an = match_verbose.group(2)

                if extracted_numar and extracted_an:
                    st.info(
                        f"💡 Am detectat o căutare specifică: Actul nr. {extracted_numar} din anul {extracted_an}. Aplic filtrele automat."
                    )
                    p_numar = extracted_numar
                    p_an = extracted_an

                    # --- FIX CRITIC ---
                    # Dacă textul introdus în "Titlu" sau "Text" a fost folosit integral pentru extragere,
                    # trebuie să îl curățăm din parametrii de căutare.
                    # Altfel, API-ul caută (ex: Text="223 din 2015" AND Numar=223 AND An=2015), ceea ce returnează 0 rezultate.

                    # Verificăm dacă textul introdus (care a generat match-ul) este "consumat" de match
                    # Dacă userul a scris "223 din 2015", extragem 223 și 2015. Textul rămas este " din ".
                    # Dacă textul rămas este trivial (doar separatori/stopwords), anulăm filtrul de text/titlu.

                    def is_trivial_after_extraction(original_text, regex_match):
                        if not original_text:
                            return True
                        # Scoatem partea match-uită din text
                        span = regex_match.span()
                        leftover = original_text[: span[0]] + original_text[span[1] :]
                        # Verificăm dacă ce a rămas conține litere sau cifre semnificative
                        clean_leftover = re.sub(r"[\W_]+", "", leftover)
                        return (
                            len(clean_leftover) < 2
                        )  # Daca au ramas mai putin de 2 caractere semnificative, e trivial

                    match_obj = match_slash if match_slash else match_verbose

                    # Daca match-ul a venit din textul combinat, trebuie sa vedem de unde provine
                    if p_titlu and match_obj.string == text_to_analyze:
                        # Aici e tricky pentru ca text_to_analyze e (titlu + " " + text).
                        # Simplificare: Dacă am extras datele, și textul din Titlu/Text pare să fie sursa, îl resetăm.
                        pass

                    # Abordare mai directă:
                    # Dacă Titlul conține numărul ȘI anul extras, îl considerăm "consumat" și îl resetăm.
                    if (
                        p_titlu
                        and extracted_numar in p_titlu
                        and extracted_an in p_titlu
                    ):
                        p_titlu = None

                    # La fel pentru Text
                    if p_text and extracted_numar in p_text and extracted_an in p_text:
                        p_text = None

            # --------------------------

            # Iteram prin paginile de server necesare
            # Placeholder pentru bara de progres daca sunt multe cereri
            progress_bar = st.empty()
            total_reqs = last_server_page - first_server_page + 1

            try:
                for i, server_page in enumerate(
                    range(first_server_page, last_server_page + 1)
                ):
                    if total_reqs > 1:
                        progress_bar.progress(
                            (i + 1) / total_reqs,
                            text=f"Incarcare set {i + 1}/{total_reqs}...",
                        )

                    batch_results = client.search(
                        numar_pagina=server_page,
                        rezultate_pagina=SERVER_PAGE_SIZE,
                        an=p_an,
                        numar=p_numar,
                        text=p_text,
                        titlu=p_titlu,
                    )
                    if batch_results:
                        all_results.extend(batch_results)
                    else:
                        # Daca o pagina e goala, probabil nu mai sunt rezultate
                        break
            except Exception as e:
                # Daca avem rezultate partiale, le afisam, dar avertizam userul
                if all_results:
                    st.warning(
                        f"Căutarea a fost întreruptă din cauza unei erori de rețea, dar afișăm rezultatele parțiale. Eroare: {e}"
                    )
                else:
                    raise e  # Retruncam eroarea pentru a fi prinsa de blocul outer

            progress_bar.empty()

            results = all_results

            if results:
                data = unpack_results(results)

                # Filtrare client-side
                data_enriched = []
                term_tip = filter_tip.lower() if filter_tip else None
                term_pub = filter_publicatie.lower() if filter_publicatie else None

                for item in data:
                    # Item e deja un dict din unpack_results
                    tip_act = item.get("TipAct")
                    publicatie = item.get("Publicatie")

                    match_tip = True
                    if term_tip:
                        match_tip = tip_act and term_tip in tip_act.lower()

                    match_pub = True
                    if term_pub:
                        match_pub = publicatie and term_pub in publicatie.lower()

                    if match_tip and match_pub:
                        data_enriched.append(item)

                # Logică de sortare
                if sort_option != "Implicită (API)":
                    try:
                        if "Dată" in sort_option:
                            reverse = "Cele mai noi" in sort_option
                            # Convertim la string pentru sortare (ISO format YYYY-MM-DD e sortabil ca string)
                            # Tratăm None ca string gol
                            data_enriched.sort(
                                key=lambda x: str(x.get("Data") or ""), reverse=reverse
                            )
                        elif "Titlu" in sort_option:
                            reverse = "Z-A" in sort_option
                            data_enriched.sort(
                                key=lambda x: str(x.get("Titlu") or "").lower(),
                                reverse=reverse,
                            )
                    except Exception as e:
                        st.warning(f"A apărut o eroare la sortare: {e}")

                # Container pentru rezultate pentru a evita artefacte vizuale
                results_container = st.container()
                
                with results_container:
                    # Actualizam mesajul de succes
                    total_gasite = len(data_enriched)
                    if total_gasite > 0:
                        st.success(f"Afisate {total_gasite} rezultate.")

                        # Export functionality
                        st.subheader("Export Rezultate")
                        col1, col2 = st.columns(2)

                        with col1:
                            # CSV Export
                            df = pd.DataFrame(data_enriched)
                            csv_data = df.to_csv(index=False, encoding="utf-8-sig")
                            st.download_button(
                                label="📥 Descarcă CSV",
                                data=csv_data,
                                file_name=f"legislatie_rezultate_{datetime.date.today()}.csv",
                                mime="text/csv",
                                key="export_csv",
                            )

                        with col2:
                            # JSON Export
                            json_data = json.dumps(
                                data_enriched, indent=2, ensure_ascii=False
                            )
                            st.download_button(
                                label="📥 Descarcă JSON",
                                data=json_data,
                                file_name=f"legislatie_rezultate_{datetime.date.today()}.json",
                                mime="application/json",
                                key="export_json",
                            )

                        st.divider()
                    else:
                        st.warning("Niciun rezultat nu corespunde filtrelor selectate.")

                    for idx, item in enumerate(data_enriched):
                        # Afisam si Tipul Actului in header
                        tip_act_str = item.get("TipAct", "")
                        tip_label = f"[{tip_act_str}] " if tip_act_str else ""

                        with st.expander(
                            f"{tip_label}{item['Data']} | {item['Emitent']} | Nr. {item['Numar']}"
                        ):
                            st.subheader(item["Titlu"])

                            # Afișare Publicație
                            if item.get("Publicatie"):
                                st.caption(f"📰 {item['Publicatie']}")

                            col_btns = st.columns([1, 4])
                            with col_btns[0]:
                                if st.button("📖 Deschide Text", key=f"btn_open_{idx}"):
                                    show_full_text_dialog(item)

                            if item["Link"]:
                                st.markdown(f"[Link Oficial]({item['Link']})")
                            st.text_area(
                                "Text Preview",
                                (
                                    item["Text"][:1000] + "..."
                                    if item["Text"]
                                    else "Fara text"
                                ),
                                height=150,
                                key=f"text_area_{idx}",
                            )
            else:
                st.warning("Nu au fost gasite rezultate pe aceasta pagina.")

    except Exception as e:
        st.error(f"Eroare de conectare: {e}")


if __name__ == "__main__":
    main()
